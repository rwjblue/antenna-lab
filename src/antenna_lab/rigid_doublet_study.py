"""Exploratory rigid V doublet: NEC loads and balanced-line length screening.

The continuous lossless L-network screen is not a Z-100A simulation. It tests
exact 50-ohm matching within published aggregate L/C limits; it omits discrete
banks, firmware, losses, parasitics, and tolerable residual mismatch.
"""

from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from antenna_lab.efrw_study import (
    _sha256,
    _solver_version,
    _write_csv,
    _write_json,
    _write_manifest,
)
from antenna_lab.nec import find_nec2c, run_cached
from antenna_lab.rigid_doublet import (
    FloatingMast,
    RigidDoublet,
    rigid_doublet_deck,
)
from antenna_lab.rigid_doublet_validation import validate_geometry
from antenna_lab.transmission_line import (
    C_FT_S,
    LineParameters,
    input_impedance,
    line_efficiency,
    swr,
)


def continuous_l_match(
    load: complex, frequency_hz: float, max_l_uh: float, max_c_pf: float
) -> dict[str, Any]:
    """Find exact lossless low-pass L matches with either shunt-C position.

    Positive series inductance and shunt capacitance only. An empty solution
    does not prove a real tuner cannot reach an acceptable, imperfect match.
    """
    values = (load.real, load.imag, frequency_hz, max_l_uh, max_c_pf)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Matching inputs must be finite")
    if load.real <= 0 or min(frequency_hz, max_l_uh, max_c_pf) <= 0:
        raise ValueError(
            "Passive load and positive frequency/component limits required"
        )
    omega = 2 * math.pi * frequency_hz
    candidates = []

    def add(topology: str, reactance: float, susceptance: float) -> None:
        if reactance < -1e-10 or susceptance < -1e-12:
            return
        inductance = max(0.0, reactance) / omega * 1e6
        capacitance = max(0.0, susceptance) / omega * 1e12
        candidates.append(
            dict(
                ideal_topology=topology,
                ideal_l_uh=inductance,
                ideal_c_pf=capacitance,
                continuous_lc_screen=bool(
                    inductance <= max_l_uh and capacitance <= max_c_pf
                ),
            )
        )

    if load.real <= 50:
        residual_x = math.sqrt(max(0.0, load.real * (50 - load.real)))
        add(
            "source_shunt",
            residual_x - load.imag,
            residual_x / (50 * load.real),
        )
    admittance = 1 / load
    if admittance.real <= 1 / 50:
        residual_b = math.sqrt(max(0.0, admittance.real / 50 - admittance.real**2))
        add(
            "load_shunt",
            residual_b * 50 / admittance.real,
            residual_b - admittance.imag,
        )
    if not candidates:
        return dict(
            ideal_topology="no_exact_lowpass_solution",
            ideal_l_uh=None,
            ideal_c_pf=None,
            continuous_lc_screen=False,
        )
    return min(
        candidates,
        key=lambda row: (
            not row["continuous_lc_screen"],
            row["ideal_l_uh"] / max_l_uh + row["ideal_c_pf"] / max_c_pf,
        ),
    )


def minimum_routed_length(feed_height_ft: float, routing: dict[str, float]) -> float:
    """Straight sloping run plus explicit slack; not a detailed installation path."""
    values = [feed_height_ft, *routing.values()]
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise ValueError("Routing dimensions must be finite and nonnegative")
    return (
        math.hypot(
            feed_height_ft - routing["tuner_height_ft"], routing["horizontal_offset_ft"]
        )
        + routing["slack_ft"]
    )


