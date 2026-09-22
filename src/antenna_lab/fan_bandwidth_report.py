"""Publish the CW-first compact fan bandwidth tradeoff."""

# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator

from antenna_lab.efrw_study import _write_manifest as write_manifest
from antenna_lab.linked_dipole_study import sha256, write_json


def publish(output, compact, config_path):
    setup = json.loads(config_path.read_text())
    data = json.loads((output / "study.json").read_text())["cases"]
    centered = json.loads((output / "centered.json").read_text())
    cw = json.loads((output / "cw-first.json").read_text())

    def row(material, spacing, band, source=data):
        return next(
            r
            for case in source
            if case["material"] == material and case["spacing_in"] == spacing
            for r in case["cases"]
            if r["band"] == band
        )

    def interval(r):
        w = r["full_swr2_window_mhz"]
        return "none" if w is None else f"{w[0]:.3f}–{w[1]:.3f}"

    def phone(r):
        bounds = setup["general_phone_intervals_mhz"][r["band"]]
        w = r["full_swr2_window_mhz"]
        if w is None or min(w[1], bounds[1]) <= max(w[0], bounds[0]):
            return "none"
        if min(w[1], bounds[1]) - max(w[0], bounds[0]) < 0.0001:
            return "edge only (<0.1 kHz)"
        return f"{max(w[0], bounds[0]):.3f}–{min(w[1], bounds[1]):.3f}"

    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.18,
        }
    )

    def save(fig, name):
        for ext in ("png", "svg"):
            fig.savefig(figures / f"{name}.{ext}", dpi=150, bbox_inches="tight")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.4, 5.3), layout="constrained")
    for material, label, color in [
        ("smooth-copper", "Smooth copper", "#0f766e"),
        ("CCS-proxy", "Linked-study wire-loss proxy", "#7c3aed"),
    ]:
        ds = setup["spacings_in"]
        ax.plot(
            ds,
            [row(material, d, "20m")["width_khz"] for d in ds],
            "o-",
            label=label,
            color=color,
            lw=2,
        )
    ax.axhline(
        205, color="#b45309", ls="--", label="14.020 → General phone edge: 205 kHz"
    )
    ax.set(
        xscale="log",
        xticks=ds,
        xticklabels=[f"{d:g}" for d in ds],
        ylim=(0, 360),
        xlabel="Adjacent wire spacing (inches, center to center)",
        ylabel="Full 20m window below 2:1 (kHz)",
        title="20m sets the spacing tradeoff\nSame 33 ft apex / 10 ft tips and thin wire",
    )
    ax.xaxis.set_minor_locator(NullLocator())
    ax.legend(fontsize=10, loc="upper left")
    save(fig, "bandwidth")

    fig, axes = plt.subplots(2, 1, figsize=(7.4, 7), layout="constrained")
    selections = [
        ("smooth-copper", 2, "Copper · 2 in"),
        ("smooth-copper", 3, "Copper · 3 in"),
        ("smooth-copper", 4, "Copper · 4 in"),
        ("smooth-copper", 6, "Copper · 6 in"),
        ("CCS-proxy", 4, "Wire proxy · 4 in"),
        ("CCS-proxy", 6, "Wire proxy · 6 in"),
    ]
    for ax, band in zip(axes, ["20m", "40m"], strict=True):
        bounds = setup["desired_intervals_mhz"][band]
        priority = setup["cw_priority_intervals_mhz"][band]
        general = setup["general_phone_intervals_mhz"][band]
        ax.axvspan(*priority, color="#dbeafe", label="Selected CW priority slice")
        ax.axvspan(*general, color="#ffedd5", label="General phone range")
        for index, (material, d, _label) in enumerate(selections):
            w = row(material, d, band, cw)["full_swr2_window_mhz"]
            ax.plot(
                w,
                [index, index],
                "-",
                color="#0f766e" if material == "smooth-copper" else "#7c3aed",
                lw=7,
                solid_capstyle="butt",
            )
            ax.scatter(w, [index, index], s=20, color="#334155", zorder=3)
        ax.set(
            xlim=bounds,
            ylim=(5.65, -0.9),
            yticks=range(6),
            yticklabels=[s[2] for s in selections],
            xlabel="Frequency (MHz)",
            title=f"{band} · match held down to ≈{setup['cw_anchor_low_mhz'][band]:.3f} MHz",
        )
    axes[0].legend(fontsize=9, loc="upper right")
    fig.suptitle(
        "Keep CW, then use the remaining width for SSB\nBars show modeled feedpoint SWR ≤2:1",
        fontsize=16,
    )
    save(fig, "cw-first")

    checks = [r for case in centered + cw for r in case["validation"]]
    passed = sum(r["passed"] for r in checks)
    lines = [
        "# Fan dipole bandwidth: CW first, some General SSB",
        "",
        "**33 ft apex / 10 ft outer tips · same constant-spacing fan and thin-wire assumptions as the first study.**",
        "",
        "**Four-inch adjacent spacing is the compact compromise with the smooth-copper model. Six inches buys a more useful slice of General SSB on 20m.** "
        "Two inches works well for a CW-focused antenna, but cannot retain the lower CW frequencies and also reach General phone on 20m at ≤2:1. "
        "With the linked study’s uncalibrated copper-clad-steel loss proxy, use the six-inch result as the first tested candidate with useful room in both.",
        "",
        "Your clarified priority is CW first with some General SSB. For this experiment, the **lower match edge is held near 7.020 and 14.020 MHz**. "
        "The illustrative CW priority slices are 7.025–7.075 and 14.025–14.075 MHz; these are planning choices, not definitions of the legal CW allocations. "
        "The match extends continuously through the intervening frequencies. 30m is centered on its 10.100–10.150 MHz band.",
        "",
        "“General SSB” is interpreted as the U.S. General phone ranges, **7.175–7.300 and 14.225–14.350 MHz**, following the "
        "[ARRL U.S. allocation chart](https://www.arrl.org/frequency-bands). Frequency windows below describe antenna matching; usable SSB carrier settings must also leave room for the occupied emission at a subband edge.",
        "",
        "![Bandwidth versus spacing](figures/bandwidth.png)",
        "",
        "## The resulting operating windows",
        "",
        "All antennas in this table are separately tuned for CW-first coverage. These are true modeled 2:1 crossing pairs, rounded to 1 kHz; "
        "a crossing is a boundary, not operating margin. The widths alone do not guarantee identical deployment performance.",
        "",
        "| Wire / adjacent spacing | 40m ≤2:1 MHz | 30m | 20m ≤2:1 MHz | General SSB intersection on 20m |",
        "| --- | --- | --- | --- | --- |",
    ]
    for material, d, label in selections:
        lines.append(
            f"| {label} | {interval(row(material, d, '40m', cw))} | full band | {interval(row(material, d, '20m', cw))} | {phone(row(material, d, '20m', cw))} |"
        )
    lines += [
        "",
        "![CW and General phone match windows](figures/cw-first.png)",
        "",
        "**My build preference: 4 inches if packing width is the deciding constraint; 6 inches if the extra 20m SSB room matters.** "
        "Four inches between adjacent wires means **8 inches between the outer wire centers**; six inches means **12 inches overall**. "
        "That points toward folding/removable spreaders for a normal winder. Permanent half-inch spacers cannot provide these wider-ribbon results. "
        "The model does not establish spacer intervals, sag resistance, packed dimensions or a mechanical design.",
        "",
        "A four-inch copper build only reaches a small part of General phone on 20m, so preserve margin when choosing a working frequency. "
        "Six inches is more forgiving in frequency coverage. A change in spacing, tip height, feed hardware or wire loss can move these windows; "
        "the [first study’s redeployment tests](../fan-dipole-v1/README.md#can-the-tuning-remain-a-one-time-job) show why repeatable geometry matters.",
        "",
        "The four-inch wire-proxy result ends at 14.225057 MHz, only about 57 Hz into General phone. That is effectively an edge touch, "
        "not useful SSB bandwidth, and is smaller than the numerical/window-position tolerances. Six inches extends the proxy result to about 14.267 MHz.",
        "",
        "## Starting points for a prototype",
        "",
        "These are modeled **per-side branch lengths beyond the ideal source bridge**, not guaranteed cut lengths. Start long to allow for actual jacket, end attachment and feed hardware. "
        "The resonance targets below place the match windows for CW first; use the original 40→30→40→20→30→40 tuning sequence with the entire fan assembled.",
        "",
        "| Wire / spacing | 40m half / target | 30m half / target | 20m half / target |",
        "| --- | --- | --- | --- |",
    ]
    for material, d in [("smooth-copper", 4), ("smooth-copper", 6), ("CCS-proxy", 6)]:
        case = next(c for c in cw if c["material"] == material and c["spacing_in"] == d)
        lengths = case["tuning_history"][-1]["tuning"]["lengths_ft"]
        targets = case["config"]["bands_mhz"]
        lines.append(
            f"| {material} / {d} in | "
            + " | ".join(
                f"{length:.3f} ft / {targets[b]:.3f} MHz"
                for b, length in zip(["40m", "30m", "20m"], lengths, strict=True)
            )
            + " |"
        )
    lines += [
        "",
        "## Where the diminishing returns begin",
        "",
        "This width comparison retains the original 7.100/10.120/14.135 MHz resonance targets. Widths use both full crossings before clipping to a band. "
        "The separately retuned CW-first windows above are the relevant operating recommendations.",
        "",
        "| Adjacent spacing in | Outer-center width in | Copper 20m width kHz | Wire-proxy 20m width kHz |",
        "| --- | --- | --- | --- |",
    ]
    for d in setup["spacings_in"]:
        lines.append(
            f"| {d:g} | {2 * d:g} | {row('smooth-copper', d, '20m')['width_khz']:.0f} | {row('CCS-proxy', d, '20m')['width_khz']:.0f} |"
        )
    lines += [
        "",
        "Copper improves from about 85 kHz at ½ inch to 172 kHz at 2 inches, then 219 kHz at 4 inches and 250 kHz at 6 inches. "
        "Thus 4→6 inches adds about 31 kHz while increasing overall ribbon width from 8 to 12 inches. "
        "A 12-inch adjacent-spacing reference is much wider physically; it is a trend comparator, not a backpack-winder recommendation.",
        "",
        "**Repositioning the window does not create bandwidth.** For 40m the approximately 250–260 kHz window already covers most of the 300 kHz band "
        "when positioned properly. For 30m there is ample width. On 20m, a half-inch copper window cannot bridge the roughly 205 kHz from our lower "
        "match edge to the start of General phone. This is why optimizing just the lowest SWR at 14.135 MHz was insufficient.",
        "",
        "## Comparison with centering on whole bands",
        "",
        "For reference, a separate run centers each actual match window inside 7.000–7.300, 10.100–10.150 and 14.000–14.350 MHz. "
        "This can sacrifice your lowest CW frequencies, so it is not the recommended tuning for your stated priority.",
        "",
        "| Wire / spacing | 40m coverage | 30m coverage | 20m coverage | 20m window MHz |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in centered:
        rows = {r["band"]: r for r in case["cases"]}
        lines.append(
            f"| {case['material']} / {case['spacing_in']:g} in | "
            + " | ".join(
                f"{100 * rows[b]['desired_fraction']:.0f}%"
                for b in ["40m", "30m", "20m"]
            )
            + f" | {interval(rows['20m'])} |"
        )
    lines += [
        "",
        "## Reproduce, limitations and saved data",
        "",
        "The existing common-feed NEC formulation is reused. Every spacing/material is retuned with the full assembly present. "
        "Actual SWR crossings are found numerically, then resonance targets are iteratively shifted to position the desired lower edge or center. "
        "This is an engineering tradeoff study over selected spacings, not a proof of a globally optimal geometry.",
        "",
        f"**{passed}/{len(checks)} added checks pass:** 0.12→0.08 m maximum-segment refinement at each selected target and both 2:1 crossings, "
        "plus lossless coated full-sphere average gain at the selected targets and window-position error. Limits are 2 Ω for impedance change, 0.10 dB for average gain and 0.5 kHz for window position. "
        "Existing feed-gap, dielectric, wire-loss, common-mode and environmental uncertainties still apply; passing numerical checks does not establish field accuracy.",
        "",
        "The smooth-copper conductivity is 58 MS/m at the original 0.2413 mm effective conductor radius and original jacket dimensions. "
        "The 10 MS/m wire proxy is not a measurement of the owned CCS wire. Wider spacing helps both, but do not transfer the copper recommendation "
        "to an unknown conductor. No new 15m tuning is performed: the first study already found no low-SWR 15m band from the harmonic alone.",
        "",
        "```bash",
        "NEC2C_PATH=build/tools/nec2c mise run fan-bandwidth",
        "```",
        "",
        "- [Configuration](config.json) · [Width summary](summary.csv)",
        "- [CW-first configurations and tuning](cw-first.json) · [Whole-band configurations](centered.json)",
        "- [Numerical checks](validation.json) · [Run provenance](run_metadata.json)",
        "- [Original fan model and construction assumptions](../fan-dipole-v1/README.md)",
        "",
    ]
    (output / "README.md").write_text("\n".join(lines))
    write_json(output / "validation.json", checks)
    write_json(output / "config.json", setup)
    source_names = [
        "fan_bandwidth.py",
        "fan_bandwidth_report.py",
        "fan_dipole.py",
        "fan_dipole_study.py",
        "linked_dipole.py",
        "linked_dipole_study.py",
        "linked_dipole_validation.py",
        "rigid_doublet_validation.py",
        "nec.py",
        "transmission_line.py",
        "efrw_study.py",
    ]
    metadata = json.loads((output / "run_metadata.json").read_text())
    metadata["source_sha256"] = {
        name: sha256(Path("src/antenna_lab") / name) for name in source_names
    }
    metadata["config_sha256"] = sha256(config_path)
    metadata["base_config_sha256"] = sha256(Path(setup["base_config"]))
    metadata["validation_passed"] = all(r["passed"] for r in checks)
    metadata["matplotlib"] = matplotlib.__version__
    for name in ["centered_metadata.json", "cw-first_metadata.json"]:
        meta = json.loads((output / name).read_text())
        metadata["used_nec_inputs"].update(meta["used_nec_inputs"])
    write_json(output / "run_metadata.json", metadata)
    write_manifest(output)
    compact.mkdir(parents=True, exist_ok=True)
    for name in ["README.md", "config.json", "summary.csv", "validation.json"]:
        shutil.copy2(output / name, compact / name)
    for name, cases in [("cw-first.json", cw), ("centered.json", centered)]:
        reduced = [
            {
                **case,
                "cases": [
                    {k: v for k, v in r.items() if k != "sweep"} for r in case["cases"]
                ],
            }
            for case in cases
        ]
        write_json(compact / name, reduced)
    metadata["used_nec_input_count"] = len(metadata.pop("used_nec_inputs"))
    write_json(compact / "run_metadata.json", metadata)
    shutil.copytree(figures, compact / "figures", dirs_exist_ok=True)
    write_json(
        compact / "full_run.json",
        dict(path=str(output), manifest_sha256=sha256(output / "SHA256SUMS")),
    )
    write_manifest(compact)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("build/fan-bandwidth-v1"))
    p.add_argument("--compact", type=Path, default=Path("results/fan-bandwidth-v1"))
    p.add_argument("--config", type=Path, default=Path("configs/fan-bandwidth-v1.json"))
    args = p.parse_args()
    publish(args.output, args.compact, args.config)


if __name__ == "__main__":
    main()
