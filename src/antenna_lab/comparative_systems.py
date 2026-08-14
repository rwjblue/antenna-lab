"""Put balanced doublets and the resonant reference on the portable-system metric."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from antenna_lab.atu import LOSS_ENVELOPES, PROFILES, solve_switched_l_network
from antenna_lab.kh1_nec import (
    BANDS,
    GEOMETRIES,
    _anchor,
    _line_scenarios,
    _rank_doublet,
)
from antenna_lab.measurements import load_impedance_measurements
from antenna_lab.portable_systems import (
    KH1_PROFILE_IDS,
    OBJECTIVES,
    SystemCandidate,
    _aggregate_systems,
    _write_csv,
)
from antenna_lab.transmission_line import input_impedance, line_efficiency

REQUIRED_BANDS = ("40m", "30m", "20m", "17m", "15m")


def select_doublet_shortlist(grid_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select generic-screen leaders plus wire-budget and physical baselines."""

    ranked = sorted(grid_rows, key=_rank_doublet)
    selected: dict[tuple[float, float], dict[str, Any]] = {}

    def add(row: dict[str, Any]) -> None:
        selected[(row["radiator_ft"], row["feedline_ft"])] = row

    for row in ranked[:8]:
        add(row)
    for dimensions in ((58.0, 28.0), (44.0, 28.0), (57.0, 28.0)):
        add(next(row for row in grid_rows if _dimensions(row) == dimensions))
    add(
        min((row for row in grid_rows if row["radiator_ft"] == 44.0), key=_rank_doublet)
    )
    for budget in (80.0, 90.0, 100.0, 110.0, 120.0):
        eligible = [row for row in grid_rows if row["total_wire_ft"] <= budget]
        if eligible:
            add(min(eligible, key=_rank_doublet))
    return sorted(
        selected.values(), key=lambda row: (row["total_wire_ft"], _rank_doublet(row))
    )


