"""Two-stage line-length optimization for 17 and 25 ft rigid whip doublets.

The objective is transmitter-available power delivered to the NEC antenna port.
This includes generic continuous tuner loss and residual mismatch, and balanced
line loss; it excludes balun/coax/common-mode losses. NEC gains are reported
separately, so a longer radiator is not rewarded solely for receiving more power.
"""

from __future__ import annotations

import itertools
import json
import math
from concurrent.futures import ThreadPoolExecutor
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
from antenna_lab.nec import find_nec2c
from antenna_lab.rigid_doublet import RigidDoublet
from antenna_lab.rigid_doublet_optimization_report import write_report
from antenna_lab.rigid_doublet_patterns import plot_comparison
from antenna_lab.rigid_doublet_study import _nec_case, minimum_routed_length
from antenna_lab.rigid_doublet_validation import validate_geometry
from antenna_lab.rigid_matching import screen_matching
from antenna_lab.transmission_line import (
    LineParameters,
    input_impedance,
    line_efficiency,
    swr,
)


def frequencies(config: dict, samples: int) -> list[tuple[str, float]]:
    if samples < 2:
        raise ValueError("At least two frequency samples are required")
    values = []
    for band, (low, high) in config["bands_mhz"].items():
        if not 0 < low < high:
            raise ValueError("Frequency bounds must be positive and increasing")
        # NEC FR cards retain nine decimals: merge floating-point aliases before
        # parallel workers can write the same deck/cache entry simultaneously.
        points = {round(float(f), 9) for f in np.linspace(low, high, samples)}
        points.add(round(config["reference_frequencies_mhz"][band], 9))
        values.extend((band, float(f)) for f in sorted(points))
    return values


def dry_lines(config: dict, *, coarse: bool) -> list[dict]:
    uncertainty = config["line_uncertainty"]
    losses = [0.07] if coarse else uncertainty["loss_db_per_100ft_at_10mhz"]
    return [
        dict(z0_ohm=z0 * vf, velocity_factor=vf, loss_db_per_100ft_at_10mhz=loss)
        for z0, vf, loss in itertools.product(
            uncertainty["air_z0_ohm"], uncertainty["velocity_factors"], losses
        )
    ]


def coarse_candidates(config: dict) -> list[tuple[float, int]]:
    sweep = config["line_sweep_ft"]
    if not all(math.isfinite(v) and v > 0 for v in sweep.values()):
        raise ValueError("Line sweep values must be finite and positive")
    if sweep["stop"] < sweep["start"]:
        raise ValueError("Line sweep stop must not precede start")
    lengths = set(np.arange(sweep["start"], sweep["stop"] + 1e-8, sweep["step"]))
    lengths.update(config["comparison_lengths_ft"])
    minimum = max(
        minimum_routed_length(
            case.get("feed_height_ft", config["geometry"]["feed_height_ft"]),
            config["routing"],
        )
        for case in config["cases"]
    )
    return [
        (float(length), ratio)
        for length in sorted(lengths)
        for ratio in config["balun_impedance_ratios"]
        if length >= minimum
    ]


def _loads(
    config: dict,
    arm: float,
    points: list,
    cases: list,
    executable: Path,
    cache: Path,
    jobs: int,
) -> list[dict]:
    nec_config = dict(config)
    nec_config["geometry"] = config["geometry"] | {"arm_length_ft": arm}
    tasks = [
        (
            nec_config,
            case | {"id": f"{arm:g}ft_{case['id']}"},
            band,
            frequency,
            executable,
            cache,
        )
        for case in cases
        for band, frequency in points
    ]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(_nec_case, tasks))
    for row, case in zip(
        rows,
        itertools.chain.from_iterable(
            itertools.repeat(case, len(points)) for case in cases
        ),
        strict=True,
    ):
        row["scenario_id"] = case["id"]
    return rows


