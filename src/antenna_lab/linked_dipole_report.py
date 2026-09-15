"""Offline figures and a computed-data viewer for the physical linked dipole.

Like ``rigid_doublet_patterns``, all gain comparisons use common absolute axes,
azimuth zero along the wire and 90 degrees broadside. This module never solves,
retunes, normalizes individual patterns, or changes the computed gain values.
"""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any

BANDS = ("40m", "30m", "20m")
BAND_EDGES = {"40m": (7.0, 7.3), "30m": (10.1, 10.15), "20m": (14.0, 14.35)}
HEIGHT_COLORS = ("#bc4b24", "#b78809", "#227963", "#267bb6", "#172d47")
SECTION_COLORS = ("#267bb6", "#227963", "#bc4b24")
GAIN_LIMITS = (-30, 12)


def _label(case: dict[str, Any]) -> str:
    height = case["end_height_ft"]
    center = case.get("geometry", {}).get("center_height_ft", 33)
    return f"{height:g} ft · flat top" if height == center else f"{height:g} ft ends"


def _cases(data: dict[str, Any], band: str, mode: str = "frozen") -> list[dict]:
    return sorted(
        (c for c in data["cases"] if c["band"] == band and c["mode"] == mode),
        key=lambda c: c["end_height_ft"],
    )


def _cut(case: dict, *, azimuth: float | None = None, elevation: float | None = None):
    """Extract a sampled cut without interpolation or per-pattern normalization."""
    if (azimuth is None) == (elevation is None):
        raise ValueError("Specify exactly one cut coordinate")
    fixed, varying, target = (
        (1, 0, azimuth) if azimuth is not None else (0, 1, elevation)
    )
    points = sorted(
        (point[varying], point[2])
        for point in case["pattern"]
        if math.isclose(point[fixed], target, abs_tol=1e-6)
    )
    if not points:
        raise ValueError(f"Missing pattern cut in {case['case_id']}: {target}")
    if elevation is not None and points[0][0] == 0 and points[-1][0] < 360:
        points.append((360, points[0][1]))
    return points


def _gain(
    case: dict, elevation: float, azimuth: float, realized: bool = False
) -> float:
    value = next(
        p[2]
        for p in case["pattern"]
        if math.isclose(p[0], elevation, abs_tol=1e-6)
        and math.isclose(p[1], azimuth, abs_tol=1e-6)
    )
    return value - (case["mismatch_loss_db"] if realized else 0)


def _save(figure, directory: Path, name: str, plt) -> None:
    figure.savefig(
        directory / f"{name}.svg", facecolor="white", metadata={"Date": None}
    )
    figure.savefig(directory / f"{name}.png", dpi=170, facecolor="white")
    plt.close(figure)


def _heading(figure, title: str, subtitle: str, *, footnote: str = "") -> None:
    figure.suptitle(title, fontsize=20, fontweight="bold", y=0.985)
    figure.text(0.5, 0.935, subtitle, ha="center", fontsize=11, color="#435267")
    if footnote:
        figure.text(0.5, 0.025, footnote, ha="center", fontsize=9, color="#435267")


def _legend(figure, axis) -> None:
    handles, labels = axis.get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncols=len(labels),
        frameon=False,
    )


def _geometry_figure(data, directory, plt):
    cases = _cases(data, "40m")
    figure, axes = plt.subplots(1, len(cases), figsize=(19, 4.4))
    figure.subplots_adjust(left=0.035, right=0.99, top=0.79, bottom=0.45, wspace=0.15)
    max_stake = max(
        c["geometry"].get("stake_distance_ft") or c["geometry"]["span_ft"] / 2
        for c in cases
    )
    extent = max_stake * 1.04
    for axis, case, color in zip(axes, cases, HEIGHT_COLORS, strict=True):
        geometry = case["geometry"]
        length = sum(case["section_lengths_ft"])
        cumulative = [0, case["section_lengths_ft"][0]]
        cumulative.extend([sum(case["section_lengths_ft"][:2]), length])
        heights = [
            geometry["center_height_ft"],
            geometry["link_a_height_ft"],
            geometry["link_b_height_ft"],
            geometry["end_height_ft"],
        ]
        horizontal_leg = math.sqrt(
            length**2 - (geometry["center_height_ft"] - heights[-1]) ** 2
        )
        bridge_half = geometry["span_ft"] / 2 - horizontal_leg
        xs = [
            bridge_half + distance / length * horizontal_leg for distance in cumulative
        ]
        axis.plot(
            [-bridge_half, bridge_half], [heights[0]] * 2, color="#172d47", linewidth=2
        )
        for side in (-1, 1):
            for section in range(3):
                axis.plot(
                    [side * xs[section], side * xs[section + 1]],
                    heights[section : section + 2],
                    color=SECTION_COLORS[section],
                    linewidth=3.2,
                )
            for x, height, link in zip(xs[1:3], heights[1:3], ("A", "B"), strict=True):
                axis.plot(side * x, height, "o", color="white", mec="#26394d", ms=5)
                if side == 1:
                    axis.annotate(link, (x, height), (3, 7), textcoords="offset points")
            stake = geometry.get("stake_distance_ft")
            if stake is not None:
                axis.plot(
                    [side * xs[-1], side * stake],
                    [heights[-1], 0],
                    linestyle="--",
                    color="#687885",
                    linewidth=1.5,
                )
                axis.plot(side * stake, 0, "v", color="#687885", ms=5)
            else:
                axis.plot(
                    [side * xs[-1]] * 2, [0, heights[-1]], color="#9aa3aa", linewidth=2
                )
        axis.plot(0, heights[0], "o", color="#172d47", ms=6)
        axis.plot([0, 0], [0, heights[0]], ":", color="#c1c9ce")
        axis.axhline(0, color="#73866b", linewidth=1.6)
        axis.set(xlim=(-extent, extent), ylim=(-3, 40), title=_label(case))
        axis.set_aspect("equal", adjustable="box")
        axis.set_xlabel("Horizontal distance (ft)")
        axis.set_xticks([-60, -30, 0, 30, 60])
        axis.set_yticks([0, 10, 20, 33])
        axis.tick_params(labelsize=8)
        axis.grid(alpha=0.12)
        axis.title.set_color(color)
        axis.title.set_fontweight("bold")
        stake_text = (
            f"Stake from center: {geometry['stake_distance_ft']:.1f} ft\n"
            f"Cord beyond wire: {geometry['cord_length_ft']:.1f} ft / side"
            if geometry.get("stake_distance_ft") is not None
            else "Elevated end supports required\nNo finite collinear ground stake"
        )
        axis.text(
            0.5,
            -0.44,
            f"Apex: {geometry['apex_angle_deg']:.1f}°  |  "
            f"Span: {geometry['span_ft']:.1f} ft\n"
            f"Link A: {geometry['link_a_height_ft']:.1f} ft high\n"
            f"Link B: {geometry['link_b_height_ft']:.1f} ft high\n{stake_text}",
            transform=axis.transAxes,
            ha="center",
            va="top",
            fontsize=9,
            linespacing=1.7,
        )
    axes[0].set_ylabel("Height (ft)")
    lengths = cases[0]["section_lengths_ft"]
    _heading(
        figure,
        "One physical antenna, five deployments",
        f"{cases[0]['geometry']['center_height_ft']:g} ft feedpoint · "
        "outermost 40m wire ends set the slope on every band · "
        "schematics share equal distance scales",
        footnote=(
            "Blue = 20m section; green = 30m extension; orange = 40m extension; "
            "dashed = support cord.\n"
            f"Provisional tuned section lengths per leg: {lengths[0]:.3f}, "
            f"{lengths[1]:.3f}, {lengths[2]:.3f} ft. These are model dimensions, "
            "not measured cut lengths."
        ),
    )
    # This figure is shallower than the pattern grids; reserve a full text line.
    figure.texts[1].set_y(0.88)
    _save(figure, directory, "geometry_comparison", plt)


