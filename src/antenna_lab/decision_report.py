"""Generate the durable KH1 portable-system decision package."""

# Report prose and Markdown tables intentionally exceed the Python line limit.
# ruff: noqa: E501

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from antenna_lab.comparative_systems import REQUIRED_BANDS, _read_typed_csv
from antenna_lab.optimization import write_manifest
from antenna_lab.portable_systems import _write_csv


def run_final_decision(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    objective = config["objective"]
    inputs = {key: Path(value) for key, value in config["inputs"].items()}
    rows = [
        row
        for row in _read_typed_csv(inputs["comparative"] / "candidate_aggregates.csv")
        if row["objective"] == objective
    ]
    by_id = {row["candidate_id"]: row for row in rows}
    non_reference = [row for row in rows if row["family"] != "linked_dipole_reference"]
    eligible = [row for row in non_reference if _match_safe(row, config)]
    rankings = _rankings(rows, non_reference, eligible, by_id, config)
    pareto = _pareto_shortlist(rows, config)

    finalist_specs = {row["candidate_id"]: row for row in config["finalists"]}
    scenario_rows = _load_finalist_scenarios(inputs, finalist_specs, objective)
    representative = _representative_rows(scenario_rows, finalist_specs)
    breakdown = [
        _power_budget(row, finalist_specs[row["candidate_id"]])
        for row in representative
    ]
    sensitivity = _band_sensitivity(scenario_rows)
    operator_priority = _operator_priority_rankings(
        scenario_rows, config["operator_profile"]
    )
    recommended_id = config["recommended_candidate_id"]
    factor_sensitivity = _factor_sensitivity(
        scenario_rows, recommended_id, config["operator_profile"]
    )
    percentile_scenarios = _percentile_scenarios(
        scenario_rows, recommended_id, config["operator_profile"]
    )
    complexity = [
        {
            **{
                key: by_id[candidate_id][key]
                for key in (
                    "candidate_id",
                    "family",
                    "total_wire_ft",
                    "component_count",
                    "support_count",
                    "band_changes_touch_antenna",
                    "packed_complexity",
                )
            },
            "label": specification["label"],
            "weight_class": specification["weight_class"],
            "tangle_risk": specification["tangle_risk"],
            "notes": specification["notes"],
        }
        for candidate_id, specification in finalist_specs.items()
    ]
    sacrifice = _linked_sacrifice(breakdown, by_id, recommended_id)
    family_winners = _family_winners(rows)
    failures = _failure_rows(by_id, inputs)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "rankings.csv", rankings)
    _write_csv(output_dir / "pareto_shortlist.csv", pareto)
    _write_csv(output_dir / "family_winners.csv", family_winners)
    _write_csv(output_dir / "finalist_band_breakdown.csv", breakdown)
    _write_csv(output_dir / "finalist_band_sensitivity.csv", sensitivity)
    _write_csv(output_dir / "operator_priority_rankings.csv", operator_priority)
    _write_csv(output_dir / "recommended_factor_sensitivity.csv", factor_sensitivity)
    _write_csv(
        output_dir / "recommended_percentile_scenarios.csv", percentile_scenarios
    )
    _write_csv(output_dir / "deployment_complexity.csv", complexity)
    _write_csv(output_dir / "linked_reference_sacrifice.csv", sacrifice["by_band"])
    _write_csv(output_dir / "failed_family_sentinels.csv", failures)

    summary = {
        "study_id": config["study_id"],
        "objective": objective,
        "efficiency_reference_plane": (
            "radiated RF power / transmitter-available RF power immediately before ATU"
        ),
        "recommended_overall": by_id[recommended_id],
        "best_non_reference_robust": by_id["direct-52r-28c-z4"],
        "absolute_winner": by_id["linked-dipole-five-band"],
        "legacy_41_17": by_id["direct-41r-17c-z1"],
        "linked_reference_sacrifice": sacrifice["aggregate"],
        "operator_profile": config["operator_profile"],
        "operator_priority_rankings": operator_priority,
        "rankings": rankings,
        "artifacts": config["artifacts"],
        "warnings": [
            "Sensitivity cases are equal-weight envelopes, not probability distributions.",
            "The >2.5 SWR rollback flag is a conservative engineering flag, not a published Elecraft threshold.",
            "Transformer/choke losses are source-backed dB envelopes, not measurements of the proposed hardware.",
            "KHATU1 bank values are secondary-source corroborated and retain a wider sensitivity profile.",
            "Qualitative weight and tangle classes are engineering judgments; no hardware mass was measured.",
            "The linked-counterpoise model assumes a zero-loss closed contact and a clean open; coupling to a nearby disconnected tail is not modeled.",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    metadata = {
        "study_id": config["study_id"],
        "config": str(config_path),
        "config_sha256": _sha256(config_path),
        "input_sha256": {
            "candidate_aggregates": _sha256(
                inputs["comparative"] / "candidate_aggregates.csv"
            ),
            "portable_scenarios": _sha256(
                inputs["portable"] / "system_band_scenarios.csv"
            ),
            "doublet_scenarios": _sha256(
                inputs["comparative"] / "doublet_band_scenarios.csv"
            ),
            "linked_scenarios": _sha256(
                inputs["comparative"] / "linked_reference_band_scenarios.csv"
            ),
            "linked_counterpoise_scenarios": _sha256(
                inputs["comparative"] / "linked_counterpoise_band_scenarios.csv"
            ),
        },
        "source_sha256": _sha256(Path(__file__)),
        "artifacts": config["artifacts"],
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "REPORT.md").write_text(
        _report(
            summary,
            family_winners,
            failures,
            percentile_scenarios,
        ),
        encoding="utf-8",
    )
    write_manifest(output_dir)
    return summary


def _rankings(rows, non_reference, eligible, by_id, config):
    best_worst = max(eligible, key=lambda row: row["worst_band_final_efficiency_p50"])
    robust = max(eligible, key=lambda row: row["worst_band_final_efficiency_p10"])
    median = max(eligible, key=lambda row: row["median_final_efficiency"])
    no_switch = max(
        (row for row in eligible if not row["band_changes_touch_antenna"]),
        key=lambda row: row["worst_band_final_efficiency_p10"],
    )
    smallest = min(
        (
            row
            for row in eligible
            if row["worst_band_final_efficiency_p10"]
            >= config["useful_efficiency_threshold"]
        ),
        key=lambda row: (row["total_wire_ft"], -row["worst_band_final_efficiency_p10"]),
    )
    absolute = max(rows, key=lambda row: row["worst_band_final_efficiency_p10"])
    choices = (
        (
            "best_worst_band_non_reference",
            best_worst,
            "maximize median-case worst band among match-safe non-reference systems",
        ),
        (
            "best_robust_lower_tail",
            robust,
            "maximize p10 worst-band efficiency among match-safe non-reference systems",
        ),
        (
            "best_median",
            median,
            "maximize five-band median among match-safe non-reference systems",
        ),
        (
            "best_no_band_switching",
            no_switch,
            "maximize robust efficiency without touching the antenna on band changes",
        ),
        (
            "smallest_above_threshold",
            smallest,
            f"minimum wire with p10 >= {config['useful_efficiency_threshold']:.0%} and match-safe",
        ),
        (
            "absolute_efficiency_winner",
            absolute,
            "include the resonant linked-dipole reference and physical band changes",
        ),
        (
            "recommended_overall",
            by_id[config["recommended_candidate_id"]],
            "best fit for the operator's 40/20-first weighting with one 17 m link change",
        ),
    )
    return [
        {
            "rank": index,
            "category": category,
            "candidate_id": row["candidate_id"],
            "family": row["family"],
            "worst_band_final_efficiency_p10": row["worst_band_final_efficiency_p10"],
            "worst_band_final_efficiency_p50": row["worst_band_final_efficiency_p50"],
            "median_final_efficiency": row["median_final_efficiency"],
            "total_wire_ft": row["total_wire_ft"],
            "all_band_target_fraction": row["all_band_target_fraction"],
            "rollback_fraction": row["rollback_fraction"],
            "reason": reason,
        }
        for index, (category, row, reason) in enumerate(choices, 1)
    ]


def _pareto_shortlist(rows, config):
    eligible = [
        row
        for row in rows
        if row["family"] == "linked_dipole_reference" or _match_safe(row, config)
    ]
    frontier = []
    for candidate in eligible:
        if any(
            _dominates(other, candidate) for other in eligible if other is not candidate
        ):
            continue
        frontier.append(candidate)
    family_ids = {
        max(
            (row for row in rows if row["family"] == family),
            key=lambda row: row["worst_band_final_efficiency_p10"],
        )["candidate_id"]
        for family in {row["family"] for row in rows}
    }
    selected = {
        row["candidate_id"]: {
            **row,
            "pareto": True,
            "selection_reason": "nondominated efficiency/wire tradeoff",
        }
        for row in frontier
    }
    for row in rows:
        if row["candidate_id"] in family_ids and row["candidate_id"] not in selected:
            selected[row["candidate_id"]] = {
                **row,
                "pareto": False,
                "selection_reason": "best lower-tail result in candidate family",
            }
    return sorted(
        selected.values(),
        key=lambda row: (-row["worst_band_final_efficiency_p10"], row["total_wire_ft"]),
    )


def _dominates(left, right):
    values_left = (
        -left["total_wire_ft"],
        left["worst_band_final_efficiency_p10"],
        left["worst_band_final_efficiency_p50"],
        left["median_final_efficiency"],
    )
    values_right = (
        -right["total_wire_ft"],
        right["worst_band_final_efficiency_p10"],
        right["worst_band_final_efficiency_p50"],
        right["median_final_efficiency"],
    )
    return all(a >= b for a, b in zip(values_left, values_right, strict=True)) and any(
        a > b for a, b in zip(values_left, values_right, strict=True)
    )


def _load_finalist_scenarios(inputs, finalists, objective):
    sources = {
        "portable": inputs["portable"] / "system_band_scenarios.csv",
        "doublet": inputs["comparative"] / "doublet_band_scenarios.csv",
        "linked_reference": inputs["comparative"]
        / "linked_reference_band_scenarios.csv",
        "linked_counterpoise": inputs["comparative"]
        / "linked_counterpoise_band_scenarios.csv",
    }
    ids_by_source = defaultdict(set)
    for candidate_id, specification in finalists.items():
        ids_by_source[specification["source"]].add(candidate_id)
    rows = []
    for source, candidate_ids in ids_by_source.items():
        with sources[source].open(newline="", encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                if (
                    raw["candidate_id"] in candidate_ids
                    and raw["objective"] == objective
                ):
                    rows.append({key: _coerce(value) for key, value in raw.items()})
    return rows


def _representative_rows(rows, finalists):
    selected = []
    for candidate_id, specification in finalists.items():
        filters = specification["representative"]
        for band in REQUIRED_BANDS:
            matches = [
                row
                for row in rows
                if row["candidate_id"] == candidate_id
                and row["band"] == band
                and all(str(row.get(key)) == value for key, value in filters.items())
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Expected one representative row for {candidate_id}/{band}; got {len(matches)}"
                )
            selected.append(matches[0])
    return selected


def _power_budget(row, specification):
    raw_r = row.get("antenna_resistance_ohm", row["raw_resistance_ohm"])
    raw_x = row.get("antenna_reactance_ohm", row["raw_reactance_ohm"])
    tuner_r = row.get("tuner_load_resistance_ohm", row["raw_resistance_ohm"])
    tuner_x = row.get("tuner_load_reactance_ohm", row["raw_reactance_ohm"])
    feedline_efficiency = row.get("feedline_efficiency", 1.0)
    mismatch_loss = -10.0 * math.log10(row["residual_mismatch_efficiency"])
    return {
        "candidate_id": row["candidate_id"],
        "label": specification["label"],
        "band": row["band"],
        "frequency_hz": row["frequency_hz"],
        "scenario": "representative nominal",
        "raw_resistance_ohm": raw_r,
        "raw_reactance_ohm": raw_x,
        "raw_swr_50ohm": _swr(complex(raw_r, raw_x)),
        "tuner_plane_resistance_ohm": tuner_r,
        "tuner_plane_reactance_ohm": tuner_x,
        "tuner_plane_raw_swr": _swr(complex(tuner_r, tuner_x)),
        "nec_radiation_efficiency": row["nec_efficiency"],
        "nec_loss_db": -10.0 * math.log10(row["nec_efficiency"]),
        "transformer_loss_db": row["transformer_loss_db"],
        "choke_loss_db": row["choke_loss_db"],
        "feedline_loss_db": -10.0 * math.log10(feedline_efficiency),
        "tuner_internal_loss_db": row["tuner_loss_db"],
        "residual_input_swr": row["input_swr"],
        "residual_mismatch_efficiency": row["residual_mismatch_efficiency"],
        "residual_mismatch_loss_db": mismatch_loss,
        "topology": row["topology"],
        "l_mask": row["l_mask"],
        "c_mask": row["c_mask"],
        "inductance_uH": row["inductance_uH"],
        "capacitance_pF": row["capacitance_pF"],
        "final_efficiency": row["final_efficiency"],
        "total_loss_db": row["total_loss_db"],
        "likely_power_rollback": row["likely_power_rollback"],
    }


def _band_sensitivity(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["candidate_id"], row["band"])].append(row)
    result = []
    for (candidate_id, band), subset in grouped.items():
        efficiencies = [row["final_efficiency"] for row in subset]
        result.append(
            {
                "candidate_id": candidate_id,
                "band": band,
                "scenario_count": len(subset),
                "final_efficiency_p10": _quantile(efficiencies, 0.1),
                "final_efficiency_p50": _quantile(efficiencies, 0.5),
                "final_efficiency_p90": _quantile(efficiencies, 0.9),
                "swr_le_1p5_fraction": float(
                    np.mean([row["input_swr"] <= 1.5 for row in subset])
                ),
                "swr_le_2p5_fraction": float(
                    np.mean([row["input_swr"] <= 2.5 for row in subset])
                ),
                "rollback_fraction": float(
                    np.mean([row["likely_power_rollback"] for row in subset])
                ),
            }
        )
    return sorted(
        result, key=lambda row: (row["candidate_id"], REQUIRED_BANDS.index(row["band"]))
    )


SCENARIO_FIELDS = (
    "deployment",
    "ground",
    "conductor",
    "profile",
    "tuner_loss_envelope",
    "component_loss_envelope",
)


def _scenario_groups(rows, candidate_id):
    grouped = defaultdict(dict)
    for row in rows:
        if row["candidate_id"] == candidate_id:
            key = tuple(row.get(field, "") for field in SCENARIO_FIELDS)
            grouped[key][row["band"]] = row
    return [
        (key, by_band)
        for key, by_band in grouped.items()
        if all(band in by_band for band in REQUIRED_BANDS)
    ]


def _operator_scenarios(rows, candidate_id, profile):
    weights = profile["band_weights"]
    total_weight = sum(weights.values())
    result = []
    for key, by_band in _scenario_groups(rows, candidate_id):
        result.append(
            {
                **dict(zip(SCENARIO_FIELDS, key, strict=True)),
                "weighted_final_efficiency": sum(
                    weights[band] * by_band[band]["final_efficiency"]
                    for band in REQUIRED_BANDS
                )
                / total_weight,
                "must_band_efficiency_floor": min(
                    by_band[band]["final_efficiency"] for band in profile["must_bands"]
                ),
                "must_bands_match": all(
                    by_band[band]["input_swr"] <= profile["must_match_swr"]
                    for band in profile["must_bands"]
                ),
                "all_bands_match": all(
                    by_band[band]["input_swr"] <= profile["must_match_swr"]
                    for band in REQUIRED_BANDS
                ),
                "by_band": by_band,
            }
        )
    return result


def _operator_priority_rankings(rows, profile):
    result = []
    for candidate_id in sorted({row["candidate_id"] for row in rows}):
        scenarios = _operator_scenarios(rows, candidate_id, profile)
        if not scenarios:
            continue
        weighted = [row["weighted_final_efficiency"] for row in scenarios]
        must_floor = [row["must_band_efficiency_floor"] for row in scenarios]
        result.append(
            {
                "candidate_id": candidate_id,
                "scenario_count": len(scenarios),
                "weighted_efficiency_p10": _quantile(weighted, 0.1),
                "weighted_efficiency_p50": _quantile(weighted, 0.5),
                "weighted_efficiency_p90": _quantile(weighted, 0.9),
                "must_band_floor_p10": _quantile(must_floor, 0.1),
                "must_band_floor_p50": _quantile(must_floor, 0.5),
                "must_band_floor_p90": _quantile(must_floor, 0.9),
                "must_band_match_fraction": float(
                    np.mean([row["must_bands_match"] for row in scenarios])
                ),
                "all_band_match_fraction": float(
                    np.mean([row["all_bands_match"] for row in scenarios])
                ),
            }
        )
    ordered = sorted(
        result,
        key=lambda row: (
            -row["must_band_match_fraction"],
            -row["weighted_efficiency_p10"],
            -row["must_band_floor_p10"],
        ),
    )
    return [{"rank": index, **row} for index, row in enumerate(ordered, 1)]


def _factor_sensitivity(rows, candidate_id, profile):
    scenarios = _operator_scenarios(rows, candidate_id, profile)
    result = []
    for factor in SCENARIO_FIELDS:
        levels = sorted({str(row[factor]) for row in scenarios})
        for level in levels:
            subset = [
                row["weighted_final_efficiency"]
                for row in scenarios
                if str(row[factor]) == level
            ]
            result.append(
                {
                    "factor": factor,
                    "level": level,
                    "scenario_count": len(subset),
                    "weighted_efficiency_p10": _quantile(subset, 0.1),
                    "weighted_efficiency_p50": _quantile(subset, 0.5),
                    "weighted_efficiency_p90": _quantile(subset, 0.9),
                    "weighted_efficiency_mean": float(np.mean(subset)),
                }
            )
    return result


def _percentile_scenarios(rows, candidate_id, profile):
    scenarios = _operator_scenarios(rows, candidate_id, profile)
    values = [row["weighted_final_efficiency"] for row in scenarios]
    result = []
    for label, probability in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9)):
        target = _quantile(values, probability)
        selected = min(
            scenarios,
            key=lambda row: abs(row["weighted_final_efficiency"] - target),
        )
        record = {
            "percentile": label,
            **{field: selected[field] for field in SCENARIO_FIELDS},
            "weighted_final_efficiency": selected["weighted_final_efficiency"],
            "must_band_efficiency_floor": selected["must_band_efficiency_floor"],
        }
        for band in REQUIRED_BANDS:
            record[f"{band}_final_efficiency"] = selected["by_band"][band][
                "final_efficiency"
            ]
            record[f"{band}_input_swr"] = selected["by_band"][band]["input_swr"]
        result.append(record)
    return result


