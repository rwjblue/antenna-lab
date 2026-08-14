"""Coarse multi-family KH1 system study using cached NEC loads."""

from __future__ import annotations

import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from antenna_lab.atu import LOSS_ENVELOPES, PROFILES, solve_switched_l_network
from antenna_lab.components import parallel_resonant_trap_impedance
from antenna_lab.nec import (
    InvertedV,
    asymmetric_inverted_v_deck,
    direct_wire_deck,
    fan_dipole_deck,
    loaded_inverted_v_deck,
    radial_vertical_deck,
    run_cached,
)

KH1_PROFILE_IDS = ("khatu1", "khatu1_wide_sensitivity")
OBJECTIVES = (
    ("best_swr", "best_swr", 1.5),
    ("lowest_loss_swr_1p5", "lowest_loss_under_target", 1.5),
    ("lowest_loss_swr_2p5", "lowest_loss_under_target", 2.5),
)


@dataclass(frozen=True)
class AntennaDesign:
    id: str
    family: str
    parameters: dict[str, Any]
    total_wire_ft: float
    component_count: int
    support_count: int
    band_changes_touch_antenna: bool
    packed_complexity: str


@dataclass(frozen=True)
class SystemCandidate:
    id: str
    design_id: str
    family: str
    transformer_ratio: float
    choke_required: bool
    total_wire_ft: float
    component_count: int
    support_count: int
    band_changes_touch_antenna: bool
    packed_complexity: str


