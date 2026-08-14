"""Generate the durable KH1 portable-system decision package."""

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
        for row in _read_typed_csv(
            inputs["comparative"] / "candidate_aggregates.csv"
        )
        if row["objective"] == objective
    ]
    by_id = {row["candidate_id"]: row for row in rows}
    non_reference = [
        row for row in rows if row["family"] != "linked_dipole_reference"
    ]
    eligible = [row for row in non_reference if _match_safe(row, config)]
    rankings = _rankings(rows, non_reference, eligible, by_id, config)
    pareto = _pareto_shortlist(rows, config)

    finalist_specs = {row["candidate_id"]: row for row in config["finalists"]}
    scenario_rows = _load_finalist_scenarios(inputs, finalist_specs, objective)
    representative = _representative_rows(scenario_rows, finalist_specs)
    breakdown = [_power_budget(row, finalist_specs[row["candidate_id"]]) for row in representative]
    sensitivity = _band_sensitivity(scenario_rows)
    complexity = [
        {
            **{key: by_id[candidate_id][key] for key in (
                "candidate_id", "family", "total_wire_ft", "component_count",
                "support_count", "band_changes_touch_antenna", "packed_complexity",
            )},
            "label": specification["label"],
            "weight_class": specification["weight_class"],
            "tangle_risk": specification["tangle_risk"],
            "notes": specification["notes"],
        }
        for candidate_id, specification in finalist_specs.items()
    ]
    sacrifice = _linked_sacrifice(breakdown, by_id)
    family_winners = _family_winners(rows)
    failures = _failure_rows(by_id, inputs)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "rankings.csv", rankings)
    _write_csv(output_dir / "pareto_shortlist.csv", pareto)
    _write_csv(output_dir / "family_winners.csv", family_winners)
    _write_csv(output_dir / "finalist_band_breakdown.csv", breakdown)
    _write_csv(output_dir / "finalist_band_sensitivity.csv", sensitivity)
    _write_csv(output_dir / "deployment_complexity.csv", complexity)
    _write_csv(output_dir / "linked_reference_sacrifice.csv", sacrifice["by_band"])
    _write_csv(output_dir / "failed_family_sentinels.csv", failures)

    summary = {
        "study_id": config["study_id"],
        "objective": objective,
        "efficiency_reference_plane": (
            "radiated RF power / transmitter-available RF power immediately before ATU"
        ),
        "recommended_overall": by_id["direct-44r-14c-z4"],
        "best_non_reference_robust": by_id["direct-52r-28c-z4"],
        "absolute_winner": by_id["linked-dipole-five-band"],
        "legacy_41_17": by_id["direct-41r-17c-z1"],
        "linked_reference_sacrifice": sacrifice["aggregate"],
        "rankings": rankings,
        "artifacts": config["artifacts"],
        "warnings": [
            "Sensitivity cases are equal-weight envelopes, not probability distributions.",
            "The >2.5 SWR rollback flag is a conservative engineering flag, not a published Elecraft threshold.",
            "Transformer/choke losses are source-backed dB envelopes, not measurements of the proposed hardware.",
            "KHATU1 bank values are secondary-source corroborated and retain a wider sensitivity profile.",
            "Qualitative weight and tangle classes are engineering judgments; no hardware mass was measured.",
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
        },
        "source_sha256": _sha256(Path(__file__)),
        "artifacts": config["artifacts"],
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "REPORT.md").write_text(
        _report(summary, family_winners, failures), encoding="utf-8"
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
        ("best_worst_band_non_reference", best_worst, "maximize median-case worst band among match-safe non-reference systems"),
        ("best_robust_lower_tail", robust, "maximize p10 worst-band efficiency among match-safe non-reference systems"),
        ("best_median", median, "maximize five-band median among match-safe non-reference systems"),
        ("best_no_band_switching", no_switch, "maximize robust efficiency without touching the antenna on band changes"),
        ("smallest_above_threshold", smallest, f"minimum wire with p10 >= {config['useful_efficiency_threshold']:.0%} and match-safe"),
        ("absolute_efficiency_winner", absolute, "include the resonant linked-dipole reference and physical band changes"),
        ("recommended_overall", by_id["direct-44r-14c-z4"], "near-best robustness with 22 ft less wire than the non-reference winner"),
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
        if any(_dominates(other, candidate) for other in eligible if other is not candidate):
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
        row["candidate_id"]: {**row, "pareto": True, "selection_reason": "nondominated efficiency/wire tradeoff"}
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
        "linked_reference": inputs["comparative"] / "linked_reference_band_scenarios.csv",
    }
    ids_by_source = defaultdict(set)
    for candidate_id, specification in finalists.items():
        ids_by_source[specification["source"]].add(candidate_id)
    rows = []
    for source, candidate_ids in ids_by_source.items():
        with sources[source].open(newline="", encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                if raw["candidate_id"] in candidate_ids and raw["objective"] == objective:
                    rows.append({key: _coerce(value) for key, value in raw.items()})
    return rows


def _representative_rows(rows, finalists):
    selected = []
    for candidate_id, specification in finalists.items():
        filters = specification["representative"]
        for band in REQUIRED_BANDS:
            matches = [
                row for row in rows
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
                "swr_le_1p5_fraction": float(np.mean([row["input_swr"] <= 1.5 for row in subset])),
                "swr_le_2p5_fraction": float(np.mean([row["input_swr"] <= 2.5 for row in subset])),
                "rollback_fraction": float(np.mean([row["likely_power_rollback"] for row in subset])),
            }
        )
    return sorted(result, key=lambda row: (row["candidate_id"], REQUIRED_BANDS.index(row["band"])))


