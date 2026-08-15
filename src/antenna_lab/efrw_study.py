"""Reproducible NEC and Elecraft-ATU study for a 53 ft 9:1 EFRW."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

from antenna_lab.atu import LOSS_ENVELOPES, PROFILES, solve_switched_l_network
from antenna_lab.nec import FT, Wire, find_nec2c, run_cached, wire_network_deck
from antenna_lab.transmission_line import (
    LineParameters,
    input_impedance,
    line_efficiency,
    swr,
)


def load_efrw_config(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "study_id",
        "bands",
        "radiator",
        "grounds",
        "feed_system",
        "returns",
        "deployments",
        "devices",
    }
    if missing := required - set(value):
        raise ValueError(f"Missing EFRW config keys: {sorted(missing)}")
    return value


def radiator_points_ft(
    deployment: dict[str, Any], total_length_ft: float
) -> tuple[tuple[float, float, float], ...]:
    """Return piecewise-straight radiator vertices, starting at the feedpoint."""

    kind = deployment["kind"]
    if kind == "horizontal":
        height = float(deployment["height_ft"])
        return ((0.0, 0.0, height), (total_length_ft, 0.0, height))
    if kind == "sloper":
        feed = float(deployment["feed_height_ft"])
        support = float(deployment["support_height_ft"])
        rise = support - feed
        if not 0 <= rise < total_length_ft:
            raise ValueError("Sloper cannot reach the requested support")
        run = math.sqrt(total_length_ft**2 - rise**2)
        return ((0.0, 0.0, feed), (run, 0.0, support))
    if kind == "inverted_l":
        feed = float(deployment["feed_height_ft"])
        support = float(deployment["support_height_ft"])
        vertical = support - feed
        if not 0 < vertical < total_length_ft:
            raise ValueError("Inverted-L vertical leg is invalid")
        return (
            (0.0, 0.0, feed),
            (0.0, 0.0, support),
            (total_length_ft - vertical, 0.0, support),
        )
    if kind == "inverted_v":
        feed = float(deployment["feed_height_ft"])
        apex = float(deployment["apex_height_ft"])
        end = float(deployment["end_height_ft"])
        leg = total_length_ft / 2.0
        first_rise = apex - feed
        second_drop = apex - end
        if not 0 <= first_rise < leg or not 0 <= second_drop < leg:
            raise ValueError("Inverted-V leg cannot reach a requested endpoint")
        first_run = math.sqrt(leg**2 - first_rise**2)
        second_run = math.sqrt(leg**2 - second_drop**2)
        return (
            (0.0, 0.0, feed),
            (first_run, 0.0, apex),
            (first_run + second_run, 0.0, end),
        )
    raise ValueError(f"Unknown EFRW deployment kind: {kind}")


def _distance_ft(
    start: tuple[float, float, float], end: tuple[float, float, float]
) -> float:
    return math.sqrt(
        sum((right - left) ** 2 for left, right in zip(start, end, strict=True))
    )


def _segments(length_ft: float) -> int:
    count = max(3, math.ceil(length_ft / 0.65))
    return count if count % 2 else count + 1


def efrw_wires(
    config: dict[str, Any], deployment_id: str, return_id: str
) -> tuple[Wire, ...]:
    """Build a 53 ft radiator and an explicit counterpoise/coax-surface return."""

    radiator = config["radiator"]
    points = radiator_points_ft(
        config["deployments"][deployment_id], float(radiator["length_ft"])
    )
    gap_m = 0.02
    radius_m = float(radiator["radius_m"])
    feed_z_m = points[0][2] * FT
    wires: list[Wire] = []
    for index, (start, end) in enumerate(zip(points[:-1], points[1:], strict=True), 1):
        start_m = (start[0] * FT + gap_m / 2, start[1] * FT, start[2] * FT)
        end_m = (end[0] * FT + gap_m / 2, end[1] * FT, end[2] * FT)
        wires.append(
            Wire(index, _segments(_distance_ft(start, end)), start_m, end_m, radius_m)
        )

    source_tag = len(wires) + 1
    wires.append(
        Wire(
            source_tag,
            1,
            (-gap_m / 2, 0.0, feed_z_m),
            (gap_m / 2, 0.0, feed_z_m),
            radius_m,
        )
    )
    feed_system = config["feed_system"]
    return_length_ft = float(feed_system["return_length_ft"])
    return_end_height_ft = float(feed_system["return_end_height_ft"])
    vertical_ft = return_end_height_ft - points[0][2]
    if abs(vertical_ft) >= return_length_ft:
        raise ValueError("Return conductor cannot reach its requested endpoint")
    horizontal_ft = math.sqrt(return_length_ft**2 - vertical_ft**2)
    angle = math.radians(float(feed_system["return_azimuth_deg"]))
    end = (
        -gap_m / 2 + horizontal_ft * FT * math.cos(angle),
        horizontal_ft * FT * math.sin(angle),
        return_end_height_ft * FT,
    )
    wires.append(
        Wire(
            source_tag + 1,
            _segments(return_length_ft),
            end,
            (-gap_m / 2, 0.0, feed_z_m),
            float(config["returns"][return_id]["radius_m"]),
        )
    )
    return tuple(wires)


def _nec_case(
    config: dict[str, Any],
    deployment_id: str,
    return_id: str,
    ground_id: str,
    band: str,
    frequency_hz: int,
    cache_dir: Path,
    nec2c: str | Path | None,
) -> dict[str, Any]:
    wires = efrw_wires(config, deployment_id, return_id)
    ground = config["grounds"][ground_id]
    source_tag = len(wires) - 1
    deck = wire_network_deck(
        title=f"53ft EFRW {deployment_id} {return_id} {ground_id} {band}",
        wires=wires,
        source_tag=source_tag,
        source_segment=1,
        frequency_mhz=frequency_hz / 1e6,
        conductivity_s_m=float(config["radiator"]["conductivity_s_m"]),
        epsilon_r=float(ground["epsilon_r"]),
        ground_conductivity_s_m=float(ground["conductivity_s_m"]),
    )
    result, _, _, cache_hit = run_cached(deck, cache_dir, nec2c)
    if result.efficiency is None or not 0 < result.efficiency <= 1.0001:
        raise ValueError(
            f"Invalid NEC efficiency for {deployment_id}/{return_id}/{band}"
        )
    return {
        "deployment": deployment_id,
        "deployment_label": config["deployments"][deployment_id]["label"],
        "return_path": return_id,
        "return_label": config["returns"][return_id]["label"],
        "choke_position": config["returns"][return_id]["choke_position"],
        "ground": ground_id,
        "band": band,
        "frequency_hz": frequency_hz,
        "antenna_resistance_ohm": result.impedance_ohm.real,
        "antenna_reactance_ohm": result.impedance_ohm.imag,
        "antenna_raw_swr_50ohm": float(swr(result.impedance_ohm)),
        "nec_radiation_efficiency": result.efficiency,
        "cache_hit": cache_hit,
    }


def _run_nec_cases(
    config: dict[str, Any],
    cache_dir: Path,
    nec2c: str | Path | None,
    jobs: int,
) -> list[dict[str, Any]]:
    cases = [
        (deployment_id, return_id, ground_id, band, int(frequency_hz))
        for deployment_id in config["deployments"]
        for return_id in config["returns"]
        for ground_id in config["grounds"]
        for band, frequency_hz in config["bands"].items()
    ]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(
                _nec_case,
                config,
                deployment_id,
                return_id,
                ground_id,
                band,
                frequency_hz,
                cache_dir,
                nec2c,
            ): (deployment_id, return_id, ground_id, band)
            for deployment_id, return_id, ground_id, band, frequency_hz in cases
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                rows.append(future.result())
            except Exception as error:
                raise RuntimeError(f"NEC failed for {key}") from error
    band_order = {band: index for index, band in enumerate(config["bands"])}
    return sorted(
        rows,
        key=lambda row: (
            row["deployment"],
            row["return_path"],
            row["ground"],
            band_order[row["band"]],
        ),
    )


def _system_rows(
    config: dict[str, Any], nec_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    feed = config["feed_system"]
    coax_config = feed["coax"]
    coax = LineParameters(
        float(coax_config["characteristic_impedance_ohm"]),
        float(coax_config["velocity_factor"]),
        float(coax_config["loss_db_per_100ft_at_10mhz"]),
    )
    line_length_ft = float(coax_config["length_ft"])
    ratio = float(feed["transformer_impedance_ratio"])
    nominal_ground = config["canonical_ground"]
    tuner_losses = {loss.id: loss for loss in LOSS_ENVELOPES}
    rows: list[dict[str, Any]] = []
    for antenna in nec_rows:
        if antenna["ground"] != nominal_ground:
            continue
        frequency_hz = float(antenna["frequency_hz"])
        antenna_load = complex(
            antenna["antenna_resistance_ohm"], antenna["antenna_reactance_ohm"]
        )
        transformer_primary_load = antenna_load / ratio
        coax_efficiency = float(
            line_efficiency(
                transformer_primary_load, frequency_hz, line_length_ft, coax
            )
        )
        tuner_load = complex(
            input_impedance(
                transformer_primary_load, frequency_hz, line_length_ft, coax
            )
        )
        for device_id, device in config["devices"].items():
            if antenna["band"] not in device["bands"]:
                continue
            for profile_id in device["profiles"]:
                profile = PROFILES[profile_id]
                for tuner_loss_id, tuner_loss in tuner_losses.items():
                    for objective, target_swr in (
                        ("best_swr", 2.5),
                        ("lowest_loss_swr_2p5", 2.5),
                    ):
                        solver_objective = (
                            "best_swr"
                            if objective == "best_swr"
                            else "lowest_loss_under_target"
                        )
                        solution = solve_switched_l_network(
                            profile,
                            tuner_load,
                            frequency_hz,
                            tuner_loss,
                            objective=solver_objective,
                            target_swr=target_swr,
                        )
                        for hardware_id, hardware in feed["hardware_loss_db"].items():
                            transformer_efficiency = 10 ** (
                                -float(hardware["transformer"]) / 10.0
                            )
                            choke_efficiency = 10 ** (-float(hardware["choke"]) / 10.0)
                            final_efficiency = (
                                solution.transducer_efficiency
                                * coax_efficiency
                                * transformer_efficiency
                                * choke_efficiency
                                * float(antenna["nec_radiation_efficiency"])
                            )
                            rows.append(
                                {
                                    **antenna,
                                    "device": device_id,
                                    "device_label": device["label"],
                                    "atu_profile": profile_id,
                                    "atu_profile_status": profile.component_status,
                                    "tuner_loss_envelope": tuner_loss_id,
                                    "tuner_objective": objective,
                                    "hardware_loss_envelope": hardware_id,
                                    "transformer_primary_resistance_ohm": transformer_primary_load.real,
                                    "transformer_primary_reactance_ohm": transformer_primary_load.imag,
                                    "tuner_load_resistance_ohm": tuner_load.real,
                                    "tuner_load_reactance_ohm": tuner_load.imag,
                                    "raw_swr_at_tuner": float(swr(tuner_load)),
                                    "coax_efficiency": coax_efficiency,
                                    "coax_loss_db": _loss_db(coax_efficiency),
                                    "transformer_loss_db": float(
                                        hardware["transformer"]
                                    ),
                                    "choke_loss_db": float(hardware["choke"]),
                                    "tuned_input_swr": solution.input_swr,
                                    "match_success_swr_2p5": solution.input_swr <= 2.5,
                                    "atu_topology": solution.topology,
                                    "atu_inductance_uH": solution.inductance_uH,
                                    "atu_capacitance_pF": solution.capacitance_pF,
                                    "atu_tuner_efficiency": solution.tuner_efficiency,
                                    "atu_dissipation_loss_db": solution.tuner_loss_db,
                                    "atu_residual_mismatch_efficiency": solution.accepted_power_w,
                                    "atu_transducer_efficiency": solution.transducer_efficiency,
                                    "atu_total_loss_db": solution.total_loss_db,
                                    "pa_forward_radiating_efficiency": final_efficiency,
                                    "pa_forward_total_loss_db": _loss_db(
                                        final_efficiency
                                    ),
                                }
                            )
    return rows


def _loss_db(efficiency: float) -> float:
    return -10.0 * math.log10(efficiency) if efficiency > 0 else math.inf


def _canonical_rows(
    config: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row["tuner_loss_envelope"] == "nominal"
        and row["tuner_objective"] == "lowest_loss_swr_2p5"
        and row["hardware_loss_envelope"] == "best"
    ]


def _main_profile(config: dict[str, Any], device_id: str) -> str:
    return str(config["devices"][device_id]["profiles"][0])


def _match_status(
    config: dict[str, Any],
    lookup: dict[tuple[str, str, str, str, str], dict[str, Any]],
    device_id: str,
    deployment_id: str,
    return_id: str,
    band: str,
) -> str:
    profiles = config["devices"][device_id]["profiles"]
    success = [
        bool(
            lookup[(device_id, deployment_id, return_id, band, profile)][
                "match_success_swr_2p5"
            ]
        )
        for profile in profiles
    ]
    if all(success):
        raw_swr_limit = config["devices"][device_id].get(
            "published_typical_raw_swr_max"
        )
        if raw_swr_limit is not None:
            main = lookup[
                (
                    device_id,
                    deployment_id,
                    return_id,
                    band,
                    _main_profile(config, device_id),
                )
            ]
            if float(main["raw_swr_at_tuner"]) > float(raw_swr_limit):
                return "uncertain"
        return "likely"
    if any(success):
        return "uncertain"
    return "unlikely"


def _summary(
    config: dict[str, Any],
    canonical: list[dict[str, Any]],
    all_system_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    lookup = {
        (
            row["device"],
            row["deployment"],
            row["return_path"],
            row["band"],
            row["atu_profile"],
        ): row
        for row in canonical
    }
    rankings = []
    for device_id, device in config["devices"].items():
        main_profile = _main_profile(config, device_id)
        for return_id in config["returns"]:
            candidates = []
            for deployment_id in config["deployments"]:
                primary_rows = [
                    lookup[(device_id, deployment_id, return_id, band, main_profile)]
                    for band in device["bands"]
                ]
                statuses = [
                    _match_status(
                        config,
                        lookup,
                        device_id,
                        deployment_id,
                        return_id,
                        band,
                    )
                    for band in device["bands"]
                ]
                efficiencies = [
                    float(row["pa_forward_radiating_efficiency"])
                    for row in primary_rows
                ]
                matched_efficiencies = [
                    efficiency
                    for efficiency, status in zip(efficiencies, statuses, strict=True)
                    if status == "likely"
                ]
                candidates.append(
                    {
                        "device": device_id,
                        "return_path": return_id,
                        "deployment": deployment_id,
                        "likely_match_band_count": statuses.count("likely"),
                        "uncertain_match_band_count": statuses.count("uncertain"),
                        "supported_band_count": len(statuses),
                        "all_band_likely_match": all(
                            status == "likely" for status in statuses
                        ),
                        "geometric_mean_efficiency_all_bands": float(
                            np.exp(np.mean(np.log(np.clip(efficiencies, 1e-12, 1.0))))
                        ),
                        "geometric_mean_efficiency_likely_matches": (
                            float(
                                np.exp(
                                    np.mean(
                                        np.log(
                                            np.clip(matched_efficiencies, 1e-12, 1.0)
                                        )
                                    )
                                )
                            )
                            if matched_efficiencies
                            else 0.0
                        ),
                        "worst_band_efficiency": min(efficiencies),
                        "median_atu_dissipation_loss_db": float(
                            np.median(
                                [row["atu_dissipation_loss_db"] for row in primary_rows]
                            )
                        ),
                    }
                )
            candidates.sort(
                key=lambda row: (
                    row["likely_match_band_count"],
                    row["geometric_mean_efficiency_all_bands"],
                ),
                reverse=True,
            )
            rankings.extend(candidates)
    firmware_rows = {
        (
            row["device"],
            row["deployment"],
            row["return_path"],
            row["band"],
            row["atu_profile"],
        ): row
        for row in all_system_rows
        if row["tuner_loss_envelope"] == "nominal"
        and row["tuner_objective"] == "best_swr"
        and row["hardware_loss_envelope"] == "best"
    }
    efficiency_advantages_db = [
        10.0
        * math.log10(
            low_loss_row["pa_forward_radiating_efficiency"]
            / firmware_rows[key]["pa_forward_radiating_efficiency"]
        )
        for key, low_loss_row in lookup.items()
        if firmware_rows[key]["pa_forward_radiating_efficiency"] > 0
    ]
    return {
        "study_id": config["study_id"],
        "canonical_case": {
            "ground": config["canonical_ground"],
            "hardware_loss_envelope": "best",
            "tuner_loss_envelope": "nominal",
            "tuner_objective": "lowest-loss state meeting 2.5:1",
        },
        "rankings": rankings,
        "maximum_efficiency_advantage_over_best_swr_state_db": max(
            efficiency_advantages_db, default=0.0
        ),
        "warnings": [
            "The 17 ft return and 17 ft RG-316 line are explicit assumptions, not Reliance-supplied dimensions.",
            "The no-counterpoise case treats the coax exterior as a NEC wire and the differential coax as a separate transmission line; coupling between those modes is not solved.",
            "The choke is an ideal common-mode boundary plus a fixed differential insertion-loss envelope; finite choking impedance is not modeled.",
            "The 9:1 transformer is an ideal impedance transformation plus a fixed loss envelope; its loss and impedance transformation should be measured on the actual unit.",
            "KHATU1 bank values and all tuner component-Q values remain inferred sensitivity inputs; KXAT2/KXAT3 bank values are schematic-derived.",
            "NEC uses bare-wire geometry and omits insulation loading, trees, supports, the operator, radio chassis, connectors, and nearby objects.",
            "Best-case efficiency is not gain: deployment shape can redirect radiation even when the percentage of power radiated is high.",
        ],
    }


def _report(
    config: dict[str, Any],
    canonical: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    lookup = {
        (
            row["device"],
            row["deployment"],
            row["return_path"],
            row["band"],
            row["atu_profile"],
        ): row
        for row in canonical
    }
    lines = [
        "# 53 ft 9:1 EFRW complete-system study",
        "",
        "## Bottom line",
        "",
        "This report gives **PA-forward radiating efficiency**, not merely NEC wire efficiency. The canonical best-component case multiplies the modeled tuner transducer efficiency (including residual mismatch), mismatch-enhanced RG-316 efficiency, a 0.25 dB 9:1 loss, a 0.10 dB choke loss, and NEC wire-plus-ground radiation efficiency.",
        "",
        "A check mark means every tuner profile used for that radio found a state at or below 2.5:1 and, where Elecraft publishes one, the raw load is within the owner's-manual typical 20:1 range. `~` means a circuit-model match outside that published range, or only one of the two inferred KHATU1 profiles matched. Both cases are deliberately labeled uncertain.",
    ]
    for device_id, device in config["devices"].items():
        main_profile = _main_profile(config, device_id)
        lines += ["", f"## {device['label']}", ""]
        for return_id, return_config in config["returns"].items():
            lines += [
                f"### {return_config['label']}",
                "",
                "| deployment | " + " | ".join(device["bands"]) + " |",
                "|---|" + "---:|" * len(device["bands"]),
            ]
            for deployment_id, deployment in config["deployments"].items():
                cells = []
                for band in device["bands"]:
                    row = lookup[
                        (device_id, deployment_id, return_id, band, main_profile)
                    ]
                    status = _match_status(
                        config,
                        lookup,
                        device_id,
                        deployment_id,
                        return_id,
                        band,
                    )
                    mark = {"likely": "✓", "uncertain": "~", "unlikely": "✕"}[status]
                    cells.append(
                        f"{100 * row['pa_forward_radiating_efficiency']:.0f}% {mark}"
                    )
                lines.append(f"| {deployment['label']} | " + " | ".join(cells) + " |")

        lines += [
            "",
            "Loss-budget summary for the main profile (all supported bands):",
            "",
            "| return | deployment | matches | efficiency geometric mean | worst band | median tuner dissipation |",
            "|---|---|---:|---:|---:|---:|",
        ]
        ranked = [row for row in summary["rankings"] if row["device"] == device_id]
        for row in ranked:
            lines.append(
                "| "
                + config["returns"][row["return_path"]]["label"]
                + " | "
                + config["deployments"][row["deployment"]]["label"]
                + f" | {row['likely_match_band_count']}/{row['supported_band_count']}"
                + f" | {100 * row['geometric_mean_efficiency_all_bands']:.1f}%"
                + f" | {100 * row['worst_band_efficiency']:.1f}%"
                + f" | {row['median_atu_dissipation_loss_db']:.2f} dB |"
            )

    hardware = config["feed_system"]["hardware_loss_db"]
    lines += [
        "",
        "## Component and model sensitivity",
        "",
        f"The best hardware envelope is {hardware['best']['transformer']:.2f} dB transformer + {hardware['best']['choke']:.2f} dB choke. The nominal envelope is {hardware['nominal']['transformer']:.2f} + {hardware['nominal']['choke']:.2f} dB, and the conservative envelope is {hardware['conservative']['transformer']:.2f} + {hardware['conservative']['choke']:.2f} dB. `system_results.csv` contains all three hardware envelopes and all three tuner-Q envelopes.",
        "",
        "The detailed CSV separates NEC efficiency, coax loss, transformer loss, choke loss, tuner dissipation, residual mismatch, and final PA-forward efficiency. `nec_loads.csv` also includes poor-ground cases; tuner calculations use the canonical average-ground cases.",
        "",
        f"The tables use the loss-minimizing discrete tuner state that still reaches 2.5:1. A firmware-like lowest-SWR state is also retained in the CSV; across this sweep, the largest modeled benefit from choosing the loss-minimizing state is only {summary['maximum_efficiency_advantage_over_best_swr_state_db']:.2f} dB.",
        "",
        "## Interpretation",
        "",
        "The radio-end choke case is not truly a counterpoise-free antenna: the coax exterior is the 17 ft return conductor. Moving or changing that cable changes the antenna. The feedpoint-choke case makes the dedicated wire the intended return and should be more repeatable and less coupled to the radio/operator, even when a particular coax-return cell happens to be more efficient.",
        "",
        "A high efficiency number on 160 or 80 m does not make this short antenna competitive with a full-size radiator: efficiency is only the fraction of accepted power radiated, while gain and useful launch angle also depend on the electrically short/current-distribution geometry. This study does not rank patterns.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "uv run antenna-lab run-efrw-study --config configs/53ft-efrw-v1.json --output results/53ft-efrw-v1 --nec2c /path/to/nec2c",
        "uv run antenna-lab verify-results results/53ft-efrw-v1",
        "```",
        "",
        "## Limitations",
        "",
    ]
    lines += [f"- {warning}" for warning in summary["warnings"]]
    lines += ["", "## Sources", ""]
    lines += [f"- [{name}]({url})" for name, url in config.get("sources", {}).items()]
    return "\n".join(lines) + "\n"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(directory: Path) -> None:
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


def _solver_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "-v"], capture_output=True, text=True, check=False
    )
    return (completed.stdout or completed.stderr).strip()


def run_efrw_study(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    nec2c: str | Path | None = None,
    cache_dir: str | Path = Path("build/53ft-efrw-nec-cache"),
    jobs: int | None = None,
) -> dict[str, Any]:
    config_path = Path(config_path)
    output_dir = Path(output_dir)
    cache_dir = Path(cache_dir)
    config = load_efrw_config(config_path)
    executable = find_nec2c(nec2c)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    job_count = jobs or max(1, min(8, os.cpu_count() or 1))

    nec_rows = _run_nec_cases(config, cache_dir, executable, job_count)
    system_rows = _system_rows(config, nec_rows)
    canonical = _canonical_rows(config, system_rows)
    summary = _summary(config, canonical, system_rows)

    _write_csv(output_dir / "nec_loads.csv", nec_rows)
    _write_csv(output_dir / "system_results.csv", system_rows)
    _write_csv(output_dir / "best_case_by_band.csv", canonical)
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(
        _report(config, canonical, summary), encoding="utf-8"
    )
    _write_json(
        output_dir / "run_metadata.json",
        {
            "study_id": config["study_id"],
            "solver": _solver_version(executable),
            "solver_sha256": _sha256(executable),
            "config": str(config_path),
            "config_sha256": _sha256(config_path),
            "source_sha256": _sha256(Path(__file__)),
            "nec_case_count": len(nec_rows),
            "system_row_count": len(system_rows),
            "cache_directory": str(cache_dir),
        },
    )
    _write_manifest(output_dir)
    return summary