def _linked_sacrifice(breakdown, by_id, recommended_id):
    reference = {
        row["band"]: row
        for row in breakdown
        if row["candidate_id"] == "linked-dipole-five-band"
    }
    recommended = {
        row["band"]: row for row in breakdown if row["candidate_id"] == recommended_id
    }
    by_band = []
    for band in REQUIRED_BANDS:
        ratio = (
            recommended[band]["final_efficiency"] / reference[band]["final_efficiency"]
        )
        by_band.append(
            {
                "band": band,
                "linked_final_efficiency": reference[band]["final_efficiency"],
                "recommended_final_efficiency": recommended[band]["final_efficiency"],
                "relative_power_fraction": ratio,
                "relative_sacrifice_fraction": 1.0 - ratio,
                "deficit_db": -10.0 * math.log10(ratio),
            }
        )
    robust_ratio = (
        by_id[recommended_id]["worst_band_final_efficiency_p10"]
        / by_id["linked-dipole-five-band"]["worst_band_final_efficiency_p10"]
    )
    return {
        "by_band": by_band,
        "aggregate": {
            "robust_relative_power_fraction": robust_ratio,
            "robust_relative_sacrifice_fraction": 1.0 - robust_ratio,
            "robust_deficit_db": -10.0 * math.log10(robust_ratio),
        },
    }