def _linked_sacrifice(breakdown, by_id):
    reference = {
        row["band"]: row for row in breakdown
        if row["candidate_id"] == "linked-dipole-five-band"
    }
    recommended = {
        row["band"]: row for row in breakdown
        if row["candidate_id"] == "direct-44r-14c-z4"
    }
    by_band = []
    for band in REQUIRED_BANDS:
        ratio = recommended[band]["final_efficiency"] / reference[band]["final_efficiency"]
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
        by_id["direct-44r-14c-z4"]["worst_band_final_efficiency_p10"]
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
    failures = [by_id[candidate_id] for candidate_id in (
        "direct-41r-17c-z1", "efhw-62ft-f0.01-z49",
        "trap-60ft-20m-traps-z1", "doublet-58r-32l",
    )]
    coarse = _read_typed_csv(inputs["coarse"] / "system_candidates.csv")
    fan = max(
        (row for row in coarse if row["family"] == "fan_dipole" and row["objective"] == "lowest_loss_swr_2p5"),
        key=lambda row: row["worst_band_final_efficiency_p10"],
    )
    return failures + [fan]


def _match_safe(row, config):
    return (
        row["all_band_target_fraction"] >= config["match_safe_all_band_fraction"]
        and row["rollback_fraction"] <= config["match_safe_rollback_fraction"]
    )