def load_coarse_config(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {"study_id", "bands", "environment", "families"}
    if missing := required - set(value):
        raise ValueError(f"Missing coarse-study config keys: {sorted(missing)}")
    return value


def build_designs(config: dict[str, Any]) -> tuple[AntennaDesign, ...]:
    families = config["families"]
    designs: list[AntennaDesign] = []
    direct = families["direct_counterpoise"]
    for radiator in direct["radiator_ft"]:
        for counterpoise in direct["counterpoise_ft"]:
            designs.append(
                AntennaDesign(
                    f"direct-{radiator:g}r-{counterpoise:g}c",
                    "direct_counterpoise",
                    {"radiator_ft": radiator, "counterpoise_ft": counterpoise},
                    radiator + counterpoise,
                    0,
                    1,
                    False,
                    "low",
                )
            )
    for family in ("ocfd", "efhw"):
        specification = families[family]
        for length in specification["total_length_ft"]:
            for fraction in specification["feed_fraction"]:
                designs.append(
                    AntennaDesign(
                        f"{family}-{length:g}ft-f{fraction:g}",
                        family,
                        {"total_length_ft": length, "feed_fraction": fraction},
                        length,
                        1,
                        1,
                        False,
                        "medium",
                    )
                )
    vertical = families["radial_vertical"]
    for radiator in vertical["radiator_ft"]:
        for radial in vertical["radial_ft"]:
            for count in vertical["radial_count"]:
                designs.append(
                    AntennaDesign(
                        f"vertical-{radiator:g}r-{count}x{radial:g}",
                        "radial_vertical",
                        {
                            "radiator_ft": radiator,
                            "radial_ft": radial,
                            "radial_count": count,
                        },
                        radiator + radial * count,
                        0,
                        1,
                        False,
                        "medium" if count == 2 else "high",
                    )
                )
    fan_specification = families["fan_dipole"]
    if fan_specification.get("enabled", True):
        fan = fan_specification["total_lengths_ft"]
        designs.append(
            AntennaDesign(
                "fan-five-band",
                "fan_dipole",
                {"total_lengths_ft": fan},
                float(sum(fan)),
                0,
                1,
                False,
                "very_high",
            )
        )
    trap_specification = families["trap_loaded"]
    for trap in (
        trap_specification["designs"]
        if trap_specification.get("enabled", True)
        else ()
    ):
        designs.append(
            AntennaDesign(
                f"trap-{trap['id']}",
                "trap_loaded",
                trap,
                float(trap["total_length_ft"]),
                2 * len(trap["trap_positions_ft"]),
                1,
                False,
                "high",
            )
        )
    return tuple(designs)


def build_system_candidates(
    designs: tuple[AntennaDesign, ...], config: dict[str, Any]
) -> tuple[SystemCandidate, ...]:
    families = config["families"]
    systems = []
    for design in designs:
        ratios = families.get(design.family, {}).get("transformer_ratios", [1])
        for ratio in ratios:
            ratio = float(ratio)
            choke_required = (
                design.family in {"ocfd", "efhw", "fan_dipole", "trap_loaded"}
                or ratio != 1
            )
            systems.append(
                SystemCandidate(
                    id=f"{design.id}-z{ratio:g}",
                    design_id=design.id,
                    family=design.family,
                    transformer_ratio=ratio,
                    choke_required=choke_required,
                    total_wire_ft=design.total_wire_ft,
                    component_count=(
                        design.component_count + (ratio != 1) + choke_required
                    ),
                    support_count=design.support_count,
                    band_changes_touch_antenna=design.band_changes_touch_antenna,
                    packed_complexity=design.packed_complexity,
                )
            )
    return tuple(systems)


def run_coarse_system_study(
    config_path: Path,
    output_dir: Path,
    *,
    nec2c: str | Path | None = None,
    jobs: int = 6,
) -> dict[str, Any]:
    config = load_coarse_config(config_path)
    designs = build_designs(config)
    systems = build_system_candidates(designs, config)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "nec-cache"
    load_rows = _run_nec_loads(designs, config, cache_dir, nec2c, jobs)
    band_rows = _evaluate_systems(systems, load_rows, config)
    aggregates = _aggregate_systems(systems, band_rows)
    _write_csv(output_dir / "nec_loads.csv", load_rows)
    _write_csv(output_dir / "system_band_scenarios.csv", band_rows)
    _write_csv(output_dir / "system_candidates.csv", aggregates)
    summary = {
        "study_id": config["study_id"],
        "status": config.get(
            "study_status",
            "coarse central-environment screening; refine before conclusions",
        ),
        "physical_design_count": len(designs),
        "system_candidate_count": len(systems),
        "nec_load_count": len(load_rows),
        "scenario_band_row_count": len(band_rows),
        "ranking_by_objective": {
            label: [row for row in aggregates if row["objective"] == label][:20]
            for label, _, _ in OBJECTIVES
        },
        "warnings": config.get(
            "study_warnings",
            [
                "This coarse pass uses one copper/average-ground deployment per family.",
                "Transformer and choke loss are empirical dB envelopes, not equivalent-circuit fits.",
                "KHATU1 component banks are inferred sensitivity profiles, not published values.",
                "Design-envelope quantiles are equal-weight sensitivities, not probabilities.",
            ],
        ),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary


def _run_nec_loads(designs, config, cache_dir, nec2c, jobs):
    bands = config["bands"]
    cases = [
        (design, deployment_id, deployment, ground_id, ground, conductor_id, conductor, band, frequency)
        for design in designs
        for deployment_id, deployment in _deployments(config, design.family).items()
        for ground_id, ground in _grounds(config).items()
        for conductor_id, conductor in _conductors(config).items()
        for band, frequency in bands.items()
    ]
    rows = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(
                _nec_case,
                design,
                deployment_id,
                deployment,
                ground_id,
                ground,
                conductor_id,
                conductor,
                band,
                frequency,
                config,
                cache_dir,
                nec2c,
            ): (
                design.id,
                deployment_id,
                ground_id,
                conductor_id,
                band,
            )
            for (
                design,
                deployment_id,
                deployment,
                ground_id,
                ground,
                conductor_id,
                conductor,
                band,
                frequency,
            ) in cases
        }
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as error:
                raise RuntimeError(f"NEC failed for {futures[future]}") from error
    band_order = {band: index for index, band in enumerate(bands)}
    return sorted(
        rows,
        key=lambda row: (
            row["design_id"],
            row["deployment"],
            row["ground"],
            row["conductor"],
            band_order[row["band"]],
        ),
    )


def _nec_case(
    design,
    deployment_id,
    deployment,
    ground_id,
    ground,
    conductor_id,
    conductor,
    band,
    frequency_hz,
    config,
    cache_dir,
    nec2c,
):
    environment = config["environment"]
    common = {
        "title": f"{design.id}-{band}",
        "frequency_mhz": frequency_hz / 1e6,
        "radius_m": environment["wire_radius_m"],
        "conductivity_s_m": conductor,
        "epsilon_r": ground[0],
        "ground_conductivity_s_m": ground[1],
    }
    parameters = design.parameters
    if design.family == "direct_counterpoise":
        deck = direct_wire_deck(
            radiator_ft=parameters["radiator_ft"],
            counterpoise_ft=parameters["counterpoise_ft"],
            feed_height_ft=deployment["feed_height_ft"],
            support_height_ft=deployment["support_height_ft"],
            counterpoise_height_ft=deployment["counterpoise_height_ft"],
            counterpoise_azimuth_deg=deployment["counterpoise_azimuth_deg"],
            **common,
        )
    elif design.family in {"ocfd", "efhw"}:
        deck = asymmetric_inverted_v_deck(
            total_length_ft=parameters["total_length_ft"],
            feed_fraction=parameters["feed_fraction"],
            center_height_ft=deployment["center_height_ft"],
            apex_angle_deg=deployment["apex_angle_deg"],
            **common,
        )
    elif design.family == "radial_vertical":
        deck = radial_vertical_deck(
            radiator_ft=parameters["radiator_ft"],
            radial_ft=parameters["radial_ft"],
            radial_count=parameters["radial_count"],
            feed_height_ft=deployment["feed_height_ft"],
            radial_end_height_ft=deployment["radial_end_height_ft"],
            **common,
        )
    elif design.family == "fan_dipole":
        lengths = tuple(parameters["total_lengths_ft"])
        deck = fan_dipole_deck(
            total_lengths_ft=lengths,
            azimuths_deg=(-16.0, -8.0, 0.0, 8.0, 16.0),
            center_height_ft=deployment["center_height_ft"],
            apex_angle_deg=deployment["apex_angle_deg"],
            **common,
        )
    elif design.family == "trap_loaded":
        loads = []
        for position, resonance_mhz in zip(
            parameters["trap_positions_ft"],
            parameters["trap_resonances_mhz"],
            strict=True,
        ):
            inductance_h = 3.3e-6
            capacitance_f = 1.0 / (
                (2.0 * math.pi * resonance_mhz * 1e6) ** 2 * inductance_h
            )
            impedance = parallel_resonant_trap_impedance(
                inductance_h,
                capacitance_f,
                235.0,
                3000.0,
                frequency_hz,
            )
            loads.append((position, impedance))
        deck = loaded_inverted_v_deck(
            total_length_ft=parameters["total_length_ft"],
            loads_from_center_ft=tuple(loads),
            geometry=InvertedV(
                deployment["center_height_ft"],
                apex_angle_deg=deployment["apex_angle_deg"],
            ),
            **common,
        )
    else:
        raise ValueError(f"Unknown family: {design.family}")
    result, _, _, cache_hit = run_cached(deck, cache_dir, nec2c)
    if result.efficiency is None or not 0 < result.efficiency <= 1:
        raise ValueError(f"Non-passive NEC efficiency for {design.id}/{band}")
    return {
        "design_id": design.id,
        "family": design.family,
        "deployment": deployment_id,
        "ground": ground_id,
        "conductor": conductor_id,
        "band": band,
        "frequency_hz": frequency_hz,
        "resistance_ohm": result.impedance_ohm.real,
        "reactance_ohm": result.impedance_ohm.imag,
        "nec_efficiency": result.efficiency,
        "cache_hit": cache_hit,
    }


def _evaluate_systems(systems, load_rows, config):
    load_lookup: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in load_rows:
        load_lookup.setdefault((row["design_id"], row["band"]), []).append(row)
    transformer_losses = config["transformer_loss_db"]
    choke_losses = config["choke_loss_db"]
    rows = []
    for system in systems:
        ratio_key = f"{system.transformer_ratio:g}"
        losses = transformer_losses[ratio_key]
        system_choke_losses = choke_losses if system.choke_required else (0, 0, 0)
        for band, frequency_hz in config["bands"].items():
            for antenna in load_lookup[(system.design_id, band)]:
                antenna_load = complex(
                    antenna["resistance_ohm"], antenna["reactance_ohm"]
                )
                tuner_load = antenna_load / system.transformer_ratio
                for profile_id in KH1_PROFILE_IDS:
                    profile = PROFILES[profile_id]
                    for loss in LOSS_ENVELOPES:
                        component_losses = zip(
                            losses, system_choke_losses, strict=True
                        )
                        for component_envelope, (
                            transformer_db,
                            choke_db,
                        ) in enumerate(component_losses):
                            downstream_efficiency = 10 ** (
                                -(float(transformer_db) + float(choke_db)) / 10.0
                            )
                            for label, objective, target_swr in OBJECTIVES:
                                solution = solve_switched_l_network(
                                    profile,
                                    tuner_load,
                                    frequency_hz,
                                    loss,
                                    objective=objective,
                                    target_swr=target_swr,
                                )
                                final = (
                                    antenna["nec_efficiency"]
                                    * downstream_efficiency
                                    * solution.transducer_efficiency
                                )
                                rows.append(
                                {
                                    "candidate_id": system.id,
                                    "design_id": system.design_id,
                                    "family": system.family,
                                    "band": band,
                                    "frequency_hz": frequency_hz,
                                    "deployment": antenna["deployment"],
                                    "ground": antenna["ground"],
                                    "conductor": antenna["conductor"],
                                    "profile": profile_id,
                                    "tuner_loss_envelope": loss.id,
                                    "component_loss_envelope": component_envelope,
                                    "objective": label,
                                    "raw_resistance_ohm": antenna_load.real,
                                    "raw_reactance_ohm": antenna_load.imag,
                                    "tuner_load_resistance_ohm": tuner_load.real,
                                    "tuner_load_reactance_ohm": tuner_load.imag,
                                    "nec_efficiency": antenna["nec_efficiency"],
                                    "transformer_loss_db": transformer_db,
                                    "choke_loss_db": choke_db,
                                    "input_swr": solution.input_swr,
                                    "target_met": solution.input_swr <= target_swr,
                                    "likely_power_rollback": solution.input_swr > 2.5,
                                    "topology": solution.topology,
                                    "l_mask": solution.l_mask,
                                    "c_mask": solution.c_mask,
                                    "inductance_uH": solution.inductance_uH,
                                    "capacitance_pF": solution.capacitance_pF,
                                    "residual_mismatch_efficiency": (
                                        solution.accepted_power_w
                                    ),
                                    "tuner_efficiency": solution.tuner_efficiency,
                                    "tuner_loss_db": solution.tuner_loss_db,
                                    "final_efficiency": final,
                                    "total_loss_db": (
                                        -10.0 * math.log10(final)
                                        if final > 0
                                        else math.inf
                                    ),
                                }
                                )
    return rows


def _aggregate_systems(systems, rows):
    metadata = {system.id: system for system in systems}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["candidate_id"], row["objective"]), []).append(row)
    aggregates = []
    for (candidate_id, objective), subset in grouped.items():
        scenario_groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for row in subset:
            key = (
                row["profile"],
                row["tuner_loss_envelope"],
                str(row["component_loss_envelope"]),
                row["deployment"],
                row["ground"],
                row["conductor"],
            )
            scenario_groups.setdefault(key, []).append(row)
        worst = [min(row["final_efficiency"] for row in value) for value in scenario_groups.values()]
        all_match = [all(row["target_met"] for row in value) for value in scenario_groups.values()]
        system = metadata[candidate_id]
        aggregates.append(
            {
                "candidate_id": system.id,
                **asdict(system),
                "objective": objective,
                "scenario_count": len(scenario_groups),
                "worst_band_final_efficiency_p10": _quantile(worst, 0.1),
                "worst_band_final_efficiency_p50": _quantile(worst, 0.5),
                "median_final_efficiency": _quantile(
                    [row["final_efficiency"] for row in subset], 0.5
                ),
                "all_band_target_fraction": float(np.mean(all_match)),
                "rollback_fraction": float(
                    np.mean([row["likely_power_rollback"] for row in subset])
                ),
                "maximum_input_swr_p90": _quantile(
                    [row["input_swr"] for row in subset], 0.9
                ),
            }
        )
    objective_order = {
        label: index for index, (label, _, _) in enumerate(OBJECTIVES)
    }
    return sorted(
        aggregates,
        key=lambda row: (
            objective_order[row["objective"]],
            -row["worst_band_final_efficiency_p10"],
            -row["worst_band_final_efficiency_p50"],
            -row["median_final_efficiency"],
            row["total_wire_ft"],
        ),
    )


