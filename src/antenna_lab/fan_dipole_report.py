"""Generate mobile-readable figures and the durable fan dipole README."""

# Report prose stays readable as complete sentences.
# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import NullLocator

from antenna_lab.efrw_study import _write_manifest as write_manifest
from antenna_lab.fan_dipole import BANDS
from antenna_lab.linked_dipole_study import sha256, write_json

COLORS = {"40m": "#155e75", "30m": "#b45309", "20m": "#7c3aed", "15m": "#be123c"}


def render(output, data):
    figdir = output / "figures"
    figdir.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.grid": True,
            "grid.alpha": 0.18,
        }
    )

    def save(fig, name):
        for ext in ("png", "svg"):
            fig.savefig(figdir / f"{name}.{ext}", dpi=150, bbox_inches="tight")
        plt.close(fig)

    def row(d, b):
        return next(r for r in data["cases"] if r["spacing_in"] == d and r["band"] == b)

    spacings = data["config"]["spacings_in"]
    fig, ax = plt.subplots(figsize=(7.4, 5.3), layout="constrained")
    for b in data["config"]["bands_mhz"]:
        ax.plot(
            spacings,
            [row(d, b)["swr"] for d in spacings],
            "o-",
            label=b,
            color=COLORS[b],
        )
    ax.axhline(2, color="#334155", ls="--", lw=1)
    ax.set(
        xscale="log",
        xticks=spacings,
        xticklabels=[f"{d:g}" for d in spacings],
        xlabel="Adjacent wire spacing (inches, center to center)",
        ylabel="50 Ω feedpoint SWR",
        ylim=(1, 5.8),
        title="Spacing comparison with the CCS wire-loss proxy\nEach spacing tuned separately · 33 ft apex / 10 ft tips",
    )
    ax.legend(ncol=4, loc="upper center")
    ax.text(
        0.54, 2.82, f"½ inch: 20m = {row(0.5, '20m')['swr']:.2f}:1", color=COLORS["20m"]
    )
    ax.tick_params(axis="x", labelrotation=45)
    ax.xaxis.set_minor_locator(NullLocator())
    save(fig, "spacing")

    fig, axes = plt.subplots(2, 1, figsize=(7.4, 7.8), layout="constrained")
    labels = ["40m", "30m", "20m", "15m"]
    for d, material, label, color, offset in [
        (0.5, False, "½ in · CCS proxy", "#7c3aed", -0.27),
        (0.5, True, "½ in · smooth copper", "#0f766e", 0),
        (2, False, "2 in · CCS proxy", "#b45309", 0.27),
    ]:
        rows = [
            next(
                r
                for r in data["material_cases"]
                if r["spacing_in"] == d and r["band"] == b
            )
            if material
            else row(d, b)
            for b in labels
        ]
        axes[0].bar(
            np.arange(4) + offset,
            [r["swr"] for r in rows],
            0.25,
            color=color,
            label=label,
        )
        axes[1].bar(
            np.arange(4) + offset,
            [r["upper_efficiency"] * 100 for r in rows],
            0.25,
            color=color,
            label=label,
        )
    axes[0].axhline(2, ls="--", color="#334155", lw=1)
    axes[0].set(
        ylabel="Target-frequency SWR", title="Retuned to the same 40/30/20m targets"
    )
    axes[1].set(
        ylabel="Upward radiated / accepted power (%)",
        ylim=(0, 80),
        title="Conductor/ground loss remains even with ideal matching",
    )
    for ax in axes:
        ax.set(xticks=range(4), xticklabels=labels)
    axes[0].legend(fontsize=10)
    fig.suptitle(
        "Wire loss changes the half-inch answer\nSame metal diameter and sheath · 33 ft apex / 10 ft tips",
        fontsize=16,
    )
    save(fig, "materials")

    fig, axes = plt.subplots(4, 1, figsize=(7.4, 10), layout="constrained")
    for ax, b in zip(axes, data["config"]["bands_mhz"], strict=True):
        for d, color in [(0.5, "#7c3aed"), (2, "#b45309")]:
            sweep = np.array(row(d, b)["sweep"])
            ax.plot(
                sweep[:, 0],
                sweep[:, 3],
                color=color,
                label=f"{d:g} in · CCS proxy",
                lw=2,
            )
        copper_row = next(
            r
            for r in data["material_cases"]
            if r["spacing_in"] == 0.5 and r["band"] == b
        )
        copper_sweep = np.array(copper_row["sweep"])
        ax.plot(
            copper_sweep[:, 0],
            copper_sweep[:, 3],
            "--",
            color="#0f766e",
            label="½ in · smooth copper",
            lw=2,
        )
        lo, hi = data["config"]["band_edges_mhz"][b]
        ax.axvspan(
            lo,
            hi,
            color="#cbd5e1",
            alpha=0.35,
            label="Band limits" if b == "40m" else None,
        )
        ax.axhline(2, color="#334155", ls="--", lw=1)
        ax.set(title=b, xlabel="Frequency (MHz)", ylabel="SWR", ylim=(1, 7))
    axes[0].legend(fontsize=10, ncol=2)
    fig.suptitle(
        "Same tuned antenna on all four bands\nFeedpoint SWR; no coax or tuner",
        fontsize=16,
    )
    save(fig, "swr")

    fig, axes = plt.subplots(2, 1, figsize=(7.4, 8.2), layout="constrained")
    for ax, d in zip(axes, (0.5, 2), strict=True):
        t = next(t for t in data["tuning"] if t["spacing_in"] == d)
        for i, b in enumerate(BANDS):
            ax.plot(
                [h["step"] for h in t["history"]],
                [abs(h["reactances_ohm"][i]) for h in t["history"]],
                "o-",
                label=b,
                color=COLORS[b],
            )
        ax.set(
            yscale="symlog",
            ylim=(0, 1500),
            ylabel="|Reactance| at target (Ω)",
            title=f"{d:g} inch adjacent spacing",
            xticks=range(7),
            xticklabels=[
                "Rough\ncut",
                "Tune\n40m",
                "Tune\n30m",
                "Recheck\n40m",
                "Tune\n20m",
                "Recheck\n30m",
                "Recheck\n40m",
            ],
        )
        ax.axhline(0.5, ls="--", color="#334155", lw=1)
        ax.legend(ncol=3)
    fig.suptitle(
        "Your tuning sequence converges\nDashed line: 0.5 Ω numerical stopping tolerance",
        fontsize=16,
    )
    save(fig, "tuning")

    fig, axes = plt.subplots(2, 1, figsize=(7.4, 7.8), layout="constrained")
    for ax, d in zip(axes, (0.5, 2), strict=True):
        labels = [
            "Nominal",
            "Spacing\n−25%",
            "Spacing\n+25%",
            "Ends\n5 ft",
            "Ends\n15 ft",
        ]
        scenarios = [None, "spacing -25%", "spacing +25%", "ends 5 ft", "ends 15 ft"]
        for i, b in enumerate(BANDS):
            values = [
                row(d, b)["swr"]
                if label is None
                else next(
                    r["swr"]
                    for r in data["sensitivity"]
                    if r["spacing_in"] == d
                    and r["band"] == b
                    and r["scenario"] == label
                )
                for label in scenarios
            ]
            ax.bar(
                np.arange(5) + (i - 1) * 0.24, values, 0.24, color=COLORS[b], label=b
            )
        ax.set(
            xticks=range(5),
            xticklabels=labels,
            ylabel="Target-frequency SWR",
            title=f"{d:g} inch spacing · original lengths held fixed",
        )
        ax.axhline(2, ls="--", color="#334155", lw=1)
        ax.margins(y=0.3)
        ax.legend(ncol=3, loc="upper center")
    fig.suptitle(
        "One-time tuning depends on repeatable geometry\nLinked-study wire-loss assumption",
        fontsize=16,
    )
    save(fig, "deployment")

    fig, axes = plt.subplots(
        2, 1, figsize=(7.4, 7.8), layout="constrained", height_ratios=[1.4, 1]
    )
    t = next(t for t in data["tuning"] if t["spacing_in"] == 0.5)
    lengths = t["lengths_ft"]
    slope = 23 / lengths[0]
    run = math.sqrt(1 - slope * slope)
    ax = axes[0]
    # Drawing offsets are intentionally exaggerated to distinguish wires.
    for i, (length, b) in enumerate(zip(lengths, BANDS, strict=True)):
        for sign in (-1, 1):
            ax.plot(
                [0, sign * length * run],
                [33 - i * 0.65, 33 - length * slope - i * 0.65],
                color=COLORS[b],
                lw=2,
            )
        ax.text(length * run + 0.4, 33 - length * slope - i * 0.65, b, color=COLORS[b])
    ax.set(
        xlabel="Horizontal distance (ft)",
        ylabel="Height (ft)",
        ylim=(0, 37),
        title="33 ft apex · 40m outer tips at 10 ft\nDrawing separation exaggerated; ribbon runs out of this view",
    )
    ax = axes[1]
    ax.grid(False)
    for y, b in zip([1, 0, -1], BANDS, strict=True):
        ax.scatter([0], [y], s=130, color=COLORS[b])
        ax.text(0.13, y, b, va="center", color=COLORS[b])
    for y in [0.5, -0.5]:
        ax.annotate(
            "",
            xy=(-0.15, y + 0.5),
            xytext=(-0.15, y - 0.5),
            arrowprops={"arrowstyle": "<->"},
        )
        ax.text(-0.2, y, "½ inch", ha="right", va="center")
    ax.text(
        0.55,
        0,
        "1 inch between outer centers\n≈1.04 inch including wire jackets\nSpreaders add their own margins",
        va="center",
    )
    ax.set(
        xlim=(-0.65, 2.1),
        ylim=(-1.5, 1.5),
        title="Ribbon cross-section · ½ inch center-to-center",
    )
    ax.axis("off")
    save(fig, "geometry")