def _pattern_figure(data, directory, plt, *, azimuth=False, realized=False):
    rows = (10, 20, 30, 60) if azimuth else (90, 0)
    figure, axes = plt.subplots(len(rows), 3, figsize=(15, 12.5 if azimuth else 8.7))
    figure.subplots_adjust(
        left=0.075, right=0.985, top=0.79, bottom=0.12, hspace=0.43, wspace=0.16
    )
    for column, band in enumerate(BANDS):
        for row, fixed in enumerate(rows):
            axis = axes[row, column]
            for case, color in zip(_cases(data, band), HEIGHT_COLORS, strict=True):
                points = (
                    _cut(case, elevation=fixed)
                    if azimuth
                    else _cut(case, azimuth=fixed)
                )
                penalty = case["mismatch_loss_db"] if realized else 0
                axis.plot(
                    [p[0] for p in points],
                    [p[1] - penalty for p in points],
                    color=color,
                    linewidth=1.9,
                    linestyle="--" if case["end_height_ft"] == 33 else "-",
                    label=_label(case),
                )
            axis.set_ylim(*GAIN_LIMITS)
            axis.set_yticks([-30, -20, -10, 0, 10])
            axis.axhline(0, color="#7c8b95", linewidth=0.65)
            axis.grid(alpha=0.18)
            if azimuth:
                axis.set_xlim(0, 360)
                axis.set_xticks([0, 90, 180, 270, 360])
                axis.set_xlabel("Azimuth (°)")
                row_name = f"{fixed}° elevation"
            else:
                axis.set_xlim(0, 90)
                axis.set_xticks([0, 15, 30, 45, 60, 75, 90])
                axis.set_xlabel("Elevation (°)")
                row_name = (
                    "Broadside · azimuth 90°" if fixed == 90 else "End-on · azimuth 0°"
                )
            if column == 0:
                axis.set_ylabel(
                    f"{row_name}\n{'Realized gain' if realized else 'Gain'} (dBi)"
                )
            if row == 0:
                case = _cases(data, band)[0]
                axis.set_title(f"{band} · {case['frequency_mhz']:g} MHz", pad=9)
    _legend(figure, axes[0, 0])
    kind = "Azimuth" if azimuth else "Elevation"
    reference = (
        "Available power from a 50 Ω source"
        if realized
        else "Accepted power at the balanced feedpoint"
    )
    _heading(
        figure,
        f"{kind} cuts · {'realized gain' if realized else 'absolute gain'}",
        f"Same frozen wire lengths · average ground · "
        f"{reference[0].lower() + reference[1:]}",
        footnote=(
            "Common absolute scale; curves are not individually normalized. "
            "Azimuth 0°/180° = along wire; 90°/270° = broadside.\n"
            "Gain includes the modeled conductor and ground effects. "
            + (
                "Mismatch is applied exactly once. "
                if realized
                else "Mismatch is excluded. "
            )
            + "Feedline, choke, tuner and mast are omitted. "
            "Values below −30 dBi are clipped."
        ),
    )
    _save(
        figure,
        directory,
        f"{'azimuth' if azimuth else 'elevation'}_"
        f"{'realized' if realized else 'accepted'}",
        plt,
    )


