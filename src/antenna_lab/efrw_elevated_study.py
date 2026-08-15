"""Counterpoise, elevated-feed, and carbon-mast extension to the 53 ft EFRW study."""

# ruff: noqa: E501

from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

from antenna_lab.atu import LOSS_ENVELOPES, PROFILES, solve_switched_l_network
from antenna_lab.efrw_study import (
    _loss_db,
    _segments,
    _sha256,
    _solver_version,
    _write_csv,
    _write_json,
    _write_manifest,
    load_efrw_config,
)
from antenna_lab.nec import FT, Wire, find_nec2c, run_cached, wire_network_deck
from antenna_lab.transmission_line import (
    LineParameters,
    input_impedance,
    line_efficiency,
    swr,
)


def load_elevated_config(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(path)
    extension = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "study_id",
        "base_config",
        "comparison_bands",
        "ground",
        "return_end_height_ft",
        "counterpoise_lengths_ft",
        "counterpoise_azimuths_deg",
        "elevated_feed_heights_ft",
        "specific_sloper",
        "carbon_mast",
    }
    if missing := required - set(extension):
        raise ValueError(f"Missing elevated EFRW config keys: {sorted(missing)}")
    base = load_efrw_config(path.parent / extension["base_config"])
    return extension, base


def _straight_endpoint(
    start: tuple[float, float, float], length_ft: float, end_height_ft: float
) -> tuple[float, float, float]:
    vertical = end_height_ft - start[2]
    if abs(vertical) >= length_ft:
        raise ValueError("Wire cannot reach requested endpoint height")
    return (
        start[0] + math.sqrt(length_ft**2 - vertical**2),
        start[1],
        end_height_ft,
    )


def _case(
    *,
    family: str,
    feed_height_ft: float,
    radiator_end_height_ft: float,
    return_kind: str,
    return_length_ft: float,
    return_azimuth_deg: float | None,
    mast_condition: str = "none",
) -> dict[str, Any]:
    angle = "vertical" if return_azimuth_deg is None else f"az{int(return_azimuth_deg)}"
    return_id = f"{return_kind}_{return_length_ft:g}ft_{angle}"
    return {
        "case_id": f"{family}_feed{feed_height_ft:g}_end{radiator_end_height_ft:g}_{return_id}_{mast_condition}",
        "family": family,
        "feed_height_ft": feed_height_ft,
        "radiator_end_height_ft": radiator_end_height_ft,
        "return_kind": return_kind,
        "return_id": return_id,
        "return_length_ft": return_length_ft,
        "return_azimuth_deg": return_azimuth_deg,
        "coax_length_ft": feed_height_ft - 0.5,
        "mast_condition": mast_condition,
    }


