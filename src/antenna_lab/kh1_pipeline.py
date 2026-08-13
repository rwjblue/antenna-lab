"""Shardable execution pipeline for the KH1 NEC-2 antenna study."""

from __future__ import annotations

import csv
import os
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from antenna_lab.kh1_nec import (
    BANDS,
    DIRECT_CANDIDATES,
    DIRECT_DEPLOYMENTS,
    GEOMETRIES,
    GROUNDS,
    REQUIRED,
    TUNER_ENVELOPES,
    _anchor,
    _baseline_tuner_rows,
    _direct_case,
    _doublet_case,
    _extension_window,
    _line_scenarios,
    _linked_reference,
    _manifest,
    _minimum_q,
    _named,
    _nanquantile,
    _quantile,
    _rank_doublet,
    _report,
    _samples_for_candidate,
    _selected_patterns,
    _sha256,
    _summarize_direct,
    _summary,
    _tuner_stress_matrix,
    _version,
    _write_csv,
    _write_json,
)
from antenna_lab.measurements import load_impedance_measurements
from antenna_lab.nec import find_nec2c
from antenna_lab.transmission_line import input_impedance, line_efficiency, swr

DEFAULT_MEASUREMENTS = Path("data/measured/58ft_doublet_2026-08-08.csv")
STUDY_LENGTHS = np.arange(40.5, 65.0 + 0.25, 0.5)
CONDUCTOR_CASES = (
    ("ccs_mid", 15_000_000.0),
    ("copper", 58_000_000.0),
)
T = TypeVar("T")


def run_doublet_nec_shard(
    output_dir: Path,
    *,
    shard_index: int,
    shard_count: int,
    nec2c: str | Path | None = None,
    jobs: int | None = None,
) -> dict[str, Any]:
    """Run one deterministic shard of the doublet NEC feedpoint cases."""
    executable = find_nec2c(nec2c)
    job_count = jobs or max(1, min(8, os.cpu_count() or 1))
    all_cases = _all_doublet_cases()
    cases = _shard_items(all_cases, shard_index, shard_count)
    _reset_directory(output_dir)

    with tempfile.TemporaryDirectory(prefix="kh1-doublet-nec-") as temporary:
        work = Path(temporary)
        rows = _run_parallel_cases(
            cases,
            lambda case: _doublet_case(*case, executable, work),
            jobs=job_count,
            label="doublet NEC",
        )

    rows = sorted(
        rows,
        key=lambda row: (
            row["geometry"],
            row["radiator_ft"],
            row["frequency_hz"],
        ),
    )
    csv_name = _shard_filename("doublet-nec", shard_index, shard_count, "csv")
    _write_csv(output_dir / csv_name, rows)
    metadata = _shard_metadata(
        stage="doublet-nec",
        shard_index=shard_index,
        shard_count=shard_count,
        selected_count=len(cases),
        total_count=len(all_cases),
        solver=_version(executable),
        output_file=csv_name,
    )
    _write_json(
        output_dir
        / _shard_filename("doublet-nec", shard_index, shard_count, "json"),
        metadata,
    )
    _manifest(output_dir)
    return metadata