def _nec_case(job: tuple) -> dict[str, Any]:
    config, case, band, frequency, executable, cache = job
    geometry_values = dict(config["geometry"])
    geometry_values.update({key: case[key] for key in geometry_values if key in case})
    geometry = RigidDoublet(**geometry_values)
    mast = FloatingMast(**case["mast"]) if "mast" in case else None
    ground = config["grounds"][case.get("ground", "average")]
    conductivity = case.get("conductivity_s_m", config["conductivity_s_m"])
    deck = rigid_doublet_deck(
        title=f"Rigid doublet {case['id']} {band}",
        geometry=geometry,
        frequency_mhz=frequency,
        conductivity_s_m=conductivity,
        epsilon_r=ground["epsilon_r"],
        ground_conductivity_s_m=ground["conductivity_s_m"],
        mast=mast,
        pattern=True,
    )
    result, deck_path, output_path, _ = run_cached(deck, cache, executable)
    if (
        not math.isfinite(abs(result.impedance_ohm))
        or result.impedance_ohm.real <= 0
        or result.efficiency is None
        or not 0 < result.efficiency <= 1.0001
        or not result.pattern
    ):
        raise ValueError(f"Invalid NEC result: {case['id']}/{band}")
    row = dict(
        case_id=case["id"],
        band=band,
        frequency_mhz=frequency,
        **asdict(geometry),
        tip_height_ft=geometry.tip_height_ft,
        span_ft=geometry.span_ft,
        conductivity_s_m=conductivity,
        ground=case.get("ground", "average"),
        mast=bool(mast),
        feedpoint_r_ohm=result.impedance_ohm.real,
        feedpoint_x_ohm=result.impedance_ohm.imag,
        nec_reported_efficiency=result.efficiency,
        peak_gain_dbi=max(point[2] for point in result.pattern),
        nec_deck_sha256=_sha256(deck_path),
        nec_output_sha256=_sha256(output_path),
    )
    for elevation in (20, 45, 90):
        row[f"broadside_gain_{elevation}deg_dbi"] = min(
            result.pattern,
            key=lambda point: abs(point[0] - elevation) + abs(point[1] - 90),
        )[2]
    return row


def line_rows(config: dict[str, Any], nec_rows: list[dict]) -> list[dict]:
    sweep = config["line_sweep_ft"]
    if (
        not all(math.isfinite(value) and value > 0 for value in sweep.values())
        or sweep["stop"] < sweep["start"]
        or not all(
            math.isfinite(value) and value > 0 for value in config["spot_lengths_ft"]
        )
        or not all(
            math.isfinite(value) and value > 0
            for value in config["balun_impedance_ratios"]
        )
    ):
        raise ValueError("Invalid positive line-length sweep")
    lengths = sorted(
        set(np.arange(sweep["start"], sweep["stop"] + 1e-8, sweep["step"]).tolist())
        | set(config["spot_lengths_ft"])
    )
    limits = config["tuner_limits"]
    rows = []
    for antenna in nec_rows:
        case_lengths = (
            lengths
            if antenna["case_id"] == config["reference_case"]
            else config["spot_lengths_ft"]
        )
        frequency = antenna["frequency_mhz"] * 1e6
        load = complex(antenna["feedpoint_r_ohm"], antenna["feedpoint_x_ohm"])
        minimum_length = minimum_routed_length(
            antenna["feed_height_ft"], config["routing"]
        )
        for scenario in config["line_scenarios"]:
            line = LineParameters(
                scenario["z0_ohm"],
                scenario["velocity_factor"],
                scenario["loss_db_per_100ft_at_10mhz"],
            )
            for length in case_lengths:
                zin = complex(input_impedance(load, frequency, length, line))
                eta = float(line_efficiency(load, frequency, length, line))
                if not 0 < eta <= 1.0000001:
                    raise ValueError("Nonpassive line result")
                for ratio in config["balun_impedance_ratios"]:
                    if ratio <= 0:
                        raise ValueError("Balun impedance ratio must be positive")
                    tuner_load = zin / ratio
                    raw_swr = float(swr(tuner_load))
                    rows.append(
                        dict(
                            case_id=antenna["case_id"],
                            band=antenna["band"],
                            frequency_mhz=antenna["frequency_mhz"],
                            line_id=scenario["id"],
                            length_ft=length,
                            length_m=length * 0.3048,
                            balun_impedance_ratio=ratio,
                            minimum_route_ft=minimum_length,
                            route_feasible=length >= minimum_length,
                            electrical_length_degrees=360
                            * frequency
                            * length
                            / (C_FT_S * line.velocity_factor),
                            line_input_r_ohm=zin.real,
                            line_input_x_ohm=zin.imag,
                            tuner_load_r_ohm=tuner_load.real,
                            tuner_load_x_ohm=tuner_load.imag,
                            raw_swr_50ohm=raw_swr,
                            within_advertised_swr=raw_swr <= limits["advertised_swr"],
                            line_efficiency=eta,
                            line_loss_db=-10 * math.log10(eta),
                            **continuous_l_match(
                                tuner_load,
                                frequency,
                                limits["max_l_uh"],
                                limits["max_c_pf"],
                            ),
                        )
                    )
    return rows


