"""Conventional polar views of the existing absolute radiation-pattern samples.

Vertical cuts combine two opposite azimuths through the upper hemisphere.
No samples are synthesized below ground or normalized to a case's own peak.
The displayed radius is an offset dBi value, not field strength or distance.
"""

from __future__ import annotations

import math
from typing import Any

GAIN_FLOOR = -30.0
GAIN_CEILING = 12.0


def radial_gain(gain: float) -> float:
    """Map absolute dBi onto the common clipped, evenly spaced dB rings."""
    if not math.isfinite(gain):
        raise ValueError("Polar gain must be finite")
    return min(GAIN_CEILING, max(GAIN_FLOOR, gain)) - GAIN_FLOOR


def elevation_polar_cut(
    case: dict[str, Any], azimuth_deg: float = 90, realized: bool = False
) -> list[tuple[float, float]]:
    """Return right horizon → zenith → left horizon, with unmodified dBi.

    The right half uses the requested azimuth; the left uses its actual opposite
    samples. Plot angle 180-elevation places the latter on the left. Zenith is
    shared by both azimuths and appears once, taken from the right-hand cut.
    """
    azimuth = azimuth_deg % 360
    opposite = (azimuth + 180) % 360
    penalty = case["mismatch_loss_db"] if realized else 0

    def samples(direction):
        return sorted(
            (elevation, gain - penalty)
            for elevation, angle, gain in case["pattern"]
            if 0 <= elevation <= 90
            and math.isclose(angle % 360, direction, abs_tol=1e-6)
        )

    right, left = samples(azimuth), samples(opposite)
    if not right or not left:
        raise ValueError("Vertical polar plot requires both opposite azimuth cuts")
    return right + sorted((180 - e, gain) for e, gain in left if e < 90)


def azimuth_polar_cut(
    case: dict[str, Any], elevation_deg: float = 20, realized: bool = False
) -> list[tuple[float, float]]:
    """Return an actual fixed-elevation azimuth sweep, closed at 360 degrees."""
    penalty = case["mismatch_loss_db"] if realized else 0
    samples = sorted(
        (azimuth, gain - penalty)
        for elevation, azimuth, gain in case["pattern"]
        if math.isclose(elevation, elevation_deg, abs_tol=1e-6) and 0 <= azimuth < 360
    )
    if not samples or not math.isclose(samples[0][0], 0, abs_tol=1e-6):
        raise ValueError("Horizontal polar plot requires an azimuth cut starting at 0")
    return [*samples, (360, samples[0][1])]


def _polar_axis(axis, *, vertical: bool) -> None:
    axis.set_theta_zero_location("E")
    axis.set_theta_direction(1)
    axis.set_ylim(0, GAIN_CEILING - GAIN_FLOOR)
    axis.set_yticks([10, 20, 30, 40], labels=["−20", "−10", "0", "+10 dBi"])
    axis.set_rlabel_position(45 if vertical else 35)
    axis.tick_params(labelsize=9, pad=5)
    axis.grid(color="#c5ced6", linewidth=0.75)
    axis.spines["polar"].set_color("#b2bec9")
    if vertical:
        axis.set_thetamin(0)
        axis.set_thetamax(180)
        axis.set_thetagrids(
            [0, 30, 60, 90, 120, 150, 180],
            ["0°", "30°", "60°", "90° · up", "60°", "30°", "0°"],
        )
        axis.spines["start"].set_color("#748276")
        axis.spines["end"].set_color("#748276")
        # Matplotlib puts half-circle radial labels along the ground line.
        # Label the rings inside the sky instead, keeping the horizon clear.
        axis.set_yticklabels([])
        for radius, label in zip(
            (10, 20, 30, 40), ("−20", "−10", "0", "+10 dBi"), strict=True
        ):
            axis.text(
                math.radians(130),
                radius,
                label,
                fontsize=8,
                color="#516171",
                ha="center",
                va="center",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.2),
            )
    else:
        axis.set_thetagrids(
            [0, 45, 90, 135, 180, 225, 270, 315],
            [
                "0°\nend-on",
                "45°",
                "90° · broadside",
                "135°",
                "180°\nend-on",
                "225°",
                "270° · broadside",
                "315°",
            ],
        )
    for label in axis.get_yticklabels():
        label.set_color("#516171")
        label.set_fontsize(8)
        label.set_bbox(dict(facecolor="white", edgecolor="none", alpha=0.7, pad=0.2))


def _trace(axis, case, *, vertical, fixed, realized, color, label, default=False):
    points = (
        elevation_polar_cut(case, fixed, realized)
        if vertical
        else azimuth_polar_cut(case, fixed, realized)
    )
    flat = case["end_height_ft"] == case["geometry"]["center_height_ft"]
    axis.plot(
        [math.radians(angle) for angle, _ in points],
        [radial_gain(gain) for _, gain in points],
        color=color,
        label=label,
        linewidth=2.6 if default else 1.8,
        linestyle="--" if flat else "-",
        zorder=4 if default else 3,
    )