def _report(summary, family_winners, failures):
    recommended = summary["recommended_overall"]
    robust = summary["best_non_reference_robust"]
    reference = summary["absolute_winner"]
    legacy = summary["legacy_41_17"]
    sacrifice = summary["linked_reference_sacrifice"]
    lines = [
        "# KH1 portable antenna system decision",
        "",
        "## Executive summary",
        "",
        f"**Absolute winner:** the resonant linked dipole, at {reference['worst_band_final_efficiency_p10']:.1%} p10 worst-band final efficiency. It requires physical link changes on every band transition.",
        "",
        f"**Best no-touch system:** 52/28 ft direct radiator/counterpoise through a compact 4:1 transformer, at {robust['worst_band_final_efficiency_p10']:.1%} p10 and {robust['worst_band_final_efficiency_p50']:.1%} p50 worst-band efficiency.",
        "",
        f"**Recommended overall:** 44/14 ft with the same 4:1 interface. Its {recommended['worst_band_final_efficiency_p10']:.1%} robust result gives up only {(robust['worst_band_final_efficiency_p10']-recommended['worst_band_final_efficiency_p10']):.1%} absolute efficiency while removing 22 ft of wire.",
        "",
        f"Relative to the resonant reference, the recommendation retains {sacrifice['robust_relative_power_fraction']:.1%} of robust radiated power: a {sacrifice['robust_relative_sacrifice_fraction']:.1%} sacrifice or {sacrifice['robust_deficit_db']:.2f} dB.",
        "",
        f"**Legacy 41/17 result:** rejected. The untransformed build has {legacy['all_band_target_fraction']:.0%} all-band success at 2.5:1 and a {legacy['rollback_fraction']:.1%} rollback-flag rate.",
        "",
        "## What surprised us",
        "",
        "- A lossy 4:1 interface improves total radiated power because it moves the loads into the actual KH1 discrete network's useful range. Low transformer SWR alone was never the objective.",
        "- The balanced doublet can have a good median but a very poor lower tail; mismatch-enhanced feedline loss dominates hostile 20/17 m cases.",
        "- The direct 44/14 system is nearly tied with much longer wires once deployment, ground, conductor, transformer, tuner, and mismatch envelopes are composed.",
        "- The raw highest-median non-reference designs often miss 2.5:1. Rankings therefore require the documented match-safe gate.",
        "",
        "## Family screen",
        "",
        "| Family | Winner | p10 worst-band | p50 worst-band | Median | All-band <=2.5 | Rollback flag |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in family_winners:
        lines.append(
            f"| {row['family']} | `{row['candidate_id']}` | {row['worst_band_final_efficiency_p10']:.1%} | {row['worst_band_final_efficiency_p50']:.1%} | {row['median_final_efficiency']:.1%} | {row['all_band_target_fraction']:.1%} | {row['rollback_fraction']:.1%} |"
        )
    lines.extend([
        "",
        "## What failed",
        "",
    ])
    for row in failures:
        lines.append(
            f"- `{row['candidate_id']}`: {row['worst_band_final_efficiency_p10']:.1%} p10 worst-band, {row['all_band_target_fraction']:.1%} all-band <=2.5, {row['rollback_fraction']:.1%} rollback flag."
        )
    lines.extend([
        "",
        "The EFHW result applies to the modeled compact 49:1 implementation, not every EFHW. The fan and trap entries are coarse sentinels, sufficient to pivot effort but not universal impossibility proofs.",
        "",
        "## Build next",
        "",
        "Build the 44 ft radiator + 14 ft counterpoise with a measured 4:1 transformer and separate choke. Also retain taps or extension points for 12, 16, and 28 ft counterpoises. Measure the tuner-plane complex impedance and RF power budget before changing lengths.",
        "",
        "## Physical validation plan",
        "",
        "1. Characterize the 4:1 transformer and choke independently with calibrated two-port measurements into representative complex loads; separate mismatch from dissipation.",
        "2. Measure raw R+jX at both antenna and KH1 tuner planes for 44/12, 44/14, 44/16, and 52/28 on all five bands, with tuner bypassed.",
        "3. Repeat ground-side, ground-collinear, table-side, and table-collinear deployments over poor and average ground; record wire height, soil, weather, and conductor.",
        "4. Record KH1 L/C/Z diagnostic states, residual SWR, tune power, and any power fallback. Compare the actual state with the model's minimum-SWR and maximum-transducer states.",
        "5. Measure forward/reflected power before the tuner and delivered power after the transformer/choke with calibrated couplers; use thermal or calorimetric checks for transformer loss where feasible.",
        "6. Run paired field-strength or WSPR tests against the linked resonant dipole without moving the support or receiver, alternating frequently to suppress propagation drift.",
        "7. Update the profile and loss envelopes from measurements, rerun the committed commands, and accept the 44/14 build only if every band stays below the chosen rollback threshold in the deployment matrix.",
        "",
        "## Reproduce",
        "",
        "```sh",
        "PYTHONPATH=src uv run antenna-lab run-kh1-portable-coarse-study \\",
        "  --config configs/kh1-portable-refine-v1.json \\",
        "  --output build/kh1-portable-refine-v1 --nec2c /path/to/nec2c --jobs 8",
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
        "All quantiles are equal-weight engineering sensitivities, not probabilities. Exact KH1 L/C bank values remain secondary-source corroborated. The 2.5:1 rollback flag is conservative and not an Elecraft-published trip point. Ground and common-mode behavior are simplified NEC/system models; human coupling, wet foliage, and routing remain field-validation items.",
        "",
        "See the CSV files beside this report for the seven rankings, Pareto shortlist, per-band power budgets, deployment sensitivity, complexity, linked-reference delta, and failed sentinels.",
    ])
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