def rank_lengths(config: dict, rows: list[dict]) -> list[dict]:
    """Descriptive screen counts over equally weighted cases, not probabilities."""
    grouped: dict[tuple, list] = {}
    for row in rows:
        if row["case_id"] != config["reference_case"] or not row["route_feasible"]:
            continue
        grouped.setdefault((row["length_ft"], row["balun_impedance_ratio"]), []).append(
            row
        )
    ranking = []
    for (length, ratio), group in grouped.items():
        dry = [row for row in group if row["line_id"] != "wet_stress"]
        ranking.append(
            dict(
                length_ft=length,
                length_m=length * 0.3048,
                balun_impedance_ratio=ratio,
                dry_lc_passes=sum(row["continuous_lc_screen"] for row in dry),
                dry_cases=len(dry),
                all_lc_passes=sum(row["continuous_lc_screen"] for row in group),
                all_cases=len(group),
                dry_worst_line_loss_db=max(row["line_loss_db"] for row in dry),
                dry_worst_raw_swr=max(row["raw_swr_50ohm"] for row in dry),
            )
        )
    return sorted(
        ranking,
        key=lambda row: (
            -row["dry_lc_passes"],
            -row["all_lc_passes"],
            row["dry_worst_line_loss_db"],
            row["length_ft"],
            row["balun_impedance_ratio"],
        ),
    )