def _swr_figure(data, directory, plt):
    figure, axes = plt.subplots(2, 3, figsize=(15, 8.5))
    figure.subplots_adjust(
        left=0.065, right=0.985, top=0.79, bottom=0.12, hspace=0.43, wspace=0.2
    )
    for column, band in enumerate(BANDS):
        for row, axis in enumerate(axes[:, column]):
            cases = _cases(data, band)
            for case, color in zip(cases, HEIGHT_COLORS, strict=True):
                sweep = case["sweep"]
                axis.plot(
                    [p[0] for p in sweep],
                    [p[3] for p in sweep],
                    color=color,
                    linewidth=2,
                    label=_label(case),
                    linestyle="--" if case["end_height_ft"] == 33 else "-",
                )
                axis.plot(
                    case["min_swr_frequency_mhz"],
                    case["min_swr"],
                    "o",
                    color=color,
                    ms=4,
                )
            axis.axhline(2, color="#6d7884", linestyle=":", linewidth=1)
            axis.axvline(
                cases[0]["frequency_mhz"], color="#8195a5", linestyle=":", linewidth=1
            )
            axis.set_ylim(1, 6)
            axis.set_xlabel("Frequency (MHz)")
            axis.set_ylabel("50 Ω SWR" if column == 0 else "")
            axis.grid(alpha=0.18)
            axis.ticklabel_format(useOffset=False, style="plain", axis="x")
            if row == 0:
                axis.set_xlim(*BAND_EDGES[band])
                axis.set_title(f"{band} · requested band window", pad=9)
            else:
                axis.axvspan(*BAND_EDGES[band], color="#92c5d5", alpha=0.13)
                axis.set_title("Full computed search · dots mark minima", fontsize=11)
    _legend(figure, axes[0, 0])
    _heading(
        figure,
        "What moves when the wire lengths stay fixed?",
        f"Five deployments of the nominal "
        f"{data['config']['nominal_end_height_ft']:g} ft-end tuning · "
        "target frequency shown by the vertical dotted line",
        footnote="The lower row includes the extended search. "
        "Pale shading = requested band window. "
        "SWR above 6 is clipped; all values remain in the machine-readable results.",
    )
    _save(figure, directory, "swr_comparison", plt)


def _summary_figure(data, directory, plt):
    figure, axes = plt.subplots(2, 3, figsize=(15, 8.2))
    figure.subplots_adjust(
        left=0.07, right=0.985, top=0.81, bottom=0.14, hspace=0.42, wspace=0.24
    )
    for column, band in enumerate(BANDS):
        cases = _cases(data, band)
        heights = [c["end_height_ft"] for c in cases]
        upper, lower = axes[:, column]
        upper.bar(
            range(len(cases)),
            [c["efficiency_upper"] * 100 for c in cases],
            color=HEIGHT_COLORS,
            width=0.65,
        )
        upper.set_ylim(0, 100)
        upper.set_ylabel("Upper-hemisphere radiation / accepted power (%)")
        upper.set_title(band)
        for index, case in enumerate(cases):
            upper.text(
                index,
                case["efficiency_upper"] * 100 + 2,
                f"{case['efficiency_upper'] * 100:.1f}",
                ha="center",
                fontsize=10,
            )
        lower.bar(
            range(len(cases)),
            [c["mismatch_loss_db"] for c in cases],
            color=HEIGHT_COLORS,
            width=0.65,
        )
        lower.set_ylim(
            0,
            max(
                1.0,
                max(
                    c["mismatch_loss_db"]
                    for c in data["cases"]
                    if c["mode"] == "frozen"
                )
                * 1.25,
            ),
        )
        lower.set_ylabel("Mismatch loss from a 50 Ω source (dB)")
        for index, case in enumerate(cases):
            lower.annotate(
                f"{case['mismatch_loss_db']:.2f}",
                (index, case["mismatch_loss_db"]),
                (0, 5),
                textcoords="offset points",
                ha="center",
                fontsize=10,
            )
        for axis in (upper, lower):
            axis.set_xticks(range(len(cases)), [f"{h:g}" for h in heights])
            axis.set_xlabel("Outermost wire-end height (ft); 33 = flat top")
            axis.grid(axis="y", alpha=0.16)
            axis.set_axisbelow(True)
    _heading(
        figure,
        "Radiated fraction and mismatch are separate quantities",
        "Frozen lengths · target frequencies · average-ground baseline",
        footnote="Radiated fraction comes from integrating absolute gain "
        "over the upper hemisphere and dividing by 4π.\n"
        "It already contains modeled conductor and ground effects. "
        "Do not subtract it again from NEC gain; "
        "subtract mismatch only for realized gain.",
    )
    _save(figure, directory, "efficiency_mismatch", plt)


def _retuned_figure(data, directory, plt):
    if not any(c["mode"] == "retuned" for c in data["cases"]):
        return
    figure, axes = plt.subplots(3, 3, figsize=(15, 10.6))
    figure.subplots_adjust(
        left=0.075, right=0.985, top=0.83, bottom=0.12, hspace=0.43, wspace=0.24
    )
    for column, band in enumerate(BANDS):
        frozen, retuned = _cases(data, band), _cases(data, band, "retuned")
        for cases, style, color, label in (
            (frozen, "o-", "#bc4b24", "Frozen lengths"),
            (retuned, "s--", "#267bb6", "Retuned lengths"),
        ):
            xs = [c["end_height_ft"] for c in cases]
            axes[0, column].plot(
                xs, [c["swr"] for c in cases], style, color=color, label=label
            )
            for row, elevation in enumerate((20, 60), start=1):
                axes[row, column].plot(
                    xs,
                    [_gain(c, elevation, 90, True) for c in cases],
                    style,
                    color=color,
                    label=label,
                )
        axes[0, column].set_title(band)
        axes[0, column].set_ylabel("50 Ω SWR at target")
        axes[0, column].set_ylim(1, max(3, max(c["swr"] for c in data["cases"]) * 1.1))
        for row, elevation in enumerate((20, 60), start=1):
            axes[row, column].set_ylim(-15, 10)
            axes[row, column].set_ylabel(
                f"Broadside at {elevation}°\nRealized gain (dBi)"
            )
        for axis in axes[:, column]:
            axis.set_xticks([5, 10, 15, 20, 33])
            axis.set_xlabel("Outermost end height (ft)")
            axis.grid(alpha=0.18)
    _legend(figure, axes[0, 0])
    _heading(
        figure,
        "Retuning can recover mismatch; geometry still changes the pattern",
        "Retuned cases require different physical wire lengths "
        "or adjustments for each deployment",
        footnote="Both sets use the same ground and material assumptions. "
        "Broadside azimuth = 90°. Realized gain includes mismatch exactly once.\n"
        "Retuned comparisons alter the physical section lengths; "
        "they are a separate experiment "
        "from redeploying the frozen antenna.",
    )
    _save(figure, directory, "retuning_comparison", plt)