def evaluate(
    config: dict,
    loads: list[dict],
    points: list,
    cases: list,
    candidates: list[tuple[float, int]],
    lines: list,
    profiles: list,
) -> dict[str, np.ndarray]:
    """Dimensions: geometry, frequency, line properties, tuner Q, fixed candidate."""
    shape = (len(cases), len(points), len(lines), len(profiles), len(candidates))
    cube = {
        key: np.empty(shape, dtype=np.float32)
        for key in ("delivery", "swr", "raw_swr", "line_eta", "tuner_eta")
    }
    cube["matched"] = np.empty(shape, dtype=bool)
    lengths = np.array([c[0] for c in candidates])
    ratios = np.array([c[1] for c in candidates])
    lookup = {
        (row["scenario_id"], row["band"], row["frequency_mhz"]): row for row in loads
    }
    for ci, case in enumerate(cases):
        for fi, (band, frequency) in enumerate(points):
            antenna = lookup[case["id"], band, frequency]
            load = complex(antenna["feedpoint_r_ohm"], antenna["feedpoint_x_ohm"])
            zin, efficiency = [], []
            for line in lines:
                params = LineParameters(
                    line["z0_ohm"],
                    line["velocity_factor"],
                    line["loss_db_per_100ft_at_10mhz"],
                )
                zin.append(input_impedance(load, frequency * 1e6, lengths, params))
                efficiency.append(
                    line_efficiency(load, frequency * 1e6, lengths, params)
                )
            terminal = np.array(zin) / ratios
            eta = np.array(efficiency)
            raw = swr(terminal)
            for qi, profile in enumerate(profiles):
                solution = screen_matching(
                    terminal,
                    frequency * 1e6,
                    **config["tuner_limits"],
                    **{k: v for k, v in profile.items() if k != "id"},
                )
                index = (ci, fi, slice(None), qi, slice(None))
                cube["delivery"][index] = solution["transducer_efficiency"] * eta
                cube["swr"][index] = solution["input_swr"]
                cube["raw_swr"][index] = raw
                cube["line_eta"][index] = eta
                cube["tuner_eta"][index] = solution["tuner_efficiency"]
                cube["matched"][index] = solution["matched"]
    if not np.all((cube["delivery"] >= 0) & (cube["delivery"] <= 1.00001)):
        raise ValueError("Nonpassive tuner/line result")
    return cube


def aggregate(
    config: dict, arm: float, points: list, candidates: list, cube: dict, *, phase: str
) -> tuple[list[dict], list[dict]]:
    # Every band gets equal weight despite differing frequency counts.
    bands = list(config["bands_mhz"])
    scored = np.where(cube["matched"], cube["delivery"], 0)
    band_rows, bands_p10, bands_median, match_fractions = [], [], [], []
    for band in bands:
        indices = [i for i, point in enumerate(points) if point[0] == band]
        block = scored[:, indices, ...]
        p10 = np.quantile(block, 0.1, axis=(0, 1, 2, 3))
        median = np.median(block, axis=(0, 1, 2, 3))
        matches = cube["matched"][:, indices, ...].mean(axis=(0, 1, 2, 3))
        bands_p10.append(p10)
        bands_median.append(median)
        match_fractions.append(matches)
        for i, (length, ratio) in enumerate(candidates):
            band_rows.append(
                dict(
                    arm_length_ft=arm,
                    length_ft=length,
                    balun_ratio=ratio,
                    phase=phase,
                    band=band,
                    delivery_p10=float(p10[i]),
                    delivery_median=float(median[i]),
                    match_fraction=float(matches[i]),
                    worst_delivery=float(np.min(block[..., i])),
                )
            )
    all_band = cube["matched"].all(axis=1).mean(axis=(0, 1, 2))
    minimum = max(
        minimum_routed_length(
            c.get("feed_height_ft", config["geometry"]["feed_height_ft"]),
            config["routing"],
        )
        for c in config["cases"]
    )
    summary = []
    p10s, medians = np.array(bands_p10), np.array(bands_median)
    for i, (length, ratio) in enumerate(candidates):
        limiting = int(np.argmin(p10s[:, i]))
        summary.append(
            dict(
                arm_length_ft=arm,
                length_ft=length,
                length_m=length * 0.3048,
                balun_ratio=ratio,
                phase=phase,
                route_feasible=length >= minimum,
                region="compact" if length <= config["compact_max_line_ft"] else "long",
                all_band_match_fraction=float(all_band[i]),
                mean_band_match_fraction=float(np.mean(match_fractions, axis=0)[i]),
                worst_band_p10_delivery=float(p10s[limiting, i]),
                limiting_band=bands[limiting],
                band_median_geometric_mean=float(
                    np.prod(medians[:, i]) ** (1 / len(bands))
                ),
                worst_raw_swr=float(np.max(cube["raw_swr"][..., i])),
                samples=int(np.prod(cube["delivery"].shape[:-1])),
            )
        )
    return sorted(summary, key=rank_key), band_rows


def rank_key(row: dict) -> tuple:
    return (
        not row["route_feasible"],
        -row["all_band_match_fraction"],
        -row["worst_band_p10_delivery"],
        -row["band_median_geometric_mean"],
        row["length_ft"],
        row["balun_ratio"],
    )