def run_comparative_study(
    nec_artifact_dir: Path,
    portable_study_dir: Path,
    output_dir: Path,
    *,
    measurement_path: Path = Path("data/measured/58ft_doublet_2026-08-08.csv"),
) -> dict[str, Any]:
    """Evaluate selected doublets/reference and merge portable aggregate results."""

    nec_data = nec_artifact_dir / "data"
    grid = _read_typed_csv(nec_data / "doublet_candidates.csv")
    feedpoints = _read_typed_csv(nec_data / "doublet_nec_feedpoints.csv")
    linked = _read_typed_csv(nec_data / "linked_dipole_reference.csv")
    shortlist = select_doublet_shortlist(grid)

    doublet_systems = tuple(_doublet_system(row) for row in shortlist)
    doublet_rows = _evaluate_doublets(
        doublet_systems,
        feedpoints,
        measurement_path,
    )
    reference_system = _reference_system(linked)
    reference_rows = _evaluate_reference(reference_system, linked)
    comparison_aggregates = _aggregate_systems(
        doublet_systems + (reference_system,),
        doublet_rows + reference_rows,
    )
    portable_aggregates = _read_typed_csv(portable_study_dir / "system_candidates.csv")
    all_aggregates = sorted(
        portable_aggregates + comparison_aggregates,
        key=lambda row: (
            _objective_index(row["objective"]),
            -row["worst_band_final_efficiency_p10"],
            -row["worst_band_final_efficiency_p50"],
            -row["median_final_efficiency"],
            row["total_wire_ft"],
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "doublet_band_scenarios.csv", doublet_rows)
    _write_csv(output_dir / "linked_reference_band_scenarios.csv", reference_rows)
    _write_csv(output_dir / "candidate_aggregates.csv", all_aggregates)
    _write_csv(output_dir / "doublet_shortlist.csv", shortlist)
    summary = {
        "study_id": "kh1-portable-comparative-v1",
        "portable_study_id": json.loads(
            (portable_study_dir / "summary.json").read_text(encoding="utf-8")
        )["study_id"],
        "doublet_shortlist_count": len(doublet_systems),
        "doublet_scenario_band_row_count": len(doublet_rows),
        "linked_reference_scenario_band_row_count": len(reference_rows),
        "candidate_aggregate_count": len(all_aggregates),
        "ranking_by_objective": {
            label: [row for row in all_aggregates if row["objective"] == label][:20]
            for label, _, _ in OBJECTIVES
        },
        "warnings": [
            "Doublet loads are anchored to one measured 58/28-foot deployment and displaced with NEC; this is not a direct measurement of every candidate.",
            "Scenario dimensions and loss envelopes are equal-weight sensitivities, not probability distributions.",
            "The linked-dipole reference uses independently resonated NEC elements as an efficiency ceiling for a field-linked implementation.",
            "KHATU1 component banks are inferred sensitivity profiles, not Elecraft-published values.",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def _doublet_system(row: dict[str, Any]) -> SystemCandidate:
    radiator = row["radiator_ft"]
    feedline = row["feedline_ft"]
    identifier = f"doublet-{radiator:g}r-{feedline:g}l"
    return SystemCandidate(
        id=identifier,
        design_id=identifier,
        family="balanced_doublet",
        transformer_ratio=1.0,
        choke_required=True,
        total_wire_ft=radiator + 2.0 * feedline,
        component_count=1,
        support_count=1,
        band_changes_touch_antenna=False,
        packed_complexity="medium",
    )


def _reference_system(linked: list[dict[str, Any]]) -> SystemCandidate:
    required = [row for row in linked if row["band"] in REQUIRED_BANDS]
    longest = max(row["resonant_total_length_ft"] for row in required)
    return SystemCandidate(
        id="linked-dipole-five-band",
        design_id="linked-dipole-five-band",
        family="linked_dipole_reference",
        transformer_ratio=1.0,
        choke_required=False,
        total_wire_ft=longest,
        component_count=2 * (len(required) - 1),
        support_count=1,
        band_changes_touch_antenna=True,
        packed_complexity="medium",
    )


def _evaluate_doublets(
    systems: tuple[SystemCandidate, ...],
    feedpoints: list[dict[str, Any]],
    measurement_path: Path,
) -> list[dict[str, Any]]:
    measurements = load_impedance_measurements(measurement_path)
    measured_by_band = {row.band: row.impedance_ohm for row in measurements}
    measured = np.asarray([measured_by_band[band] for band, _, _ in BANDS])
    line_scenarios = _line_scenarios(measured)
    impedance_lookup = {
        (row["geometry"], row["radiator_ft"], row["band"]): complex(
            row["resistance_ohm"], row["reactance_ohm"]
        )
        for row in feedpoints
    }
    efficiency_lookup = {
        (row["geometry"], row["radiator_ft"], row["band"]): row["nec_efficiency"]
        for row in feedpoints
    }
    rows: list[dict[str, Any]] = []
    for system in systems:
        radiator, feedline = _system_dimensions(system)
        for geometry_id in GEOMETRIES:
            baseline = np.asarray(
                [impedance_lookup[(geometry_id, 58.0, band)] for band, _, _ in BANDS]
            )
            candidate = np.asarray(
                [
                    impedance_lookup[(geometry_id, radiator, band)]
                    for band, _, _ in BANDS
                ]
            )
            for metadata, line, coax, coax_ft, baseline_load in line_scenarios:
                for anchor_method in ("impedance_delta", "smith_displacement"):
                    antenna_loads = _anchor(
                        baseline_load,
                        baseline,
                        candidate,
                        line.characteristic_impedance_ohm,
                        anchor_method,
                    )
                    for band_index, (band, frequency_hz, _) in enumerate(BANDS):
                        if band not in REQUIRED_BANDS:
                            continue
                        antenna_load = antenna_loads[band_index]
                        if antenna_load.real > 0 and np.isfinite(antenna_load):
                            radio_load = input_impedance(
                                antenna_load, frequency_hz, feedline, line
                            )
                            feedline_efficiency = line_efficiency(
                                antenna_load, frequency_hz, feedline, line
                            )
                            if coax_ft:
                                feedline_efficiency *= line_efficiency(
                                    radio_load, frequency_hz, coax_ft, coax
                                )
                                radio_load = input_impedance(
                                    radio_load, frequency_hz, coax_ft, coax
                                )
                        else:
                            radio_load = antenna_load
                            feedline_efficiency = 0.0
                        nec_efficiency = efficiency_lookup[
                            (geometry_id, radiator, band)
                        ]
                        antenna_scenario = (
                            f"{geometry_id}|{metadata['id']}|{anchor_method}"
                        )
                        rows.extend(
                            _tuner_rows(
                                system,
                                band,
                                frequency_hz,
                                radio_load,
                                nec_efficiency,
                                feedline_efficiency,
                                (0.1, 0.2, 0.5),
                                antenna_scenario,
                                {
                                    "antenna_resistance_ohm": antenna_load.real,
                                    "antenna_reactance_ohm": antenna_load.imag,
                                    "line_scenario": metadata["id"],
                                    "anchor_method": anchor_method,
                                    "geometry": geometry_id,
                                },
                            )
                        )
    return rows


def _evaluate_reference(
    system: SystemCandidate, linked: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for antenna in linked:
        if antenna["band"] not in REQUIRED_BANDS:
            continue
        load = complex(antenna["resistance_ohm"], antenna["reactance_ohm"])
        rows.extend(
            _tuner_rows(
                system,
                antenna["band"],
                antenna["frequency_hz"],
                load,
                antenna["nec_efficiency"],
                1.0,
                (0.0,),
                antenna["geometry"],
                {
                    "antenna_resistance_ohm": load.real,
                    "antenna_reactance_ohm": load.imag,
                    "line_scenario": "none",
                    "anchor_method": "direct_nec",
                    "geometry": antenna["geometry"],
                },
            )
        )
    return rows


def _tuner_rows(
    system: SystemCandidate,
    band: str,
    frequency_hz: float,
    tuner_load: complex,
    nec_efficiency: float,
    feedline_efficiency: float,
    choke_losses_db: tuple[float, ...],
    antenna_scenario: str,
    detail: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    passive = (
        tuner_load.real > 0
        and np.isfinite(tuner_load)
        and 0 < nec_efficiency <= 1
        and 0 < feedline_efficiency <= 1
    )
    for profile_id in KH1_PROFILE_IDS:
        for loss in LOSS_ENVELOPES:
            for component_envelope, choke_db in enumerate(choke_losses_db):
                downstream_efficiency = feedline_efficiency * 10 ** (-choke_db / 10.0)
                for label, objective, target_swr in OBJECTIVES:
                    solution = (
                        solve_switched_l_network(
                            PROFILES[profile_id],
                            tuner_load,
                            frequency_hz,
                            loss,
                            objective=objective,
                            target_swr=target_swr,
                        )
                        if passive
                        else None
                    )
                    final = (
                        nec_efficiency
                        * downstream_efficiency
                        * solution.transducer_efficiency
                        if solution is not None
                        else 0.0
                    )
                    rows.append(
                        {
                            "candidate_id": system.id,
                            "design_id": system.design_id,
                            "family": system.family,
                            "band": band,
                            "frequency_hz": frequency_hz,
                            "antenna_scenario": antenna_scenario,
                            "deployment": detail["geometry"],
                            "ground": detail["line_scenario"],
                            "conductor": detail["anchor_method"],
                            "profile": profile_id,
                            "tuner_loss_envelope": loss.id,
                            "component_loss_envelope": component_envelope,
                            "objective": label,
                            "raw_resistance_ohm": tuner_load.real,
                            "raw_reactance_ohm": tuner_load.imag,
                            **detail,
                            "nec_efficiency": nec_efficiency,
                            "feedline_efficiency": feedline_efficiency,
                            "transformer_loss_db": 0.0,
                            "choke_loss_db": choke_db,
                            "input_swr": solution.input_swr if solution else 1e9,
                            "target_met": bool(
                                solution and solution.input_swr <= target_swr
                            ),
                            "likely_power_rollback": bool(
                                not solution or solution.input_swr > 2.5
                            ),
                            "topology": (
                                solution.topology
                                if solution
                                else "invalid_nonpassive_anchor"
                            ),
                            "l_mask": solution.l_mask if solution else -1,
                            "c_mask": solution.c_mask if solution else -1,
                            "inductance_uH": solution.inductance_uH
                            if solution
                            else 0.0,
                            "capacitance_pF": solution.capacitance_pF
                            if solution
                            else 0.0,
                            "residual_mismatch_efficiency": (
                                solution.accepted_power_w if solution else 0.0
                            ),
                            "tuner_efficiency": (
                                solution.tuner_efficiency if solution else 0.0
                            ),
                            "tuner_loss_db": (
                                solution.tuner_loss_db if solution else 999.0
                            ),
                            "final_efficiency": final,
                            "total_loss_db": (
                                -10.0 * math.log10(final) if final > 0 else 999.0
                            ),
                        }
                    )
    return rows


def _read_typed_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [{key: _coerce(value) for key, value in row.items()} for row in rows]


def _coerce(value: str) -> Any:
    if value == "True":
        return True
    if value == "False":
        return False
    try:
        number = float(value)
    except ValueError:
        return value
    return int(number) if number.is_integer() and "." not in value else number


def _dimensions(row: dict[str, Any]) -> tuple[float, float]:
    return float(row["radiator_ft"]), float(row["feedline_ft"])


def _system_dimensions(system: SystemCandidate) -> tuple[float, float]:
    values = system.id.removeprefix("doublet-").removesuffix("l").split("r-")
    return float(values[0]), float(values[1])


def _objective_index(label: str) -> int:
    return next(index for index, item in enumerate(OBJECTIVES) if item[0] == label)