def build_cases(extension: dict[str, Any], base: dict[str, Any]) -> list[dict[str, Any]]:
    """Create every requested geometry, omitting physically impossible counterpoises."""

    lengths = [float(value) for value in extension["counterpoise_lengths_ft"]]
    azimuths = [float(value) for value in extension["counterpoise_azimuths_deg"]]
    return_end = float(extension["return_end_height_ft"])
    cases: list[dict[str, Any]] = []

    # Existing 3-to-30 ft sloper, now swept for counterpoise length and direction.
    for length in lengths:
        if length <= 3.0 - return_end:
            continue
        for azimuth in azimuths:
            cases.append(
                _case(
                    family="low_sloper_cp_sweep",
                    feed_height_ft=3.0,
                    radiator_end_height_ft=30.0,
                    return_kind="dedicated_angled",
                    return_length_ft=length,
                    return_azimuth_deg=azimuth,
                )
            )
            cases[-1]["coax_length_ft"] = float(
                base["feed_system"]["coax"]["length_ft"]
            )

    # Tree-limb cases: high feedpoint, radiator down one way, feedline straight down.
    for feed_height in map(float, extension["elevated_feed_heights_ft"]):
        drop = feed_height - return_end
        for return_kind, radius_length in (
            ("coax_return", drop),
            ("dedicated_vertical", drop),
        ):
            cases.append(
                _case(
                    family="elevated_tree",
                    feed_height_ft=feed_height,
                    radiator_end_height_ft=float(
                        extension["elevated_radiator_end_height_ft"]
                    ),
                    return_kind=return_kind,
                    return_length_ft=radius_length,
                    return_azimuth_deg=None,
                )
            )
        for length in lengths:
            if length <= drop:
                continue
            for azimuth in azimuths:
                cases.append(
                    _case(
                        family="elevated_tree",
                        feed_height_ft=feed_height,
                        radiator_end_height_ft=float(
                            extension["elevated_radiator_end_height_ft"]
                        ),
                        return_kind="dedicated_angled",
                        return_length_ft=length,
                        return_azimuth_deg=azimuth,
                    )
                )

    # User's 20-to-40 ft shallow sloper, with a vertical feedline and mast bounds.
    specific = extension["specific_sloper"]
    feed_height = float(specific["feed_height_ft"])
    end_height = float(specific["far_end_height_ft"])
    drop = feed_height - return_end
    bare_returns = [
        ("coax_return", drop, None),
        ("dedicated_vertical", drop, None),
    ]
    bare_returns += [
        ("dedicated_angled", length, azimuth)
        for length in lengths
        if length > drop
        for azimuth in azimuths
    ]
    for mast_condition in extension["carbon_mast"]["conditions"]:
        for return_kind, length, azimuth in bare_returns:
            cases.append(
                _case(
                    family="sloper_20_to_40",
                    feed_height_ft=feed_height,
                    radiator_end_height_ft=end_height,
                    return_kind=return_kind,
                    return_length_ft=length,
                    return_azimuth_deg=azimuth,
                    mast_condition=mast_condition,
                )
            )
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Generated elevated EFRW case IDs are not unique")
    return cases


def case_wires(
    extension: dict[str, Any], base: dict[str, Any], case: dict[str, Any]
) -> tuple[tuple[Wire, ...], int, dict[int, float]]:
    """Build the radiator, return conductor, and optional floating carbon mast."""

    radiator = base["radiator"]
    length_ft = float(radiator["length_ft"])
    feed = (0.0, 0.0, float(case["feed_height_ft"]))
    radiator_end = _straight_endpoint(
        feed, length_ft, float(case["radiator_end_height_ft"])
    )
    gap = 0.02
    source_tag = 2
    radius = float(radiator["radius_m"])
    wires = [
        Wire(
            1,
            _segments(length_ft),
            (gap / 2, 0.0, feed[2] * FT),
            (radiator_end[0] * FT + gap / 2, 0.0, radiator_end[2] * FT),
            radius,
        ),
        Wire(
            source_tag,
            1,
            (-gap / 2, 0.0, feed[2] * FT),
            (gap / 2, 0.0, feed[2] * FT),
            radius,
        ),
    ]
    return_length = float(case["return_length_ft"])
    return_end_z = float(extension["return_end_height_ft"])
    vertical = return_end_z - feed[2]
    if abs(vertical) > return_length + 1e-9:
        raise ValueError("Return conductor is too short for requested geometry")
    if case["return_azimuth_deg"] is None:
        horizontal = 0.0
        azimuth = 0.0
    else:
        horizontal = math.sqrt(max(0.0, return_length**2 - vertical**2))
        azimuth = math.radians(float(case["return_azimuth_deg"]))
    return_end = (
        -gap / 2 + horizontal * FT * math.cos(azimuth),
        horizontal * FT * math.sin(azimuth),
        return_end_z * FT,
    )
    return_radius = (
        float(base["feed_system"]["coax"]["outside_radius_m"])
        if case["return_kind"] == "coax_return"
        else radius
    )
    # At 3 in spacing, the sideways counterpoise passes close to the mast near
    # the feedpoint. Finer segments prevent the thin-wire kernel from producing
    # the non-physical >100% efficiency seen with the normal portable-wire grid.
    close_sideways_mast = (
        case["mast_condition"] in {"cfrp_5e3_3in", "cfrp_5e4_3in"}
        and case["return_azimuth_deg"] == 90
    )
    return_segments = (
        _odd_segments_at_most(return_length, 0.25)
        if close_sideways_mast
        else _segments(return_length)
    )
    wires.append(
        Wire(
            3,
            return_segments,
            return_end,
            (-gap / 2, 0.0, feed[2] * FT),
            return_radius,
        )
    )

    conductivity_overrides: dict[int, float] = {}
    mast_id = str(case["mast_condition"])
    mast = extension["carbon_mast"]["conditions"][mast_id]
    if mast_id != "none":
        separation_m = float(mast["separation_in"]) * 0.0254
        mast_config = extension["carbon_mast"]
        wires.append(
            Wire(
                4,
                (
                    _odd_segments_at_most(
                        float(mast_config["top_height_ft"])
                        - float(mast_config["bottom_height_ft"]),
                        0.25,
                    )
                    if close_sideways_mast
                    else _segments(
                        float(mast_config["top_height_ft"])
                        - float(mast_config["bottom_height_ft"])
                    )
                ),
                (0.0, separation_m, float(mast_config["bottom_height_ft"]) * FT),
                (0.0, separation_m, float(mast_config["top_height_ft"]) * FT),
                float(mast_config["radius_m"]),
            )
        )
        conductivity_overrides[4] = float(mast["conductivity_s_m"])
    return tuple(wires), source_tag, conductivity_overrides