def _report(
    config: dict,
    nec_rows: list,
    rows: list,
    ranking: list,
    validation: list | None = None,
) -> str:
    reference = next(
        row for row in nec_rows if row["case_id"] == config["reference_case"]
    )
    route = config["routing"]
    lines = [
        "# Rigid V doublet — initial modeling",
        "",
        f"Two nominal {reference['arm_length_ft']:g} ft arms, with a reference feed",
        f"height of {reference['feed_height_ft']:g} ft and arms "
        f"{reference['arm_elevation_deg']:g}° above horizontal. "
        "The transcript at 12:36",
        "says **10 meters / 32.81 ft of line**, not 20 meters. Exact whip extension,",
        "angle, taper and line parameters remain unmeasured.",
        "",
        "## Reference radiator",
        "",
        "NEC reported efficiency is retained as solver bookkeeping, not a verified",
        "total radiator/ground efficiency. Gains include the modeled real-ground",
        "pattern at the antenna feedpoint, excluding line, balun and tuner losses.",
        "",
        "| Band | Feedpoint R + jX (Ω) | NEC efficiency | "
        "Gain at 20° broadside (dBi) |",
        "|---|---:|---:|---:|",
    ]
    for row in nec_rows:
        if row["case_id"] == config["reference_case"]:
            lines.append(
                f"| {row['band']} | {row['feedpoint_r_ohm']:.1f} "
                f"{row['feedpoint_x_ohm']:+.1f}j | "
                f"{100 * row['nec_reported_efficiency']:.1f}% | "
                f"{row['broadside_gain_20deg_dbi']:.2f} |"
            )
    lines += [
        "",
        "## Video-length line, nominal homebrew parameters, ideal 1:1 interface",
        "",
        "| Band | Tuner load R + jX (Ω) | SWR vs 50 Ω | Line loss (dB) | "
        "Ideal L (µH) | Ideal C (pF) | Continuous L/C screen |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        if (
            row["case_id"] == config["reference_case"]
            and row["line_id"] == "homebrew_nominal"
            and math.isclose(row["length_m"], 10)
            and row["balun_impedance_ratio"] == 1
        ):
            l_text = "—" if row["ideal_l_uh"] is None else f"{row['ideal_l_uh']:.2f}"
            c_text = "—" if row["ideal_c_pf"] is None else f"{row['ideal_c_pf']:.0f}"
            screen = (
                "within limits" if row["continuous_lc_screen"] else "outside limits"
            )
            lines.append(
                f"| {row['band']} | {row['tuner_load_r_ohm']:.1f} "
                f"{row['tuner_load_x_ohm']:+.1f}j | {row['raw_swr_50ohm']:.1f} | "
                f"{row['line_loss_db']:.2f} | {l_text} | {c_text} | "
                f"{screen} |"
            )
    lines += [
        "",
        "## Length candidates for measurement",
        "",
        "Ranked by dry continuous-L/C screen counts, then all-case counts, then",
        "worst dry line loss. These are sensitivity counts, not tuner success rates.",
        "A 4:1 entry uses ideal impedance division by four with zero balun loss.",
        f"The routing screen reserves {route['horizontal_offset_ft']:g} ft horizontal",
        f"offset and {route['slack_ft']:g} ft slack to a "
        f"{route['tuner_height_ft']:g} ft high tuner: "
        f"{minimum_routed_length(reference['feed_height_ft'], route):.2f} ft minimum.",
        "",
        "| Line (ft) | Line (m) | Ideal ratio | Dry L/C screens | "
        "All L/C screens | Worst dry line loss (dB) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ranking[:12]:
        lines.append(
            f"| {row['length_ft']:.2f} | {row['length_m']:.2f} | "
            f"{row['balun_impedance_ratio']}:1 | "
            f"{row['dry_lc_passes']}/{row['dry_cases']} | "
            f"{row['all_lc_passes']}/{row['all_cases']} | "
            f"{row['dry_worst_line_loss_db']:.2f} |"
        )
    if validation:
        finest = max(row["arm_segments"] for row in validation)
        fine_rows = [row for row in validation if row["arm_segments"] == finest]
        lines += [
            "",
            "## Numerical checks",
            "",
            "A three-segment source bridge keeps the voltage source's adjacent",
            "segments collinear. A single source segment between bent arms gave",
            "poor average-gain/mesh convergence and was replaced before this run.",
            "Lossless full-sphere average gain should be 1.0. This checks numerical",
            "power balance, not agreement with the physical antenna.",
            "",
            "| Band | Finest mesh AG | AG error (dB) | "
            "Impedance change vs preceding mesh | 20° gain change (dB) |",
            "|---|---:|---:|---:|---:|",
        ]
        for row in fine_rows:
            lines.append(
                f"| {row['band']} | {row['free_space_average_gain']:.4f} | "
                f"{row['free_space_average_gain_error_db']:+.3f} | "
                f"{100 * row['relative_z_change_from_previous']:.2f}% | "
                f"{row['broadside_gain_change_db_from_previous']:+.2f} |"
            )
    lines += [
        "",
        "## Interpretation boundaries",
        "",
        "- Exact, continuous lossless low-pass L matching is checked against 20 µH",
        "  and 1300 pF. This is not the LDG discrete bank or its search algorithm.",
        "  Passing cannot guarantee a tune; failure cannot exclude a usable",
        "  partial match.",
        "- The separate 10:1 raw-SWR flag is the published range screen. A continuous",
        "  solution outside 10:1 does not extend LDG's advertised specification.",
        "- No tuner, balun, coax jumper, common-mode or truck loss is calculated.",
        "- Mast variants only probe radiator-to-floating-mast interaction; the",
        "  balanced-line model has no spatial route or mast/truck coupling.",
        "- The 91/181/259 segment cases test numerical sensitivity at the reference",
        "  geometry. They do not validate a tapered telescoping whip or its joints.",
        "- Seven frequency samples do not establish full-band tuning coverage.",
        "",
        "See [design notes](../../docs/case-studies/rigid-v-hitch-doublet.md) for",
        "transcript provenance, winter mounting ideas and the measurement plan.",
        "",
        "## Sources",
        "",
    ]
    lines += [f"- {name}: {url}" for name, url in config["sources"].items()]
    return "\n".join(lines) + "\n"


def run_rigid_doublet_study(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    nec2c: str | Path | None = None,
    cache_dir: str | Path = "build/rigid-v-nec-cache",
    jobs: int = 6,
    compact: bool = False,
    plot: bool = False,
    validate: bool = False,
) -> dict[str, Any]:
    config_path, output_dir, cache_dir = map(Path, (config_path, output_dir, cache_dir))
    config = json.loads(config_path.read_text())
    ids = [case["id"] for case in config["cases"]]
    if len(ids) != len(set(ids)) or config["reference_case"] not in ids:
        raise ValueError("Cases must have unique IDs and contain the reference case")
    if jobs < 1:
        raise ValueError("jobs must be positive")
    executable = find_nec2c(nec2c)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Remove only optional artifacts owned by this generator on repeat runs.
    for filename, keep in (
        ("line_sweep.csv", not compact),
        ("line-length-sensitivity.png", plot),
        ("numerical_validation.csv", validate),
        ("numerical_validation.json", validate),
    ):
        if not keep:
            (output_dir / filename).unlink(missing_ok=True)
    tasks = [
        (config, case, band, frequency, executable, cache_dir)
        for case in config["cases"]
        for band, frequency in config["bands_mhz"].items()
    ]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        nec_rows = list(pool.map(_nec_case, tasks))
    rows = line_rows(config, nec_rows)
    ranking = rank_lengths(config, rows)
    validation = None
    if validate:
        reference = next(
            row for row in nec_rows if row["case_id"] == config["reference_case"]
        )
        ground = config["grounds"][reference["ground"]]
        validation = validate_geometry(
            geometry=RigidDoublet(
                **{key: reference[key] for key in RigidDoublet.__dataclass_fields__}
            ),
            bands_mhz=config["bands_mhz"],
            conductivity_s_m=reference["conductivity_s_m"],
            epsilon_r=ground["epsilon_r"],
            ground_conductivity_s_m=ground["conductivity_s_m"],
            nec2c=executable,
            output_dir=output_dir,
        )
    summary = dict(
        study_id=config["study_id"],
        status="exploratory_uncalibrated_not_a_build_recommendation",
        nec_cases=len(nec_rows),
        line_cases=len(rows),
        best_screen_candidate=ranking[0] if ranking else None,
        config_sha256=_sha256(config_path),
        solver_sha256=_sha256(executable),
        solver_version=_solver_version(executable),
        assumptions=config["assumptions"],
        full_line_sweep_included=not compact,
        numerical_validation_performed=validate,
        average_gain_checks_passed=(
            all(row["average_gain_within_tolerance"] for row in validation)
            if validation
            else None
        ),
        source_sha256={
            name: _sha256(Path(__file__).with_name(name))
            for name in (
                "rigid_doublet.py",
                "rigid_doublet_study.py",
                "rigid_doublet_validation.py",
                "nec.py",
                "transmission_line.py",
            )
        },
    )
    _write_csv(output_dir / "nec_loads.csv", nec_rows)
    if not compact:
        _write_csv(output_dir / "line_sweep.csv", rows)
    _write_csv(
        output_dir / "reference_spot_checks.csv",
        [
            row
            for row in rows
            if row["case_id"] == config["reference_case"]
            and row["line_id"] == "homebrew_nominal"
            and row["length_ft"] in config["spot_lengths_ft"]
        ],
    )
    _write_csv(output_dir / "length_screen.csv", ranking)
    if plot:
        _plot_line_sweep(output_dir / "line-length-sensitivity.png", config, rows)
    _write_json(output_dir / "config.json", config)
    _write_json(output_dir / "summary.json", summary)
    report = _report(config, nec_rows, rows, ranking, validation)
    if plot:
        report += "\n![Line-length sensitivity](line-length-sensitivity.png)\n"
    (output_dir / "REPORT.md").write_text(report)
    _write_manifest(output_dir)
    return summary


def _plot_line_sweep(path: Path, config: dict, rows: list[dict]) -> None:
    """Plot computed samples, keeping ideal matching separate from raw SWR/loss."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    selected = [
        row
        for row in rows
        if row["case_id"] == config["reference_case"]
        and row["line_id"] == "homebrew_nominal"
        and row["balun_impedance_ratio"] == 1
    ]
    bands = list(config["bands_mhz"])
    lengths = sorted({row["length_ft"] for row in selected})
    fig, axes = plt.subplots(
        3, 1, figsize=(11, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1.25, 2]}
    )
    colors = plt.get_cmap("tab10").colors
    screens = []
    for index, band in enumerate(bands):
        group = sorted(
            [row for row in selected if row["band"] == band],
            key=lambda row: row["length_ft"],
        )
        axes[0].plot(
            lengths,
            [r["raw_swr_50ohm"] for r in group],
            label=band,
            color=colors[index],
        )
        axes[2].plot(lengths, [r["line_loss_db"] for r in group], color=colors[index])
        screens.append([int(row["continuous_lc_screen"]) for row in group])
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Raw SWR at tuner port (50 Ω)")
    axes[0].axhline(10, color="#555555", linestyle="--", linewidth=1)
    axes[0].legend(ncol=7, loc="upper center", fontsize=9)
    axes[0].grid(alpha=0.2)
    edges = [lengths[0] - (lengths[1] - lengths[0]) / 2]
    edges += [(a + b) / 2 for a, b in zip(lengths[:-1], lengths[1:], strict=True)]
    edges += [lengths[-1] + (lengths[-1] - lengths[-2]) / 2]
    axes[1].pcolormesh(
        edges,
        np.arange(len(bands) + 1) - 0.5,
        screens,
        cmap=ListedColormap(["#eeeeee", "#218380"]),
        vmin=0,
        vmax=1,
    )
    axes[1].set_yticks(range(len(bands)), bands)
    axes[1].invert_yaxis()
    axes[1].set_title(
        "Ideal exact L/C match: teal = within 20 µH / 1300 pF; "
        "not a Z-100A tune prediction",
        fontsize=10,
    )
    axes[2].set_ylabel("Balanced-line loss (dB)")
    axes[2].set_xlabel("Physical balanced-line length (feet)")
    axes[2].grid(alpha=0.2)
    minimum = selected[0]["minimum_route_ft"]
    for ax in axes:
        ax.axvspan(lengths[0], minimum, color="#bbbbbb", alpha=0.25)
        ax.axvline(28, color="#777777", linestyle=":", linewidth=1)
        ax.axvline(10 / 0.3048, color="#222222", linestyle="--", linewidth=1)
        ax.set_xlim(min(lengths), max(lengths))
    reference_case = next(
        case for case in config["cases"] if case["id"] == config["reference_case"]
    )
    geometry = config["geometry"] | reference_case
    fig.suptitle(
        f"{geometry['arm_length_ft']:g} ft per arm rigid V doublet · "
        f"{geometry['feed_height_ft']:g} ft feedpoint\n"
        "Nominal homebrew line · ideal 1:1 balun · seven frequency samples",
        fontsize=14,
    )
    fig.text(
        0.5,
        0.018,
        "Dotted: existing 28 ft line   |   Dashed vertical: video 10 m (32.81 ft)"
        "   |   Shading: assumed route too short\n"
        "Line loss excludes tuner, balun and radiator loss. "
        "Length preferences depend on uncertain line and antenna parameters.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    fig.savefig(path, dpi=160)
    plt.close(fig)