def shortlist(config: dict, coarse: list[dict]) -> list[tuple[float, int]]:
    chosen = {
        (length, ratio)
        for length in config["comparison_lengths_ft"]
        for ratio in config["balun_impedance_ratios"]
    }
    count = config["shortlist_per_region_ratio"]
    for region, ratio in itertools.product(
        ("compact", "long"), config["balun_impedance_ratios"]
    ):
        group = [
            r
            for r in coarse
            if r["region"] == region
            and r["balun_ratio"] == ratio
            and r["route_feasible"]
        ]
        for row in group[:count]:
            chosen.add((row["length_ft"], ratio))
        # Probe neighboring lengths rather than claiming the best quarter-foot.
        if group:
            for delta in (-2, -1, -0.5, 0.5, 1, 2):
                length = group[0]["length_ft"] + delta
                if (
                    config["line_sweep_ft"]["start"]
                    <= length
                    <= config["line_sweep_ft"]["stop"]
                ):
                    chosen.add((length, ratio))
    return sorted(chosen)


def nominal_details(
    config: dict, arm: float, candidates: list, loads: list[dict]
) -> list[dict]:
    lines = [
        dict(z0_ohm=495 * 0.97, velocity_factor=0.97, loss_db_per_100ft_at_10mhz=0.07)
    ]
    profile = next(p for p in config["loss_profiles"] if p["id"] == "nominal")
    points = list(config["reference_frequencies_mhz"].items())
    cube = evaluate(
        config, loads, points, [{"id": "nominal"}], candidates, lines, [profile]
    )
    lookup = {
        (r["band"], r["frequency_mhz"]): r
        for r in loads
        if r["scenario_id"] == "nominal"
    }
    rows = []
    for fi, (band, frequency) in enumerate(points):
        antenna = lookup[band, frequency]
        for i, (length, ratio) in enumerate(candidates):
            index = (0, fi, 0, 0, i)
            delivery = float(cube["delivery"][index])
            rows.append(
                dict(
                    arm_length_ft=arm,
                    length_ft=length,
                    balun_ratio=ratio,
                    band=band,
                    frequency_mhz=frequency,
                    antenna_r_ohm=antenna["feedpoint_r_ohm"],
                    antenna_x_ohm=antenna["feedpoint_x_ohm"],
                    delivery_efficiency=delivery,
                    network_loss_db=-10 * math.log10(delivery),
                    line_loss_db=-10 * math.log10(float(cube["line_eta"][index])),
                    tuner_dissipation_loss_db=-10
                    * math.log10(float(cube["tuner_eta"][index])),
                    input_swr=float(cube["swr"][index]),
                    raw_swr=float(cube["raw_swr"][index]),
                    modeled_match=bool(cube["matched"][index]),
                    antenna_gain_20deg_dbi=antenna["broadside_gain_20deg_dbi"],
                    antenna_gain_45deg_dbi=antenna["broadside_gain_45deg_dbi"],
                    system_gain_20deg_dbi=antenna["broadside_gain_20deg_dbi"]
                    + 10 * math.log10(delivery),
                    system_gain_45deg_dbi=antenna["broadside_gain_45deg_dbi"]
                    + 10 * math.log10(delivery),
                )
            )
    return rows