def run_direct_nec_shard(
    output_dir: Path,
    *,
    shard_index: int,
    shard_count: int,
    nec2c: str | Path | None = None,
    jobs: int | None = None,
) -> dict[str, Any]:
    """Run one deterministic shard of the direct-fed NEC cases."""
    executable = find_nec2c(nec2c)
    job_count = jobs or max(1, min(8, os.cpu_count() or 1))
    all_cases = _all_direct_cases()
    cases = _shard_items(all_cases, shard_index, shard_count)
    _reset_directory(output_dir)

    with tempfile.TemporaryDirectory(prefix="kh1-direct-nec-") as temporary:
        work = Path(temporary)
        rows = _run_parallel_cases(
            cases,
            lambda case: _direct_case(*case, executable, work),
            jobs=job_count,
            label="direct NEC",
        )

    rows = sorted(
        rows,
        key=lambda row: (
            row["candidate"],
            row["deployment"],
            row["ground"],
            row["conductivity"],
            row["frequency_hz"],
        ),
    )
    csv_name = _shard_filename("direct-nec", shard_index, shard_count, "csv")
    _write_csv(output_dir / csv_name, rows)
    metadata = _shard_metadata(
        stage="direct-nec",
        shard_index=shard_index,
        shard_count=shard_count,
        selected_count=len(cases),
        total_count=len(all_cases),
        solver=_version(executable),
        output_file=csv_name,
    )
    _write_json(
        output_dir / _shard_filename("direct-nec", shard_index, shard_count, "json"),
        metadata,
    )
    _manifest(output_dir)
    return metadata


def run_doublet_grid_shard(
    output_dir: Path,
    *,
    input_dir: Path,
    shard_index: int,
    shard_count: int,
    measurement_path: Path = DEFAULT_MEASUREMENTS,
) -> dict[str, Any]:
    """Evaluate one radiator-length shard of the doublet uncertainty grid."""
    measurements, measured = _load_measurements(measurement_path)
    feedpoints = _load_stage_rows(input_dir, "doublet-nec")
    _validate_doublet_feedpoints(feedpoints)
    all_lengths = [float(value) for value in STUDY_LENGTHS]
    lengths = np.asarray(_shard_items(all_lengths, shard_index, shard_count))
    scenarios = _line_scenarios(measured)
    rows = _evaluate_doublet_grid(lengths, feedpoints, measured, scenarios)
    _reset_directory(output_dir)

    csv_name = _shard_filename("doublet-grid", shard_index, shard_count, "csv")
    _write_csv(output_dir / csv_name, rows)
    metadata = _shard_metadata(
        stage="doublet-grid",
        shard_index=shard_index,
        shard_count=shard_count,
        selected_count=len(rows),
        total_count=len(STUDY_LENGTHS) * len(_feedlines()),
        solver=None,
        output_file=csv_name,
        extra={
            "radiator_length_count": len(lengths),
            "radiator_lengths_ft": [float(value) for value in lengths],
            "feedpoint_row_count": len(feedpoints),
            "line_scenario_count": len(scenarios),
            "measurement_reference_plane": measurements[0].measurement_reference_plane,
            "measurement_sha256": _sha256(measurement_path),
        },
    )
    _write_json(
        output_dir
        / _shard_filename("doublet-grid", shard_index, shard_count, "json"),
        metadata,
    )
    _manifest(output_dir)
    return metadata


