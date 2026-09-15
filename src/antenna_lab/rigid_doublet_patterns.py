"""Absolute NEC gain cuts for comparing rigid doublet arm lengths."""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from antenna_lab.nec import find_nec2c, run_cached
from antenna_lab.rigid_doublet import RigidDoublet, rigid_doublet_deck


def plot_comparison(
    *,
    output_dir: str | Path,
    nec2c: str | Path,
    cache_dir: str | Path = "build/rigid-v-pattern-cache",
    arm_lengths_ft: tuple[float, ...] = (17, 25),
    feed_height_ft: float = 30,
    arm_elevation_deg: float = 30,
    radius_m: float = 0.0015,
    arm_segments: int = 181,
    feed_gap_m: float = 0.06,
    conductivity_s_m: float = 1.4e6,
    epsilon_r: float = 13,
    ground_conductivity_s_m: float = 0.005,
) -> dict[str, Any]:
    """Write absolute gain cuts, full sampled patterns, and case provenance.

    The three bands use 7.15, 14.175 and 28.5 MHz. Ground is epsilon_r=13,
    conductivity=0.005 S/m; radiator conductivity is 1.4e6 S/m. Gains are at
    the antenna feedpoint, including this ground and conductor model but
    excluding the line, balun and tuner. Curves are not individually normalized.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not arm_lengths_ft or len(set(arm_lengths_ft)) != len(arm_lengths_ft):
        raise ValueError("Arm lengths must be nonempty and unique")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    executable = find_nec2c(nec2c)
    cache = Path(cache_dir)
    frequencies = {"40m": 7.15, "20m": 14.175, "10m": 28.5}
    conductivity = conductivity_s_m
    ground_conductivity = ground_conductivity_s_m
    samples: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    patterns: dict[tuple[float, str], tuple[tuple[float, float, float], ...]] = {}
    for arm_length in arm_lengths_ft:
        geometry = RigidDoublet(
            arm_length_ft=arm_length,
            feed_height_ft=feed_height_ft,
            arm_elevation_deg=arm_elevation_deg,
            radius_m=radius_m,
            arm_segments=arm_segments,
            feed_gap_m=feed_gap_m,
        )
        for band, frequency in frequencies.items():
            case_id = f"arm_{arm_length:g}ft_{band}"
            deck = rigid_doublet_deck(
                title=f"Rigid doublet pattern comparison {case_id}",
                geometry=geometry,
                frequency_mhz=frequency,
                conductivity_s_m=conductivity,
                epsilon_r=epsilon_r,
                ground_conductivity_s_m=ground_conductivity,
                pattern=True,
            )
            result, deck_path, result_path, _ = run_cached(deck, cache, executable)
            if not result.pattern or any(
                not all(math.isfinite(value) for value in point)
                for point in result.pattern
            ):
                raise ValueError(f"Missing or invalid NEC pattern for {case_id}")
            patterns[arm_length, band] = result.pattern
            peak = max(result.pattern, key=lambda point: point[2])
            broadside = next(
                gain
                for elevation, azimuth, gain in result.pattern
                if elevation == 20 and azimuth == 90
            )
            cases.append(
                dict(
                    case_id=case_id,
                    band=band,
                    frequency_mhz=frequency,
                    **asdict(geometry),
                    tip_height_ft=geometry.tip_height_ft,
                    span_ft=geometry.span_ft,
                    conductivity_s_m=conductivity,
                    ground_epsilon_r=epsilon_r,
                    ground_conductivity_s_m=ground_conductivity,
                    feedpoint_r_ohm=result.impedance_ohm.real,
                    feedpoint_x_ohm=result.impedance_ohm.imag,
                    nec_reported_efficiency=result.efficiency,
                    broadside_gain_20deg_dbi=broadside,
                    peak_gain_dbi=peak[2],
                    peak_elevation_deg=peak[0],
                    peak_azimuth_deg=peak[1],
                    nec_deck_sha256=_sha256(deck_path),
                    nec_output_sha256=_sha256(result_path),
                )
            )
            samples.extend(
                dict(
                    case_id=case_id,
                    arm_length_ft=arm_length,
                    band=band,
                    frequency_mhz=frequency,
                    elevation_deg=elevation,
                    azimuth_deg=azimuth,
                    feedpoint_gain_dbi=gain,
                )
                for elevation, azimuth, gain in result.pattern
            )

    plt.rcParams.update({"font.size": 11, "axes.titlesize": 14})
    figure, axes = plt.subplots(2, 3, figsize=(16, 9), sharey=True)
    figure.subplots_adjust(
        left=0.07, right=0.985, bottom=0.14, top=0.79, hspace=0.34, wspace=0.12
    )
    for column, (band, frequency) in enumerate(frequencies.items()):
        top, bottom = axes[0, column], axes[1, column]
        for arm_length in arm_lengths_ft:
            points = patterns[arm_length, band]
            azimuth_cut = sorted(
                (azimuth, gain)
                for elevation, azimuth, gain in points
                if elevation == 20
            )
            # Join the 355-to-360 degree interval using the periodic zero value.
            azimuth_cut.append((360, azimuth_cut[0][1]))
            elevation_cut = sorted(
                (elevation, gain)
                for elevation, azimuth, gain in points
                if azimuth == 90 and elevation > 0
            )
            label = f"{arm_length:g} ft per arm"
            top.plot(*zip(*azimuth_cut, strict=True), label=label, linewidth=2.2)
            bottom.plot(*zip(*elevation_cut, strict=True), label=label, linewidth=2.2)
        top.set_title(f"{band} · {frequency:g} MHz", pad=12)
        top.set_xlim(0, 360)
        top.set_xticks([0, 90, 180, 270, 360])
        top.set_xlabel("Azimuth (degrees)")
        bottom.set_xlim(0, 90)
        bottom.set_xticks([0, 15, 30, 45, 60, 75, 90])
        bottom.set_xlabel("Elevation (degrees)")
        bottom.axvline(20, color="0.6", linestyle=":", linewidth=1)
        for axis in (top, bottom):
            axis.set_ylim(-30, 12)
            axis.set_yticks([-30, -20, -10, 0, 10])
            axis.axhline(0, color="0.55", linewidth=0.8)
            axis.grid(alpha=0.22)
    axes[0, 0].set_ylabel("Azimuth cut at 20° elevation\nFeedpoint gain (dBi)")
    axes[1, 0].set_ylabel("Elevation cut at 90° azimuth\nFeedpoint gain (dBi)")
    title = " vs ".join(f"{length:g} ft" for length in arm_lengths_ft)
    figure.suptitle(f"{title} per arm rigid V doublets", fontsize=21, y=0.98)
    figure.text(
        0.5,
        0.923,
        f"{feed_height_ft:g} ft feedpoint · "
        f"arms {arm_elevation_deg:g}° above horizontal · average-ground model",
        ha="center",
        fontsize=13,
    )
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.89),
        ncols=len(arm_lengths_ft),
        frameon=False,
        fontsize=13,
    )
    figure.text(
        0.5,
        0.055,
        "Absolute antenna-feedpoint gain; curves are not normalized to their peaks. "
        "Excludes line, balun and tuner losses.\n"
        "Azimuth 0° lies in the arm plane; 90° is broadside. "
        "5° samples; horizon omitted from elevation cuts.\n"
        "Gains below −30 dBi fall outside the axes; full samples are saved.",
        ha="center",
        va="center",
        fontsize=11,
    )
    figure_path = output / "pattern_comparison.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    samples_path = output / "pattern_samples.csv"
    cases_path = output / "pattern_cases.csv"
    _write_csv(samples_path, samples)
    _write_csv(cases_path, cases)
    return dict(
        figure_file=figure_path.name,
        samples_file=samples_path.name,
        case_metadata_file=cases_path.name,
        case_count=len(cases),
        sample_count=len(samples),
        bands_mhz=frequencies,
        arm_lengths_ft=list(arm_lengths_ft),
        feed_height_ft=feed_height_ft,
        arm_elevation_deg=arm_elevation_deg,
        gain_reference="antenna_feedpoint_excludes_line_balun_tuner",
        gain_axis_limits_dbi=[-30, 12],
        individually_normalized=False,
        solver_sha256=_sha256(executable),
        source_sha256=_sha256(Path(__file__)),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