def _decomposition_figure(data, directory, plt):
    figure, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    figure.subplots_adjust(
        left=0.065, right=0.985, top=0.79, bottom=0.13, hspace=0.42, wspace=0.2
    )
    for column, band in enumerate(BANDS):
        cases = _cases(data, band)
        reference = cases[0]
        heights = [c["end_height_ft"] for c in cases]
        fraction = [
            10 * math.log10(c["efficiency_upper"] / reference["efficiency_upper"])
            for c in cases
        ]
        for row, elevation in enumerate((20, 60)):
            axis = axes[row, column]
            accepted = [
                _gain(c, elevation, 90) - _gain(reference, elevation, 90) for c in cases
            ]
            direction = [a - f for a, f in zip(accepted, fraction, strict=True)]
            realized = [
                _gain(c, elevation, 90, True) - _gain(reference, elevation, 90, True)
                for c in cases
            ]
            axis.plot(
                heights, accepted, "o-", color="#172d47", label="Accepted gain change"
            )
            axis.plot(
                heights, fraction, "s-", color="#227963", label="Radiated-fraction term"
            )
            axis.plot(
                heights, direction, "^--", color="#bc4b24", label="Directivity term"
            )
            axis.plot(
                heights,
                realized,
                ":",
                color="#267bb6",
                linewidth=2.3,
                label="Realized gain change",
            )
            axis.axhline(0, color="#8da0af", linewidth=0.8)
            axis.set_ylim(-4, 6)
            axis.set_xticks([5, 10, 15, 20, 33])
            axis.set_xlabel("Outermost end height (ft)")
            axis.set_ylabel(
                f"Broadside at {elevation}°\n"
                f"Change from {reference['end_height_ft']:g} ft ends (dB)"
            )
            axis.grid(alpha=0.15)
            if row == 0:
                axis.set_title(band)
    _legend(figure, axes[0, 0])
    _heading(
        figure,
        "How much is loss reduction, and how much is direction?",
        "Frozen lengths · accepted gain change = radiated-fraction term + "
        f"directivity term · reference = {reference['end_height_ft']:g} ft ends",
        footnote="Radiated-fraction term = 10 log₁₀(η / ηref); "
        "directivity term = accepted gain change minus that term.\n"
        "The reference is the lowest deployment, not the nominal tuning geometry. "
        "The realized curve includes each case's change in mismatch loss.",
    )
    _save(figure, directory, "gain_decomposition", plt)


def _sensitivity_figure(data, directory, plt):
    soil_cases = [
        c
        for c in data.get("sensitivity", [])
        if c.get("variant", "").startswith("soil-wire-")
    ]
    if not soil_cases:
        return
    figure, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    figure.subplots_adjust(
        left=0.065, right=0.985, top=0.79, bottom=0.13, hspace=0.42, wspace=0.2
    )
    nominal_conductivity = data["config"]["effective_conductivity_s_m"]
    for column, band in enumerate(BANDS):
        for row, elevation in enumerate((20, 60)):
            axis = axes[row, column]
            key = f"realized_broadside_{elevation}deg_dbi"
            nominal = _cases(data, band)
            heights = [c["end_height_ft"] for c in nominal]
            for ground, color in (
                ("poor", "#bc4b24"),
                ("average", "#267bb6"),
                ("good", "#227963"),
            ):
                values = [
                    [
                        c
                        for c in soil_cases
                        if c["band"] == band
                        and c["ground"] == ground
                        and c["end_height_ft"] == height
                    ]
                    for height in heights
                ]
                if any(not v for v in values):
                    continue
                lower = [min(c[key] for c in rows) for rows in values]
                upper = [max(c[key] for c in rows) for rows in values]
                center = [
                    next(
                        c[key]
                        for c in rows
                        if math.isclose(
                            c["effective_conductivity_s_m"], nominal_conductivity
                        )
                    )
                    for rows in values
                ]
                axis.fill_between(heights, lower, upper, color=color, alpha=0.11)
                axis.plot(
                    heights, center, "o-", color=color, label=f"{ground.title()} ground"
                )
            axis.set_ylim(-10, 10)
            axis.set_xticks([5, 10, 15, 20, 33])
            axis.set_xlabel("Outermost end height (ft)")
            axis.set_ylabel(f"Broadside at {elevation}°\nRealized gain (dBi)")
            axis.grid(alpha=0.15)
            if row == 0:
                axis.set_title(band)
    _legend(figure, axes[0, 0])
    _heading(
        figure,
        "Which deployment trends survive soil and wire uncertainty?",
        "Frozen lengths · solid lines use the nominal effective conductivity; "
        "shading spans the configured wire-loss bounds",
        footnote="Bands are sensitivity ranges, not probability intervals. "
        "The optimistic solid-copper comparator is not an estimate of "
        "copper-clad-steel loss.\n"
        "Every point includes its computed 50 Ω mismatch once. "
        "All material and soil assumptions remain configurable.",
    )
    _save(figure, directory, "soil_wire_sensitivity", plt)


def render_artifacts(output_dir: Path, data: dict[str, Any]) -> None:
    """Write reproducible static figures and an offline, data-backed HTML viewer."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(
        {
            "font.size": 10,
            "axes.titlesize": 13,
            "font.family": "DejaVu Sans",
            "svg.hashsalt": "linked-dipole",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": "#26394d",
            "text.color": "#172d47",
        }
    ):
        _geometry_figure(data, figures, plt)
        for realized in (False, True):
            _pattern_figure(data, figures, plt, realized=realized)
            _pattern_figure(data, figures, plt, azimuth=True, realized=realized)
        _swr_figure(data, figures, plt)
        _summary_figure(data, figures, plt)
        _retuned_figure(data, figures, plt)
        _decomposition_figure(data, figures, plt)
        _sensitivity_figure(data, figures, plt)
    (output_dir / "viewer.html").write_text(_viewer_html(data), encoding="utf-8")


def _viewer_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Retain exact computed cuts and metadata while omitting unused full grids.

    The offline viewer displays broadside/end-on elevation cuts, four fixed
    elevation azimuth cuts, and the directional table. Filtering the grid
    preserves every original value needed by those views; no interpolation or
    rounding is applied. Full hemispheres remain in the reproducible study JSON.
    """
    cases = []
    for case in data["cases"]:
        compact = {
            key: value
            for key, value in case.items()
            if key not in {"pattern", "power_budget"}
        }
        compact["pattern"] = [
            point
            for point in case["pattern"]
            if point[1] in {0, 90} or point[0] in {10, 20, 30, 60}
        ]
        cases.append(compact)
    return {"cases": cases, "config": data.get("config", {})}


