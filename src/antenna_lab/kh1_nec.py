"""Actual NEC-2 study for N1RWJ's compact KH1/KX2 antenna choices."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import brentq

from antenna_lab.measurements import load_impedance_measurements
from antenna_lab.nec import InvertedV, direct_wire_deck, doublet_deck, find_nec2c, run
from antenna_lab.transmission_line import (
    LineParameters,
    input_impedance,
    line_efficiency,
    load_impedance,
    swr,
)

# BANDS is the measured/reference-plane anchored set.  Keep this order aligned
# with data/measured/58ft_doublet_2026-08-08.csv.
BANDS = (
    ("40m", 7_050_000, True),
    ("30m", 10_120_000, True),
    ("20m", 14_050_000, True),
    ("17m", 18_080_000, True),
    ("15m", 21_050_000, True),
    ("12m", 24_910_000, False),
    ("10m", 28_050_000, False),
)

# The direct-fed and resonant-reference models do not depend on the measured
# doublet reference plane, so they can cover the wider portable-HF question.
# 6 m is included as an exploratory case for the KX3 and Z-11Pro II; the KH1
# and KX2 do not transmit there.
EXTENDED_BANDS = (
    ("80m", 3_550_000, False),
    ("60m", 5_357_000, False),
    *BANDS,
    ("6m", 50_100_000, False),
)
KH1_REQUIRED_BANDS = tuple(band for band, _, required in BANDS if required)
REQUIRED = np.asarray(
    [index for index, (_, _, required) in enumerate(BANDS) if required]
)
RADIUS_M = 0.0002415
WIRE_CONDUCTIVITY = 15_000_000.0
GROUNDS = {
    "poor": (5.0, 0.001),
    "average": (13.0, 0.005),
}
GEOMETRIES = {
    "pulaski_30_10": InvertedV(30.0, end_height_ft=10.0),
    "carolina_20_5": InvertedV(20.0, end_height_ft=5.0),
    "reference_30_120": InvertedV(30.0, apex_angle_deg=120.0),
}
DIRECT_CANDIDATES = {
    "29r-17c": (29.0, 17.0),
    "35r-13c": (35.0, 13.0),
    "35r-17c": (35.0, 17.0),
    "35r-25c": (35.0, 25.0),
    "41r-17c": (41.0, 17.0),
    "53r-17c": (53.0, 17.0),
}
TUNER_ENVELOPES = {
    "conservative": {"lmax_uH": 8.0, "cmax_pF": 325.0},
    "central": {"lmax_uH": 12.0, "cmax_pF": 400.0},
    "permissive": {"lmax_uH": 15.0, "cmax_pF": 500.0},
}
TUNER_BYPASS_SWR = 2.5
TUNER_TOPOLOGY_NAMES = {
    0: "series_l_then_source_shunt_c",
    1: "load_shunt_c_then_series_l",
    2: "bypass",
    -1: "none",
}
DIRECT_DEPLOYMENTS = {
    "ground_side_20": (0.5, 20.0, 0.10, 90.0),
    "ground_bent_20": (0.5, 20.0, 0.10, 135.0),
    "ground_collinear_20": (0.5, 20.0, 0.10, 180.0),
    "table_side_30": (3.0, 30.0, 0.50, 90.0),
    "table_bent_30": (3.0, 30.0, 0.50, 135.0),
    "table_collinear_30": (3.0, 30.0, 0.50, 180.0),
}


def run_study(
    output_dir: Path,
    *,
    measurement_path: Path = Path("data/measured/58ft_doublet_2026-08-08.csv"),
    nec2c: str | Path | None = None,
    jobs: int | None = None,
) -> dict[str, Any]:
    executable = find_nec2c(nec2c)
    job_count = jobs or max(1, min(8, os.cpu_count() or 1))
    measurements = load_impedance_measurements(measurement_path)
    measured = np.asarray([row.impedance_ohm for row in measurements])
    if [row.band for row in measurements] != [band for band, _, _ in BANDS]:
        raise ValueError("Measurement band order does not match study bands")
    baseline_tuner = _baseline_tuner_rows(measured)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    data_dir = output_dir / "data"
    raw_dir = output_dir / "raw"
    data_dir.mkdir()
    raw_dir.mkdir()

    lengths = np.arange(40.5, 65.0 + 0.25, 0.5)
    with tempfile.TemporaryDirectory(prefix="kh1-nec-") as temporary:
        work = Path(temporary)
        feedpoints = _run_doublet_nec(lengths, executable, work / "doublet", job_count)
        _write_csv(data_dir / "doublet_nec_feedpoints.csv", feedpoints)

        line_scenarios = _line_scenarios(measured)
        _write_csv(
            data_dir / "line_scenarios.csv",
            [scenario[0] for scenario in line_scenarios],
        )

        grid, named, band_detail = _evaluate_doublets(
            lengths, feedpoints, measured, line_scenarios
        )
        _write_csv(data_dir / "doublet_candidates.csv", grid)
        _write_csv(data_dir / "doublet_named.csv", named)
        _write_csv(data_dir / "doublet_named_by_band.csv", band_detail)

        direct_rows = _run_direct_nec(executable, work / "direct", job_count)
        _write_csv(data_dir / "direct_nec.csv", direct_rows)
        direct_summary = _summarize_direct(direct_rows)
        direct_by_band = _summarize_direct_by_band(direct_rows)
        _write_csv(data_dir / "direct_candidates.csv", direct_summary)
        _write_csv(data_dir / "direct_candidates_by_band.csv", direct_by_band)

        linked = _linked_reference(executable, work / "linked")
        _write_csv(data_dir / "linked_dipole_reference.csv", linked)

        selections = {
            "current_58_28": _named(named, "current_58_28"),
            "classic_44_28": _named(named, "classic_44_28"),
            "44ft_optimized_line": _named(named, "44ft_optimized_line"),
            "robust_model_best": _named(named, "robust_model_best"),
            "current_plus_3ft_line": _named(named, "current_plus_3ft_line"),
        }
        pattern_rows = _selected_patterns(
            selections, direct_summary, linked, executable, work / "patterns", raw_dir
        )
        _write_csv(data_dir / "selected_pattern_metrics.csv", pattern_rows)
        _write_csv(data_dir / "baseline_tuner_envelope.csv", baseline_tuner)

    extension_window = _extension_window(grid)
    solver_version = _version(executable)
    summary = _summary(
        solver_version,
        baseline_tuner,
        extension_window,
        len(feedpoints),
        len(line_scenarios),
        selections,
        direct_summary,
        direct_by_band,
        linked,
    )
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(_report(summary), encoding="utf-8")
    _write_json(
        output_dir / "run_metadata.json",
        {
            "solver": solver_version,
            "measurement_sha256": _sha256(measurement_path),
            "source_sha256": _sha256(Path(__file__)),
            "github_sha": os.environ.get("GITHUB_SHA"),
            "method": "actual NEC-2 radiator/direct-wire runs; measured-reference-plane anchored doublet deltas",
        },
    )
    _manifest(output_dir)
    return summary


def _run_doublet_nec(
    lengths: np.ndarray, executable: Path, work: Path, jobs: int
) -> list[dict[str, Any]]:
    cases = [
        (geometry_id, geometry, float(length), band, frequency)
        for geometry_id, geometry in GEOMETRIES.items()
        for length in lengths
        for band, frequency, _ in EXTENDED_BANDS
    ]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        future_map = {
            pool.submit(
                _doublet_case,
                geometry_id,
                geometry,
                length,
                band,
                frequency,
                executable,
                work,
            ): (geometry_id, length, band)
            for geometry_id, geometry, length, band, frequency in cases
        }
        for index, future in enumerate(as_completed(future_map), 1):
            try:
                rows.append(future.result())
            except Exception as error:
                raise RuntimeError(f"NEC failed for {future_map[future]}") from error
            if index % 100 == 0:
                print(f"doublet NEC {index}/{len(future_map)}", flush=True)
    return sorted(
        rows, key=lambda row: (row["geometry"], row["radiator_ft"], row["frequency_hz"])
    )


def _doublet_case(
    geometry_id: str,
    geometry: InvertedV,
    length: float,
    band: str,
    frequency_hz: int,
    executable: Path,
    work: Path,
) -> dict[str, Any]:
    stem = f"{geometry_id}-{length:.1f}-{band}".replace(".", "p")
    result, deck_path, output_path = run(
        doublet_deck(
            title=stem,
            total_length_ft=length,
            geometry=geometry,
            frequency_mhz=frequency_hz / 1e6,
            radius_m=RADIUS_M,
            conductivity_s_m=WIRE_CONDUCTIVITY,
            epsilon_r=13.0,
            ground_conductivity_s_m=0.005,
        ),
        work,
        stem,
        executable,
    )
    deck_path.unlink()
    output_path.unlink()
    _, end_height = geometry.endpoints(length)
    return {
        "geometry": geometry_id,
        "radiator_ft": length,
        "band": band,
        "frequency_hz": frequency_hz,
        "resistance_ohm": result.impedance_ohm.real,
        "reactance_ohm": result.impedance_ohm.imag,
        "nec_efficiency": result.efficiency,
        "center_height_ft": geometry.center_height_ft,
        "end_height_ft": end_height,
        "included_angle_deg": geometry.included_angle_deg(length),
    }


def _line_scenarios(
    measured: np.ndarray,
) -> list[tuple[dict[str, Any], LineParameters, LineParameters, float, np.ndarray]]:
    spacing = 0.0127
    diameter = 0.000483
    air_z0 = 120.0 * math.acosh(spacing / diameter)
    coax = LineParameters(50.0, 0.78, 0.45)
    rows = []
    for vf in (0.90, 0.95, 0.99):
        for scale in (0.90, 1.00, 1.10):
            for loss in (0.20, 0.60):
                line = LineParameters(air_z0 * vf * scale, vf, loss)
                for coax_ft in (0.0, 3.0):
                    loads = []
                    for z, (_, frequency, _) in zip(measured, BANDS, strict=True):
                        at_line = (
                            z
                            if not coax_ft
                            else load_impedance(z, frequency, coax_ft, coax)
                        )
                        loads.append(load_impedance(at_line, frequency, 28.0, line))
                    loads_array = np.asarray(loads)
                    if np.min(loads_array.real) <= 0.05:
                        continue
                    metadata = {
                        "id": f"vf{vf:.2f}-scale{scale:.2f}-loss{loss:.2f}-coax{coax_ft:.0f}",
                        "air_z0_ohm": air_z0,
                        "effective_z0_ohm": line.characteristic_impedance_ohm,
                        "velocity_factor": vf,
                        "z0_scale": scale,
                        "loss_db_100ft_10mhz": loss,
                        "coax_length_ft": coax_ft,
                        "minimum_deembedded_r_ohm": float(np.min(loads_array.real)),
                    }
                    rows.append((metadata, line, coax, coax_ft, loads_array))
    if not rows:
        raise RuntimeError("No passive line scenarios")
    return rows


def _evaluate_doublets(
    lengths: np.ndarray,
    feedpoint_rows: list[dict[str, Any]],
    measured: np.ndarray,
    scenarios: list[
        tuple[dict[str, Any], LineParameters, LineParameters, float, np.ndarray]
    ],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    geometry_ids = list(GEOMETRIES)
    lookup = {
        (row["geometry"], row["radiator_ft"], row["band"]): complex(
            row["resistance_ohm"], row["reactance_ohm"]
        )
        for row in feedpoint_rows
    }
    feedlines = np.unique(
        np.concatenate(
            (
                np.arange(10.0, 40.0 + 0.25, 0.5),
                np.arange(27.5, 32.5 + 0.125, 0.25),
            )
        )
    )
    physical_sample_count = len(geometry_ids) * 2 * len(scenarios)
    sample_count = physical_sample_count * len(TUNER_ENVELOPES)
    grid: list[dict[str, Any]] = []
    sample_cache: dict[
        tuple[float, float],
        list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    ] = {}
    frequencies = np.asarray([frequency for _, frequency, _ in BANDS], dtype=float)

    for length in lengths:
        for feedline in feedlines:
            compat_count = np.zeros(len(BANDS), dtype=int)
            tuner_stress_max = []
            qmax = []
            worst_eff = []
            max_swrs = []
            all_required = []
            samples = []
            for geometry_id in geometry_ids:
                nec_base = np.asarray(
                    [lookup[(geometry_id, 58.0, band)] for band, _, _ in BANDS]
                )
                nec_candidate = np.asarray(
                    [lookup[(geometry_id, float(length), band)] for band, _, _ in BANDS]
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
                        samples.append((radio, q, efficiency, tuner_stresses))
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
            if (float(length), float(feedline)) in {
                (58.0, 28.0),
                (44.0, 28.0),
                (58.0, 31.0),
                (57.0, 28.0),
            }:
                sample_cache[(float(length), float(feedline))] = samples

    ranked = sorted(grid, key=_rank_doublet)
    by_dimensions = {(row["radiator_ft"], row["feedline_ft"]): row for row in grid}
    selections: dict[str, dict[str, Any]] = {
        "current_58_28": by_dimensions[(58.0, 28.0)],
        "classic_44_28": by_dimensions[(44.0, 28.0)],
        "current_plus_3ft_line": by_dimensions[(58.0, 31.0)],
        "reversible_57_28": by_dimensions[(57.0, 28.0)],
        "robust_model_best": ranked[0],
    }
    selections["44ft_optimized_line"] = sorted(
        [row for row in grid if row["radiator_ft"] == 44.0], key=_rank_doublet
    )[0]
    named = [{"selection": name, **row} for name, row in selections.items()]
    details = []
    central_index = list(TUNER_ENVELOPES).index("central")
    for name, row in selections.items():
        key = (row["radiator_ft"], row["feedline_ft"])
        samples = sample_cache.get(key)
        if samples is None:
            samples = _samples_for_candidate(key[0], key[1], lookup, scenarios)
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
    return (
        sorted(grid, key=lambda row: (row["radiator_ft"], row["feedline_ft"])),
        named,
        details,
    )


def _samples_for_candidate(
    length: float, feedline: float, lookup: dict, scenarios: list
) -> list:
    samples = []
    frequencies = np.asarray([frequency for _, frequency, _ in BANDS], dtype=float)
    for geometry_id in GEOMETRIES:
        nec_base = np.asarray(
            [lookup[(geometry_id, 58.0, band)] for band, _, _ in BANDS]
        )
        nec_candidate = np.asarray(
            [lookup[(geometry_id, length, band)] for band, _, _ in BANDS]
        )
        for _, line, coax, coax_ft, baseline_load in scenarios:
            for method in ("impedance_delta", "smith_displacement"):
                load = _anchor(
                    baseline_load,
                    nec_base,
                    nec_candidate,
                    line.characteristic_impedance_ohm,
                    method,
                )
                radio = []
                efficiency = []
                for z, (_, frequency, _) in zip(load, BANDS, strict=True):
                    if z.real <= 0:
                        radio.append(np.nan + 1j * np.nan)
                        efficiency.append(np.nan)
                        continue
                    at_line = input_impedance(z, frequency, feedline, line)
                    eff = line_efficiency(z, frequency, feedline, line)
                    if coax_ft:
                        eff *= line_efficiency(at_line, frequency, coax_ft, coax)
                        at_line = input_impedance(at_line, frequency, coax_ft, coax)
                    radio.append(at_line)
                    efficiency.append(eff)
                radio_array = np.asarray(radio)
                samples.append(
                    (
                        radio_array,
                        _minimum_q(radio_array),
                        np.asarray(efficiency),
                        _tuner_stress_matrix(radio_array, frequencies),
                    )
                )
    return samples


def _run_direct_nec(
    executable: Path, work: Path, jobs: int
) -> list[dict[str, Any]]:
    cases = [
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
        for conductivity_id, conductivity in (
            ("ccs_mid", 15_000_000.0),
            ("copper", 58_000_000.0),
        )
        for band, frequency, _ in EXTENDED_BANDS
    ]
    rows = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(_direct_case, *case, executable, work): case[:2]
            + (case[3], case[5], case[7], case[9])
            for case in cases
        }
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as error:
                raise RuntimeError(f"Direct NEC failed: {futures[future]}") from error
    return sorted(
        rows,
        key=lambda row: (
            row["candidate"],
            row["deployment"],
            row["ground"],
            row["conductivity"],
            row["frequency_hz"],
        ),
    )


def _direct_case(
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
    executable,
    work,
):
    feed, support, counterpoise_height, counterpoise_azimuth = deployment
    case_identity = (
        f"{candidate_id}|{deployment_id}|{ground_id}|"
        f"{conductivity_id}|{band}"
    )
    stem = (
        f"d-{candidate_id}-"
        f"{hashlib.sha256(case_identity.encode()).hexdigest()[:12]}"
    )
    result, deck_path, output_path = run(
        direct_wire_deck(
            title=stem,
            radiator_ft=radiator,
            counterpoise_ft=counterpoise,
            feed_height_ft=feed,
            support_height_ft=support,
            counterpoise_height_ft=counterpoise_height,
            counterpoise_azimuth_deg=counterpoise_azimuth,
            frequency_mhz=frequency / 1e6,
            radius_m=RADIUS_M,
            conductivity_s_m=conductivity,
            epsilon_r=ground[0],
            ground_conductivity_s_m=ground[1],
        ),
        work,
        stem,
        executable,
    )
    deck_path.unlink()
    output_path.unlink()
    row = {
        "candidate": candidate_id,
        "radiator_ft": radiator,
        "counterpoise_ft": counterpoise,
        "deployment": deployment_id,
        "feed_height_ft": feed,
        "support_height_ft": support,
        "counterpoise_height_ft": counterpoise_height,
        "counterpoise_azimuth_deg": counterpoise_azimuth,
        "ground": ground_id,
        "conductivity": conductivity_id,
        "band": band,
        "frequency_hz": frequency,
        "resistance_ohm": result.impedance_ohm.real,
        "reactance_ohm": result.impedance_ohm.imag,
        "raw_swr": float(swr(result.impedance_ohm)),
        "minimum_q": float(_minimum_q(result.impedance_ohm)),
        "nec_efficiency": result.efficiency,
    }
    for envelope_id, limits in TUNER_ENVELOPES.items():
        stress, l_uh, c_pf, topology = _kh1_tuner_proxy(
            result.impedance_ohm,
            frequency,
            lmax_uH=limits["lmax_uH"],
            cmax_pF=limits["cmax_pF"],
        )
        row[f"{envelope_id}_tuner_stress"] = float(stress)
        row[f"{envelope_id}_compatible"] = bool(stress <= 1.0)
        if envelope_id == "central":
            row["central_l_uH"] = float(l_uh)
            row["central_c_pF"] = float(c_pf)
            row["central_topology"] = TUNER_TOPOLOGY_NAMES[int(topology)]
    return row


def _summarize_direct(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank direct-fed candidates on the five KH1 priority bands.

    Rows may contain additional exploratory bands.  Those bands are intentionally
    excluded from the candidate ranking so extending the study cannot silently
    change the original KH1 optimization objective.
    """
    summaries = []
    required_band_set = set(KH1_REQUIRED_BANDS)
    for candidate in DIRECT_CANDIDATES:
        subset = [row for row in rows if row["candidate"] == candidate]
        scenarios: dict[tuple, list[dict[str, Any]]] = {}
        for row in subset:
            scenarios.setdefault(
                (row["deployment"], row["ground"], row["conductivity"]), []
            ).append(row)
        all_compatible = []
        worst_eff = []
        max_q = []
        max_stress = []
        band_compat: dict[str, float] = {}
        for band in KH1_REQUIRED_BANDS:
            band_rows = [row for row in subset if row["band"] == band]
            compatibility = [
                bool(row[f"{envelope_id}_compatible"])
                for row in band_rows
                for envelope_id in TUNER_ENVELOPES
            ]
            band_compat[band] = float(np.mean(compatibility))
        for scenario_rows in scenarios.values():
            required_rows = [
                row for row in scenario_rows if row["band"] in required_band_set
            ]
            if len(required_rows) != len(KH1_REQUIRED_BANDS):
                raise ValueError(
                    "Direct-fed scenario is missing one or more KH1 priority bands"
                )
            for envelope_id in TUNER_ENVELOPES:
                all_compatible.append(
                    all(
                        row[f"{envelope_id}_compatible"]
                        for row in required_rows
                    )
                )
                max_stress.append(
                    max(
                        row[f"{envelope_id}_tuner_stress"]
                        for row in required_rows
                    )
                )
            efficiencies = [
                row["nec_efficiency"]
                for row in required_rows
                if row["nec_efficiency"] is not None
            ]
            worst_eff.append(min(efficiencies))
            max_q.append(max(row["minimum_q"] for row in required_rows))
        radiator, counterpoise = DIRECT_CANDIDATES[candidate]
        summaries.append(
            {
                "candidate": candidate,
                "radiator_ft": radiator,
                "counterpoise_ft": counterpoise,
                "total_wire_ft": radiator + counterpoise,
                "physical_scenario_count": len(scenarios),
                "tuner_envelope_count": len(TUNER_ENVELOPES),
                "sample_count": len(scenarios) * len(TUNER_ENVELOPES),
                "modeled_band_count": len(EXTENDED_BANDS),
                "all_required_compatibility_fraction": float(
                    np.mean(all_compatible)
                ),
                "minimum_required_band_compatibility_fraction": min(
                    band_compat.values()
                ),
                "required_max_tuner_stress_p90": _quantile(max_stress, 0.9),
                "required_max_q_p90": _quantile(max_q, 0.9),
                "required_worst_nec_efficiency_p10": _quantile(
                    worst_eff, 0.1
                ),
                **{
                    f"{band}_compatibility_fraction": value
                    for band, value in band_compat.items()
                },
            }
        )
    return sorted(
        summaries,
        key=lambda row: (
            -row["all_required_compatibility_fraction"],
            -row["minimum_required_band_compatibility_fraction"],
            row["required_max_tuner_stress_p90"],
            row["required_max_q_p90"],
            -row["required_worst_nec_efficiency_p10"],
            row["total_wire_ft"],
        ),
    )