def _odd_segments_at_most(length_ft: float, maximum_segment_ft: float) -> int:
    count = max(3, math.ceil(length_ft / maximum_segment_ft))
    return count if count % 2 else count + 1


def _nec_case(
    extension: dict[str, Any],
    base: dict[str, Any],
    case: dict[str, Any],
    band: str,
    frequency_hz: int,
    cache_dir: Path,
    nec2c: str | Path | None,
) -> dict[str, Any]:
    wires, source_tag, conductivity_overrides = case_wires(extension, base, case)
    ground = base["grounds"][extension["ground"]]
    deck = wire_network_deck(
        title=f"53ft EFRW elevated {case['case_id']} {band}",
        wires=wires,
        source_tag=source_tag,
        source_segment=1,
        frequency_mhz=frequency_hz / 1e6,
        conductivity_s_m=float(base["radiator"]["conductivity_s_m"]),
        epsilon_r=float(ground["epsilon_r"]),
        ground_conductivity_s_m=float(ground["conductivity_s_m"]),
        wire_conductivity_s_m=conductivity_overrides,
    )
    result, _, _, cache_hit = run_cached(deck, cache_dir, nec2c)
    if result.efficiency is None or not 0 < result.efficiency <= 1.0001:
        raise ValueError(f"Invalid NEC efficiency for {case['case_id']}/{band}")
    return {
        **case,
        "band": band,
        "frequency_hz": frequency_hz,
        "antenna_resistance_ohm": result.impedance_ohm.real,
        "antenna_reactance_ohm": result.impedance_ohm.imag,
        "antenna_raw_swr_50ohm": float(swr(result.impedance_ohm)),
        "nec_radiation_efficiency": result.efficiency,
        "cache_hit": cache_hit,
    }


def _run_nec_cases(
    extension: dict[str, Any],
    base: dict[str, Any],
    cases: list[dict[str, Any]],
    cache_dir: Path,
    nec2c: str | Path | None,
    jobs: int,
) -> list[dict[str, Any]]:
    requests = [
        (case, band, int(frequency_hz))
        for case in cases
        for band, frequency_hz in base["bands"].items()
    ]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(
                _nec_case,
                extension,
                base,
                case,
                band,
                frequency_hz,
                cache_dir,
                nec2c,
            ): (case["case_id"], band)
            for case, band, frequency_hz in requests
        }
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as error:
                raise RuntimeError(f"NEC failed for {futures[future]}") from error
    band_order = {band: index for index, band in enumerate(base["bands"])}
    return sorted(rows, key=lambda row: (row["case_id"], band_order[row["band"]]))