def _viewer_html(data: dict[str, Any]) -> str:
    """Embed compact exact values with configuration-driven default selections."""
    payload = _viewer_payload(data)
    config = payload["config"]
    frequencies = {c["band"]: c["frequency_mhz"] for c in payload["cases"]}
    frequencies.update(config.get("bands_mhz", {}))
    bands = sorted(
        {c["band"] for c in payload["cases"]},
        key=lambda band: frequencies[band],
    )
    heights = sorted({c["end_height_ft"] for c in payload["cases"]})
    center = config.get("center_height_ft", 33)
    nominal = config.get("nominal_end_height_ft", 10)
    selected_height = nominal if nominal in heights else heights[0]
    band_options = "".join(
        f'<option value="{escape(band, quote=True)}">{escape(band)} · '
        f"{frequencies[band]:g}"
        " MHz</option>"
        for band in bands
    )
    height_options = "".join(
        f'<option value="{height:g}"'
        f"{' selected' if height == selected_height else ''}>"
        f"{height:g} ft{' · flat top' if height == center else ''}</option>"
        for height in heights
    )
    html = _HTML.replace("__GAIN_LIMITS__", json.dumps(GAIN_LIMITS))
    html = html.replace("__BAND_OPTIONS__", band_options)
    html = html.replace("__HEIGHT_OPTIONS__", height_options)
    html = html.replace("__CENTER_HEIGHT__", f"{center:g}")
    html = html.replace("__NOMINAL_HEIGHT__", f"{nominal:g}")
    embedded = json.dumps(
        payload,
        separators=(",", ":"),
        allow_nan=False,
    ).replace("<", "\\u003c")
    return html.replace("__COMPUTED_DATA__", embedded)