def run_optimization(
    config_path: str | Path,
    output_dir: str | Path,
    *,
    nec2c: str | Path | None = None,
    jobs: int = 6,
    cache_dir: str | Path = "build/rigid-v-optimization-cache",
    compact: bool = False,
) -> dict[str, Any]:
    config_path, output, cache = map(Path, (config_path, output_dir, cache_dir))
    config = json.loads(config_path.read_text())
    executable = find_nec2c(nec2c)
    output.mkdir(parents=True, exist_ok=True)
    if compact:
        for arm in config["arm_lengths_ft"]:
            (output / f"{arm:g}ft_dry_ensemble.npz").unlink(missing_ok=True)
    coarse_points = frequencies(config, config["coarse_samples_per_band"])
    fine_points = frequencies(config, config["validation_samples_per_band"])
    coarse_cands = coarse_candidates(config)
    all_coarse, all_fine, all_bands, all_wet, all_nominal, all_loads = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    nominal_profile = [p for p in config["loss_profiles"] if p["id"] == "nominal"]
    winners = []
    for arm in config["arm_lengths_ft"]:
        print(f"{arm:g} ft arms: coarse NEC and line search", flush=True)
        loads = _loads(
            config, arm, coarse_points, [{"id": "nominal"}], executable, cache, jobs
        )
        cube = evaluate(
            config,
            loads,
            coarse_points,
            [{"id": "nominal"}],
            coarse_cands,
            dry_lines(config, coarse=True),
            nominal_profile,
        )
        coarse, _ = aggregate(
            config, arm, coarse_points, coarse_cands, cube, phase="coarse"
        )
        all_coarse.extend(coarse)
        candidates = shortlist(config, coarse)
        print(
            f"{arm:g} ft arms: validating {len(candidates)} fixed line/ratio choices",
            flush=True,
        )
        loads = _loads(
            config, arm, fine_points, config["cases"], executable, cache, jobs
        )
        all_loads.extend(loads)
        cube = evaluate(
            config,
            loads,
            fine_points,
            config["cases"],
            candidates,
            dry_lines(config, coarse=False),
            config["loss_profiles"],
        )
        fine, by_band = aggregate(
            config, arm, fine_points, candidates, cube, phase="dry_validation"
        )
        all_fine.extend(fine)
        all_bands.extend(by_band)
        if not compact:
            np.savez_compressed(output / f"{arm:g}ft_dry_ensemble.npz", **cube)
        for region in ("compact", "long"):
            for ratio in config["balun_impedance_ratios"]:
                selected = next(
                    (
                        r
                        for r in fine
                        if r["region"] == region
                        and r["balun_ratio"] == ratio
                        and r["route_feasible"]
                    ),
                    None,
                )
                if selected:
                    winners.append(selected)
        del cube
        wet = evaluate(
            config,
            loads,
            fine_points,
            config["cases"],
            candidates,
            [config["wet_line"]],
            config["loss_profiles"],
        )
        wet_summary, _ = aggregate(
            config, arm, fine_points, candidates, wet, phase="wet_stress"
        )
        all_wet.extend(wet_summary)
        all_nominal.extend(nominal_details(config, arm, candidates, loads))
    _write_csv(output / "coarse_rankings.csv", all_coarse)
    _write_csv(output / "validated_rankings.csv", all_fine)
    _write_csv(output / "validated_by_band.csv", all_bands)
    _write_csv(output / "wet_stress.csv", all_wet)
    _write_csv(output / "nominal_by_band.csv", all_nominal)
    _write_csv(output / "nec_loads.csv", all_loads)
    _write_json(output / "config.json", config)
    _write_json(output / "winners.json", winners)
    print(
        "Rendering comparison and checking endpoint/peak numerical convergence",
        flush=True,
    )
    ground = config["grounds"]["average"]
    pattern_metadata = plot_comparison(
        output_dir=output,
        nec2c=executable,
        arm_lengths_ft=tuple(config["arm_lengths_ft"]),
        **{k: v for k, v in config["geometry"].items() if k != "arm_length_ft"},
        conductivity_s_m=config["conductivity_s_m"],
        epsilon_r=ground["epsilon_r"],
        ground_conductivity_s_m=ground["conductivity_s_m"],
    )
    numerical = {}
    for arm in config["arm_lengths_ft"]:
        checks = {
            f"{band}_{f:g}": f
            for band, bounds in config["bands_mhz"].items()
            for f in bounds
        }
        reference_loads = [
            r
            for r in all_loads
            if r["arm_length_ft"] == arm and r["scenario_id"] == "nominal"
        ]
        peak = max(
            reference_loads,
            key=lambda r: abs(complex(r["feedpoint_r_ohm"], r["feedpoint_x_ohm"])),
        )
        checks["highest_sampled_impedance"] = peak["frequency_mhz"]
        validation = validate_geometry(
            geometry=RigidDoublet(**(config["geometry"] | {"arm_length_ft": arm})),
            bands_mhz=checks,
            conductivity_s_m=config["conductivity_s_m"],
            epsilon_r=ground["epsilon_r"],
            ground_conductivity_s_m=ground["conductivity_s_m"],
            nec2c=executable,
            output_dir=output / "numerical" / f"{arm:g}ft",
        )
        finest = max(row["arm_segments"] for row in validation)
        numerical[f"{arm:g}ft"] = dict(
            average_gain_passed=all(
                r["average_gain_within_tolerance"] for r in validation
            ),
            fine_mesh_max_relative_z_change=max(
                r["relative_z_change_from_previous"]
                for r in validation
                if r["arm_segments"] == finest
            ),
        )
    summary = dict(
        study_id=config["study_id"],
        status="generic_continuous_tuner_exploration_not_LDG_prediction",
        coarse_candidates_per_arm=len(coarse_cands),
        validated_candidates=len(all_fine),
        nec_cases=len(all_loads),
        dry_network_cases=sum(r["samples"] for r in all_fine),
        coarse_frequency_samples=len(coarse_points),
        validation_frequency_samples=len(fine_points),
        config_sha256=_sha256(config_path),
        solver_sha256=_sha256(executable),
        solver_version=_solver_version(executable),
        patterns=pattern_metadata,
        numerical=numerical,
        source_sha256={
            name: _sha256(Path(__file__).with_name(name))
            for name in (
                "rigid_doublet_optimization.py",
                "rigid_doublet_optimization_report.py",
                "rigid_doublet_patterns.py",
                "rigid_doublet_validation.py",
                "rigid_matching.py",
                "rigid_doublet.py",
                "rigid_doublet_study.py",
                "transmission_line.py",
                "nec.py",
            )
        },
        winners=winners,
        assumptions=config["assumptions"],
    )
    _write_json(output / "summary.json", summary)
    write_report(output)
    _write_manifest(output)
    return summary