def assemble_study(
    output_dir: Path,
    *,
    input_dir: Path,
    measurement_path: Path = DEFAULT_MEASUREMENTS,
    nec2c: str | Path | None = None,
) -> dict[str, Any]:
    """Merge all shard artifacts and produce the canonical result package."""
    executable = find_nec2c(nec2c)
    measurements, measured = _load_measurements(measurement_path)
    baseline_tuner = _baseline_tuner_rows(measured)

    feedpoints = _load_stage_rows(input_dir, "doublet-nec")
    grid = _load_stage_rows(input_dir, "doublet-grid")
    direct_rows = _load_stage_rows(input_dir, "direct-nec")
    _validate_doublet_feedpoints(feedpoints)
    _validate_doublet_grid(grid)
    _validate_direct_rows(direct_rows)

    scenarios = _line_scenarios(measured)
    named, band_detail = _select_doublets(grid, feedpoints, scenarios)
    direct_summary = _summarize_direct(direct_rows)
    selections = {
        "current_58_28": _named(named, "current_58_28"),
        "classic_44_28": _named(named, "classic_44_28"),
        "44ft_optimized_line": _named(named, "44ft_optimized_line"),
        "robust_model_best": _named(named, "robust_model_best"),
        "current_plus_3ft_line": _named(named, "current_plus_3ft_line"),
    }

    _reset_directory(output_dir)
    data_dir = output_dir / "data"
    raw_dir = output_dir / "raw"
    provenance_dir = output_dir / "provenance" / "shards"
    data_dir.mkdir(parents=True)
    raw_dir.mkdir()
    provenance_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="kh1-nec-assemble-") as temporary:
        work = Path(temporary)
        linked = _linked_reference(executable, work / "linked")
        pattern_rows = _selected_patterns(
            selections,
            direct_summary,
            linked,
            executable,
            work / "patterns",
            raw_dir,
        )

    _write_csv(data_dir / "doublet_nec_feedpoints.csv", feedpoints)
    _write_csv(data_dir / "doublet_candidates.csv", grid)
    _write_csv(data_dir / "doublet_named.csv", named)
    _write_csv(data_dir / "doublet_named_by_band.csv", band_detail)
    _write_csv(
        data_dir / "line_scenarios.csv", [scenario[0] for scenario in scenarios]
    )
    _write_csv(data_dir / "direct_nec.csv", direct_rows)
    _write_csv(data_dir / "direct_candidates.csv", direct_summary)
    _write_csv(data_dir / "linked_dipole_reference.csv", linked)
    _write_csv(data_dir / "selected_pattern_metrics.csv", pattern_rows)
    _write_csv(data_dir / "baseline_tuner_envelope.csv", baseline_tuner)
    _copy_shard_metadata(input_dir, provenance_dir)

    extension_window = _extension_window(grid)
    solver_version = _version(executable)
    summary = _summary(
        solver_version,
        baseline_tuner,
        extension_window,
        len(feedpoints),
        len(scenarios),
        selections,
        direct_summary,
        linked,
    )
    summary["pipeline"] = {
        "mode": "github-actions-sharded",
        "doublet_nec_rows": len(feedpoints),
        "doublet_grid_rows": len(grid),
        "direct_nec_rows": len(direct_rows),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(_report(summary), encoding="utf-8")
    _write_json(
        output_dir / "run_metadata.json",
        {
            "solver": solver_version,
            "pipeline": "github-actions-sharded",
            "measurement_sha256": _sha256(measurement_path),
            "source_sha256": {
                "kh1_nec": _sha256(Path(__file__).with_name("kh1_nec.py")),
                "kh1_pipeline": _sha256(Path(__file__)),
            },
            "github_sha": os.environ.get("GITHUB_SHA"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "input_artifact_file_count": sum(
                path.is_file() for path in input_dir.rglob("*")
            ),
        },
    )
    _manifest(output_dir)
    return summary


def _evaluate_doublet_grid(
    lengths: np.ndarray,
    feedpoint_rows: list[dict[str, Any]],
    measured: np.ndarray,
    scenarios: list,
) -> list[dict[str, Any]]:
    geometry_ids = list(GEOMETRIES)
    lookup = _feedpoint_lookup(feedpoint_rows)
    feedlines = _feedlines()
    physical_sample_count = len(geometry_ids) * 2 * len(scenarios)
    sample_count = physical_sample_count * len(TUNER_ENVELOPES)
    frequencies = np.asarray([frequency for _, frequency, _ in BANDS], dtype=float)
    grid: list[dict[str, Any]] = []

    for length in lengths:
        for feedline in feedlines:
            compat_count = np.zeros(len(BANDS), dtype=int)
            tuner_stress_max: list[float] = []
            qmax: list[float] = []
            worst_eff: list[float] = []
            max_swrs: list[float] = []
            all_required: list[bool] = []
            for geometry_id in geometry_ids:
                nec_base = np.asarray(
                    [lookup[(geometry_id, 58.0, band)] for band, _, _ in BANDS]
                )
                nec_candidate = np.asarray(
                    [
                        lookup[(geometry_id, float(length), band)]
                        for band, _, _ in BANDS
                    ]
                )
                for _metadata, line, coax, coax_ft, baseline_load in scenarios:
                    for method in ("impedance_delta", "smith_displacement"):
                        load = _anchor(
                            baseline_load,
                            nec_base,
                            nec_candidate,
                            line.characteristic_impedance_ohm,
                            method,
                        )
                        radio = np.empty(len(BANDS), dtype=complex)
                        efficiency = np.empty(len(BANDS))
                        valid = np.ones(len(BANDS), dtype=bool)
                        for index, (_, frequency, _) in enumerate(BANDS):
                            if load[index].real <= 0:
                                valid[index] = False
                                radio[index] = np.nan + 1j * np.nan
                                efficiency[index] = np.nan
                                continue
                            at_line = input_impedance(
                                load[index], frequency, feedline, line
                            )
                            eff = line_efficiency(
                                load[index], frequency, feedline, line
                            )
                            if coax_ft:
                                eff *= line_efficiency(
                                    at_line, frequency, coax_ft, coax
                                )
                                at_line = input_impedance(
                                    at_line, frequency, coax_ft, coax
                                )
                            radio[index] = at_line
                            efficiency[index] = eff
                        q = _minimum_q(radio)
                        tuner_stresses = _tuner_stress_matrix(radio, frequencies)
                        compatible = (
                            valid[np.newaxis, :]
                            & np.isfinite(tuner_stresses)
                            & (tuner_stresses <= 1.0)
                        )
                        compat_count += np.sum(compatible, axis=0)
                        all_required.extend(
                            np.all(compatible[:, REQUIRED], axis=1).tolist()
                        )
                        if np.all(valid[REQUIRED]):
                            tuner_stress_max.extend(
                                np.max(tuner_stresses[:, REQUIRED], axis=1).tolist()
                            )
                            qmax.append(float(np.max(q[REQUIRED])))
                            worst_eff.append(float(np.min(efficiency[REQUIRED])))
                            max_swrs.append(float(np.max(swr(radio[REQUIRED]))))
            row = {
                "radiator_ft": float(length),
                "feedline_ft": float(feedline),
                "total_wire_ft": float(length + 2 * feedline),
                "physical_sample_count": physical_sample_count,
                "tuner_envelope_count": len(TUNER_ENVELOPES),
                "sample_count": sample_count,
                "all_required_compatibility_fraction": float(np.mean(all_required)),
                "minimum_required_band_compatibility_fraction": float(
                    np.min(compat_count[REQUIRED] / sample_count)
                ),
                "required_max_tuner_stress_p90": _quantile(
                    tuner_stress_max, 0.90
                ),
                "required_max_q_p90": _quantile(qmax, 0.90),
                "required_max_raw_swr_p90": _quantile(max_swrs, 0.90),
                "required_worst_line_efficiency_p10": _quantile(worst_eff, 0.10),
            }
            for index, (band, _, _) in enumerate(BANDS):
                row[f"{band}_compatibility_fraction"] = float(
                    compat_count[index] / sample_count
                )
            grid.append(row)
    return sorted(grid, key=lambda row: (row["radiator_ft"], row["feedline_ft"]))


def _select_doublets(
    grid: list[dict[str, Any]],
    feedpoint_rows: list[dict[str, Any]],
    scenarios: list,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lookup = _feedpoint_lookup(feedpoint_rows)
    ranked = sorted(grid, key=_rank_doublet)
    by_dimensions = {
        (row["radiator_ft"], row["feedline_ft"]): row for row in grid
    }
    selections: dict[str, dict[str, Any]] = {
        "current_58_28": by_dimensions[(58.0, 28.0)],
        "classic_44_28": by_dimensions[(44.0, 28.0)],
        "current_plus_3ft_line": by_dimensions[(58.0, 31.0)],
        "reversible_57_28": by_dimensions[(57.0, 28.0)],
        "robust_model_best": ranked[0],
    }
    selections["44ft_optimized_line"] = sorted(
        [row for row in grid if row["radiator_ft"] == 44.0],
        key=_rank_doublet,
    )[0]
    named = [{"selection": name, **row} for name, row in selections.items()]

    details: list[dict[str, Any]] = []
    central_index = list(TUNER_ENVELOPES).index("central")
    for name, row in selections.items():
        samples = _samples_for_candidate(
            row["radiator_ft"], row["feedline_ft"], lookup, scenarios
        )
        for band_index, (band, frequency, _) in enumerate(BANDS):
            z = np.asarray([sample[0][band_index] for sample in samples])
            q = np.asarray([sample[1][band_index] for sample in samples])
            eff = np.asarray([sample[2][band_index] for sample in samples])
            stresses = np.asarray(
                [sample[3][:, band_index] for sample in samples]
            ).reshape(-1)
            central_stress = np.asarray(
                [sample[3][central_index, band_index] for sample in samples]
            )
            valid = np.isfinite(z.real) & (z.real > 0) & np.isfinite(q)
            details.append(
                {
                    "selection": name,
                    "band": band,
                    "frequency_hz": frequency,
                    "compatibility_fraction": float(
                        np.mean(np.isfinite(stresses) & (stresses <= 1.0))
                    ),
                    "resistance_p50": _nanquantile(z.real, 0.5),
                    "reactance_p50": _nanquantile(z.imag, 0.5),
                    "central_tuner_stress_p50": _nanquantile(
                        central_stress, 0.5
                    ),
                    "central_tuner_stress_p90": _nanquantile(
                        central_stress, 0.9
                    ),
                    "minimum_q_p50": _nanquantile(q[valid], 0.5),
                    "minimum_q_p90": _nanquantile(q[valid], 0.9),
                    "raw_swr_p50": _nanquantile(swr(z[valid]), 0.5),
                    "line_efficiency_p10": _nanquantile(eff[valid], 0.1),
                }
            )
    return named, details


def _all_doublet_cases() -> list[tuple]:
    return [
        (geometry_id, geometry, float(length), band, frequency)
        for geometry_id, geometry in GEOMETRIES.items()
        for length in STUDY_LENGTHS
        for band, frequency, _ in BANDS
    ]


def _all_direct_cases() -> list[tuple]:
    return [
        (
            candidate_id,
            radiator,
            counterpoise,
            deployment_id,
            deployment,
            ground_id,
            ground,
            conductivity_id,
            conductivity,
            band,
            frequency,
        )
        for candidate_id, (radiator, counterpoise) in DIRECT_CANDIDATES.items()
        for deployment_id, deployment in DIRECT_DEPLOYMENTS.items()
        for ground_id, ground in GROUNDS.items()
        for conductivity_id, conductivity in CONDUCTOR_CASES
        for band, frequency, required in BANDS
        if required
    ]


def _run_parallel_cases(
    cases, function, *, jobs: int, label: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(function, case): index
            for index, case in enumerate(cases)
        }
        for completed, future in enumerate(as_completed(futures), 1):
            try:
                rows.append(future.result())
            except Exception as error:
                raise RuntimeError(
                    f"{label} failed for shard item {futures[future]}"
                ) from error
            if completed % 100 == 0 or completed == len(futures):
                print(f"{label} {completed}/{len(futures)}", flush=True)
    return rows


def _shard_items(items: list[T], shard_index: int, shard_count: int) -> list[T]:
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("shard_index must be in [0, shard_count)")
    return items[shard_index::shard_count]


def _feedlines() -> np.ndarray:
    return np.unique(
        np.concatenate(
            (
                np.arange(10.0, 40.0 + 0.25, 0.5),
                np.arange(27.5, 32.5 + 0.125, 0.25),
            )
        )
    )


def _feedpoint_lookup(rows: list[dict[str, Any]]) -> dict[tuple, complex]:
    return {
        (row["geometry"], row["radiator_ft"], row["band"]): complex(
            row["resistance_ohm"], row["reactance_ohm"]
        )
        for row in rows
    }


def _load_measurements(measurement_path: Path):
    measurements = load_impedance_measurements(measurement_path)
    if [row.band for row in measurements] != [band for band, _, _ in BANDS]:
        raise ValueError("Measurement band order does not match study bands")
    return measurements, np.asarray([row.impedance_ohm for row in measurements])


def _load_stage_rows(input_dir: Path, stage: str) -> list[dict[str, Any]]:
    files = sorted(input_dir.rglob(f"{stage}-shard-*.csv"))
    if not files:
        raise FileNotFoundError(f"No {stage} shard CSV files found below {input_dir}")
    rows: list[dict[str, Any]] = []
    for path in files:
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(
                {
                    key: _coerce_csv_value(value)
                    for key, value in row.items()
                }
                for row in csv.DictReader(handle)
            )
    return rows


def _coerce_csv_value(value: str | None) -> Any:
    if value is None or value == "":
        return None
    if value == "True":
        return True
    if value == "False":
        return False
    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def _validate_doublet_feedpoints(rows: list[dict[str, Any]]) -> None:
    expected = {
        (geometry_id, float(length), band)
        for geometry_id in GEOMETRIES
        for length in STUDY_LENGTHS
        for band, _, _ in BANDS
    }
    actual = {(row["geometry"], row["radiator_ft"], row["band"]) for row in rows}
    _validate_key_set("doublet NEC feedpoints", expected, actual, len(rows))


def _validate_doublet_grid(rows: list[dict[str, Any]]) -> None:
    expected = {
        (float(length), float(feedline))
        for length in STUDY_LENGTHS
        for feedline in _feedlines()
    }
    actual = {(row["radiator_ft"], row["feedline_ft"]) for row in rows}
    _validate_key_set("doublet grid", expected, actual, len(rows))


def _validate_direct_rows(rows: list[dict[str, Any]]) -> None:
    expected = {
        (candidate, deployment, ground, conductivity, band)
        for candidate in DIRECT_CANDIDATES
        for deployment in DIRECT_DEPLOYMENTS
        for ground in GROUNDS
        for conductivity, _ in CONDUCTOR_CASES
        for band, _, required in BANDS
        if required
    }
    actual = {
        (
            row["candidate"],
            row["deployment"],
            row["ground"],
            row["conductivity"],
            row["band"],
        )
        for row in rows
    }
    _validate_key_set("direct NEC", expected, actual, len(rows))


def _validate_key_set(label: str, expected: set, actual: set, row_count: int) -> None:
    if row_count != len(actual):
        raise ValueError(f"{label} contains duplicate rows")
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        raise ValueError(
            f"{label} is incomplete: {len(missing)} missing, {len(extra)} unexpected"
        )


def _copy_shard_metadata(input_dir: Path, output_dir: Path) -> None:
    for path in sorted(input_dir.rglob("*-shard-*.json")):
        destination = output_dir / path.name
        if destination.exists() and destination.read_bytes() != path.read_bytes():
            raise ValueError(f"Conflicting shard metadata file: {path.name}")
        shutil.copy2(path, destination)


def _shard_filename(stage: str, index: int, count: int, suffix: str) -> str:
    return f"{stage}-shard-{index:02d}-of-{count:02d}.{suffix}"


def _shard_metadata(
    *,
    stage: str,
    shard_index: int,
    shard_count: int,
    selected_count: int,
    total_count: int,
    solver: str | None,
    output_file: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "stage": stage,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "selected_count": selected_count,
        "total_count": total_count,
        "output_file": output_file,
        "solver": solver,
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }
    if extra:
        metadata.update(extra)
    return metadata


def _reset_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