def render_polar_artifacts(data, directory, plt) -> None:
    """Add PNG/SVG polar figures from already solved samples; no NEC calls."""
    from antenna_lab.linked_dipole_report import (
        BANDS,
        HEIGHT_COLORS,
        _cases,
        _label,
        _save,
    )

    config = data["config"]
    nominal = config["nominal_end_height_ft"]
    center = config["center_height_ft"]

    def finish(figure, axes, title, subtitle, name):
        figure.suptitle(title, fontsize=20, fontweight="bold", y=0.985)
        figure.text(0.5, 0.945, subtitle, ha="center", fontsize=11, color="#435267")
        handles, labels = axes.flat[0].get_legend_handles_labels()
        figure.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.918),
            ncols=len(labels),
            frameon=False,
        )
        figure.text(
            0.5,
            0.025,
            "Common absolute gain rings: −30 dBi at the center to +12 dBi at the "
            "outer edge; deep nulls clipped at −30 dBi.\n"
            "Radius shows gain, not contact distance. No individual peak "
            "normalization. Azimuths are relative to the wire, not compass bearings.",
            ha="center",
            fontsize=9,
            color="#435267",
        )
        _save(figure, directory, name, plt)

    figure, axes = plt.subplots(
        3, 2, figsize=(12, 16), subplot_kw={"projection": "polar"}
    )
    figure.subplots_adjust(
        left=0.055, right=0.92, top=0.79, bottom=0.08, hspace=0.8, wspace=0.3
    )
    for row, band in enumerate(BANDS):
        cases = _cases(data, band)
        selected = next(case for case in cases if case["end_height_ft"] == nominal)
        flat = next(case for case in cases if case["end_height_ft"] == center)
        right = [point for point in elevation_polar_cut(selected) if point[0] <= 90]
        peak_gain = max(gain for _, gain in right)
        peak_angles = [angle for angle, gain in right if gain == peak_gain]
        peak_angle_label = (
            f"{min(peak_angles):g}–{max(peak_angles):g}"
            if len(peak_angles) > 1
            else f"{peak_angles[0]:g}"
        )
        for column, vertical in enumerate((True, False)):
            axis = axes[row, column]
            _polar_axis(axis, vertical=vertical)
            for case, color, label, default in (
                (selected, "#227963", f"{nominal:g} ft ends · default", True),
                (flat, "#748394", f"{center:g} ft ends · flat top", False),
            ):
                _trace(
                    axis,
                    case,
                    vertical=vertical,
                    fixed=90 if vertical else 20,
                    realized=False,
                    color=color,
                    label=label,
                    default=default,
                )
            title = (
                f"{band} · vertical / broadside\n"
                f"Default cut peak: {peak_angle_label}° elevation · {peak_gain:.2f} dBi"
                if vertical
                else f"{band} · horizontal / azimuth\n20° elevation"
            )
            axis.set_title(title, fontsize=12, pad=23)
    finish(
        figure,
        axes,
        "Linked dipole: vertical and horizontal patterns",
        f"{center:g} ft feedpoint · same wire lengths tuned at {nominal:g} ft ends · "
        "accepted-power gain, before 50 Ω mismatch",
        "polar_default_accepted",
    )

    for realized in (False, True):
        reference = (
            "Realized gain · 50 Ω mismatch included once"
            if realized
            else "Accepted-power gain · before 50 Ω mismatch"
        )
        suffix = "realized" if realized else "accepted"
        for vertical in (True, False):
            rows = (90, 0) if vertical else (20, 60)
            figure, axes = plt.subplots(
                2,
                3,
                figsize=(16.5, 9 if vertical else 12),
                subplot_kw={"projection": "polar"},
            )
            figure.subplots_adjust(
                left=0.045,
                right=0.945,
                top=0.8,
                bottom=0.1,
                hspace=0.38 if vertical else 0.5,
                wspace=0.38,
            )
            for column, band in enumerate(BANDS):
                for row, fixed in enumerate(rows):
                    axis = axes[row, column]
                    _polar_axis(axis, vertical=vertical)
                    for case, color in zip(
                        _cases(data, band), HEIGHT_COLORS, strict=True
                    ):
                        _trace(
                            axis,
                            case,
                            vertical=vertical,
                            fixed=fixed,
                            realized=realized,
                            color=color,
                            label=_label(case),
                            default=case["end_height_ft"] == nominal,
                        )
                    cut = (
                        (
                            "Broadside · az. 90° / 270°"
                            if fixed == 90
                            else "End-on · az. 0° / 180°"
                        )
                        if vertical
                        else f"{fixed}° elevation"
                    )
                    axis.set_title(f"{band} · {cut}", fontsize=12, pad=23)
            finish(
                figure,
                axes,
                "Vertical radiation patterns"
                if vertical
                else "Horizontal radiation patterns",
                f"{reference} · all five deployments · unchanged wire lengths",
                f"polar_{'elevation' if vertical else 'azimuth'}_{suffix}",
            )