def _family_winners(rows):
    return sorted(
        (
            max(
                (row for row in rows if row["family"] == family),
                key=lambda row: row["worst_band_final_efficiency_p10"],
            )
            for family in {row["family"] for row in rows}
        ),
        key=lambda row: -row["worst_band_final_efficiency_p10"],
    )


def _failure_rows(by_id, inputs):
    failures = [
        by_id[candidate_id]
        for candidate_id in (
            "direct-41r-17c-z1",
            "efhw-62ft-f0.01-z49",
            "trap-60ft-20m-traps-z1",
            "doublet-58r-32l",
        )
    ]
    coarse = _read_typed_csv(inputs["coarse"] / "system_candidates.csv")
    fan = max(
        (
            row
            for row in coarse
            if row["family"] == "fan_dipole"
            and row["objective"] == "lowest_loss_swr_2p5"
        ),
        key=lambda row: row["worst_band_final_efficiency_p10"],
    )
    return failures + [fan]


def _match_safe(row, config):
    return (
        row["all_band_target_fraction"] >= config["match_safe_all_band_fraction"]
        and row["rollback_fraction"] <= config["match_safe_rollback_fraction"]
    )


def _report(summary, family_winners, failures, percentile_scenarios):
    recommended = summary["recommended_overall"]
    robust = summary["best_non_reference_robust"]
    reference = summary["absolute_winner"]
    legacy = summary["legacy_41_17"]
    sacrifice = summary["linked_reference_sacrifice"]
    operator = next(
        row
        for row in summary["operator_priority_rankings"]
        if row["candidate_id"] == recommended["candidate_id"]
    )
    lines = [
        "# KH1 portable antenna system decision",
        "",
        "## Executive summary",
        "",
        f"**Absolute winner:** the resonant linked dipole at {reference['worst_band_final_efficiency_p10']:.1%} p10 worst-band efficiency; it needs link changes for every band.",
        "",
        f"**Best no-touch system:** 52/28 ft through a 4:1 transformer at {robust['worst_band_final_efficiency_p10']:.1%} p10 and {robust['worst_band_final_efficiency_p50']:.1%} p50 worst-band efficiency.",
        "",
        f"**Recommended for this operator:** a direct-fed 41 ft radiator + 28 ft counterpoise, opened at 14 ft only on 17 m. It achieves {recommended['worst_band_final_efficiency_p10']:.1%} p10 worst-band efficiency and {recommended['all_band_target_fraction']:.0%} all-band success at 2.5:1.",
        "",
        f"For weights 40/20 = 5, 30 = 3, and 17/15 = 2, weighted p10/p50/p90 efficiency is {operator['weighted_efficiency_p10']:.1%}/{operator['weighted_efficiency_p50']:.1%}/{operator['weighted_efficiency_p90']:.1%}. The 40/20 efficiency floor is {operator['must_band_floor_p10']:.1%}/{operator['must_band_floor_p50']:.1%}/{operator['must_band_floor_p90']:.1%}, with {operator['must_band_match_fraction']:.0%} modeled match success on those must bands.",
        "",
        f"Relative to the resonant reference, the recommendation retains {sacrifice['robust_relative_power_fraction']:.1%} of robust radiated power, a {sacrifice['robust_deficit_db']:.2f} dB deficit.",
        "",
        f"**Legacy 41/17:** rejected: {legacy['all_band_target_fraction']:.0%} all-band success at 2.5:1 and {legacy['rollback_fraction']:.1%} rollback flags.",
        "",
        "## What p10, p50, and p90 physically look like",
        "",
        "These are points in an equal-weight engineering sensitivity set, not weather probabilities. P10 means only 10% of modeled cases scored lower; p50 is the middle case; p90 means 90% scored lower.",
        "",
        "| Case | Deployment | Ground | Wire | Tuner profile/loss | Weighted | 40 m | 30 m | 20 m | 17 m | 15 m |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in percentile_scenarios:
        lines.append(
            f"| {row['percentile']} | {row['deployment']} | {row['ground']} | {row['conductor']} | {row['profile']}/{row['tuner_loss_envelope']} | {row['weighted_final_efficiency']:.1%} | {row['40m_final_efficiency']:.1%} | {row['30m_final_efficiency']:.1%} | {row['20m_final_efficiency']:.1%} | {row['17m_final_efficiency']:.1%} | {row['15m_final_efficiency']:.1%} |"
        )
    lines.extend(
        [
            "",
            "The low tail is a combination, not a single poor-ground switch. Conductor resistance and the conservative KHATU1 loss envelope are usually the largest modeled penalties. Deployment and ground also change the impedance presented to the tuner. Poor soil is not automatically the worst case because an impedance shift can reduce tuner loss even while earth loss increases.",
            "",
            "## Why counterpoise length still matters",
            "",
            "The counterpoise is the other half of the RF circuit, not an ideal zero-ohm ground. It carries current, radiates, and couples capacitively to earth. On 17 m, 28 ft is about one-half wavelength while 14 ft is about one-quarter wavelength, so opening the link substantially changes current phase and feed impedance. Earth coupling shifts and damps that behavior; it does not erase electrical length.",
            "",
            "The model places the counterpoise close to real ground rather than bonding it to earth. A disconnected outer tail is a clean open in the model. In the field, separate and stow that tail away from the active 14 ft section; folding it alongside the active wire creates a coupled stub not represented here.",
            "",
            "## Family screen",
            "",
            "| Family | Winner | p10 worst-band | p50 worst-band | Median | All-band <=2.5 | Rollback |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in family_winners:
        lines.append(
            f"| {row['family']} | `{row['candidate_id']}` | {row['worst_band_final_efficiency_p10']:.1%} | {row['worst_band_final_efficiency_p50']:.1%} | {row['median_final_efficiency']:.1%} | {row['all_band_target_fraction']:.1%} | {row['rollback_fraction']:.1%} |"
        )
    lines.extend(["", "## What failed", ""])
    for row in failures:
        lines.append(
            f"- `{row['candidate_id']}`: {row['worst_band_final_efficiency_p10']:.1%} p10 worst-band, {row['all_band_target_fraction']:.1%} all-band <=2.5, {row['rollback_fraction']:.1%} rollback flags."
        )
    lines.extend(
        [
            "",
            "The EFHW result applies to the modeled compact 49:1 implementation, not every EFHW. Fan and trap entries are coarse sentinels, not impossibility proofs.",
            "",
            "## Build next",
            "",
            "Build 41 ft of radiator and 28 ft of counterpoise with a low-resistance connector or banana-plug break 14 ft from the feed. Leave it closed on 40/30/20/15 and open it only on 17 m. Add strain relief and physically separate the open outer tail. No 4:1 transformer is part of this recommendation.",
            "",
            "## Physical validation plan",
            "",
            "1. Measure raw R+jX at the antenna and tuner planes with the 28 ft link closed and the 14 ft link open, tuner bypassed.",
            "2. Repeat ground-side, ground-collinear, table-side, and table-collinear deployments over poor and average ground; record heights, soil, weather, routing, and conductor.",
            "3. Record KH1 L/C/Z states, residual SWR, tune power, and power fallback on all five bands.",
            "4. Compare closed versus open contact resistance and test the open tail both separated and folded nearby to measure the coupling omitted by the model.",
            "5. Run paired field-strength or WSPR tests against a resonant linked dipole without moving the support or receiver.",
            "6. Replace model envelopes with measurements and accept the build only if 40/20 always meet the operational match threshold and all five bands remain usable.",
            "",
            "## Reproduce",
            "",
            "```sh",
            "PYTHONPATH=src uv run antenna-lab run-kh1-comparative-study \\",
            "  --nec-artifact build/upstream-artifacts-31750551947 \\",
            "  --portable-study build/kh1-portable-refine-v1 \\",
            "  --output build/kh1-portable-comparative-v1",
            "PYTHONPATH=src uv run antenna-lab run-kh1-final-decision \\",
            "  --config configs/kh1-portable-final-v1.json \\",
            "  --output results/kh1-portable-final-v1",
            "uv run antenna-lab verify-results results/kh1-portable-final-v1",
            "```",
            "",
            "## Interpretation limits",
            "",
            "Quantiles are equal-weight engineering sensitivities, not probabilities. The 2.5:1 rollback flag is conservative, not an Elecraft-published trip point. Ground/common-mode behavior and the open link are simplified; connector loss, people, wet foliage, and coupled-tail routing require field validation.",
            "",
            "See the adjacent CSV files for rankings, per-band p10/p50/p90, representative power budgets, factor sensitivity, percentile scenarios, complexity, and linked-reference delta.",
        ]
    )
    return "\n".join(lines) + "\n"


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


def _swr(impedance: complex) -> float:
    gamma = abs((impedance - 50.0) / (impedance + 50.0))
    return (1.0 + gamma) / (1.0 - gamma)


def _quantile(values, probability):
    return float(np.quantile(np.asarray(values, dtype=float), probability))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