def _system_rows(base: dict[str, Any], nec_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coax_config = base["feed_system"]["coax"]
    coax = LineParameters(
        float(coax_config["characteristic_impedance_ohm"]),
        float(coax_config["velocity_factor"]),
        float(coax_config["loss_db_per_100ft_at_10mhz"]),
    )
    ratio = float(base["feed_system"]["transformer_impedance_ratio"])
    hardware = base["feed_system"]["hardware_loss_db"]["best"]
    tuner_loss = next(item for item in LOSS_ENVELOPES if item.id == "nominal")
    hardware_efficiency = 10 ** (
        -(float(hardware["transformer"]) + float(hardware["choke"])) / 10.0
    )
    rows: list[dict[str, Any]] = []
    for antenna in nec_rows:
        frequency_hz = float(antenna["frequency_hz"])
        antenna_load = complex(
            antenna["antenna_resistance_ohm"], antenna["antenna_reactance_ohm"]
        )
        transformer_load = antenna_load / ratio
        coax_efficiency = float(
            line_efficiency(
                transformer_load,
                frequency_hz,
                float(antenna["coax_length_ft"]),
                coax,
            )
        )
        tuner_load = complex(
            input_impedance(
                transformer_load,
                frequency_hz,
                float(antenna["coax_length_ft"]),
                coax,
            )
        )
        for device_id, device in base["devices"].items():
            if antenna["band"] not in device["bands"]:
                continue
            for profile_id in device["profiles"]:
                solution = solve_switched_l_network(
                    PROFILES[profile_id],
                    tuner_load,
                    frequency_hz,
                    tuner_loss,
                    objective="lowest_loss_under_target",
                    target_swr=2.5,
                )
                final_efficiency = (
                    float(antenna["nec_radiation_efficiency"])
                    * coax_efficiency
                    * hardware_efficiency
                    * solution.transducer_efficiency
                )
                rows.append(
                    {
                        **antenna,
                        "device": device_id,
                        "device_label": device["label"],
                        "atu_profile": profile_id,
                        "raw_swr_at_tuner": float(swr(tuner_load)),
                        "coax_efficiency": coax_efficiency,
                        "coax_loss_db": _loss_db(coax_efficiency),
                        "transformer_loss_db": float(hardware["transformer"]),
                        "choke_loss_db": float(hardware["choke"]),
                        "tuned_input_swr": solution.input_swr,
                        "match_success_swr_2p5": solution.input_swr <= 2.5,
                        "atu_topology": solution.topology,
                        "atu_inductance_uH": solution.inductance_uH,
                        "atu_capacitance_pF": solution.capacitance_pF,
                        "atu_dissipation_loss_db": solution.tuner_loss_db,
                        "atu_residual_mismatch_efficiency": solution.accepted_power_w,
                        "atu_transducer_efficiency": solution.transducer_efficiency,
                        "atu_total_loss_db": solution.total_loss_db,
                        "pa_forward_radiating_efficiency": final_efficiency,
                        "pa_forward_total_loss_db": _loss_db(final_efficiency),
                    }
                )
    return rows


def _match_status(
    base: dict[str, Any],
    lookup: dict[tuple[str, str, str, str], dict[str, Any]],
    device_id: str,
    case_id: str,
    band: str,
) -> str:
    device = base["devices"][device_id]
    rows = [lookup[(device_id, case_id, band, profile)] for profile in device["profiles"]]
    successes = [bool(row["match_success_swr_2p5"]) for row in rows]
    if all(successes):
        raw_limit = device.get("published_typical_raw_swr_max")
        if raw_limit is not None and float(rows[0]["raw_swr_at_tuner"]) > float(raw_limit):
            return "uncertain"
        return "likely"
    if any(successes):
        return "uncertain"
    return "unlikely"


def _rank_case_groups(
    extension: dict[str, Any],
    base: dict[str, Any],
    cases: list[dict[str, Any]],
    system_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = {
        (row["device"], row["case_id"], row["band"], row["atu_profile"]): row
        for row in system_rows
    }
    rankings: list[dict[str, Any]] = []
    comparison = set(extension["comparison_bands"])
    for device_id, device in base["devices"].items():
        bands = [band for band in device["bands"] if band in comparison]
        profile = device["profiles"][0]
        for case in cases:
            primary = [lookup[(device_id, case["case_id"], band, profile)] for band in bands]
            statuses = [
                _match_status(base, lookup, device_id, case["case_id"], band)
                for band in bands
            ]
            efficiencies = [float(row["pa_forward_radiating_efficiency"]) for row in primary]
            rankings.append(
                {
                    **case,
                    "device": device_id,
                    "comparison_bands": ",".join(bands),
                    "likely_match_band_count": statuses.count("likely"),
                    "uncertain_match_band_count": statuses.count("uncertain"),
                    "unlikely_match_band_count": statuses.count("unlikely"),
                    "supported_comparison_band_count": len(bands),
                    "geometric_mean_efficiency": float(
                        np.exp(np.mean(np.log(np.clip(efficiencies, 1e-12, 1.0))))
                    ),
                    "worst_band_efficiency": min(efficiencies),
                    "median_atu_dissipation_loss_db": float(
                        np.median([row["atu_dissipation_loss_db"] for row in primary])
                    ),
                }
            )
    return rankings


def _band_optima(
    base: dict[str, Any],
    cases: list[dict[str, Any]],
    system_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = {
        (row["device"], row["case_id"], row["band"], row["atu_profile"]): row
        for row in system_rows
    }
    candidates = [case for case in cases if case["family"] == "low_sloper_cp_sweep"]
    result: list[dict[str, Any]] = []
    priority = {"likely": 2, "uncertain": 1, "unlikely": 0}
    for device_id, device in base["devices"].items():
        profile = device["profiles"][0]
        for band in device["bands"]:
            scored = []
            for case in candidates:
                row = lookup[(device_id, case["case_id"], band, profile)]
                status = _match_status(base, lookup, device_id, case["case_id"], band)
                scored.append((priority[status], float(row["pa_forward_radiating_efficiency"]), case, row, status))
            _, _, case, row, status = max(scored, key=lambda item: (item[0], item[1]))
            result.append(
                {
                    "device": device_id,
                    "band": band,
                    "counterpoise_length_ft": case["return_length_ft"],
                    "counterpoise_azimuth_deg": case["return_azimuth_deg"],
                    "match_status": status,
                    "pa_forward_radiating_efficiency": row["pa_forward_radiating_efficiency"],
                    "raw_swr_at_tuner": row["raw_swr_at_tuner"],
                    "tuned_input_swr": row["tuned_input_swr"],
                    "atu_dissipation_loss_db": row["atu_dissipation_loss_db"],
                    "coax_loss_db": row["coax_loss_db"],
                }
            )
    return result


def _best_ranked(
    rankings: list[dict[str, Any]],
    *,
    device: str,
    family: str,
    mast: str | None = None,
    feed_height: float | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    rows = [
        row
        for row in rankings
        if row["device"] == device
        and row["family"] == family
        and (mast is None or row["mast_condition"] == mast)
        and (feed_height is None or row["feed_height_ft"] == feed_height)
        and (
            category is None
            or (category == "angled" and row["return_kind"] == "dedicated_angled")
            or (category != "angled" and row["return_kind"] == category)
        )
    ]
    return max(
        rows,
        key=lambda row: (
            row["likely_match_band_count"],
            row["uncertain_match_band_count"],
            row["geometric_mean_efficiency"],
        ),
    )


def _same_geometry_mast_deltas(
    extension: dict[str, Any],
    base: dict[str, Any],
    rankings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare each no-mast optimum with the exact same return beside each mast."""

    result: list[dict[str, Any]] = []
    categories = ("coax_return", "dedicated_vertical", "dedicated_angled")
    for device_id in base["devices"]:
        for category in categories:
            baseline = _best_ranked(
                rankings,
                device=device_id,
                family="sloper_20_to_40",
                mast="none",
                category=("angled" if category == "dedicated_angled" else category),
            )
            for mast_id in extension["carbon_mast"]["conditions"]:
                if mast_id == "none":
                    continue
                mast_row = next(
                    row
                    for row in rankings
                    if row["device"] == device_id
                    and row["family"] == "sloper_20_to_40"
                    and row["mast_condition"] == mast_id
                    and row["return_id"] == baseline["return_id"]
                )
                result.append(
                    {
                        "device": device_id,
                        "return_kind": category,
                        "baseline_return_id": baseline["return_id"],
                        "mast_condition": mast_id,
                        "baseline_geometric_mean_efficiency": baseline[
                            "geometric_mean_efficiency"
                        ],
                        "mast_geometric_mean_efficiency": mast_row[
                            "geometric_mean_efficiency"
                        ],
                        "geometric_mean_delta_db": 10
                        * math.log10(
                            mast_row["geometric_mean_efficiency"]
                            / baseline["geometric_mean_efficiency"]
                        ),
                        "baseline_worst_band_efficiency": baseline[
                            "worst_band_efficiency"
                        ],
                        "mast_worst_band_efficiency": mast_row[
                            "worst_band_efficiency"
                        ],
                        "worst_band_delta_db": 10
                        * math.log10(
                            mast_row["worst_band_efficiency"]
                            / baseline["worst_band_efficiency"]
                        ),
                        "baseline_likely_matches": baseline[
                            "likely_match_band_count"
                        ],
                        "mast_likely_matches": mast_row["likely_match_band_count"],
                    }
                )
    return result


def _report(
    extension: dict[str, Any],
    base: dict[str, Any],
    rankings: list[dict[str, Any]],
    optima: list[dict[str, Any]],
    mast_deltas: list[dict[str, Any]],
) -> str:
    lines = [
        "# 53 ft EFRW counterpoise, elevated-feed, and carbon-mast addendum",
        "",
        "## What was compared",
        "",
        "The same 53 ft, 26-AWG copper radiator, ideal 9:1 transformation, RG-316 model, Elecraft tuner models, and best-component 0.25 dB transformer + 0.10 dB choke envelope are retained. PA-forward efficiency includes NEC wire/ground loss, mismatch-enhanced coax loss, tuner dissipation and residual mismatch, transformer loss, and choke loss.",
        "",
        "Ranking uses the common POTA bands 40/30/20/17/15/12/10 m that each radio supports. All of each radio's modeled bands remain in the detailed CSV. A 180-degree counterpoise slopes away exactly opposite the radiator projection; 135 degrees is diagonal and 90 degrees is sideways.",
        "",
        "## Counterpoise length sweep on the 3-to-30 ft sloper",
        "",
    ]
    for device_id, device in base["devices"].items():
        rows = [row for row in optima if row["device"] == device_id]
        lines += [
            f"### {device['label']}",
            "",
            "| band | best length | direction | match | PA→radiated | tuner dissipation | coax loss |",
            "|---|---:|---:|---|---:|---:|---:|",
        ]
        for row in rows:
            lines.append(
                f"| {row['band']} | {row['counterpoise_length_ft']:g} ft | {row['counterpoise_azimuth_deg']:g}° | {row['match_status']} | {100 * row['pa_forward_radiating_efficiency']:.1f}% | {row['atu_dissipation_loss_db']:.2f} dB | {row['coax_loss_db']:.2f} dB |"
            )
        best = _best_ranked(
            rankings,
            device=device_id,
            family="low_sloper_cp_sweep",
        )
        lines += [
            "",
            f"Best one-size compromise: **{best['return_length_ft']:g} ft at {best['return_azimuth_deg']:g}°**, with {best['likely_match_band_count']}/{best['supported_comparison_band_count']} likely matches and {100 * best['geometric_mean_efficiency']:.1f}% geometric-mean PA-forward efficiency on the comparison bands.",
            "",
        ]

    lines += [
        "## Elevated feedpoint: coax vertical or counterpoise angled away",
        "",
        "Each radiator runs from the elevated feedpoint down to a 3 ft far end. The coax is vertical in every case. With a feedpoint choke, a separate counterpoise is either vertical beside that feedline or slopes to 0.5 ft; without that counterpoise, the coax exterior is the vertical return and the choke is at the radio.",
        "",
        "| radio | feed | return choice | selected CP | likely matches | geometric mean | worst band |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for device_id in base["devices"]:
        for feed_height in map(float, extension["elevated_feed_heights_ft"]):
            for category, label in (
                ("coax_return", "coax exterior"),
                ("dedicated_vertical", "vertical CP"),
                ("angled", "best angled CP"),
            ):
                row = _best_ranked(
                    rankings,
                    device=device_id,
                    family="elevated_tree",
                    feed_height=feed_height,
                    category=category,
                )
                selected = (
                    f"{row['return_length_ft']:g} ft vertical"
                    if row["return_azimuth_deg"] is None
                    else f"{row['return_length_ft']:g} ft @ {row['return_azimuth_deg']:g}°"
                )
                lines.append(
                    f"| {device_id.upper()} | {feed_height:g} ft | {label} | {selected} | {row['likely_match_band_count']}/{row['supported_comparison_band_count']} | {100 * row['geometric_mean_efficiency']:.1f}% | {100 * row['worst_band_efficiency']:.1f}% |"
                )

    lines += [
        "",
        "## The 20-to-40 ft sloper and carbon-fiber mast",
        "",
        "The radiator slopes gently upward from the 20 ft feedpoint to the 40 ft far end. The coax drops vertically to 0.5 ft. For each mast condition, the table selects the strongest multi-band angled counterpoise separately; this is useful as a deployment recommendation, but `case_rankings.csv` also permits exact same-geometry mast comparisons.",
        "",
        "| radio | mast model | return | selected CP | likely matches | geometric mean | worst band |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    mast_conditions = extension["carbon_mast"]["conditions"]
    for device_id in base["devices"]:
        for mast_id, mast in mast_conditions.items():
            for category, label in (
                ("coax_return", "coax exterior"),
                ("dedicated_vertical", "vertical CP"),
                ("angled", "best angled CP"),
            ):
                row = _best_ranked(
                    rankings,
                    device=device_id,
                    family="sloper_20_to_40",
                    mast=mast_id,
                    category=category,
                )
                selected = (
                    f"{row['return_length_ft']:g} ft vertical"
                    if row["return_azimuth_deg"] is None
                    else f"{row['return_length_ft']:g} ft @ {row['return_azimuth_deg']:g}°"
                )
                lines.append(
                    f"| {device_id.upper()} | {mast['label']} | {label} | {selected} | {row['likely_match_band_count']}/{row['supported_comparison_band_count']} | {100 * row['geometric_mean_efficiency']:.1f}% | {100 * row['worst_band_efficiency']:.1f}% |"
                )

    delta_lookup = {
        (row["device"], row["return_kind"], row["mast_condition"]): row
        for row in mast_deltas
    }
    lines += [
        "",
        "### Exact same-geometry mast penalty",
        "",
        "These cells show **geometric-mean / worst-band dB change** relative to the no-mast optimum while holding the return geometry fixed. Thus they isolate mast interaction instead of granting each mast a newly optimized counterpoise.",
        "",
        "| return geometry | mast model | KX2 | KX3 | KH1 |",
        "|---|---|---:|---:|---:|",
    ]
    return_labels = {
        "coax_return": "19.5 ft vertical coax exterior",
        "dedicated_vertical": "19.5 ft vertical copper CP",
        "dedicated_angled": "no-mast-optimum angled CP",
    }
    for category, label in return_labels.items():
        for mast_id, mast in mast_conditions.items():
            if mast_id == "none":
                continue
            cells = []
            for device_id in ("kx2", "kx3", "kh1"):
                row = delta_lookup[(device_id, category, mast_id)]
                cells.append(
                    f"{row['geometric_mean_delta_db']:+.2f} / {row['worst_band_delta_db']:+.2f} dB"
                )
            lines.append(f"| {label} | {mast['label']} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Interpretation and limits",
        "",
        "A dedicated counterpoise need not be resonant, and no single length is best on every band. Length changes both feedpoint impedance and the tuner/coax loss budget; use the per-band optima as evidence of sensitivity, not as quarter-wave cutting instructions.",
        "",
        "The continuous-carbon cases deliberately bracket a strong interaction. Published CFRP longitudinal conductivity spans roughly 5e3 to 5e4 S/m, but a real telescoping mast is tapered, anisotropic, resin-rich, and may have electrically discontinuous joints. The NEC mast is a uniform, continuous floating wire, so an actual mast measurement can land anywhere between 'almost absent' and these modeled cases.",
        "",
        "The coax exterior and differential transmission line are represented separately; their mutual mode conversion is not solved. Chokes are ideal common-mode boundaries plus insertion loss. Trees, wet bark, the transformer enclosure, the operator, and mast hardware are omitted. Efficiency is not gain or takeoff angle.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "uv run antenna-lab run-efrw-elevated-study --config configs/53ft-efrw-elevated-v1.json --output results/53ft-efrw-elevated-v1 --nec2c /path/to/nec2c",
        "uv run antenna-lab verify-results results/53ft-efrw-elevated-v1",
        "```",
        "",
        "## Sources",
        "",
    ]
    sources = {**base.get("sources", {}), **extension.get("sources", {})}
    lines += [f"- [{name}]({url})" for name, url in sources.items()]
    return "\n".join(lines) + "\n"


def run_efrw_elevated_study(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    nec2c: str | Path | None = None,
    cache_dir: str | Path = Path("build/53ft-efrw-elevated-nec-cache"),
    jobs: int | None = None,
) -> dict[str, Any]:
    config_path = Path(config_path)
    output_dir = Path(output_dir)
    cache_dir = Path(cache_dir)
    extension, base = load_elevated_config(config_path)
    cases = build_cases(extension, base)
    executable = find_nec2c(nec2c)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    job_count = jobs or max(1, min(8, os.cpu_count() or 1))

    nec_rows = _run_nec_cases(extension, base, cases, cache_dir, executable, job_count)
    system_rows = _system_rows(base, nec_rows)
    rankings = _rank_case_groups(extension, base, cases, system_rows)
    optima = _band_optima(base, cases, system_rows)
    mast_deltas = _same_geometry_mast_deltas(extension, base, rankings)
    summary = {
        "study_id": extension["study_id"],
        "geometry_case_count": len(cases),
        "nec_case_count": len(nec_rows),
        "system_row_count": len(system_rows),
        "canonical_case": {
            "ground": extension["ground"],
            "hardware_loss_envelope": "best",
            "tuner_loss_envelope": "nominal",
            "tuner_objective": "lowest-loss state meeting 2.5:1",
        },
        "comparison_bands": extension["comparison_bands"],
    }

    _write_csv(output_dir / "geometry_cases.csv", cases)
    _write_csv(output_dir / "nec_loads.csv", nec_rows)
    _write_csv(output_dir / "system_results.csv", system_rows)
    _write_csv(output_dir / "case_rankings.csv", rankings)
    _write_csv(output_dir / "counterpoise_band_optima.csv", optima)
    _write_csv(output_dir / "same_geometry_mast_deltas.csv", mast_deltas)
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(
        _report(extension, base, rankings, optima, mast_deltas), encoding="utf-8"
    )
    _write_json(
        output_dir / "run_metadata.json",
        {
            **summary,
            "solver": _solver_version(executable),
            "solver_sha256": _sha256(executable),
            "config": str(config_path),
            "config_sha256": _sha256(config_path),
            "base_config_sha256": _sha256(config_path.parent / extension["base_config"]),
            "source_sha256": _sha256(Path(__file__)),
            "nec_source_sha256": _sha256(Path(__file__).with_name("nec.py")),
            "cache_directory": str(cache_dir),
        },
    )
    _write_manifest(output_dir)
    return summary