def _quantile(values, q):
    return float(np.quantile(np.asarray(values, dtype=float), q))


def _deployments(config, family):
    configured = config.get("deployments", {}).get(family)
    if configured:
        return {row["id"]: row for row in configured}
    defaults = {
        "direct_counterpoise": {
            "feed_height_ft": 3.0,
            "support_height_ft": 30.0,
            "counterpoise_height_ft": 0.5,
            "counterpoise_azimuth_deg": 135.0,
        },
        "radial_vertical": {"feed_height_ft": 1.0, "radial_end_height_ft": 0.1},
        "ocfd": {"center_height_ft": 30.0, "apex_angle_deg": 140.0},
        "efhw": {"center_height_ft": 30.0, "apex_angle_deg": 140.0},
        "fan_dipole": {"center_height_ft": 30.0, "apex_angle_deg": 120.0},
        "trap_loaded": {"center_height_ft": 30.0, "apex_angle_deg": 120.0},
    }
    return {"central": defaults[family]}


def _grounds(config):
    configured = config.get("grounds")
    if configured:
        return {
            row["id"]: (row["epsilon_r"], row["conductivity_s_m"])
            for row in configured
        }
    environment = config["environment"]
    return {
        "central": (
            environment["epsilon_r"],
            environment["ground_conductivity_s_m"],
        )
    }


def _conductors(config):
    configured = config.get("conductors")
    if configured:
        return {row["id"]: row["conductivity_s_m"] for row in configured}
    return {"central": config["environment"]["wire_conductivity_s_m"]}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
