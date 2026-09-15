"""Generate a compact field-facing interpretation from computed linked results."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


def table(headers, rows):
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows],
        "",
    ]


def write_report(output: Path, data: dict[str, Any]) -> None:
    config = data["config"]
    cases = data["cases"]
    fixed = [c for c in cases if c["mode"] == "frozen"]
    sensitivity = data["sensitivity"]
    bands = list(config["bands_mhz"])
    heights = config["outer_end_heights_ft"]
    lengths = data["nominal_tuning"]["section_lengths_ft"]
    nominal_height = config["nominal_end_height_ft"]
    center_height = config["center_height_ft"]

    def case(band, height, mode="frozen"):
        return next(
            c
            for c in cases
            if c["band"] == band and c["end_height_ft"] == height and c["mode"] == mode
        )

    def diff(band, height, key, reference=5):
        return case(band, height)[key] - case(band, reference)[key]

    def below_flat_gain(band, height):
        # Adding zero clears a negative-zero label at the flat reference.
        return -diff(band, height, "realized_broadside_20deg_dbi", 33) + 0.0

    steep_40 = case("40m", 5)
    end_on_advantage = (
        steep_40["gain_end_on_10deg_dbi"] - steep_40["gain_broadside_10deg_dbi"]
    )

    def interval(values):
        return f"{min(values):.2f} to {max(values):.2f}"

    def resonance_shift_khz(band):
        return 1000 * (case(band, 5)["resonance_mhz"] - case(band, 33)["resonance_mhz"])

    def retuned_improvement(band):
        return (
            case(band, 33, "retuned")["realized_broadside_20deg_dbi"]
            - case(band, 5, "retuned")["realized_broadside_20deg_dbi"]
        )

    ground_residual = "ground_and_numerical_residual_fraction"

    lines = [
        "# Portable 20/30/40m linked dipole",
        "",
        f"**Provisional NEC-2 study · {center_height:g} ft feedpoint · "
        "all three sections deployed on "
        "every band.**",
        "",
        "## Tune once, then deploy it",
        "",
        f"**Use {center_height:g} ft at the feedpoint and {nominal_height:g} ft at "
        "the outer 40m wire ends as the default tuning setup. Then keep the same "
        "wire lengths when changing deployment height.** Retuning for each height "
        "is optional; the primary comparison below uses one unchanged antenna. "
        "The separate retuned comparison explains what further adjustments could "
        "recover and is not an operating requirement.",
        "",
        "### Initial wire cuts, per leg",
        "",
    ]

    def blank_length(value):
        feet = int(value)
        inches = (value - feet) * 12
        return f"{feet} ft" if inches == 0 else f"{feet} ft {inches:g} in"

    lines += table(
        ["Section", "Initial construction choice", "Nominal modeled dimension"],
        [
            [
                "20m",
                "Preserve the existing tuned legs and folds",
                f"{lengths[0]:.3f} ft",
            ],
            [
                "30m extension",
                blank_length(config["raw_blank_lengths_ft"][1]) + " raw blank",
                f"{lengths[1]:.3f} ft",
            ],
            [
                "40m extension",
                blank_length(config["raw_blank_lengths_ft"][2]) + " raw blank",
                f"{lengths[2]:.3f} ft",
            ],
        ],
    )
    lines += [
        "Cut two of each new extension blank, one for each leg. **Do not cut the "
        "wire directly to the modeled dimensions.** The blanks include tuning "
        "allowance; the model dimensions run between link centers and a separate "
        "feed bridge, and omit the actual threading, folds and connector tails. "
        "Preserve the existing 20m adjustment first, then recheck it with the "
        "disconnected extensions physically deployed. Finish tuning in 20/30/40m "
        "order and leave the resulting lengths fixed.",
        "",
        "### Fixed-wire SWR when the outer ends move",
        "",
        "These are feedpoint SWRs at the intended operating frequencies, using "
        "average ground and the same nominal assembly in every row.",
        "",
    ]
    lines += table(
        ["Outer ends ft"]
        + [f"{band} · {config['bands_mhz'][band]:g} MHz" for band in bands],
        [
            [
                f"{height:g}" + (" **default**" if height == nominal_height else ""),
                *[f"{case(band, height)['swr']:.2f}:1" for band in bands],
            ]
            for height in heights
        ],
    )
    worst_swr = max(c["swr"] for c in fixed)
    worst_mismatch = max(c["mismatch_loss_db"] for c in fixed)
    lines += [
        f"The largest target-frequency SWR in this comparison is "
        f"**{worst_swr:.2f}:1**, with at most **{worst_mismatch:.2f} dB** of "
        "50 Ω source mismatch loss. For perspective, 2:1 SWR means 0.51 dB of "
        "mismatch loss; it does not by itself require changing the wire. Actual "
        "radio power reduction and additional coax loss are not modeled. These "
        "spot-frequency results do not promise the same match across an entire "
        "band: the full SWR windows are shown below.",
        "",
        "## Field recommendation",
        "",
        "- **20m:** 10–15 ft outer ends are a useful compromise. Raising farther "
        "improves lower-angle broadside radiation, but reduces very-high-angle "
        "radiation. The steep 5 ft setup remains a practical compact option; it is "
        "not uniformly worse in every direction.",
        "- **30m:** aim for 10–15 ft ends when convenient. This recovers much of the "
        "useful gain while retaining strong high-angle coverage. Check the match "
        "after changing shape: this narrow band can sit above the shifted SWR minimum.",
        "- **40m:** give the ends as much height as practical, preferably 15–20 ft or "
        "a flat top. The steep setup has a meaningful penalty in both upward power "
        "and gain, including high-angle regional coverage. Even a rise to 10 ft helps "
        "substantially.",
        "",
        "These are relative antenna-model conclusions, not guaranteed contact "
        "distances. Propagation, noise, station orientation and the actual feed "
        "system still matter.",
        "",
        "Download [the self-contained viewer](viewer.html) and open it locally, "
        "or use **`mise run linked-dipole-viewer`** from the repository. GitHub "
        "displays HTML source rather than running the viewer. It selects band, "
        "deployment, frozen/retuned lengths and accepted/realized gain, and exports "
        "SVG charts. The [artifact index](#saved-artifacts) links the maintained "
        "results; complete solver runs remain under `build/linked-dipole-v1/`.",
        "",
        "## Read the radiation shape at a glance",
        "",
        f"The bold curves show the **{nominal_height:g} ft default outer ends**; "
        "gray dashed curves show the flat top. Each row is one band, with a "
        "broadside vertical slice on the left and a horizontal-direction sweep "
        "at 20° elevation on the right. These use the same frozen wire lengths.",
        "",
        "![Default deployment and flat-top polar radiation patterns]"
        "(figures/polar_default_accepted.png)",
        "",
        "**Read outward as stronger radiation in that direction.** The rings "
        "show absolute gain from −30 to +12 dBi on the same scale in every "
        "panel; the curves are not rescaled to their own peaks. The drawing "
        "shows gain, not contact distance or the antenna's physical shape. "
        "Deep nulls below −30 dBi meet the plot floor. A labeled peak-angle "
        "range identifies tied maxima in the 2° samples after solver rounding; "
        "it does not describe the width of the lobe.",
        "",
        "In a vertical slice, the horizontal baseline is the horizon and the "
        "top is straight overhead (90° elevation). The two halves use computed "
        "samples in opposite azimuth directions; nothing below ground is drawn. "
        "The broadside slice has azimuth 90° on the right and 270° on the left. "
        "In a horizontal-direction sweep, 0°/180° are along the wire span "
        "(end-on), and 90°/270° are perpendicular to it (broadside). These are "
        "directions relative to the antenna, not compass bearings. A horizontal "
        "sweep holds elevation above the horizon fixed: a literal 0° horizon "
        "cut is an unhelpful null in this ground model.",
        "",
        "This first figure uses accepted-power gain: it includes the modeled "
        "wire and ground effects. Realized-gain figures below also apply the "
        "50 Ω source mismatch once. The viewer lets you switch between these "
        "references and inspect another band or deployment.",
        "",
        "## The same physical antenna, five shapes",
        "",
        "![Five physical deployments](figures/geometry_comparison.png)",
        "",
        "The nominal assembly was tuned **sequentially on 20, 30, then 40m at "
        f"{center_height:g}/{nominal_height:g} ft**, then every band was rechecked "
        "and the sequence repeated until |X| ≤ "
        f"{config['tuning_reactance_tolerance_ohm']:g} Ω. It took "
        f"{len(data['nominal_tuning']['history'])} passes. The resulting modeled "
        "sections "
        f"per leg are **{lengths[0]:.3f} + {lengths[1]:.3f} + {lengths[2]:.3f} ft**. "
        "These are electrical model dimensions, **not measured cuts or cutting "
        "instructions**. The 8 ft and 11 ft 6 in extension blanks include tuning "
        "allowance. Folded ends, wire threading and connector tails can change the "
        "required physical lengths.",
        "",
        f"A separate {config['source_length_m'] * 100:g} cm ideal-feed bridge is "
        "included; the section lengths start at its edges and end at link centers or "
        "the outer wire tip. The included angle describes the two straight leg "
        "directions. All outer 40m ends stay at the specified height, including on "
        "20/30m. Link heights follow their fractional distance down the full slope.",
        "",
        "The ideal-feed bridge has three equal segments, with the middle segment "
        "excited. Short neighboring leg segments increase gradually toward the "
        "normal wire mesh. This keeps the source's immediate neighbors collinear "
        "and improves numerical convergence without changing the physical wire "
        "path or link positions.",
        "",
    ]
    rows = []
    for height in heights:
        g = case(bands[0], height)["geometry"]
        rows.append(
            [
                height,
                f"{g['apex_angle_deg']:.1f}°",
                f"{g['span_ft']:.1f}",
                f"{g['link_a_height_ft']:.1f}",
                f"{g['link_b_height_ft']:.1f}",
                "elevated supports"
                if g["stake_distance_ft"] is None
                else f"{g['stake_distance_ft']:.1f}",
                "—" if g["cord_length_ft"] is None else f"{g['cord_length_ft']:.1f}",
            ]
        )
    lines += table(
        [
            "Outer ends ft",
            "Apex",
            "Wire span ft",
            "A height ft",
            "B height ft",
            "Center→stake ft, each side",
            "Cord ft, each side",
        ],
        rows,
    )
    lines += [
        "Cords continue along the wire slope to level ground. These are straight-line "
        "lengths before knots, sag or stretch; double the stake distance for the "
        "total footprint. At 20 ft ends this requires a large clearing. Elevated end "
        "supports can avoid that long ground-stake extension. A flat top cannot reach "
        "ground with a horizontal cord.",
        "",
        "## Frozen lengths: impedance, match and power",
        "",
        "All values below use the same nominal lengths, average ground and the target "
        "frequency in the band label. **η↑** is accepted feedpoint power reaching the "
        "upper-hemisphere far field. Mismatch loss is separate. **Gain** already "
        "includes the modeled material and ground effects; **realized gain** "
        "additionally includes the 50 Ω source mismatch exactly once. Peak direction "
        "uses elevation/azimuth; azimuth 0° is along the wire span (end-on), 90° is "
        "broadside. Symmetric opposite directions have the same gain, and azimuth is "
        "immaterial at zenith.",
        "",
    ]
    lines += table(
        [
            "Band (MHz)",
            "Ends ft",
            "Feedpoint Ω",
            "SWR50",
            "η↑ %",
            "Mismatch dB",
            "Peak dBi",
            "Peak el/az",
            "Realized peak dBi",
        ],
        [
            [
                f"{c['band']} ({c['frequency_mhz']:g})",
                c["end_height_ft"],
                f"{c['r_ohm']:.1f}{c['x_ohm']:+.1f}j",
                f"{c['swr']:.2f}",
                f"{100 * c['efficiency_upper']:.1f}",
                f"{c['mismatch_loss_db']:.2f}",
                f"{c['peak_gain_dbi']:.2f}",
                f"{c['peak_elevation_deg']:g}°/{c['peak_azimuth_deg']:g}°",
                f"{c['realized_peak_gain_dbi']:.2f}",
            ]
            for c in fixed
        ],
    )
    lines += [
        "![Efficiency and mismatch](figures/efficiency_mismatch.png)",
        "",
        "## What each rise buys, and how close it gets to flat",
        "",
        "These are **realized broadside gains at 20° elevation**, at the target "
        "frequency with frozen lengths. Positive improvements mean more power in that "
        "direction. This is one useful lower-angle comparison, not an all-direction "
        "ranking.",
        "",
    ]
    lines += table(
        ["Band", "Ends ft", "Gain dBi", "Change from 5 ft dB", "Below flat dB"],
        [
            [
                band,
                height,
                f"{case(band, height)['realized_broadside_20deg_dbi']:.2f}",
                f"{diff(band, height, 'realized_broadside_20deg_dbi'):+.2f}",
                f"{below_flat_gain(band, height):.2f}",
            ]
            for band in bands
            for height in heights
        ],
    )
    lines += [
        "The first 5 ft rise produces "
        + ", ".join(
            f"**{diff(band, 10, 'realized_broadside_20deg_dbi'):.2f} dB on {band}**"
            for band in bands
        )
        + ". The successive 5 ft rises through 20 ft add progressively less "
        "at this angle. At 20 ft ends the remaining gap to flat is "
        + ", ".join(
            f"{diff(band, 33, 'realized_broadside_20deg_dbi', 20):.2f} dB on {band}"
            for band in bands
        )
        + ".",
        "",
        "## Directional patterns and high-angle coverage",
        "",
        "For most compared lower-angle cases, place the wire span perpendicular "
        "to the desired bearing so the path is broadside. Inspect the azimuth cut: "
        "40m with 5 ft ends at 10° elevation is an exception, favoring end-on by "
        f"{end_on_advantage:.2f} "
        "dB. Flatter deployments deepen lower-angle end-on minima on all three "
        "bands. A steep V can therefore beat the flat top along the wire span "
        "even while radiating less total power upward. Compare the direction "
        "you need, not only the peak gain.",
        "",
        "### Polar comparisons: all five deployments",
        "",
        "The vertical cuts show broadside and end-on slices; the horizontal "
        "sweeps hold elevation at 20° and 60°. Every polar panel shares the "
        "−30 to +12 dBi rings used above. Compare both the outward reach and "
        "the angle of a lobe: a taller lobe in one direction can accompany a "
        "deeper null elsewhere.",
        "",
        "![Accepted-power vertical polar comparisons]"
        "(figures/polar_elevation_accepted.png)",
        "",
        "![Realized-gain vertical polar comparisons]"
        "(figures/polar_elevation_realized.png)",
        "",
        "![Accepted-power horizontal-direction polar comparisons]"
        "(figures/polar_azimuth_accepted.png)",
        "",
        "![Realized-gain horizontal-direction polar comparisons]"
        "(figures/polar_azimuth_realized.png)",
        "",
        "### Detailed angle-versus-gain charts",
        "",
        "These charts show the same computed samples with angle along the "
        "horizontal axis, which makes exact gain differences easier to read.",
        "",
        "![Absolute elevation gain](figures/elevation_accepted.png)",
        "",
        "![Realized elevation gain](figures/elevation_realized.png)",
        "",
        "![Absolute azimuth gain](figures/azimuth_accepted.png)",
        "",
        "![Realized azimuth gain](figures/azimuth_realized.png)",
        "",
        "Each group of detailed panels uses a common absolute dBi scale. Curves "
        "are not individually normalized. The saved azimuth cuts include "
        "10°, 20°, 30° and "
        "60° elevations. The plot floor clips deep nulls for readability; full "
        "computed samples are retained.",
        "",
        "For high-angle regional paths, inspect 60° and 90°, not just the peak. "
        f"On 20m, going 5 ft→flat changes realized 20° broadside gain by "
        f"{diff('20m', 33, 'realized_broadside_20deg_dbi'):+.2f} dB, but 60° by "
        f"{diff('20m', 33, 'realized_broadside_60deg_dbi'):+.2f} dB and zenith by "
        f"{diff('20m', 33, 'realized_broadside_90deg_dbi'):+.2f} dB. The broadside "
        "lobe moves lower. On 30m the pattern remains useful at medium/high angles. "
        "On 40m the same change adds "
        f"{diff('40m', 33, 'realized_broadside_60deg_dbi'):.2f} dB "
        "at 60°; its 33 ft center is still low in wavelengths, so strong high-angle "
        "radiation persists. Raising the ends helps lower-angle 40m radiation without "
        "turning this into a predominantly low-angle antenna.",
        "",
        "### Gain at the requested elevations",
        "",
        "Each cell is **broadside / end-on accepted-power gain in dBi**. To obtain "
        "realized gain at any listed direction, subtract that row's mismatch loss "
        "from the earlier table. Both quantities are also explicit columns in "
        "`summary.csv` and the viewer.",
        "",
    ]
    lines += table(
        ["Band", "Ends ft", "10° B/E", "20° B/E", "30° B/E", "60° B/E", "90° B/E"],
        [
            [
                c["band"],
                c["end_height_ft"],
                *[
                    f"{c[f'gain_broadside_{e}deg_dbi']:.2f} / "
                    f"{c[f'gain_end_on_{e}deg_dbi']:.2f}"
                    for e in (10, 20, 30, 60, 90)
                ],
            ]
            for c in fixed
        ],
    )
    lines += [
        "## Reduced loss versus redistribution",
        "",
        "At a fixed direction, Δgain = **10 log₁₀(η↑₂/η↑₁)** plus the change in "
        "pattern shape after division by η↑. Realized gain then subtracts the change "
        "in mismatch loss. This decomposition does not apply efficiency to gain twice.",
        "",
        "Opening the V raises more of the current-carrying wire and increases its "
        "horizontal span. The model's feed resistance rises: less of the accepted "
        "power is spent heating the same thin wire and contacts. Ground-related "
        "loss is also reduced most clearly on 40m, whose active wire extends all "
        "the way to the low outer tips. On 20m, the active tips are already about "
        f"{case('20m', 5)['geometry']['link_a_height_ft']:.0f} ft high in the steep "
        "setup; much of the extra broadside gain comes "
        "from moving radiation toward lower elevations.",
        "",
        "![Gain decomposition](figures/gain_decomposition.png)",
        "",
    ]
    rows = []
    for band in bands:
        base, flat = case(band, 5), case(band, 33)
        efficiency = 10 * math.log10(
            flat["efficiency_upper"] / base["efficiency_upper"]
        )
        pattern = (
            flat["gain_broadside_20deg_dbi"]
            - base["gain_broadside_20deg_dbi"]
            - efficiency
        )
        mismatch = flat["mismatch_loss_db"] - base["mismatch_loss_db"]
        rows.append(
            [
                band,
                f"{efficiency:+.2f}",
                f"{pattern:+.2f}",
                f"{-mismatch:+.2f}",
                f"{diff(band, 33, 'realized_broadside_20deg_dbi'):+.2f}",
            ]
        )
    lines += table(
        [
            "5 ft→flat",
            "Upward-efficiency contribution dB",
            "20° shape contribution dB",
            "Mismatch contribution dB",
            "Net realized 20° change dB",
        ],
        rows,
    )
    lines += [
        "The power ledger below is a fraction of accepted feedpoint power. Structure "
        "loss includes wire and closed-contact dissipation. The residual is power "
        "absent from upper space waves and explicit NEC dissipation: it is consistent "
        "with ground/environmental absorption plus numerical error, **not an "
        "independent volume integral of soil heating**.",
        "",
    ]
    lines += table(
        [
            "Band",
            "Ends ft",
            "Upward %",
            "Structure/contact %",
            "Ground/numerical residual %",
            "NEC printed efficiency %",
        ],
        [
            [
                c["band"],
                c["end_height_ft"],
                f"{100 * c['efficiency_upper']:.1f}",
                f"{100 * c['power_budget']['structure_loss_fraction']:.1f}",
                f"{100 * c['power_budget'][ground_residual]:.1f}",
                f"{100 * c['power_budget']['nec_printed_efficiency_fraction']:.1f}",
            ]
            for c in fixed
            if c["end_height_ft"] in (5, 33)
        ],
    )
    lines += [
        "## Resonance and usable bandwidth without retuning",
        "",
        "![Band and extended SWR sweeps](figures/swr_comparison.png)",
        "",
        "Resonance means X=0 nearest the intended band; minimum SWR need not occur at "
        "resonance because R also changes with frequency. Every band has "
        f"{config['sweep_samples_in_band']} in-band "
        "samples plus an extended search, refined minima and 2:1 crossings. The "
        "table's 2:1 interval is the full local matched window, including out-of-band "
        "frequencies; only its intersection with the intended band is a usable "
        "in-band window. 2:1 is a comparison threshold, not a transmitter "
        "power-foldback specification.",
        "",
    ]
    lines += table(
        [
            "Band",
            "Ends ft",
            "Resonance MHz",
            "SWR minimum MHz / value",
            "2:1 window MHz",
            "Width kHz",
            "In-band ≤2:1 MHz",
        ],
        [
            [
                c["band"],
                c["end_height_ft"],
                f"{c['resonance_mhz']:.4f}",
                f"{c['min_swr_frequency_mhz']:.4f} / {c['min_swr']:.2f}",
                "none"
                if c["swr2_low_mhz"] is None
                else f"{c['swr2_low_mhz']:.4f}–{c['swr2_high_mhz']:.4f}",
                "—"
                if c["swr2_bandwidth_khz"] is None
                else f"{c['swr2_bandwidth_khz']:.0f}",
                "none"
                if not c["in_band_swr2_interval_mhz"]
                else "–".join(f"{v:.4f}" for v in c["in_band_swr2_interval_mhz"]),
            ]
            for c in fixed
        ],
    )
    lines += [
        "With ends raised from 5 ft to flat, resonance shifts down by "
        + ", ".join(f"{resonance_shift_khz(band):.0f} kHz on {band}" for band in bands)
        + ". The bandwidth is not a simple monotonic function of end height: "
        "increased feed resistance initially broadens the 50 Ω match window, while "
        "increasing resistance toward/above 100 Ω eventually narrows the 2:1 window. "
        "Added wire loss can also broaden a match without improving radiation.",
        "",
        "## Separate retuned comparison — different wire adjustments",
        "",
        "![Retuned versus frozen](figures/retuning_comparison.png)",
        "",
        "This is an optional comparison, not a requirement to adjust the antenna "
        "for every deployment. Each row below retunes all three sections at that "
        "geometry and rechecks the complete assembly. Retuning "
        "cancels reactance at the target; it does **not** force the resistance to 50 "
        "Ω. An ideal lossless matching network would recover all of the reported "
        "mismatch loss, whereas length-only tuning usually recovers only part of it. "
        "No real tuner efficiency is assumed.",
        "",
    ]
    lines += table(
        [
            "Ends ft",
            "20m section ft",
            "30m extension ft",
            "40m extension ft",
            "Target SWR 20/30/40",
            "η↑ % 20/30/40",
        ],
        [
            [
                height,
                *[
                    f"{v:.3f}"
                    for v in case("20m", height, "retuned")["section_lengths_ft"]
                ],
                " / ".join(f"{case(b, height, 'retuned')['swr']:.2f}" for b in bands),
                " / ".join(
                    f"{100 * case(b, height, 'retuned')['efficiency_upper']:.1f}"
                    for b in bands
                ),
            ]
            for height in heights
        ],
    )
    lines += [
        "The higher-end patterns and upward-efficiency advantage remain after "
        "retuning. For 5 ft→flat, the retuned realized 20° broadside improvements are "
        + ", ".join(f"{retuned_improvement(b):.2f} dB on {b}" for b in bands)
        + ". Full retuned impedances, scans and patterns are in the data/viewer.",
        "",
        "## Which conclusions survive uncertainty?",
        "",
        "The soil/wire grid holds the nominal lengths fixed and combines all three "
        "grounds (poor εr=5, σ=0.001; average 13/0.005; good 20/0.03 S/m) with three "
        "homogeneous effective-conductivity proxies (1.4, 10 and 58 MS/m). The last "
        "is an optimistic smooth-copper comparison, not a claim that the CCS wire is "
        "copper. These bounded scenarios are exploratory, not measured limits or "
        "probabilities.",
        "",
    ]
    soil_rows = [s for s in sensitivity if s["variant"].startswith("soil-wire")]
    rows = []
    for band in bands:
        variants = sorted({s["variant"] for s in soil_rows})
        changes20, changes60, steep_eta, flat_eta = [], [], [], []
        for variant in variants:
            a, b = [
                next(
                    s
                    for s in soil_rows
                    if s["variant"] == variant
                    and s["band"] == band
                    and s["end_height_ft"] == h
                )
                for h in (5, 33)
            ]
            changes20.append(
                b["realized_broadside_20deg_dbi"] - a["realized_broadside_20deg_dbi"]
            )
            changes60.append(
                b["realized_broadside_60deg_dbi"] - a["realized_broadside_60deg_dbi"]
            )
            steep_eta.append(100 * a["efficiency_upper"])
            flat_eta.append(100 * b["efficiency_upper"])
        rows.append(
            [
                band,
                interval(changes20),
                interval(changes60),
                interval(steep_eta),
                interval(flat_eta),
            ]
        )
    lines += table(
        [
            "Band",
            "5 ft→flat 20° realized dB",
            "5 ft→flat 60° realized dB",
            "5 ft η↑ % range",
            "Flat η↑ % range",
        ],
        rows,
    )
    lines += [
        "The lower-angle benefit survives this soil/wire grid on every band. The 20m "
        "high-angle tradeoff and the 40m high-angle improvement also survive. "
        "Absolute efficiency varies substantially; measure RF loss and soil before "
        "treating these percentages as properties of the actual antenna.",
        "",
        "![Soil and wire uncertainty](figures/soil_wire_sensitivity.png)",
        "",
        "Additional one-at-a-time tests keep all nominal lengths fixed. The following "
        "are maximum absolute changes over the three bands and five deployments (20m "
        "only for closing B), measured against the matching nominal case. They are "
        "sensitivity to these idealized dimensions, not a model of the unmeasured "
        "relaxed connector tails or folded wire.",
        "",
    ]
    rows = []
    for prefix, label in (
        ("open_gap_m", "Open gaps 10 / 100 mm"),
        ("contact_resistance_ohm", "Contacts 0 / 0.2 / 0.5 Ω each"),
        ("insulation_loading_scale", "Sheath correction 0 / 1.5×"),
        ("outer-links-closed-20m", "Close outer B links on 20m; A stays open"),
    ):
        selected = [s for s in sensitivity if s["variant"].startswith(prefix)]

        def maximum(key, rows=selected):
            return max(
                abs(s[key] - case(s["band"], s["end_height_ft"])[key]) for s in rows
            )

        rows.append(
            [
                label,
                f"{maximum('swr'):.2f}",
                f"{maximum('x_ohm'):.1f}",
                f"{maximum('realized_broadside_20deg_dbi'):.2f}",
                f"{100 * maximum('efficiency_upper'):.2f}",
            ]
        )
    lines += table(
        ["Sensitivity", "ΔSWR", "ΔX Ω", "Δrealized 20° dB", "Δη↑ percentage points"],
        rows,
    )
    lines += [
        "The disconnected extensions participate through coupling even though they "
        "are not directly fed. Closing B on 20m joins the two disconnected outer "
        "sections per side into longer parasitic conductors; the comparison above "
        "tests that explicitly. Do not assume equivalence for closely folded tails, "
        "different gaps or different extension lengths.",
        "",
        "For these collinear modeled tails, the B-open/B-closed differences in "
        "20m gain are small enough to be practically negligible. The small "
        "impedance change is worth checking with an analyzer, but it does not "
        "change the deployment recommendation.",
        "",
        "## Numerical verification and limits",
        "",
    ]
    validation = data["validation"]
    failed = [r for r in validation if not r["passed"]]
    meshes = [r for r in validation if r["kind"] == "mesh_and_free_space"]
    angular = [r for r in validation if r["kind"] == "angular_and_power"]
    convergence = [r for r in validation if r["kind"] == "mesh_convergence"]
    sources = [r for r in validation if r["kind"] == "source_length"]
    lines += [
        f"**{len(validation) - len(failed)}/{len(validation)} numerical checks pass.** "
        "The retained JSON/CSV contains individual results and tolerances.",
        "",
        "- Three meshes (maximum long-wire segment 0.18/0.12/0.08 m), all 15 frozen "
        "cases: largest primary→fine ΔZ "
        f"{max(r['impedance_change_ohm'] for r in convergence):.3f} Ω "
        f"and peak-gain change {max(r['gain_change_db'] for r in convergence):.3f} dB.",
        f"- Lossless full-sphere free-space average gain: worst bare error "
        f"{max(abs(r['average_gain_error_db']) for r in meshes):.3f} dB; "
        f"with reactive insulation retained "
        f"{max(abs(r['reactive_average_gain_error_db']) for r in meshes):.3f} dB. "
        "No automatic average-gain correction is applied to reported gain.",
        f"- 2°→1° angular refinement: largest η↑ change "
        f"{100 * max(r['efficiency_change'] for r in angular):.3f} percentage points. "
        "An independent integration of printed Eθ/Eφ reproduces the gain "
        "normalization.",
        f"- 6/10/14 cm source-bridge check on steep/flat, every band: worst impedance "
        f"spread {max(r['impedance_spread_ohm'] for r in sources):.3f} Ω, peak spread "
        f"{max(r['gain_spread_db'] for r in sources):.3f} dB. Total conductor path is "
        "held constant; the nearby bend and end positions move slightly.",
        "- NEC's printed endpoint connectivity is checked, including the smallest "
        "open gap. Lossless isotropic/quadrature tests, free-space and perfect-ground "
        "sentinels, source-power and field/gain tests guard the 4π normalization and "
        "mismatch accounting.",
        "",
        "η↑ = ∫upper 10^(GdBi/10) dΩ / **4π**. NEC printed efficiency alone is not "
        "η↑. The inferred residual closes the accepted-power ledger but does not "
        "independently separate local soil heating from surface-wave effects and "
        "numerical error. The source and thin-wire approximations set an accuracy "
        "floor; hundredths of a dB are computation detail, not field precision.",
        "",
        "Actual coax length/type, choke, tuner and common-mode currents are "
        "unspecified and absent; the feedpoint is ideally balanced. Mast coupling, "
        "people, terrain, vegetation, sag, hardware dielectrics, actual "
        "strand/plating structure, dielectric loss, and folded/relaxed connector-tail "
        "routing are absent. The historical 1.09 SWR at 14.135 MHz and 1.42 at 14.315 "
        "MHz was taken with a different estimated 40 ft center and an uncertain "
        "measurement plane; it was **not used for calibration** and establishes no "
        "radiation-efficiency claim.",
        "",
        "## Reproduce and validate in the field",
        "",
        "```bash",
        "uv sync --no-editable --extra plots --group dev",
        "NEC2C_PATH=build/tools/nec2c mise run linked-dipole",
        "mise run check",
        "mise run linked-dipole-viewer",
        "```",
        "",
        "Use any installed nec2c via `NEC2C_PATH=/path/to/nec2c`; the exact "
        "executable hash is recorded. `config.json`, tuning history, `study.json`, "
        "CSVs, NEC decks/outputs, source/solver hashes and `SHA256SUMS` make the run "
        "inspectable. The repository's `verify-results` verifies full and compact "
        "manifests. Replace unknown dimensions in `configs/linked-dipole-v1.json` "
        "before interpreting modeled lengths as your antenna.",
        "",
        "1. Measure final straight section lengths, folds/tails, closed bridge "
        "lengths and actual open separations; photograph the link routing. Record "
        "center, both links, tips, span and soil moisture for every deployment.",
        "2. With unchanged wires, measure calibrated **feedpoint** R+jX sweeps at "
        "5/10/15/20 ft ends, then flat if feasible. If measuring through coax, record "
        "and de-embed it. This directly tests the predicted downward resonance shift "
        "and usable match window.",
        "3. On 20m repeat B open versus B closed with A open. Repeat with measured "
        "tail separations. Use a four-wire low-resistance measurement for contacts; "
        "obtain wire RF resistance from a suitable fixture or a measured length, not "
        "DC resistance alone.",
        "4. For comparative radiation, use stable receive stations in several "
        "directions and alternate configurations quickly with controlled accepted "
        "power. Log many paired observations; one ionospheric path or SWR reading "
        "cannot measure efficiency. Check feedline common-mode current and choke "
        "dependence before attributing differences to the wire geometry.",
        "",
        "## Saved artifacts",
        "",
        "This README and its figures are the maintained GitHub-readable study. "
        "The offline viewer embeds the computed data and runs without a server. "
        "Raw NEC solves, expanded sweeps and complete generated runs stay under "
        "`build/`; their input identities and full-run manifest are retained.",
        "",
        "| Artifact | Contents |",
        "| --- | --- |",
        "| [Offline viewer](viewer.html) | Download and open locally; band and "
        "deployment selection, patterns, SWR, and SVG export |",
        "| [Summary CSV](summary.csv) | All frozen and retuned target-frequency "
        "metrics, resonance and bandwidth |",
        "| [Geometry CSV](geometry.csv) | Span, apex, link heights, stakes and cords |",
        "| [Sensitivity CSV](sensitivity.csv) | Soil, wire, links, contacts and "
        "insulation scenarios |",
        "| [Numerical validation](numerical_validation.json) | Individual "
        "pass/fail results and convergence metrics |",
        "| [Configuration](config.json) · [Tuning history](tuning.json) | "
        "Replaceable assumptions and nominal/retuned section dimensions |",
        "| [Run metadata](run_metadata.json) · [Full-run reference](full_run.json) "
        "| Source, solver and full-run identity |",
        "| [SHA256 manifest](SHA256SUMS) | Integrity checks for this result package |",
        "",
        "### Sources and detailed method",
        "",
        "- [Construction "
        "observation](https://rwjblue.com/notes/2026-09-13-compact-20-meter-dipole/)",
        "- [Link insulators](https://www.printables.com/model/"
        "1842032-linked-dipole-link-insulators) "
        "(dimensions/tail uncertainty supplied by the operator)",
        "- [DXE-SANTW-500](https://www.dxengineering.com/parts/dxe-santw-500) and "
        "[manufacturer wire "
        "specifications](https://www.dxengineering.com/search/part-type/wire?GroupBy=ProductName&SortBy=BestKeywordMatch&SortOrder=Ascending&keyword=insulators)",
        "- [Cebik insulation "
        "approximation](https://hamwaves.com/wire/doc/Insulated%20Wires:%20The%20NEC-2%20Way.html)",
        "- [NEC-2 user guide](https://www.nec2.org/other/nec2prt3.pdf); [power/gain "
        "audit](../../docs/linked-dipole-power-audit.md); [construction method and "
        "measurement plan](../../docs/case-studies/linked-dipole-method.md)",
        "- [ARRL antenna modeling background and "
        "tutorials](https://www.arrl.org/antenna-modeling-for-beginners)",
        "",
    ]
    illustrated = []
    for line in lines:
        figure = re.fullmatch(r"!\[([^]]+)\]\((figures/[^)]+\.png)\)", line)
        if figure:
            caption, png = figure.groups()
            svg = png.removesuffix(".png") + ".svg"
            illustrated.extend(
                [
                    f"[![{caption}]({png})]({png})",
                    "",
                    f"[Download PNG]({png}) · [Download SVG]({svg})",
                ]
            )
        else:
            illustrated.append(line)
    (output / "README.md").write_text("\n".join(illustrated))
