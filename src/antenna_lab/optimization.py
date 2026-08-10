"""Deterministic, uncertainty-aware doublet optimization."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from numpy.typing import NDArray

from antenna_lab.measurements import ImpedanceMeasurement, load_impedance_measurements
from antenna_lab.radiator_model import candidate_loads
from antenna_lab.transmission_line import (
    LineParameters,
    input_impedance,
    line_efficiency,
    load_impedance,
    swr,
)


@dataclass(frozen=True)
class Scenario:
    """One passive feedline uncertainty scenario."""

    line: LineParameters
    air_geometry_z0_ohm: float
    baseline_loads_ohm: NDArray[np.complex128]
    minimum_baseline_load_resistance_ohm: float


@dataclass(frozen=True)
class CandidateResult:
    """Aggregate robust metrics for one physical length pair."""

    radiator_total_ft: float
    feedline_ft: float
    valid_fraction: float
    worst_band_line_efficiency_p10: float
    worst_band_line_efficiency_median: float
    weighted_line_efficiency_p10: float
    weighted_line_efficiency_median: float
    maximum_raw_swr_p90: float
    maximum_raw_swr_median: float
    match_proxy_feasible: bool


@dataclass(frozen=True)
class CandidateEnsemble:
    """Per-ensemble arrays retained for paired comparisons."""

    aggregate: CandidateResult
    band_efficiency: NDArray[np.float64]
    worst_efficiency: NDArray[np.float64]
    weighted_efficiency: NDArray[np.float64]
    maximum_swr: NDArray[np.float64]


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "baseline",
        "candidate_sweep",
        "line_uncertainty",
        "surrogate_models",
        "band_weights",
        "ranking",
    }
    missing = required - set(config)
    if missing:
        raise ValueError(f"Missing config sections: {sorted(missing)}")
    return config


def build_scenarios(
    measurements: tuple[ImpedanceMeasurement, ...], config: dict[str, Any]
) -> tuple[Scenario, ...]:
    """Enumerate feedline uncertainty, rejecting non-passive de-embeddings."""

    uncertainty = config["line_uncertainty"]
    baseline_line_ft = float(config["baseline"]["feedline_length_ft"])
    scenarios = []
    for velocity_factor in uncertainty["velocity_factors"]:
        for air_z0 in uncertainty["air_geometry_z0_ohm"]:
            z0 = float(air_z0) * float(velocity_factor)
            for loss in uncertainty["loss_db_per_100ft_at_10mhz"]:
                line = LineParameters(z0, float(velocity_factor), float(loss))
                loads = np.asarray(
                    [
                        load_impedance(
                            measurement.impedance_ohm,
                            measurement.frequency_hz,
                            baseline_line_ft,
                            line,
                        )
                        for measurement in measurements
                    ],
                    dtype=np.complex128,
                )
                minimum_resistance = float(np.min(loads.real))
                if minimum_resistance > float(uncertainty["passivity_min_load_r_ohm"]):
                    scenarios.append(
                        Scenario(
                            line=line,
                            air_geometry_z0_ohm=float(air_z0),
                            baseline_loads_ohm=loads,
                            minimum_baseline_load_resistance_ohm=minimum_resistance,
                        )
                    )
    if not scenarios:
        raise RuntimeError("No passive line scenarios survived")
    verify_scenario_round_trips(measurements, scenarios, baseline_line_ft)
    return tuple(scenarios)


def verify_scenario_round_trips(
    measurements: tuple[ImpedanceMeasurement, ...],
    scenarios: Iterable[Scenario],
    baseline_line_ft: float,
    tolerance_ohm: float = 1e-6,
) -> None:
    """Require exact reconstruction of every measurement anchor."""

    for scenario in scenarios:
        for measurement, load in zip(
            measurements, scenario.baseline_loads_ohm, strict=True
        ):
            reconstructed = complex(
                input_impedance(
                    load, measurement.frequency_hz, baseline_line_ft, scenario.line
                )
            )
            if abs(reconstructed - measurement.impedance_ohm) > tolerance_ohm:
                raise AssertionError("Feedline de-embed/re-embed round trip failed")


def evaluate_candidate(
    radiator_total_ft: float,
    feedline_ft: float,
    measurements: tuple[ImpedanceMeasurement, ...],
    scenarios: tuple[Scenario, ...],
    config: dict[str, Any],
) -> CandidateEnsemble:
    """Evaluate a physical candidate over every line/surrogate ensemble member."""

    frequencies = np.asarray([row.frequency_hz for row in measurements], dtype=float)
    bands = [row.band for row in measurements]
    weights = np.asarray([config["band_weights"][band] for band in bands], dtype=float)
    weights /= weights.sum()
    baseline_radiator_ft = float(config["baseline"]["radiator_total_ft"])
    radius_m = float(config["wire"]["conductor_radius_m"])

    band_rows: list[NDArray[np.float64]] = []
    worst_rows: list[float] = []
    weighted_rows: list[float] = []
    swr_rows: list[float] = []
    for scenario in scenarios:
        for model_name in config["surrogate_models"]:
            loads = candidate_loads(
                scenario.baseline_loads_ohm,
                frequencies,
                scenario.line.characteristic_impedance_ohm,
                baseline_radiator_ft,
                radiator_total_ft,
                model_name,
                radius_m,
            )
            efficiencies = np.asarray(
                [
                    float(line_efficiency(load, frequency, feedline_ft, scenario.line))
                    for load, frequency in zip(loads, frequencies, strict=True)
                ]
            )
            input_values = np.asarray(
                [
                    complex(
                        input_impedance(load, frequency, feedline_ft, scenario.line)
                    )
                    for load, frequency in zip(loads, frequencies, strict=True)
                ],
                dtype=np.complex128,
            )
            is_valid = bool(
                np.all(np.isfinite(efficiencies))
                and np.all(efficiencies > 0)
                and np.all(efficiencies <= 1.0001)
                and np.all(loads.real > 0)
            )
            if not is_valid:
                band_rows.append(np.full(len(measurements), np.nan))
                worst_rows.append(math.nan)
                weighted_rows.append(math.nan)
                swr_rows.append(math.nan)
                continue
            band_rows.append(efficiencies)
            worst_rows.append(float(np.min(efficiencies)))
            weighted_rows.append(
                float(
                    np.exp(np.sum(weights * np.log(np.clip(efficiencies, 1e-12, 1.0))))
                )
            )
            swr_rows.append(float(np.max(swr(input_values))))

    band_efficiency = np.asarray(band_rows, dtype=float)
    worst = np.asarray(worst_rows, dtype=float)
    weighted = np.asarray(weighted_rows, dtype=float)
    maximum_swr = np.asarray(swr_rows, dtype=float)
    valid_fraction = float(np.mean(np.isfinite(worst)))
    ranking = config["ranking"]
    maximum_swr_p90 = _nanquantile(maximum_swr, 0.90)
    aggregate = CandidateResult(
        radiator_total_ft=radiator_total_ft,
        feedline_ft=feedline_ft,
        valid_fraction=valid_fraction,
        worst_band_line_efficiency_p10=_nanquantile(worst, 0.10),
        worst_band_line_efficiency_median=_nanquantile(worst, 0.50),
        weighted_line_efficiency_p10=_nanquantile(weighted, 0.10),
        weighted_line_efficiency_median=_nanquantile(weighted, 0.50),
        maximum_raw_swr_p90=maximum_swr_p90,
        maximum_raw_swr_median=_nanquantile(maximum_swr, 0.50),
        match_proxy_feasible=bool(
            valid_fraction >= float(ranking["minimum_valid_fraction"])
            and maximum_swr_p90 <= float(ranking["match_proxy_maximum_raw_swr_p90"])
        ),
    )
    return CandidateEnsemble(aggregate, band_efficiency, worst, weighted, maximum_swr)


def run_optimization(config_path: Path, output_dir: Path) -> dict[str, Any]:
    """Run a deterministic grid and write a hash-verifiable result set."""

    config = load_config(config_path)
    np.random.seed(int(config["random_seed"]))
    measurement_path = _resolve_input_path(config_path, config["measurement_path"])
    measurements = load_impedance_measurements(measurement_path)
    scenarios = build_scenarios(measurements, config)

    radiator_values = _frange(config["candidate_sweep"]["radiator_total_ft"])
    feedline_values = _frange(config["candidate_sweep"]["feedline_length_ft"])
    evaluations = [
        evaluate_candidate(radiator, feedline, measurements, scenarios, config)
        for radiator in radiator_values
        for feedline in feedline_values
    ]
    aggregates = [evaluation.aggregate for evaluation in evaluations]
    by_dimensions = {
        (row.aggregate.radiator_total_ft, row.aggregate.feedline_ft): row
        for row in evaluations
    }
    baseline_dimensions = (
        float(config["baseline"]["radiator_total_ft"]),
        float(config["baseline"]["feedline_length_ft"]),
    )
    if baseline_dimensions not in by_dimensions:
        raise ValueError("Candidate sweep must include the measured baseline")

    feasible = [row for row in aggregates if row.match_proxy_feasible]
    if not feasible:
        raise RuntimeError("No candidate passed the configured matchability proxy")
    model_best = _best(feasible)
    recommended_pool = [
        row
        for row in aggregates
        if math.isclose(row.feedline_ft, baseline_dimensions[1])
        and row.radiator_total_ft <= baseline_dimensions[0]
        and row.valid_fraction >= float(config["ranking"]["minimum_valid_fraction"])
        and row.maximum_raw_swr_p90
        <= float(config["ranking"]["recommended_maximum_raw_swr_p90"])
    ]
    recommended = _best(recommended_pool)
    baseline = by_dimensions[baseline_dimensions].aggregate

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "candidates.csv", [asdict(row) for row in aggregates])
    selected_rows = [
        {"selection_category": "measured_baseline", **asdict(baseline)},
        {"selection_category": "recommended_reversible_test", **asdict(recommended)},
        {"selection_category": "model_best_under_match_proxy", **asdict(model_best)},
    ]
    _write_csv(output_dir / "selected_candidates.csv", selected_rows)
    paired = _paired_comparison(
        measurements,
        by_dimensions[baseline_dimensions],
        by_dimensions[(recommended.radiator_total_ft, recommended.feedline_ft)],
    )
    _write_csv(output_dir / "paired_comparison.csv", paired)
    summary = {
        "model_version": config["model_version"],
        "candidate_count": len(aggregates),
        "passive_line_scenario_count": len(scenarios),
        "ensemble_count_per_candidate": len(scenarios)
        * len(config["surrogate_models"]),
        "baseline": asdict(baseline),
        "recommended_reversible_test": asdict(recommended),
        "model_best_under_match_proxy": asdict(model_best),
        "confidence_labels": config.get("confidence_labels", {}),
        "warnings": [
            "Line efficiency is modeled, not measured total antenna efficiency.",
            "The radiator change is a surrogate ensemble, not NEC or "
            "full-wave modeling.",
            "The raw-SWR screen is a heuristic and not a KXAT2 specification.",
            "Nearby paired changes are more informative than absolute percentages.",
        ],
    }
    _write_json(output_dir / "summary.json", summary)
    metadata = {
        "random_seed": int(config["random_seed"]),
        "config_sha256": _sha256(config_path),
        "measurement_sha256": _sha256(measurement_path),
        "source_sha256": {
            path.name: _sha256(path)
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
        "config_file": config_path.name,
        "measurement_path": config["measurement_path"],
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "determinism": "No random sampling; seed reserved and fixed.",
    }
    lock_path = config_path.parent.parent / "uv.lock"
    if lock_path.exists():
        metadata["dependency_lock_sha256"] = _sha256(lock_path)
    _write_json(output_dir / "run_metadata.json", metadata)
    write_manifest(output_dir)
    return summary


def compare_candidate(
    config_path: Path, radiator_ft: float, feedline_ft: float
) -> dict[str, Any]:
    config = load_config(config_path)
    measurements = load_impedance_measurements(
        _resolve_input_path(config_path, config["measurement_path"])
    )
    scenarios = build_scenarios(measurements, config)
    baseline = evaluate_candidate(
        float(config["baseline"]["radiator_total_ft"]),
        float(config["baseline"]["feedline_length_ft"]),
        measurements,
        scenarios,
        config,
    )
    candidate = evaluate_candidate(
        radiator_ft, feedline_ft, measurements, scenarios, config
    )
    return {
        "baseline": asdict(baseline.aggregate),
        "candidate": asdict(candidate.aggregate),
        "paired_change_by_band": _paired_comparison(measurements, baseline, candidate),
        "confidence": "provisional nearby surrogate comparison",
    }


def write_manifest(directory: Path) -> None:
    paths = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    content = "".join(f"{_sha256(path)}  {path.name}\n" for path in paths)
    (directory / "SHA256SUMS").write_text(content, encoding="utf-8")


def verify_manifest(directory: Path) -> tuple[bool, list[str]]:
    manifest = directory / "SHA256SUMS"
    if not manifest.exists():
        return False, ["Missing SHA256SUMS"]
    failures = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = directory / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
        elif _sha256(path) != expected:
            failures.append(f"hash mismatch: {relative}")
    return not failures, failures


def _paired_comparison(
    measurements: tuple[ImpedanceMeasurement, ...],
    baseline: CandidateEnsemble,
    candidate: CandidateEnsemble,
) -> list[dict[str, Any]]:
    rows = []
    for band_index, measurement in enumerate(measurements):
        ratio = (
            candidate.band_efficiency[:, band_index]
            / baseline.band_efficiency[:, band_index]
        )
        change_db = 10.0 * np.log10(ratio)
        rows.append(
            {
                "band": measurement.band,
                "frequency_hz": measurement.frequency_hz,
                "paired_line_efficiency_change_db_p10": _nanquantile(change_db, 0.10),
                "paired_line_efficiency_change_db_median": _nanquantile(
                    change_db, 0.50
                ),
                "paired_line_efficiency_change_db_p90": _nanquantile(change_db, 0.90),
            }
        )
    return rows


def _best(rows: list[CandidateResult]) -> CandidateResult:
    if not rows:
        raise RuntimeError("Candidate selection pool is empty")
    return max(
        rows,
        key=lambda row: (
            row.worst_band_line_efficiency_p10,
            row.weighted_line_efficiency_p10,
            -abs(row.radiator_total_ft - 58.0),
            -abs(row.feedline_ft - 28.0),
        ),
    )


def _frange(specification: dict[str, float]) -> NDArray[np.float64]:
    start = float(specification["start"])
    stop = float(specification["stop"])
    step = float(specification["step"])
    if step <= 0 or stop < start:
        raise ValueError("Invalid candidate sweep")
    count = int(round((stop - start) / step)) + 1
    values = np.round(start + np.arange(count) * step, 10)
    if not math.isclose(float(values[-1]), stop):
        raise ValueError("Sweep stop is not reachable by step")
    return values


def _nanquantile(values: NDArray[np.float64], quantile: float) -> float:
    if not np.any(np.isfinite(values)):
        return math.nan
    return float(np.nanquantile(values, quantile))


def _resolve_input_path(config_path: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    candidates = [Path.cwd() / path, config_path.parent.parent / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(configured_path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
