"""Readable summaries and plots for the rigid-doublet line optimization."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


def _read_csv(path: Path) -> list[dict[str, Any]]:
    """CSV has no types; preserve labels and parse numbers and booleans."""
    rows = []
    with path.open(newline="") as stream:
        for source in csv.DictReader(stream):
            row: dict[str, Any] = {}
            for key, value in source.items():
                if value in ("True", "False"):
                    row[key] = value == "True"
                elif value in (None, ""):
                    row[key] = None
                else:
                    try:
                        row[key] = float(value)
                    except ValueError:
                        row[key] = value
            rows.append(row)
    return rows


def _key(row: dict) -> tuple[float, float, int]:
    return (
        float(row["arm_length_ft"]),
        round(float(row["length_ft"]), 7),
        int(row["balun_ratio"]),
    )


def _rank(row: dict) -> tuple:
    return (
        not row["route_feasible"],
        -row["all_band_match_fraction"],
        -row["worst_band_p10_delivery"],
        -row["band_median_geometric_mean"],
        row["length_ft"],
        row["balun_ratio"],
    )


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def _delta(value: float, baseline: float) -> str:
    if value <= 0 or baseline <= 0:
        return "—"
    return f"{10 * math.log10(value / baseline):+.2f}"


def _nominal_cell(row: dict) -> str:
    return _pct(row["delivery_efficiency"]) + ("" if row["modeled_match"] else "*")


def _rounded_length(row: dict, compact_max: float) -> str:
    if row["region"] == "long" and round(row["length_ft"]) <= compact_max:
        return f">{compact_max:g}"
    return f"{row['length_ft']:.0f}"


def _bands(config: dict) -> list[str]:
    return sorted(
        config["bands_mhz"], key=config["reference_frequencies_mhz"].__getitem__
    )


def _near_best_windows(config: dict, coarse: list[dict], winner: dict) -> str:
    group = [
        row
        for row in coarse
        if row["arm_length_ft"] == winner["arm_length_ft"]
        and row["region"] == winner["region"]
        and row["balun_ratio"] == winner["balun_ratio"]
        and row["route_feasible"]
    ]
    best = min(group, key=_rank)
    if best["worst_band_p10_delivery"] <= 0:
        return "No positive p10 window"
    eligible = sorted(
        row["length_ft"]
        for row in group
        if row["all_band_match_fraction"] >= best["all_band_match_fraction"] - 1e-9
        and row["worst_band_p10_delivery"]
        >= best["worst_band_p10_delivery"] * 10 ** (-0.2 / 10)
    )
    windows = []
    start = previous = eligible[0]
    for length in eligible[1:]:
        if length - previous > config["line_sweep_ft"]["step"] + 1e-7:
            windows.append((start, previous))
            start = length
        previous = length
    windows.append((start, previous))
    return "; ".join(
        f"{low:.2f}–{high:.2f} ft" if low != high else f"{low:.2f} ft"
        for low, high in windows
    )


def _plot(
    output: Path,
    config: dict,
    coarse: list[dict],
    chosen: list[dict],
    nominal: list[dict],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    arms = config["arm_lengths_ft"]
    bands = _bands(config)
    lookup = {(_key(row), row["band"]): row for row in nominal}
    colors = {1: "#0072B2", 4: "#D55E00"}
    with plt.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "savefig.facecolor": "white",
        }
    ):
        fig, axes = plt.subplots(2, len(arms), figsize=(13, 8.4), squeeze=False)
        for column, arm in enumerate(arms):
            ax = axes[0, column]
            for ratio in config["balun_impedance_ratios"]:
                rows = sorted(
                    (
                        r
                        for r in coarse
                        if r["arm_length_ft"] == arm and r["balun_ratio"] == ratio
                    ),
                    key=lambda r: r["length_ft"],
                )
                ax.plot(
                    [r["length_ft"] for r in rows],
                    [r["worst_band_p10_delivery"] for r in rows],
                    color=colors.get(ratio),
                    linewidth=1.8,
                    linestyle="-" if ratio == 1 else "--",
                    label=f"Fixed {ratio}:1 interface",
                )
            ax.axvline(
                10 / 0.3048,
                color="#777777",
                linestyle=":",
                linewidth=1,
                label="10 m reference",
            )
            ax.axvline(config["compact_max_line_ft"], color="#444444", linewidth=0.8)
            ax.axvspan(
                config["line_sweep_ft"]["start"],
                config["compact_max_line_ft"],
                color="#E7EEF3",
                alpha=0.45,
            )
            ax.text(
                0.03,
                0.97,
                f"Compact ≤ {config['compact_max_line_ft']:g} ft",
                transform=ax.transAxes,
                va="top",
                fontsize=9,
            )
            ax.set(
                title=f"{arm:g} ft per arm · coarse line search",
                xlabel="Balanced-line length (ft)",
                ylabel="Worst-band p10 delivery score",
                ylim=(0, 1.05),
                xlim=(
                    min(r["length_ft"] for r in coarse),
                    config["line_sweep_ft"]["stop"],
                ),
            )
            ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.grid(axis="y", alpha=0.25)
            ax.legend(loc="lower right", fontsize=9)

            ax = axes[1, column]
            comparisons = [
                (
                    (float(arm), round(10 / 0.3048, 7), 1),
                    "10 m baseline · 1:1",
                    "#606060",
                    ":",
                    "o",
                )
            ]
            for region, color, marker in (
                ("compact", "#0072B2", "s"),
                ("long", "#D55E00", "^"),
            ):
                winner = next(
                    r
                    for r in chosen
                    if r["arm_length_ft"] == arm and r["region"] == region
                )
                comparisons.append(
                    (
                        _key(winner),
                        f"{region.title()} "
                        f"{_rounded_length(winner, config['compact_max_line_ft'])} ft"
                        f" · {winner['balun_ratio']:g}:1",
                        color,
                        "-" if region == "compact" else "--",
                        marker,
                    )
                )
            for key, label, color, style, marker in comparisons:
                rows = [lookup[key, band] for band in bands]
                values = [r["delivery_efficiency"] for r in rows]
                ax.plot(
                    range(len(bands)),
                    values,
                    color=color,
                    linestyle=style,
                    marker=marker,
                    markersize=5,
                    linewidth=1.6,
                    label=label,
                )
                failed = [i for i, r in enumerate(rows) if not r["modeled_match"]]
                if failed:
                    ax.scatter(
                        failed,
                        [values[i] for i in failed],
                        color=color,
                        marker="x",
                        s=65,
                        linewidths=2,
                        zorder=5,
                    )
            ax.set(
                title=f"{arm:g} ft per arm · nominal band comparison",
                xlabel="Band (one reference frequency each)",
                ylabel="Available power delivered to antenna port",
                ylim=(0, 1.05),
                xticks=range(len(bands)),
                xticklabels=bands,
            )
            ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.grid(axis="y", alpha=0.25)
            ax.legend(loc="lower right", fontsize=9)

        fig.suptitle("Rigid V doublets: line search and nominal power delivery", y=0.99)
        fig.text(
            0.5,
            0.025,
            "Top: coarse geometry and nominal tuner Q; unmatched cases score zero. "
            "Bottom: selected dry-validation candidates, nominal conditions.\n"
            "× exceeds the model's input-SWR target. Generic continuous tuner; "
            "balun, coax and common-mode losses excluded.",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#444444",
        )
        fig.tight_layout(rect=(0, 0.085, 1, 0.965), h_pad=2.5, w_pad=2)
        fig.savefig(output / "optimization_comparison.png", dpi=170)
        plt.close(fig)


def write_report(output_dir: Path) -> None:
    """Read completed optimizer outputs and write REPORT.md and its figure."""
    output = Path(output_dir)
    config = json.loads((output / "config.json").read_text())
    summary = json.loads((output / "summary.json").read_text())
    winners = json.loads((output / "winners.json").read_text())
    coarse = _read_csv(output / "coarse_rankings.csv")
    validated = _read_csv(output / "validated_rankings.csv")
    band_rows = _read_csv(output / "validated_by_band.csv")
    nominal = _read_csv(output / "nominal_by_band.csv")
    wet = _read_csv(output / "wet_stress.csv")
    chosen = []
    for arm in config["arm_lengths_ft"]:
        for region in ("compact", "long"):
            candidates = [
                r
                for r in winners
                if r["arm_length_ft"] == arm
                and r["region"] == region
                and r["route_feasible"]
            ]
            if not candidates:
                raise ValueError(f"Missing route-feasible winner: {arm} ft/{region}")
            chosen.append(min(candidates, key=_rank))
    nominal_lookup = {(_key(row), row["band"]): row for row in nominal}
    band_lookup = {(_key(row), row["band"]): row for row in band_rows}
    wet_lookup = {_key(row): row for row in wet}
    compact_max = config["compact_max_line_ft"]
    count = summary["validation_frequency_samples"]
    target = config["tuner_limits"]["target_swr"]

    lines = [
        "# Rigid V doublet: 17 ft vs 25 ft arms",
        "",
        "These are the **best validated line lengths in the sampled search** for",
        f"compact (≤{compact_max:g} ft) and longer runs. Each choice keeps one line",
        "length and one ideal transformer ratio across all seven bands.",
        "",
        "| Arm length | Line region | Approx. line ft / m | Fixed ratio | "
        "All-frequency "
        "match scenarios | Worst-band p10 delivery | Limiting band |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in chosen:
        lines.append(
            f"| {row['arm_length_ft']:g} ft | {row['region']} | "
            f"{_rounded_length(row, compact_max)} / {row['length_m']:.1f} | "
            f"{row['balun_ratio']:g}:1 | {_pct(row['all_band_match_fraction'])} | "
            f"{_pct(row['worst_band_p10_delivery'])} | {row['limiting_band']} |"
        )
    if all(
        row["length_ft"] == min(r["length_ft"] for r in coarse)
        for row in chosen
        if row["region"] == "compact"
    ):
        lines.extend(
            [
                "",
                "The compact candidates sit at the **shortest route-feasible grid",
                "point**. Their advantage depends on the assumed routing constraint;",
                "the installation still needs adequate supported line and slack.",
            ]
        )
    if all(
        _rank(
            next(
                r
                for r in chosen
                if r["arm_length_ft"] == arm and r["region"] == "compact"
            )
        )
        < _rank(
            next(
                r for r in chosen if r["arm_length_ft"] == arm and r["region"] == "long"
            )
        )
        for arm in config["arm_lengths_ft"]
    ):
        lines.extend(
            [
                "",
                "Neither longer-run candidate improves on its compact counterpart",
                "under the stated ranking objective.",
            ]
        )
    lines.extend(
        [
            "",
            "Lengths are rounded starting points for a prototype, not precise cut",
            "recommendations. Scores use the exact sampled lengths in the linked",
            "CSV/JSON files; rounding a cut has not itself been validated.",
            "",
            "The selected ratios are **ideal, lossless interfaces**. Their advantage",
            "does not establish which real balun to use; incremental balun loss or",
            "different common-mode behavior can reverse the modeled ordering.",
            "",
            "The objective is transmitter-available power delivered to the **antenna",
            "feedpoint**, including generic tuner dissipation, residual input mismatch",
            "and balanced-line loss. It is not radiated power or total antenna",
            "efficiency. Balun, coax, common-mode and truck losses are excluded.",
            "",
            "Ranking first maximizes the fraction of dry scenarios that meet the",
            f"input-SWR target of {target:g}:1 at **every one of {count} sampled",
            "frequencies**, then maximizes the lowest band’s tenth-percentile delivery",
            "score, then the geometric mean of the seven band medians. Unmatched",
            "samples score zero. These equally weighted scenario fractions and",
            "percentiles describe this grid; **they are not tuning probabilities**.",
            "",
            "![Two panels compare coarse line-length scores for 17- and 25-foot arms; "
            "two panels compare nominal antenna-port power by band.]"
            "(optimization_comparison.png)",
            "",
            "## Practical 30 ft line: both fixed ratios",
            "",
            "At nominal 40 m conditions, this comparison holds physical line length",
            "at exactly 30 ft. The final column is also the **extra 4:1 balun loss**",
            "that would erase its modeled delivery advantage over the 1:1 interface",
            "if other behavior stayed equal. Neither balun’s actual loss is modeled.",
            "",
            "| Arms | 10 m / 1:1 baseline | 30 ft / 1:1 | 30 ft / ideal 4:1 | "
            "4:1 advantage / loss margin |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for arm in config["arm_lengths_ft"]:
        base = nominal_lookup[(float(arm), round(10 / 0.3048, 7), 1), "40m"]
        one = nominal_lookup[(float(arm), 30.0, 1), "40m"]
        four = nominal_lookup[(float(arm), 30.0, 4), "40m"]
        margin = _delta(four["delivery_efficiency"], one["delivery_efficiency"])
        lines.append(
            f"| {arm:g} ft | {_nominal_cell(base)} | {_nominal_cell(one)} | "
            f"{_nominal_cell(four)} | {margin} dB |"
        )
    lines.extend(
        [
            "",
            "## Compared with the video’s 10 m line",
            "",
            "Nominal conditions use the reference geometry, line parameters and tuner",
            "Q profile, at one reference frequency per band. Percentages are delivered",
            "antenna-port power divided by available transmitter power. Δ is the",
            "delivery change in dB from the **same radiator’s 10 m / 1:1 baseline**.",
            "An asterisk marks a sample outside the model’s input-SWR target; these",
            "tables show its actual modeled delivery, while ranking scores it zero.",
        ]
    )
    for arm in config["arm_lengths_ft"]:
        compact = next(
            r for r in chosen if r["arm_length_ft"] == arm and r["region"] == "compact"
        )
        long = next(
            r for r in chosen if r["arm_length_ft"] == arm and r["region"] == "long"
        )
        baseline = (float(arm), round(10 / 0.3048, 7), 1)
        lines.extend(
            [
                "",
                f"### {arm:g} ft per arm",
                "",
                f"Compact: about {_rounded_length(compact, compact_max)} ft, "
                f"{compact['balun_ratio']:g}:1. Long: "
                f"{_rounded_length(long, compact_max)} ft, "
                f"{long['balun_ratio']:g}:1.",
                "",
                "| Band / MHz | 10 m baseline | Compact | Δ dB | Long | Δ dB |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for band in _bands(config):
            base = nominal_lookup[baseline, band]
            short = nominal_lookup[_key(compact), band]
            longer = nominal_lookup[_key(long), band]
            short_delta = _delta(
                short["delivery_efficiency"], base["delivery_efficiency"]
            )
            long_delta = _delta(
                longer["delivery_efficiency"], base["delivery_efficiency"]
            )
            lines.append(
                f"| {band} / {base['frequency_mhz']:g} | {_nominal_cell(base)} | "
                f"{_nominal_cell(short)} | {short_delta} | "
                f"{_nominal_cell(longer)} | {long_delta} |"
            )

    lines.extend(
        [
            "",
            "## Broad regions in the coarse search",
            "",
            "For each selected fixed ratio, these sampled intervals stay within",
            "0.2 dB of that arm/region/ratio’s best coarse p10 score, with no lower",
            "all-frequency match fraction. They use the **reference geometry and",
            "nominal tuner Q**, not the expanded dry validation ensemble. Interval",
            "endpoints are grid coordinates, not physically established tolerances.",
            "Only the shortlisted lengths receive expanded validation.",
            "",
            "| Arms / region | Fixed ratio | Coarse near-best sampled intervals |",
            "|---|---:|---|",
        ]
    )
    for row in chosen:
        lines.append(
            f"| {row['arm_length_ft']:g} ft / {row['region']} | "
            f"{row['balun_ratio']:g}:1 | {_near_best_windows(config, coarse, row)} |"
        )
    lines.extend(
        [
            "",
            "## Dry robustness and separate wet stress",
            "",
            "The 40 m column below is the dry validation tenth-percentile score",
            "for 40 m, useful for assessing the short-radiator tradeoff. Wet results",
            "use a deliberately adverse hypothetical line and do not influence",
            "selection; they are not a prediction of actual rain, snow or icing.",
            "",
            "| Arms / region | Dry 40 m p10 | Wet worst-band p10 | "
            "Wet all-frequency match scenarios |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in chosen:
        dry40 = band_lookup[_key(row), "40m"]
        stress = wet_lookup[_key(row)]
        lines.append(
            f"| {row['arm_length_ft']:g} ft / {row['region']} | "
            f"{_pct(dry40['delivery_p10'])} | "
            f"{_pct(stress['worst_band_p10_delivery'])} | "
            f"{_pct(stress['all_band_match_fraction'])} |"
        )
    lines.extend(
        [
            "",
            "## How to interpret the comparison",
            "",
            f"- The coarse search evaluates {summary['coarse_candidates_per_arm']} "
            "fixed line/ratio combinations per arm length at the reference geometry.",
            f"  The selected shortlist contains {len(validated)} combinations across "
            f"both arm lengths, tested at {count} frequencies and "
            f"{len(config['cases'])} geometry/material/ground cases.",
            "  It may miss a length that is weak at the reference geometry but",
            "  stronger under other conditions. No global or exact cut-length optimum",
            "  is established; sampled frequencies do not guarantee band coverage.",
            "- Geometry perturbations are one at a time; this is not a complete",
            "  joint uncertainty grid. Dry line loss, VF and geometry impedance",
            "  assumptions are crossed with the component-Q profiles.",
            "- The generic continuous tuner uses component maxima, assumed Q and",
            "  contact resistance. Actual LDG banks, minimum steps, firmware,",
            "  parasitics and voltage/current limits remain unknown. A modeled match",
            "  does not establish a Z-100A match or a usable power rating.",
            "- NEC gain includes modeled radiator effects. Subtracting delivery loss",
            "  gives modeled directional gain relative to available transmitter power;",
            "  multiplying by NEC efficiency again would count losses twice.",
            "  Longer arms can change lobes and nulls; feedpoint delivery alone does",
            "  not establish stronger radiation in a particular direction.",
            "- The same hub height is used for both radiators. Longer arms also put",
            "  their tips higher and widen the structure. Extended runs need a",
            "  repeatable suspended route clear of the mast and vehicle; mast loading",
            "  and actual feedline coupling are not validated by this calculation.",
            "",
            "All fixed-ratio winners: [winners.json](winners.json). "
            "Full candidate ranking: [validated_rankings.csv](validated_rankings.csv).",
            "Band detail: [validated_by_band.csv](validated_by_band.csv). "
            "Nominal loss and gain: [nominal_by_band.csv](nominal_by_band.csv).",
            "Assumptions and provenance: [config.json](config.json), "
            "[summary.json](summary.json).",
        ]
    )
    if (output / "pattern_comparison.png").exists():
        lines.extend(
            [
                "",
                "## Radiation pattern comparison",
                "",
                "![Modeled radiation patterns compare 17- and 25-foot arms.]"
                "(pattern_comparison.png)",
            ]
        )
    numerical = sorted((output / "numerical").glob("*/numerical_validation.*"))
    if numerical:
        lines.extend(
            [
                "",
                "Numerical solver checks: "
                + ", ".join(
                    f"[{path.parent.name} {path.suffix[1:]}]"
                    f"({path.relative_to(output).as_posix()})"
                    for path in numerical
                )
                + ".",
            ]
        )
    _plot(output, config, coarse, chosen, nominal)
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