def _summarize_direct_by_band(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize every modeled band without changing the KH1 ranking."""
    summaries: list[dict[str, Any]] = []
    for candidate, (radiator, counterpoise) in DIRECT_CANDIDATES.items():
        candidate_rows = [row for row in rows if row["candidate"] == candidate]
        for band, frequency, kh1_required in EXTENDED_BANDS:
            band_rows = [row for row in candidate_rows if row["band"] == band]
            if not band_rows:
                raise ValueError(f"No direct-fed rows for {candidate} on {band}")
            resistance = [row["resistance_ohm"] for row in band_rows]
            reactance = [row["reactance_ohm"] for row in band_rows]
            raw_swrs = [row["raw_swr"] for row in band_rows]
            minimum_q = [row["minimum_q"] for row in band_rows]
            efficiencies = [
                row["nec_efficiency"]
                for row in band_rows
                if row["nec_efficiency"] is not None
            ]
            all_stresses = [
                row[f"{envelope_id}_tuner_stress"]
                for row in band_rows
                for envelope_id in TUNER_ENVELOPES
            ]
            all_compatibility = [
                row[f"{envelope_id}_compatible"]
                for row in band_rows
                for envelope_id in TUNER_ENVELOPES
            ]
            central_stresses = [
                row["central_tuner_stress"] for row in band_rows
            ]
            central_compatibility = [
                row["central_compatible"] for row in band_rows
            ]
            summaries.append(
                {
                    "candidate": candidate,
                    "radiator_ft": radiator,
                    "counterpoise_ft": counterpoise,
                    "band": band,
                    "frequency_hz": frequency,
                    "kh1_priority_band": kh1_required,
                    "physical_scenario_count": len(band_rows),
                    "resistance_p10": _quantile(resistance, 0.1),
                    "resistance_p50": _quantile(resistance, 0.5),
                    "resistance_p90": _quantile(resistance, 0.9),
                    "reactance_p10": _quantile(reactance, 0.1),
                    "reactance_p50": _quantile(reactance, 0.5),
                    "reactance_p90": _quantile(reactance, 0.9),
                    "raw_swr_p50": _quantile(raw_swrs, 0.5),
                    "raw_swr_p90": _quantile(raw_swrs, 0.9),
                    "minimum_q_p90": _quantile(minimum_q, 0.9),
                    "nec_efficiency_p10": _quantile(efficiencies, 0.1),
                    "nec_efficiency_p50": _quantile(efficiencies, 0.5),
                    "generic_tuner_proxy_compatibility_fraction": float(
                        np.mean(all_compatibility)
                    ),
                    "generic_tuner_proxy_stress_p90": _quantile(
                        all_stresses, 0.9
                    ),
                    "central_proxy_compatibility_fraction": float(
                        np.mean(central_compatibility)
                    ),
                    "central_proxy_stress_p90": _quantile(
                        central_stresses, 0.9
                    ),
                }
            )
    band_order = {band: index for index, (band, _, _) in enumerate(EXTENDED_BANDS)}
    return sorted(
        summaries,
        key=lambda row: (row["candidate"], band_order[row["band"]]),
    )

def _linked_geometry(band: str) -> tuple[str, InvertedV]:
    if band == "80m":
        return "reference_30_5", InvertedV(30.0, end_height_ft=5.0)
    return "reference_30_120", GEOMETRIES["reference_30_120"]


def _linked_reference(executable: Path, work: Path) -> list[dict[str, Any]]:
    rows = []
    for band, frequency, kh1_required in EXTENDED_BANDS:
        geometry_id, geometry = _linked_geometry(band)
        estimate = 468.0 / (frequency / 1e6)
        cache = {}

        def evaluate(
            length,
            *,
            band=band,
            frequency=frequency,
            cache=cache,
            geometry=geometry,
        ):
            key = round(float(length), 6)
            if key not in cache:
                stem = f"linked-{band}-{key:.6f}".replace(".", "p")
                result, deck_path, output_path = run(
                    doublet_deck(
                        title=stem,
                        total_length_ft=length,
                        geometry=geometry,
                        frequency_mhz=frequency / 1e6,
                        radius_m=RADIUS_M,
                        conductivity_s_m=WIRE_CONDUCTIVITY,
                        epsilon_r=13.0,
                        ground_conductivity_s_m=0.005,
                    ),
                    work,
                    stem,
                    executable,
                )
                deck_path.unlink()
                output_path.unlink()
                cache[key] = result
            return cache[key]

        scan = np.arange(estimate * 0.75, estimate * 1.25 + 0.25, 0.5)
        values = [(float(length), evaluate(float(length))) for length in scan]
        brackets = [
            (a[0], b[0])
            for a, b in zip(values, values[1:], strict=False)
            if a[1].impedance_ohm.imag * b[1].impedance_ohm.imag <= 0
        ]
        if brackets:
            bracket = min(brackets, key=lambda pair: abs(sum(pair) / 2 - estimate))
            length = brentq(
                lambda value: evaluate(value).impedance_ohm.imag,
                *bracket,
                xtol=0.005,
            )
            result = evaluate(length)
        else:
            length, result = min(
                values, key=lambda pair: abs(pair[1].impedance_ohm.imag)
            )
        _, end_height = geometry.endpoints(float(length))
        rows.append(
            {
                "band": band,
                "frequency_hz": frequency,
                "kh1_priority_band": kh1_required,
                "geometry": geometry_id,
                "center_height_ft": geometry.center_height_ft,
                "end_height_ft": end_height,
                "included_angle_deg": geometry.included_angle_deg(float(length)),
                "resonant_total_length_ft": float(length),
                "resistance_ohm": result.impedance_ohm.real,
                "reactance_ohm": result.impedance_ohm.imag,
                "raw_swr": float(swr(result.impedance_ohm)),
                "nec_efficiency": result.efficiency,
            }
        )
    return rows

def _selected_patterns(selections, direct_summary, linked, executable, work, raw_dir):
    rows = []
    cases = []
    for name in ("current_58_28", "classic_44_28", "robust_model_best"):
        row = selections[name]
        cases.append(
            ("doublet", name, row["radiator_ft"], None, GEOMETRIES["pulaski_30_10"])
        )
    direct_best = direct_summary[0]
    for row in (
        direct_best,
        next(item for item in direct_summary if item["candidate"] == "35r-17c"),
        next(item for item in direct_summary if item["candidate"] == "41r-17c"),
    ):
        cases.append(
            (
                "direct",
                row["candidate"],
                row["radiator_ft"],
                row["counterpoise_ft"],
                None,
            )
        )
    seen = set()
    linked_by_band = {row["band"]: row for row in linked}
    for kind, name, radiator, counterpoise, geometry in cases:
        for band, frequency, _ in EXTENDED_BANDS:
            if (kind, radiator, counterpoise, band) in seen:
                continue
            seen.add((kind, radiator, counterpoise, band))
            stem = f"pattern-{kind}-{radiator}-{counterpoise}-{band}".replace(".", "p")
            if kind == "doublet":
                deck = doublet_deck(
                    title=stem,
                    total_length_ft=radiator,
                    geometry=geometry,
                    frequency_mhz=frequency / 1e6,
                    radius_m=RADIUS_M,
                    conductivity_s_m=WIRE_CONDUCTIVITY,
                    epsilon_r=13.0,
                    ground_conductivity_s_m=0.005,
                    pattern=True,
                )
            else:
                feed, support, cp_height, cp_azimuth = DIRECT_DEPLOYMENTS[
                    "table_collinear_30"
                ]
                deck = direct_wire_deck(
                    title=stem,
                    radiator_ft=radiator,
                    counterpoise_ft=counterpoise,
                    feed_height_ft=feed,
                    support_height_ft=support,
                    counterpoise_height_ft=cp_height,
                    counterpoise_azimuth_deg=cp_azimuth,
                    frequency_mhz=frequency / 1e6,
                    radius_m=RADIUS_M,
                    conductivity_s_m=WIRE_CONDUCTIVITY,
                    epsilon_r=13.0,
                    ground_conductivity_s_m=0.005,
                    pattern=True,
                )
            result, deck_path, output_path = run(deck, work, stem, executable)
            shutil.copy2(deck_path, raw_dir / deck_path.name)
            shutil.copy2(output_path, raw_dir / output_path.name)
            gains = np.asarray([point[2] for point in result.pattern])
            elevations = np.asarray([point[0] for point in result.pattern])
            rows.append(
                {
                    "antenna_type": kind,
                    "selection": name,
                    "band": band,
                    "frequency_hz": frequency,
                    "maximum_gain_dbi": float(np.max(gains)),
                    "maximum_gain_0_30deg_dbi": float(
                        np.max(gains[(elevations >= 0) & (elevations <= 30)])
                    ),
                    "maximum_gain_60_90deg_dbi": float(
                        np.max(gains[(elevations >= 60) & (elevations <= 90)])
                    ),
                    "nec_efficiency": result.efficiency,
                }
            )
    for band, frequency, _ in EXTENDED_BANDS:
        length = linked_by_band[band]["resonant_total_length_ft"]
        _, linked_geometry = _linked_geometry(band)
        stem = f"pattern-linked-{band}"
        result, deck_path, output_path = run(
            doublet_deck(
                title=stem,
                total_length_ft=length,
                geometry=linked_geometry,
                frequency_mhz=frequency / 1e6,
                radius_m=RADIUS_M,
                conductivity_s_m=WIRE_CONDUCTIVITY,
                epsilon_r=13.0,
                ground_conductivity_s_m=0.005,
                pattern=True,
            ),
            work,
            stem,
            executable,
        )
        shutil.copy2(deck_path, raw_dir / deck_path.name)
        shutil.copy2(output_path, raw_dir / output_path.name)
        gains = np.asarray([point[2] for point in result.pattern])
        elevations = np.asarray([point[0] for point in result.pattern])
        rows.append(
            {
                "antenna_type": "linked_reference",
                "selection": "resonant",
                "band": band,
                "frequency_hz": frequency,
                "maximum_gain_dbi": float(np.max(gains)),
                "maximum_gain_0_30deg_dbi": float(
                    np.max(gains[(elevations >= 0) & (elevations <= 30)])
                ),
                "maximum_gain_60_90deg_dbi": float(
                    np.max(gains[(elevations >= 60) & (elevations <= 90)])
                ),
                "nec_efficiency": result.efficiency,
            }
        )
    return rows


def _anchor(measured, nec_base, nec_candidate, z0, method):
    if method == "impedance_delta":
        return measured + nec_candidate - nec_base
    gm = (measured - z0) / (measured + z0)
    gb = (nec_base - z0) / (nec_base + z0)
    gc = (nec_candidate - z0) / (nec_candidate + z0)
    displacement = (gc - gb) / (1 - np.conj(gb) * gc)
    translated = (gm + displacement) / (1 + np.conj(gm) * displacement)
    magnitude = np.abs(translated)
    translated = np.where(
        magnitude >= 0.999999, translated / magnitude * 0.999999, translated
    )
    return z0 * (1 + translated) / (1 - translated)


def _kh1_tuner_proxy(
    impedance_ohm,
    frequency_hz,
    *,
    lmax_uH: float,
    cmax_pF: float,
    bypass_swr: float = TUNER_BYPASS_SWR,
):
    """Ideal series-L/shunt-C proxy with the capacitor on either side.

    The limits are explicit sensitivity assumptions. They are not published KH1
    component values. Stress <= 1 means an ideal continuous solution lies inside
    the selected effective L/C envelope.
    """
    if lmax_uH <= 0 or cmax_pF <= 0:
        raise ValueError("Tuner limits must be positive")
    z, frequency = np.broadcast_arrays(
        np.asarray(impedance_ohm, dtype=complex),
        np.asarray(frequency_hz, dtype=float),
    )
    omega = 2.0 * math.pi * frequency
    r = z.real
    x = z.imag
    rs = 50.0
    best = np.full(z.shape, np.inf, dtype=float)
    best_l = np.full(z.shape, np.nan, dtype=float)
    best_c = np.full(z.shape, np.nan, dtype=float)
    best_topology = np.full(z.shape, -1, dtype=int)
    passive = (r > 0) & np.isfinite(r) & np.isfinite(x) & (frequency > 0)

    # Load -> series L -> source-side shunt C.
    discriminant = rs * r - r * r
    valid = passive & (discriminant >= -1e-10)
    total_x = np.sqrt(np.maximum(discriminant, 0.0))
    series_x = total_x - x
    shunt_b = np.divide(
        total_x,
        rs * r,
        out=np.zeros_like(total_x),
        where=r != 0,
    )
    l_uh = series_x / omega * 1e6
    c_pf = shunt_b / omega * 1e12
    stress = np.maximum(l_uh / lmax_uH, c_pf / cmax_pF)
    update = valid & (l_uh >= 0) & (c_pf >= 0) & (stress < best)
    best[update] = stress[update]
    best_l[update] = l_uh[update]
    best_c[update] = c_pf[update]
    best_topology[update] = 0

    # Load-side shunt C -> series L -> source.
    admittance = np.divide(
        1.0,
        z,
        out=np.full_like(z, np.nan + 1j * np.nan),
        where=z != 0,
    )
    g = admittance.real
    b_load = admittance.imag
    discriminant = g / rs - g * g
    valid = passive & (g > 0) & (discriminant >= -1e-10)
    total_b = np.sqrt(np.maximum(discriminant, 0.0))
    denominator = g + 1j * total_b
    after_shunt = np.divide(
        1.0,
        denominator,
        out=np.full_like(z, np.nan + 1j * np.nan),
        where=denominator != 0,
    )
    series_x = -after_shunt.imag
    shunt_b = total_b - b_load
    l_uh = series_x / omega * 1e6
    c_pf = shunt_b / omega * 1e12
    stress = np.maximum(l_uh / lmax_uH, c_pf / cmax_pF)
    update = valid & (l_uh >= 0) & (c_pf >= 0) & (stress < best)
    best[update] = stress[update]
    best_l[update] = l_uh[update]
    best_c[update] = c_pf[update]
    best_topology[update] = 1

    raw_swr = swr(z)
    bypass_stress = raw_swr / bypass_swr
    update = passive & (raw_swr <= bypass_swr) & (bypass_stress < best)
    best[update] = bypass_stress[update]
    best_l[update] = 0.0
    best_c[update] = 0.0
    best_topology[update] = 2

    if best.shape == ():
        return (
            float(best),
            float(best_l),
            float(best_c),
            int(best_topology),
        )
    return best, best_l, best_c, best_topology


def _tuner_stress_matrix(impedance_ohm, frequencies_hz) -> np.ndarray:
    return np.asarray(
        [
            _kh1_tuner_proxy(
                impedance_ohm,
                frequencies_hz,
                lmax_uH=limits["lmax_uH"],
                cmax_pF=limits["cmax_pF"],
            )[0]
            for limits in TUNER_ENVELOPES.values()
        ]
    )


def _baseline_tuner_rows(measured: np.ndarray) -> list[dict[str, Any]]:
    rows = []
    for impedance, (band, frequency, _) in zip(measured, BANDS, strict=True):
        row = {
            "band": band,
            "frequency_hz": frequency,
            "resistance_ohm": float(impedance.real),
            "reactance_ohm": float(impedance.imag),
            "raw_swr": float(swr(impedance)),
            "observed_kh1_outcome": (
                "success" if band in {"40m", "30m", "15m"} else
                "failure" if band in {"20m", "17m"} else "not_scored"
            ),
        }
        for envelope_id, limits in TUNER_ENVELOPES.items():
            stress, l_uh, c_pf, topology = _kh1_tuner_proxy(
                impedance,
                frequency,
                lmax_uH=limits["lmax_uH"],
                cmax_pF=limits["cmax_pF"],
            )
            row[f"{envelope_id}_tuner_stress"] = float(stress)
            row[f"{envelope_id}_compatible"] = bool(stress <= 1.0)
            if envelope_id == "central":
                row["central_l_uH"] = float(l_uh)
                row["central_c_pF"] = float(c_pf)
                row["central_topology"] = TUNER_TOPOLOGY_NAMES[int(topology)]
        rows.append(row)
    scored = [row for row in rows if row["observed_kh1_outcome"] != "not_scored"]
    for row in scored:
        predicted = row["central_compatible"]
        observed = row["observed_kh1_outcome"] == "success"
        if predicted != observed:
            raise RuntimeError("Central empirical tuner envelope does not reproduce baseline")
    return rows


def _extension_window(grid: list[dict[str, Any]]) -> dict[str, float] | None:
    compatible = sorted(
        [
            row
            for row in grid
            if row["radiator_ft"] == 58.0
            and row["all_required_compatibility_fraction"] >= 0.95
            and row["minimum_required_band_compatibility_fraction"] >= 0.95
        ],
        key=lambda row: row["feedline_ft"],
    )
    if not compatible:
        return None
    return {
        "minimum_feedline_ft": compatible[0]["feedline_ft"],
        "maximum_feedline_ft": compatible[-1]["feedline_ft"],
        "minimum_extension_ft": compatible[0]["feedline_ft"] - 28.0,
        "maximum_extension_ft": compatible[-1]["feedline_ft"] - 28.0,
        "candidate_count": len(compatible),
    }


def _minimum_q(z):
    z = np.asarray(z, dtype=complex)
    r = z.real
    x = z.imag
    rs = 50.0
    best = np.full(z.shape, np.inf)
    passive = r > 0
    disc = rs * r - r * r
    valid = passive & (disc >= -1e-10)
    root = np.sqrt(np.maximum(disc, 0))
    for total_x in (root, -root):
        q = np.maximum(np.abs(total_x - x) / r, np.abs(total_x) / r)
        best = np.where(valid, np.minimum(best, q), best)
    y = np.divide(1, z, out=np.full_like(z, np.nan + 1j * np.nan), where=z != 0)
    g = y.real
    b = y.imag
    disc = g / rs - g * g
    valid = passive & (g > 0) & (disc >= -1e-10)
    root = np.sqrt(np.maximum(disc, 0))
    for total_b in (root, -root):
        after = 1 / (g + 1j * total_b)
        series_x = -after.imag
        shunt_b = total_b - b
        q = np.maximum(np.abs(series_x) / rs, np.abs(after) ** 2 * np.abs(shunt_b) / rs)
        best = np.where(valid, np.minimum(best, q), best)
    return best



def _rank_doublet(row):
    return (
        -row["all_required_compatibility_fraction"],
        -row["minimum_required_band_compatibility_fraction"],
        row["required_max_tuner_stress_p90"],
        row["required_max_q_p90"],
        -row["required_worst_line_efficiency_p10"],
        row["total_wire_ft"],
    )


def _named(rows, name):
    return next(row for row in rows if row["selection"] == name)


def _summary(
    solver,
    baseline_tuner,
    extension_window,
    nec_runs,
    line_count,
    selections,
    direct,
    direct_by_band,
    linked,
):
    current = selections["current_58_28"]
    classic = selections["classic_44_28"]
    classic_opt = selections["44ft_optimized_line"]
    best = selections["robust_model_best"]
    plus3 = selections["current_plus_3ft_line"]
    preferred_35 = next(row for row in direct if row["candidate"] == "35r-17c")
    preferred_41 = next(row for row in direct if row["candidate"] == "41r-17c")
    direct_best = direct[0]
    direct_41_by_band = [
        row for row in direct_by_band if row["candidate"] == "41r-17c"
    ]
    if extension_window is None:
        existing_test = (
            f"reversibly test the model-best {best['feedline_ft']:.2f} ft line "
            "without cutting the 58 ft radiator"
        )
    else:
        existing_test = (
            "test detachable balanced-line extensions from "
            f"{extension_window['minimum_extension_ft']:.2f} to "
            f"{extension_window['maximum_extension_ft']:.2f} ft"
        )
    return {
        "solver": solver,
        "method": (
            "actual NEC-2 radiator/direct-wire runs with measured 58/28 "
            "radio-end anchoring and an explicit series-L/shunt-C tuner envelope"
        ),
        "anchored_doublet_bands": [band for band, _, _ in BANDS],
        "extended_nec_bands": [band for band, _, _ in EXTENDED_BANDS],
        "kh1_priority_bands": list(KH1_REQUIRED_BANDS),
        "nec_feedpoint_run_count": nec_runs,
        "line_scenario_count": line_count,
        "tuner_envelopes": TUNER_ENVELOPES,
        "tuner_bypass_swr": TUNER_BYPASS_SWR,
        "baseline_tuner_diagnostics": baseline_tuner,
        "doublet": {
            "current_58_28": current,
            "classic_44_28": classic,
            "classic_44_optimized_line": classic_opt,
            "current_plus_3ft_line": plus3,
            "robust_model_best": best,
            "58ft_extension_window": extension_window,
        },
        "direct_wire": {
            "field_evidence_35_17": preferred_35,
            "model_led_41_17": preferred_41,
            "model_best": direct_best,
            "41_17_by_band": direct_41_by_band,
        },
        "linked_dipole_reference": linked,
        "practical_recommendation": {
            "existing_antenna_test": existing_test,
            "new_antenna_test": (
                "build a direct-fed 41 ft radiator / 17 ft explicit counterpoise "
                "trial; retain 35/17 as the shorter field-evidence control"
            ),
            "efficiency_reference": "resonant linked dipoles on every modeled band",
            "field_validation_required": True,
        },
        "warnings": [
            "NEC geometry omits trees, operator, choke, connectors, insulation and sparse spacers.",
            "Doublet station impedances are measured-reference-plane anchored only on 40 through 10 m; 80, 60 and 6 m doublet rows are radiator-only NEC results.",
            "The tuner envelopes are empirical sensitivity cases, not published KH1 component values.",
            "The 80, 60, 12, 10 and 6 m direct-wire matchability columns use a generic topology proxy until tuner-specific loss models are applied.",
            "Line efficiency excludes tuner/choke/common-mode/radiator loss; direct-wire NEC efficiency includes modeled wire and ground loss only.",
        ],
    }

def _report(summary):
    d = summary["doublet"]
    direct = summary["direct_wire"]
    candidates = [
        ("current 58/28", d["current_58_28"]),
        ("classic 44/28", d["classic_44_28"]),
        ("44 ft optimized line", d["classic_44_optimized_line"]),
        ("58 ft + 3 ft line", d["current_plus_3ft_line"]),
        ("robust model best", d["robust_model_best"]),
    ]
    lines = [
        "# KH1/KX2 portable antenna NEC-2 study",
        "",
        f"Solver: `{summary['solver']}`",
        "",
        "## Modeled band scope",
        "",
        "The measured-reference-plane doublet optimization remains anchored on "
        + ", ".join(summary["anchored_doublet_bands"])
        + ". Direct-fed wires, radiator-only doublet NEC rows, patterns, and resonant references now cover "
        + ", ".join(summary["extended_nec_bands"])
        + ".",
        "",
        "The hard KH1 objective remains "
        + ", ".join(summary["kh1_priority_bands"])
        + ". The other bands are exploratory and do not affect candidate ranking. Six meters is included for KX3/external-tuner investigation; the KH1 and KX2 do not transmit there.",
        "",
        "## Method",
        "",
        "The radiator and direct-wire impedance, loss, and pattern calculations in this result set were executed by NEC-2. The measured 58 ft / 28 ft radio-end impedances remain exact anchors because a bare-wire NEC deck cannot reproduce the installed insulation, trees, choke, connectors, and operator. NEC supplies the physical impedance change as radiator length/deployment changes; a lossy balanced-line ensemble carries that result to the radio.",
        "",
        "Matchability uses the Elecraft-style topology class—series inductance and shunt capacitance, with the capacitor allowed on either side—not an unrestricted ideal L-network. Because the KH1 component range is unpublished, three explicit effective envelopes are evaluated: 8 uH/325 pF, 12 uH/400 pF, and 15 uH/500 pF. All reproduce the observed 58/28 success/failure split. These are sensitivity cases, not KH1 specifications, and this stage does not calculate tuner loss.",
        "",
        "## Measured-baseline tuner diagnostics",
        "",
        "| band | measured R+jX | observed | central ideal elements | topology |",
        "|---|---:|---:|---:|---|",
    ]
    for row in summary["baseline_tuner_diagnostics"]:
        lines.append(
            f"| {row['band']} | {row['resistance_ohm']:.1f} {row['reactance_ohm']:+.1f}j | {row['observed_kh1_outcome']} | {row['central_l_uH']:.2f} uH / {row['central_c_pF']:.1f} pF | {row['central_topology']} |"
        )
    lines += [
        "",
        "## Doublets",
        "",
        "| case | radiator | line | all 40/30/20/17/15 | weakest band | tuner stress p90 | Q p90 | worst line eff p10 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in candidates:
        lines.append(
            f"| {name} | {row['radiator_ft']:.1f} ft | {row['feedline_ft']:.2f} ft | {row['all_required_compatibility_fraction'] * 100:.1f}% | {row['minimum_required_band_compatibility_fraction'] * 100:.1f}% | {row['required_max_tuner_stress_p90']:.2f} | {row['required_max_q_p90']:.2f} | {row['required_worst_line_efficiency_p10'] * 100:.1f}% |"
        )
    window = d["58ft_extension_window"]
    if window is not None:
        lines += [
            "",
            "For the unchanged 58 ft radiator, the >=95% all-band ensemble window is "
            f"{window['minimum_feedline_ft']:.2f}-{window['maximum_feedline_ft']:.2f} ft of line, or detachable additions of {window['minimum_extension_ft']:.2f}-{window['maximum_extension_ft']:.2f} ft to the present 28 ft line.",
        ]
    lines += [
        "",
        "The percentages are fractions of the explicit NEC geometry, line, anchoring, reference-plane, and tuner-envelope ensemble. They are not tune probabilities. The newly added 80, 60, and 6 m doublet feedpoint rows are not fed into this anchored optimization because no measured station-end anchor exists on those bands.",
        "",
        "## Direct-fed wires: KH1 priority bands",
        "",
        "| case | wire | all five bands | weakest band | tuner stress p90 | Q p90 | worst NEC efficiency p10 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    shown = []
    for row in (
        direct["field_evidence_35_17"],
        direct["model_led_41_17"],
        direct["model_best"],
    ):
        if row["candidate"] in shown:
            continue
        shown.append(row["candidate"])
        lines.append(
            f"| {row['candidate']} | {row['radiator_ft']:.0f}/{row['counterpoise_ft']:.0f} ft | {row['all_required_compatibility_fraction'] * 100:.1f}% | {row['minimum_required_band_compatibility_fraction'] * 100:.1f}% | {row['required_max_tuner_stress_p90']:.2f} | {row['required_max_q_p90']:.2f} | {row['required_worst_nec_efficiency_p10'] * 100:.1f}% |"
        )
    lines += [
        "",
        "Direct-wire results span six counterpoise orientations/heights, two grounds, two conductor cases, and three generic tuner envelopes. They remain more deployment-sensitive than a balanced antenna.",
        "",
        "## 41 ft radiator / 17 ft counterpoise by band",
        "",
        "| band | median R+jX | median raw SWR | generic proxy compatibility | NEC efficiency p10 / p50 |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in direct["41_17_by_band"]:
        lines.append(
            f"| {row['band']} | {row['resistance_p50']:.1f} {row['reactance_p50']:+.1f}j | {row['raw_swr_p50']:.1f} | {row['generic_tuner_proxy_compatibility_fraction'] * 100:.1f}% | {row['nec_efficiency_p10'] * 100:.1f}% / {row['nec_efficiency_p50'] * 100:.1f}% |"
        )
    lines += [
        "",
        "For 80, 60, 12, 10, and 6 m, the compatibility column is only the same generic series-L/shunt-C sensitivity proxy used for the KH1 study. It is not yet a prediction for a particular KX2, KX3, LDG, or manual tuner. The NEC efficiency column is the modeled wire-plus-ground radiation efficiency after power reaches the feedpoint; it excludes tuner loss.",
        "",
        "## Resonant linked-dipole reference",
        "",
        "| band | geometry | total length | R+jX | raw SWR | NEC efficiency |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summary["linked_dipole_reference"]:
        lines.append(
            f"| {row['band']} | {row['geometry']} | {row['resonant_total_length_ft']:.2f} ft | {row['resistance_ohm']:.1f} {row['reactance_ohm']:+.1f}j | {row['raw_swr']:.2f} | {row['nec_efficiency'] * 100:.1f}% |"
        )
    recommendation = summary["practical_recommendation"]
    lines += [
        "",
        "## Practical conclusion",
        "",
        f"1. Existing antenna: **{recommendation['existing_antenna_test']}**.",
        f"2. Separate compact antenna: **{recommendation['new_antenna_test']}**.",
        f"3. Efficiency/matching reference: **{recommendation['efficiency_reference']}**.",
        "",
        "The classic 44/28 doublet is not the preferred build from this study: the 20 and 17 m station-end loads remain hostile across the uncertainty ensemble, and its modeled mismatched-line efficiency tails are poor.",
        "",
        "Measure radio-end R+jX and final tuner state on each intended band before cutting the existing antenna. The next study stage applies component-loss models for the actual tuners.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "sudo apt-get install nec2c",
        "uv sync --no-editable --extra plots --group dev",
        "uv run antenna-lab run-kh1-nec-study --output build/kh1-portable-nec-v2",
        "uv run antenna-lab verify-results build/kh1-portable-nec-v2",
        "```",
        "",
        "## Limitations",
        "",
    ]
    lines += [f"- {warning}" for warning in summary["warnings"]]
    return "\n".join(lines) + "\n"

def _version(executable):
    completed = subprocess.run(
        [str(executable), "-v"], capture_output=True, text=True, check=False
    )
    return (completed.stdout or completed.stderr).strip()


def _quantile(values, q):
    return float(np.quantile(np.asarray(values), q)) if values else math.nan


def _nanquantile(values, q):
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    return float(np.quantile(array, q)) if len(array) else math.nan


def _write_csv(path, rows):
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path):
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _manifest(directory):
    paths = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (directory / "SHA256SUMS").write_text(
        "".join(
            f"{_sha256(path)}  {path.relative_to(directory).as_posix()}\n"
            for path in paths
        ),
        encoding="utf-8",
    )