_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Linked dipole · field deployment study</title>
<style>
:root{color-scheme:light;--ink:#172d47;--muted:#596c80;--line:#d9e1e6;--paper:#f4f6f7;--blue:#267bb6}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 system-ui,-apple-system,sans-serif}
header{background:var(--ink);color:white;padding:32px max(24px,calc((100vw - 1420px)/2))}
header p{margin:8px 0 0;color:#cad8e5;max-width:1000px}h1{font-size:30px;line-height:1.2;margin:0}h2{font-size:19px;margin:0 0 6px}
main{max-width:1468px;padding:24px;margin:auto}.eyebrow{text-transform:uppercase;letter-spacing:.13em;font-size:11px;font-weight:750;margin-bottom:8px;color:#a4d6e8}
.controls{display:flex;gap:20px;flex-wrap:wrap;align-items:end;background:white;border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:18px}
label{display:flex;flex-direction:column;gap:6px;font-size:12px;font-weight:650}select,button{font:inherit;color:var(--ink);background:white;border:1px solid #aebcc8;border-radius:6px;padding:8px 10px;min-height:40px}
select:focus,button:focus{outline:3px solid #87c9e3;outline-offset:2px}button{cursor:pointer}button:hover{background:#e9f1f7}
.mode-note{font-size:13px;background:#fff3df;border-left:4px solid #b78809;padding:12px 16px;margin-bottom:18px}
.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:18px}.metric{background:white;border:1px solid var(--line);border-radius:10px;padding:14px}
.metric b{display:block;font-size:22px;letter-spacing:-.025em}.metric span{display:block;font-size:11px;color:var(--muted)}.metric small{font-size:11px;color:var(--muted)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{min-width:0;background:white;border:1px solid var(--line);border-radius:12px;padding:20px}
.panel-head{display:flex;align-items:start;justify-content:space-between;gap:16px}.panel-head button{white-space:nowrap;font-size:12px;min-height:32px;padding:5px 8px}
.sub{font-size:12px;color:var(--muted);margin:0 0 8px}.full{grid-column:1/-1}svg{width:100%;height:auto;display:block}.legend{display:flex;flex-wrap:wrap;gap:5px 16px;font-size:12px;margin-top:8px}
.key{display:inline-block;width:22px;border-top:3px solid;margin-right:5px;vertical-align:middle}.dimensions{font-size:13px;color:var(--muted);display:flex;gap:10px 26px;flex-wrap:wrap}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:right;padding:9px 12px;border-bottom:1px solid var(--line);white-space:nowrap}th:first-child,td:first-child{text-align:left}th{font-weight:650;background:#f3f6f8}
footer{font-size:12px;color:var(--muted);margin-top:20px}a{color:#116e9e}.gain-help{font-size:13px;margin:0 0 16px;color:var(--muted)}
@media(max-width:1050px){.metrics{grid-template-columns:repeat(3,1fr)}}@media(max-width:740px){header{padding:24px}main{padding:14px}.grid{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}h1{font-size:24px}.controls{gap:12px}.panel{padding:14px}select{max-width:260px}}
@media print{header{background:white;color:var(--ink);padding:0}.controls,.panel-head button{display:none}main{padding:0}.panel{break-inside:avoid}.grid{display:block}.panel{margin-bottom:15px}}
</style></head><body>
<header><div class="eyebrow">Antenna lab / computed field reference</div><h1>One linked dipole. Five ways to hang it.</h1>
<p>__CENTER_HEIGHT__ ft center height · nominal tuning with __NOMINAL_HEIGHT__ ft outer ends · physically deployed 20/30/40m sections on every band · provisional model dimensions. Explore radiation direction, accepted-power radiation and 50 Ω mismatch.</p></header>
<main><div class="controls">
<label>Operating band<select id="band">__BAND_OPTIONS__</select></label>
<label>Outermost 40m wire ends<select id="height">__HEIGHT_OPTIONS__</select></label>
<label>Wire lengths<select id="mode"><option value="frozen">Frozen · same physical antenna</option><option value="retuned">Retuned for each deployment</option></select></label>
<label>Gain reference<select id="reference"><option value="accepted">Accepted feedpoint power</option><option value="realized">Available 50 Ω source power</option></select></label>
<label>Azimuth-cut elevation<select id="elevation"><option>10</option><option selected>20</option><option>30</option><option>60</option></select></label>
</div><div id="mode-note" class="mode-note"></div><div id="metrics" class="metrics" aria-live="polite"></div>
<p class="gain-help" id="gain-help"></p><div class="grid">
<section class="panel full"><div class="panel-head"><div><h2>The physical deployment</h2><p class="sub">Wire lies along the x axis. The electrically disconnected extensions remain conductors in the model.</p></div><button data-export="geometry">Export SVG</button></div><div id="geometry"></div><div id="dimensions" class="dimensions"></div></section>
<section class="panel"><div class="panel-head"><div><h2>Broadside elevation</h2><p class="sub">Azimuth 90° · regional high angles through lower angles</p></div><button data-export="broadside">Export SVG</button></div><div id="broadside"></div><div class="legend" data-legend></div></section>
<section class="panel"><div class="panel-head"><div><h2>End-on elevation</h2><p class="sub">Azimuth 0° · looking along the wire direction</p></div><button data-export="endon">Export SVG</button></div><div id="endon"></div><div class="legend" data-legend></div></section>
<section class="panel"><div class="panel-head"><div><h2>Azimuth at a fixed elevation</h2><p class="sub">0° / 180° end-on · 90° / 270° broadside</p></div><button data-export="azimuth">Export SVG</button></div><div id="azimuth"></div><div class="legend" data-legend></div></section>
<section class="panel"><div class="panel-head"><div><h2>50 Ω SWR sweep</h2><p class="sub">Full computed search · pale region is the requested band · dots are minima</p></div><button data-export="swr">Export SVG</button></div><div id="swr"></div><div class="legend" data-legend></div></section>
<section class="panel full"><h2>Selected deployment versus the flat-top reference</h2><p class="sub" id="table-caption"></p><div class="table-wrap"><table><thead><tr><th>Elevation / direction</th><th>Selected gain</th><th>Flat-top gain</th><th>Selected − flat top</th></tr></thead><tbody id="gain-table"></tbody></table></div></section>
</div><footer><strong>How to read this:</strong> Every pattern uses a common absolute dBi scale; no curve is normalized to its own peak. Values below −30 dBi are clipped in charts and retained in data. Radiation into the upper hemisphere is computed by integrating absolute gain over solid angle and dividing by 4π. This is distinct from NEC's printed efficiency. Feedline/common-mode currents, mast, coax/choke/tuner losses and unmeasured hardware are absent from the baseline. Patterns cannot guarantee contact distances. Retuning requires physical adjustments.<br><br>
This page is self-contained and works offline. It embeds exact sampled cuts and full SWR sweeps; full hemispheres remain in the reproducible study results. Export buttons save standalone SVG charts. <a href="README.md">Read the report, assumptions and reproduction commands</a> · <a href="figures/geometry_comparison.svg">All geometries</a> · <a href="figures/elevation_accepted.svg">Elevation comparison</a> · <a href="figures/retuning_comparison.svg">Retuning comparison</a> · <a href="figures/soil_wire_sensitivity.svg">Soil and wire uncertainty</a></footer></main>
<script id="computed-data" type="application/json">__COMPUTED_DATA__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('computed-data').textContent);
const GAIN_LIMITS=__GAIN_LIMITS__;
const COLORS=['#bc4b24','#b78809','#227963','#267bb6','#172d47'];
const EDGES=DATA.config.band_edges_mhz||{'40m':[7,7.3],'30m':[10.1,10.15],'20m':[14,14.35]};
const $=id=>document.getElementById(id), fmt=(x,n=2)=>Number.isFinite(x)?x.toFixed(n):'—';
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const label=c=>c.end_height_ft===c.geometry.center_height_ft?`${c.end_height_ft} ft · flat top`:`${c.end_height_ft} ft ends`;
const selected=()=>DATA.cases.filter(c=>c.mode===$('mode').value&&c.band===$('band').value).sort((a,b)=>a.end_height_ft-b.end_height_ft);
const current=()=>selected().find(c=>c.end_height_ft===Number($('height').value));
const penalty=c=>$('reference').value==='realized'?c.mismatch_loss_db:0;
const sample=(c,e,a)=>{const p=c.pattern.find(p=>Math.abs(p[0]-e)<1e-6&&Math.abs(p[1]-a)<1e-6);return p?p[2]-penalty(c):NaN;};
function cut(c,fixed,value){let points=c.pattern.filter(p=>Math.abs(p[fixed]-value)<1e-6).map(p=>[p[1-fixed],p[2]-penalty(c)]).sort((a,b)=>a[0]-b[0]);if(fixed===0&&points.length&&points.at(-1)[0]<360)points.push([360,points[0][1]]);return points;}
function svgStart(w,h,title){return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}"><rect width="${w}" height="${h}" fill="white"/><style>text{font-family:system-ui,-apple-system,sans-serif;fill:#344c63;font-size:12px}</style>`;}
function chart(id,series,opt){const W=660,H=330,L=58,R=17,T=31,B=48,w=W-L-R,h=H-T-B;const xs=x=>L+(x-opt.x[0])/(opt.x[1]-opt.x[0])*w,ys=y=>T+(opt.y[1]-y)/(opt.y[1]-opt.y[0])*h;let s=svgStart(W,H,opt.title);s+=`<defs><clipPath id="clip-${id}"><rect x="${L}" y="${T}" width="${w}" height="${h}"/></clipPath></defs><text x="${L}" y="17" style="font-weight:650">${esc(opt.title)}</text>`;
if(opt.shade)s+=`<rect x="${xs(opt.shade[0])}" y="${T}" width="${xs(opt.shade[1])-xs(opt.shade[0])}" height="${h}" fill="#edf5f8"/>`;
for(const y of opt.yticks)s+=`<line x1="${L}" x2="${W-R}" y1="${ys(y)}" y2="${ys(y)}" stroke="#dde4e9"/><text x="${L-9}" y="${ys(y)+4}" text-anchor="end">${y}</text>`;
for(const x of opt.xticks)s+=`<line y1="${T}" y2="${H-B}" x1="${xs(x)}" x2="${xs(x)}" stroke="#eef1f4"/><text x="${xs(x)}" y="${H-B+22}" text-anchor="middle">${opt.freq?fmt(x,3):x}</text>`;
s+=`<g clip-path="url(#clip-${id})">`;
if(opt.marker)s+=`<line x1="${xs(opt.marker)}" x2="${xs(opt.marker)}" y1="${T}" y2="${H-B}" stroke="#8195a5" stroke-dasharray="3 3"/>`;
for(const line of series){const points=line.points.filter(p=>p.every(Number.isFinite));const d=points.map((p,i)=>`${i?'L':'M'}${fmt(xs(p[0]),2)},${fmt(ys(p[1]),2)}`).join(' ');s+=`<path d="${d}" fill="none" stroke="${line.color}" stroke-width="${line.selected?3.3:1.5}" opacity="${line.selected?1:.57}" ${line.flat?'stroke-dasharray="7 4"':''}/>`;if(line.dot)s+=`<circle cx="${xs(line.dot[0])}" cy="${ys(line.dot[1])}" r="${line.selected?4:3}" fill="${line.color}"/>`;}
s+=`</g><line x1="${L}" x2="${W-R}" y1="${H-B}" y2="${H-B}" stroke="#8da0af"/><text x="${L+w/2}" y="${H-5}" text-anchor="middle">${esc(opt.xlabel)}</text><text transform="translate(15 ${T+h/2}) rotate(-90)" text-anchor="middle">${esc(opt.ylabel)}</text></svg>`;$(id).innerHTML=s;}
function geometry(c){const g=c.geometry,W=1260,H=290,cumulative=[0,c.section_lengths_ft[0],c.section_lengths_ft[0]+c.section_lengths_ft[1],c.section_lengths_ft.reduce((a,b)=>a+b,0)],heights=[g.center_height_ft,g.link_a_height_ft,g.link_b_height_ft,g.end_height_ft];const extent=Math.max(g.span_ft/2,g.stake_distance_ft||0)+7,scale=Math.min((W-50)/(2*extent),(H-75)/g.center_height_ft),x=v=>W/2+v*scale,y=v=>H-44-v*scale;let s=svgStart(W,H,'Selected physical linked dipole geometry');s+=`<line x1="25" x2="${W-25}" y1="${y(0)}" y2="${y(0)}" stroke="#a0ae96"/><text x="28" y="${y(0)-8}">level ground</text><line x1="${x(0)}" x2="${x(0)}" y1="${y(0)}" y2="${y(g.center_height_ft)}" stroke="#b3c2cc" stroke-dasharray="4 4"/>`;
const legRun=Math.sqrt(cumulative[3]**2-(g.center_height_ft-g.end_height_ft)**2),bridgeHalf=g.span_ft/2-legRun,along=d=>bridgeHalf+d/cumulative[3]*legRun;
s+=`<line x1="${x(-bridgeHalf)}" x2="${x(bridgeHalf)}" y1="${y(g.center_height_ft)}" y2="${y(g.center_height_ft)}" stroke="#172d47" stroke-width="3"/>`;
for(const side of [-1,1]){for(let j=0;j<3;j++){const a=side*along(cumulative[j]),b=side*along(cumulative[j+1]);const active=j===0||(j===1&&c.band!=='20m')||(j===2&&c.band==='40m');s+=`<line x1="${x(a)}" x2="${x(b)}" y1="${y(heights[j])}" y2="${y(heights[j+1])}" stroke="${['#267bb6','#227963','#bc4b24'][j]}" stroke-width="${active?4:2.2}" ${active?'':'stroke-dasharray="5 3"'}/>`;}
for(let j=1;j<3;j++){const a=side*along(cumulative[j]);const closed=(j===1&&c.band!=='20m')||(j===2&&c.band==='40m');s+=`<circle cx="${x(a)}" cy="${y(heights[j])}" r="5" fill="${closed?'#172d47':'white'}" stroke="#172d47"/><text x="${x(a)}" y="${y(heights[j])-12}" text-anchor="middle">${j===1?'A':'B'} ${closed?'closed':'open'}</text>`;}
const end=side*g.span_ft/2;if(g.stake_distance_ft!=null){s+=`<line x1="${x(end)}" x2="${x(side*g.stake_distance_ft)}" y1="${y(g.end_height_ft)}" y2="${y(0)}" stroke="#687885" stroke-width="2" stroke-dasharray="6 4"/>`;}else{s+=`<line x1="${x(end)}" x2="${x(end)}" y1="${y(0)}" y2="${y(g.end_height_ft)}" stroke="#a6b3bb" stroke-width="3"/>`;}s+=`<text x="${x(end)}" y="${y(g.end_height_ft)+20}" text-anchor="middle">${fmt(g.end_height_ft,0)} ft end</text>`;}
s+=`<circle cx="${x(0)}" cy="${y(g.center_height_ft)}" r="5" fill="#172d47"/><text x="${x(0)}" y="${y(g.center_height_ft)-14}" text-anchor="middle">${fmt(g.center_height_ft,0)} ft balanced feedpoint</text><text x="${W/2}" y="${H-8}" text-anchor="middle">Wire span ${fmt(g.span_ft,1)} ft · included apex angle ${fmt(g.apex_angle_deg,1)}° · x axis / azimuth 0° →</text></svg>`;$('geometry').innerHTML=s;
$('dimensions').innerHTML=[`Link A height <b>${fmt(g.link_a_height_ft,1)} ft</b>`,`Link B height <b>${fmt(g.link_b_height_ft,1)} ft</b>`,`Per-leg model sections <b>${c.section_lengths_ft.map(n=>fmt(n,3)).join(' / ')} ft</b>`,g.stake_distance_ft==null?'Flat top requires elevated end supports':`Stake from center <b>${fmt(g.stake_distance_ft,1)} ft</b> · cord <b>${fmt(g.cord_length_ft,1)} ft / side</b>`].map(t=>`<span>${t}</span>`).join('');}
function update(){const cases=selected(),c=current();if(!c)return;const realized=$('reference').value==='realized',gainName=realized?'Realized gain':'Accepted-power gain';
$('mode-note').textContent=$('mode').value==='frozen'?'Frozen comparison: every deployment uses the same provisional section lengths, tuned in the __CENTER_HEIGHT__ ft center / __NOMINAL_HEIGHT__ ft outer-end geometry. Link heights follow the full wire slope on every band.':'Retuned comparison: the complete physical assembly is tuned separately for each deployment. These cases require different section lengths or physical adjustments.';
const r=fmt(c.r_ohm,1),x=`${c.x_ohm<0?'−':'+'}j${fmt(Math.abs(c.x_ohm),1)}`;
const cards=[['Feedpoint impedance',`${r}${x} Ω`,`${fmt(c.frequency_mhz,3)} MHz`],['50 Ω SWR',`${fmt(c.swr,2)}:1`,`Mismatch loss ${fmt(c.mismatch_loss_db,2)} dB`],['Resonance · X = 0',`${fmt(c.resonance_mhz,4)}`,`MHz · min SWR ${fmt(c.min_swr,2)} at ${fmt(c.min_swr_frequency_mhz,4)}`],['Upper-hemisphere radiation',`${fmt(c.efficiency_upper*100,1)}%`,'Fraction of accepted feedpoint power'],[realized?'Peak realized gain':'Peak absolute gain',`${fmt(c.peak_gain_dbi-penalty(c),2)} dBi`,`Elevation ${fmt(c.peak_elevation_deg,0)}° · azimuth ${fmt(c.peak_azimuth_deg,0)}°`],['Broadside / 20°',`${fmt(sample(c,20,90),2)} dBi`,gainName]];
$('metrics').innerHTML=cards.map(([a,b,d])=>`<div class="metric"><span>${a}</span><b>${b}</b><small>${d}</small></div>`).join('');
$('gain-help').textContent=realized?'Realized gain = NEC accepted-power gain minus this case’s mismatch loss once. The accepted-power radiation fraction is already included in NEC gain.':'Accepted-power gain includes modeled conductor and ground effects. Mismatch is excluded here; switch the gain reference to see available-power realized gain.';
geometry(c);const makeSeries=fn=>cases.map((a,i)=>({points:fn(a),color:COLORS[i],selected:a.case_id===c.case_id,flat:a.end_height_ft===33}));
const opts={x:[0,90],y:GAIN_LIMITS,xticks:[0,15,30,45,60,75,90],yticks:[-30,-20,-10,0,10],xlabel:'Elevation (°)',ylabel:`${gainName} (dBi)`};
chart('broadside',makeSeries(a=>cut(a,1,90)),{...opts,title:`${c.band} · broadside at azimuth 90°`});chart('endon',makeSeries(a=>cut(a,1,0)),{...opts,title:`${c.band} · end-on at azimuth 0°`});
chart('azimuth',makeSeries(a=>cut(a,0,Number($('elevation').value))),{...opts,x:[0,360],xticks:[0,90,180,270,360],xlabel:'Azimuth (°)',title:`${c.band} · ${$('elevation').value}° elevation`});
const lo=Math.min(...cases.map(a=>a.sweep[0][0])),hi=Math.max(...cases.map(a=>a.sweep.at(-1)[0]));const swrSeries=makeSeries(a=>a.sweep.map(p=>[p[0],p[3]]));swrSeries.forEach((s,i)=>s.dot=[cases[i].min_swr_frequency_mhz,cases[i].min_swr]);chart('swr',swrSeries,{x:[lo,hi],y:[1,6],xticks:Array.from({length:5},(_,i)=>lo+(hi-lo)*i/4),yticks:[1,2,3,4,5,6],freq:true,xlabel:'Frequency (MHz)',ylabel:'50 Ω SWR',title:`${c.band} · ${$('mode').value} lengths · SWR above 6 clipped`,shade:EDGES[c.band],marker:c.frequency_mhz});
const legend=cases.map((a,i)=>`<span style="${a.case_id===c.case_id?'font-weight:750':''}"><i class="key" style="border-color:${COLORS[i]};${a.end_height_ft===33?'border-top-style:dashed':''}"></i>${label(a)}</span>`).join('');document.querySelectorAll('[data-legend]').forEach(el=>el.innerHTML=legend);
const flat=cases.find(a=>a.end_height_ft===33);let rows='';for(const e of [10,20,30,60,90])for(const a of (e===90?[90]:[90,0])){const v=sample(c,e,a),f=sample(flat,e,a),d=v-f;rows+=`<tr><td>${e}° · ${e===90?'zenith (azimuth arbitrary)':a===90?'broadside (90° az.)':'end-on (0° az.)'}</td><td>${fmt(v)} dBi</td><td>${fmt(f)} dBi</td><td>${d>0?'+':''}${fmt(d)} dB</td></tr>`;}$('gain-table').innerHTML=rows;$('table-caption').textContent=`${gainName} · ${fmt(c.frequency_mhz,3)} MHz · ${$('mode').value} lengths. Positive difference favors the selected deployment in that direction.`;
}
document.querySelectorAll('select').forEach(el=>el.addEventListener('change',update));
document.querySelectorAll('[data-export]').forEach(button=>button.addEventListener('click',()=>{const id=button.dataset.export,svg=$(id).querySelector('svg'),text=new XMLSerializer().serializeToString(svg),blob=new Blob([text],{type:'image/svg+xml;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`linked-dipole-${$('band').value}-${$('height').value}ft-${$('mode').value}-${$('reference').value}-${id}.svg`;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}));
update();
</script></body></html>"""  # noqa: E501