def report(output, data):
    def case(d, b):
        return next(r for r in data["cases"] if r["spacing_in"] == d and r["band"] == b)

    def tuning(d):
        return next(t for t in data["tuning"] if t["spacing_in"] == d)

    def windows(row):
        return (
            ", ".join(f"{a:.4f}–{b:.4f}" for a, b in row["in_band_swr2_windows_mhz"])
            or "none"
        )

    c = data["config"]
    checks = data["validation"]
    passed = sum(r["passed"] for r in checks)
    threshold = next(
        (d for d in c["spacings_in"] if all(case(d, b)["swr"] <= 2 for b in BANDS)),
        None,
    )
    lines = [
        "# Backpackable 40/30/20m fan dipole",
        "",
        "**Provisional NEC-2 study · 33 ft apex / 10 ft 40m tips · constant parallel spacing · 50 Ω balanced feed.**",
        "",
        "## Answer for the build",
        "",
        "**Half-inch spacing is tunable. Whether it matches well depends strongly on wire loss.** "
        f"With the linked study’s 10 MS/m thin-wire loss proxy, the ½-inch resonant feedpoint SWRs are {case(0.5, '40m')['swr']:.2f}:1 / "
        f"{case(0.5, '30m')['swr']:.2f}:1 / {case(0.5, '20m')['swr']:.2f}:1 on 40/30/20m. "
        "The limitation is elevated feed resistance on the shorter bands, more than an endlessly unstable tuning sequence.",
        "",
        f"**With that same wire-loss assumption, use about 2 inches between adjacent wires for a first low-SWR prototype** "
        f"(4 inches between outer centers). The smallest tested spacing below 2:1 at all three target frequencies is "
        f"**{threshold:g} inches**; this is a sampled model boundary with little allowance for construction/site changes, "
        "not a universal minimum. Two inches leaves more margin and may suit removable or folding spreaders. "
        "If a narrow winder is the priority, **½ inch remains a candidate with matching assistance**, subject to "
        "measuring the completed antenna and verifying the actual tuner/feedline. This study does not simulate a specific tuner.",
        "",
        "**Half-inch spacing is more promising with lower-loss wire.** The separately retuned, same-diameter "
        "smooth-copper comparison is reported below. It changes conductivity, not spacing or jacket dimensions; "
        "it is an optimistic material comparator, not a claim that the existing CCS wire behaves like copper. "
        "A tuner can address mismatch but cannot recover power dissipated in the wire.",
        "",
        "**15m is a useful harmonic to investigate, not a promised fourth matched band.** "
        f"The ½-inch assembly has {case(0.5, '15m')['swr']:.2f}:1 at 21.2 MHz. "
        "The full 15m sweep below tests the actual coupled structure after tuning 40/30/20m; no 15m adjustment is made.",
        "",
        "![SWR versus spacing](figures/spacing.png)",
        "",
        "## What is physically modeled",
        "",
        "All six arms remain connected and deployed on every band. Wires run parallel, with equal adjacent "
        "center-to-center spacing everywhere along their overlapping lengths. The 40m wire establishes each straight "
        "inverted-V leg; the 30m and 20m wires stop higher along that slope. A horizontal ribbon is assumed. "
        "This is not an angular fan with an inch of separation only at its tips.",
        "",
        "![Geometry and compact ribbon cross-section](figures/geometry.png)",
        "",
        f"The ½-inch example has approximately **{2 * sum(tuning(0.5)['lengths_ft']):.1f} ft of radiator wire**, "
        f"compared with {2 * tuning(0.5)['lengths_ft'][0]:.1f} ft for its 40m dipole alone (about "
        f"{sum(tuning(0.5)['lengths_ft']) / tuning(0.5)['lengths_ft'][0]:.2f}× as much). "
        "The antenna footprint remains roughly 47 ft tip to tip, before support cords. "
        "At half-inch spacing the three-wire ribbon is about 1.04 inches wide including the modeled jackets. "
        "No particular winder, spacer mass, bend radius, or packed-volume claim is modeled.",
        "",
        "The wire and soil assumptions carry over from the linked-dipole study: 0.2413 mm effective metal radius, "
        "0.5207 mm jacket radius, εr=2.3 sheath approximation, 10 MS/m effective conductivity, and average ground "
        "(εr=13, σ=0.005 S/m). Conductivity is an uncalibrated copper-clad-steel loss proxy. "
        "Targets are 7.100, 10.120, 14.135 MHz, with 21.200 MHz as the 15m spot check.",
        "",
        "## Spacing comparison",
        "",
        "Each row is a separately tuned antenna. Wire lengths are frozen for its frequency sweep and subsequent deployment tests.",
        "",
        "| Adjacent spacing in | Ribbon outer centers in | SWR 40m | 30m | 20m | 15m |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for d in c["spacings_in"]:
        lines.append(
            f"| {d:g} | {2 * d:g} | "
            + " | ".join(f"{case(d, b)['swr']:.2f}" for b in c["bands_mhz"])
            + " |"
        )
    lines += [
        "",
        "**Resonance means feedpoint X≈0; match also requires R near 50 Ω.** At ½ inch, modeled "
        f"resonant resistances are {case(0.5, '40m')['r_ohm']:.1f}, {case(0.5, '30m')['r_ohm']:.1f}, "
        f"and {case(0.5, '20m')['r_ohm']:.1f} Ω. Further shortening to chase SWR moves the resonance; "
        "it does not independently fix the resistance. Minimum SWR and resonance need not coincide.",
        "",
        "## The wire-loss qualification",
        "",
        "Close parallel wires carry induced currents as well as their directly driven current. The stronger "
        "coupling makes conductor loss important, particularly on the shorter bands. Compare the same metal "
        "radius and jacket with conductivity changed from the uncalibrated 10 MS/m CCS proxy to an optimistic "
        "58 MS/m smooth-copper model. Both antennas are separately retuned; these are not frozen-length substitutions.",
        "",
        "![Wire loss, SWR and upward radiation](figures/materials.png)",
        "",
        "Upward efficiency integrates the far field over the upper hemisphere and divides by accepted feedpoint power. "
        "It includes modeled wire/ground effects and excludes mismatch, coax and tuner loss. A perfect tuner "
        "could remove mismatch but would leave this efficiency unchanged. These percentages are particularly "
        "dependent on the unknown CCS RF loss and should not be treated as measured antenna efficiencies.",
        "",
        "| Material / spacing | SWR 40 / 30 / 20 / 15 | Upward efficiency %: 40 / 30 / 20 / 15 |",
        "| --- | --- | --- |",
    ]
    for d, material, label in (
        (0.5, False, "CCS proxy / ½ in"),
        (0.5, True, "Smooth copper / ½ in"),
        (2, False, "CCS proxy / 2 in"),
        (2, True, "Smooth copper / 2 in"),
    ):
        rows = [
            next(
                r
                for r in data["material_cases"]
                if r["spacing_in"] == d and r["band"] == b
            )
            if material
            else case(d, b)
            for b in c["bands_mhz"]
        ]
        lines.append(
            f"| {label} | "
            + " / ".join(f"{r['swr']:.2f}" for r in rows)
            + " | "
            + " / ".join(f"{100 * r['upper_efficiency']:.0f}" for r in rows)
            + " |"
        )
    copper = next(
        r
        for r in data["material_cases"]
        if r["spacing_in"] == 0.5 and r["band"] == "20m"
    )
    lines += [
        "",
        f"The half-inch smooth-copper comparison covers **{windows(copper)} MHz** on 20m at ≤2:1. "
        "Its dimensions and all other band windows are in the material summary and tuning files. "
        "If the narrow winder is essential, this is the more useful prototype direction than assuming "
        "that additional trimming will cure the existing-wire model. Check actual wire construction/RF resistance "
        "and re-run before extending this conclusion to a different gauge or insulation. Copper was retuned at ½ and 2 inches only; a smaller copper minimum is not established.",
        "",
        "## Your assembly-and-trim sequence",
        "",
        "The simulation starts with **35 / 25 / 18 ft per side** for 40/30/20m, all connected. "
        "These are generous straight-wire trial blanks, not verified construction cuts or connector allowances. "
        "It tunes 40 → 30 → recheck 40 → 20 → recheck 30 → recheck 40, then checks all three together. "
        "Every tested spacing converged in this six-adjustment cycle to |X|≤0.5 Ω at the target frequencies. "
        "The search permits both shortening and lengthening; a real analyzer-guided session involves more individual snips/readings.",
        "",
        "![Sequential tuning history](figures/tuning.png)",
        "",
        "| Step at ½ inch | Change to each affected leg | Remaining X: 40 / 30 / 20 Ω |",
        "| --- | --- | --- |",
    ]
    for h in tuning(0.5)["history"][1:]:
        delta = h["delta_in"]
        action = "lengthen" if delta > 0 else "shorten"
        change = (
            f"{action} {abs(delta):.3f} in" if abs(delta) > 0.0001 else "no adjustment"
        )
        lines.append(
            f"| {h['adjusted_band']} | {change} | "
            + " / ".join(f"{x:.2f}" for x in h["reactances_ohm"])
            + " |"
        )
    lines += [
        "",
        "The small positive corrections show why **cut-only tuning is not exactly reversible**. "
        "Use adjustable ends or temporary extensions until all three bands are checked. Folded tails have their own "
        "capacitance and are not represented by simply shortening a straight wire; finish with the actual tail routing "
        "and spreaders in place. Avoid permanent final cuts after the first 40m reading.",
        "",
        "### Provisional finished straight lengths, per side",
        "",
        "Measured from each feed-bridge edge to the tip; **exclude half of the separate 10 cm source bridge**. "
        "Do not use these as exact build cuts. Feed hardware, insulation and tails can shift the required lengths.",
        "",
        "| Spacing / material | 40m ft | 30m ft | 20m ft |",
        "| --- | --- | --- | --- |",
    ]
    for d in (0.5, 1.5, 2):
        lines.append(
            f"| {d:g} in / CCS proxy | "
            + " | ".join(f"{x:.3f}" for x in tuning(d)["lengths_ft"])
            + " |"
        )
    for t in data["material_tuning"]:
        lines.append(
            f"| {t['spacing_in']:g} in / smooth copper | "
            + " | ".join(f"{x:.3f}" for x in t["lengths_ft"])
            + " |"
        )
    lines += [
        "",
        "### Local interaction after tuning",
        "",
        "The table gives the predicted resonance shift in kHz after **shortening both ends of one pair by 1 inch each**, "
        "with the other wire lengths fixed. Values are local derivatives at the tuned ½-inch model, not a large-trim rule. "
        "The 40m-tip height stays at 10 ft, so adjusting its length also slightly changes the slope of all branches.",
        "",
        "| Band whose resonance moves | Trim 40m pair | Trim 30m pair | Trim 20m pair |",
        "| --- | --- | --- | --- |",
    ]
    jac = next(j for j in data["jacobians"] if j["spacing_in"] == 0.5)
    for b, values in zip(BANDS, jac["shift_khz_per_inch_trim"], strict=True):
        lines.append(f"| {b} | " + " | ".join(f"{v:+.1f}" for v in values) + " |")
    lines += [
        "",
        "## Bandwidth and the 15m harmonic",
        "",
        "The gray regions are band boundaries; curves extend beyond them to show the resonance. "
        "The table reports only in-band intervals with SWR≤2:1, refined at the crossings. "
        "The table uses the linked-study wire-loss proxy; the dashed copper curve has separate windows in the material summary. These are feedpoint values; coax can transform the measured impedance and add loss.",
        "",
        "![40/30/20/15m SWR curves](figures/swr.png)",
        "",
        "| Spacing in | Band | Nearest X=0 MHz | In-band ≤2:1 MHz | Worst sampled in-band SWR |",
        "| --- | --- | --- | --- | --- |",
    ]
    for d in (0.5, 2):
        for b in c["bands_mhz"]:
            r = case(d, b)
            res = (
                "none in search"
                if r["resonance_mhz"] is None
                else f"{r['resonance_mhz']:.4f}"
            )
            lines.append(
                f"| {d:g} | {b} | {res} | {windows(r)} | {r['in_band_max_swr']:.2f} |"
            )
    lines += [
        "",
        "A 40m dipole supports a higher odd-order mode near 15m, but the resonances are not an exact 3:1 "
        "frequency scaling once end effects, insulation, ground and the other wires are included. "
        "The mode also has a different radiation pattern. This study establishes feedpoint matching behavior, "
        "not contact probability or a 15m efficiency advantage over a dedicated element.",
        "",
        "## Can the tuning remain a one-time job?",
        "",
        "Yes in a repeatable mechanical geometry; that premise is worth testing in the field. "
        "All following variants keep the originally tuned lengths. Spacing ±25% is a uniform change over the whole ribbon, "
        "not a prediction of random sag, touching wires or twisted sections. Tip-height changes reset the straight-leg slope.",
        "",
        "![Spacing and end-height sensitivity](figures/deployment.png)",
        "",
        "| Spacing in | Deployment | SWR 40 / 30 / 20 |",
        "| --- | --- | --- |",
    ]
    for d in (0.5, 2):
        for scenario in ("spacing -25%", "spacing +25%", "ends 5 ft", "ends 15 ft"):
            vals = [
                next(
                    r["swr"]
                    for r in data["sensitivity"]
                    if r["spacing_in"] == d
                    and r["band"] == b
                    and r["scenario"] == scenario
                )
                for b in BANDS
            ]
            lines.append(
                f"| {d:g} | {scenario} | " + " / ".join(f"{v:.2f}" for v in vals) + " |"
            )
    lines += [
        "",
        "The retuned **½-inch smooth-copper** comparator with its own lengths held fixed:",
        "",
        "| Deployment | SWR 40 / 30 / 20 |",
        "| --- | --- |",
    ]
    for scenario in ("spacing -25%", "spacing +25%", "ends 5 ft", "ends 15 ft"):
        vals = [
            next(
                r["swr"]
                for r in data["material_sensitivity"]
                if r["band"] == b and r["scenario"] == scenario
            )
            for b in BANDS
        ]
        lines.append(f"| {scenario} | " + " / ".join(f"{v:.2f}" for v in vals) + " |")
    lines += [
        "",
        "Maintain the chosen spacing along the overlap, particularly near the shorter-wire tips. "
        "Keep all six wires under repeatable tension; let nonconductive extensions carry the short-wire ends toward "
        "the same outer supports. Removable spreaders can reduce the width while winding. The study does not establish "
        "a required distance between spreaders; that needs a mechanical sag/tension test.",
        "",
        "The CSV also includes poor/good ground, no-sheath and 1.5× sheath-loading variants, and a solid-copper "
        "conductivity proxy at ½ and 2 inches. These are exploratory one-variable changes, not a statistical error bar. "
        "The sheath approximation changes electrical length but does not rigorously solve the dielectric field between "
        "closely coupled insulated wires.",
        "",
        "## Numerical verification and limits",
        "",
        f"**{passed}/{len(checks)} numerical checks pass the declared limits.** "
        f"Largest primary-to-fine ΔZ: {max(r['delta_z_ohm'] for r in checks if r['kind'] == 'mesh'):.3f} Ω. "
        f"Largest lossless average-gain error: {max(max(abs(r['bare_error_db']), abs(r['coated_error_db'])) for r in checks if r['kind'] == 'average_gain'):.3f} dB.",
        "",
        "**The sub-half-inch results are exploratory trends.** The ⅛- and ¼-inch meshes fail the 2 Ω convergence "
        "limit on 30/20m; the ¼-inch fine-mesh bare 30m average gain narrowly exceeds 0.10 dB. "
        "At ½ inch, the mesh and average-gain checks pass, but varying the source bridge changes 30m impedance "
        "by about 2.1 Ω and 20m by about 5.3 Ω, exceeding the separate 2 Ω source check. "
        "The 2-inch references pass all these checks. The half-inch copper source variation similarly exceeds the 2 Ω limit: 2.2 Ω on 30m and 5.8 Ω on 20m. These uncertainties are small relative to the "
        "half-inch shorter-band resistance excess, but do not justify an exact minimum-spacing or cutting claim.",
        "",
        "Parallel wires have matching segment boundaries, with local refinement at every short-wire tip on all "
        "neighboring wires. Long-segment caps are 0.18 / 0.12 / 0.08 m; the primary mesh is 0.12 m. "
        "Source bridges contain nine equal segments. All nine spacings and four bands receive mesh and bare/coated "
        "lossless full-sphere power checks; the two retuned copper comparators receive the same mesh/power checks. Declared limits are 2 Ω for primary→fine impedance and 0.10 dB for average gain. "
        "Feed-bridge lengths of 6/10/14 cm are checked at ½ and 2 inches while keeping total conductor path fixed.",
        "",
        "The common balanced port is represented by **three equal in-phase 1 V sources**, one per dipole pair. "
        "The solver includes mutual coupling among every wire. Total port impedance is 1 / Σ(1/Zsource), "
        "using NEC’s complex per-source impedances; source power is independently checked against ½ Re(1/Ztotal). "
        "This represents ideal equipotential feed terminals without finite lead/bus parasitics. "
        "It is not three separately simulated impedances connected afterward. An optional physical-bus topology "
        "is retained for diagnostics; coarse trial bus models failed power checks and are not used for conclusions.",
        "",
        "Numerical checks validate this idealized formulation, not the real antenna. Feed hardware, coax/common-mode "
        "current, choke, mast, people, vegetation, sloping ground, dielectric spacer loading, wet insulation, "
        "sag/twist and folded tails are absent. Wire loss uses a homogeneous effective conductivity without "
        "a full stranded/plated or circumferential proximity-current model. Exact fractions of an inch and "
        "hundredths of SWR are computational detail, not promised field precision.",
        "",
        "### Prototype procedure",
        "",
        "1. Build all three pairs long with adjustable tips. Install the intended feed hardware and spreaders first.",
        "2. Raise to 33 ft / 10 ft and measure calibrated feedpoint R+jX sweeps. Tune 40 → 30 → 40 → 20 → 30 → 40.",
        "3. Record final R as well as X. If the shorter bands are resonant but high in resistance, widen spacing or "
        "evaluate lower-loss wire or a matching solution; repeated trimming is not an independent resistance control.",
        "4. Sweep all of 15m. Then pack, unwind and redeploy several times; compare resonance and SWR before making final cuts.",
        "5. Repeat at practical tip heights and with actual coax/choke. If measurements are through coax, record/de-embed "
        "it before comparing to these feedpoint results.",
        "",
        "## Reproduce and inspect",
        "",
        "```bash",
        "uv sync --no-editable --extra plots --group dev",
        "NEC2C_PATH=build/tools/nec2c mise run fan-dipole",
        "mise run check",
        "```",
        "",
        "The task regenerates the full data and report under `build/fan-dipole-v1/` and the compact checked-in "
        "package here. Raw NEC decks/outputs remain in `build/fan-dipole-cache/`; exact deck/output and solver hashes "
        "are retained in full-run metadata. Both result packages have verified recursive SHA256 manifests.",
        "",
        "- [Configuration](config.json) · [Summary CSV](summary.csv) · [All SWR samples](sweeps.csv)",
        "- [Sequential tuning history](tuning.json) · [Interaction derivatives](jacobians.json)",
        "- [Retuned copper comparison](material_summary.csv) · [Copper tuning history](material_tuning.json) · [Copper redeployment](material_sensitivity.csv)",
        "- [Deployment/material sensitivity](sensitivity.csv) · [Numerical checks](validation.json)",
        "- [Run provenance](run_metadata.json) · [Full-run manifest identity](full_run.json)",
        "",
        "### Method sources",
        "",
        "- [NEC-2 user guide, wire-modeling rules](https://www.nec2.org/other/nec2prt3.pdf): "
        "close parallel segments must align; check mesh dependence and wire/source geometry.",
        "- [Cebik’s thin-sheath series-inductance approximation](https://hamwaves.com/wire/doc/Insulated%20Wires:%20The%20NEC-2%20Way.html): "
        "approximate insulation loading, not a full coupled-dielectric solution.",
        "- [Linked-dipole reference](../linked-dipole-v1/README.md) and "
        "[power normalization audit](../../docs/linked-dipole-power-audit.md).",
        "",
    ]
    (output / "README.md").write_text("\n".join(lines))


def finish(output, compact):
    data = json.loads((output / "study.json").read_text())
    render(output, data)
    report(output, data)
    metadata = json.loads((output / "run_metadata.json").read_text())
    metadata["source_sha256"][Path(__file__).name] = sha256(Path(__file__))
    metadata["matplotlib"] = matplotlib.__version__
    write_json(output / "run_metadata.json", metadata)
    write_manifest(output)
    compact.mkdir(parents=True, exist_ok=True)
    for name in (
        "README.md",
        "config.json",
        "summary.csv",
        "sweeps.csv",
        "tuning.json",
        "jacobians.json",
        "material_summary.csv",
        "material_tuning.json",
        "material_sensitivity.csv",
        "sensitivity.csv",
        "validation.json",
    ):
        shutil.copy2(output / name, compact / name)
    metadata = json.loads((output / "run_metadata.json").read_text())
    metadata["used_nec_input_count"] = len(metadata.pop("used_nec_inputs"))
    write_json(compact / "run_metadata.json", metadata)
    shutil.copytree(output / "figures", compact / "figures", dirs_exist_ok=True)
    write_json(
        compact / "full_run.json",
        dict(path=str(output), manifest_sha256=sha256(output / "SHA256SUMS")),
    )
    write_manifest(compact)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("build/fan-dipole-v1"))
    parser.add_argument("--compact", type=Path, default=Path("results/fan-dipole-v1"))
    args = parser.parse_args()
    finish(args.output, args.compact)


if __name__ == "__main__":
    main()
