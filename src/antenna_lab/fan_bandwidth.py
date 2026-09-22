"""Compare full 2:1 window widths and recenter a compact fan's match windows."""

from __future__ import annotations

import argparse
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scipy.optimize import brentq

from antenna_lab.fan_dipole import BANDS, fan_deck
from antenna_lab.fan_dipole_study import FanStudy
from antenna_lab.linked_dipole_study import sha256, write_csv, write_json
from antenna_lab.linked_dipole_validation import free_space_reactive_deck
from antenna_lab.nec import find_nec2c
from antenna_lab.rigid_doublet_validation import average_gain
from antenna_lab.transmission_line import swr


def full_window(study, lengths, spacing, band, scan):
    """Find both 2:1 crossings around the scanned minimum, before band clipping."""
    sweep = scan["sweep"]
    best = min(sweep, key=lambda row: row[3])
    if best[3] > 2:
        return None
    roots = [row[0] for row in sweep if abs(row[3] - 2) < 1e-8]
    for a, b in zip(sweep[:-1], sweep[1:], strict=True):
        if (a[3] - 2) * (b[3] - 2) < 0:

            def objective(f):
                z = study.solve(lengths, spacing, f)[0].impedance_ohm
                return float(swr(z)) - 2

            roots.append(float(brentq(objective, a[0], b[0], xtol=1e-6)))
    lower = [f for f in roots if f < best[0]]
    upper = [f for f in roots if f > best[0]]
    if not lower or not upper:
        raise ValueError(f"Unbracketed matched window: {spacing} {band}")
    return [max(lower), min(upper)]


def coverage(window, interval):
    if window is None:
        return 0.0
    return max(0, min(window[1], interval[1]) - max(window[0], interval[0])) / (
        interval[1] - interval[0]
    )


def evaluate(study, spacing, tuned):
    rows = []
    for band in BANDS:
        scan = study.scan(tuned["lengths_ft"], spacing, band)
        window = full_window(study, tuned["lengths_ft"], spacing, band, scan)
        rows.append(
            dict(
                **scan,
                full_swr2_window_mhz=window,
                width_khz=0 if window is None else 1000 * (window[1] - window[0]),
            )
        )
    return rows


def local_windows(study, spacing, tuned):
    """Bracket outward from each tuned match, avoiding repeated broad sweeps."""
    rows = []
    for band in BANDS:
        target = study.config["bands_mhz"][band]
        samples = {}

        def mismatch(f, samples=samples):
            f = round(float(f), 8)
            if f not in samples:
                z = study.solve(tuned["lengths_ft"], spacing, f)[0].impedance_ohm
                samples[f] = [f, z.real, z.imag, float(swr(z))]
            return samples[f][3] - 2

        if mismatch(target) >= 0:
            raise ValueError("No match at tuned frequency for local crossing search")
        roots = []
        for sign in (-1, 1):
            inside = target
            offset = 0.015
            while offset < target * 0.15:
                outside = target + sign * offset
                if mismatch(outside) > 0:
                    roots.append(
                        float(brentq(mismatch, *sorted([inside, outside]), xtol=1e-6))
                    )
                    break
                inside = outside
                offset *= 1.7
            else:
                raise ValueError("Could not bracket local 2:1 crossing")
        # Ensure the reported single window has no sampled unmatched hole.
        for i in range(1, 13):
            if mismatch(roots[0] + (roots[1] - roots[0]) * i / 13) > 0.001:
                raise ValueError("Disjoint match found inside local window")
        z = samples[round(target, 8)]
        rows.append(
            dict(
                band=band,
                frequency_mhz=target,
                r_ohm=z[1],
                x_ohm=z[2],
                swr=z[3],
                full_swr2_window_mhz=roots,
                width_khz=1000 * (roots[1] - roots[0]),
                sweep=[samples[f] for f in sorted(samples)],
            )
        )
    return rows


def recenter(setup, baseline, executable, output, jobs, profile="centered"):
    """Recenter actual crossing pairs, not merely X=0, inside desired ranges."""
    intervals = setup["desired_intervals_mhz"]
    anchors = setup.get("cw_anchor_low_mhz", {}) if profile == "cw-first" else {}
    spacing_key = "cw_spacings_in" if profile == "cw-first" else "recenter_spacings_in"
    tasks = [
        (material, setup["materials"][material], d)
        for material, spacings in setup[spacing_key].items()
        for d in spacings
    ]

    def run(task):
        material, conductivity, spacing = task
        config = {
            **baseline,
            "effective_conductivity_s_m": conductivity,
            "bands_mhz": {
                **baseline["bands_mhz"],
                **{
                    b: baseline["bands_mhz"][b]
                    if b in anchors
                    else sum(intervals[b]) / 2
                    for b in BANDS
                },
            },
        }
        histories = []
        used = {}
        for iteration in range(3):
            study = FanStudy(config, executable, Path("build/fan-dipole-cache"))
            tuned = study.tune(spacing)
            if not tuned["converged"]:
                raise ValueError("Recenter tuning failed")
            rows = local_windows(study, spacing, tuned)
            used.update(study.used_inputs)
            errors = {
                r["band"]: (anchors[r["band"]] - r["full_swr2_window_mhz"][0])
                if r["band"] in anchors
                else sum(intervals[r["band"]]) / 2 - sum(r["full_swr2_window_mhz"]) / 2
                for r in rows
                if r["full_swr2_window_mhz"] is not None
            }
            if len(errors) != 3:
                raise ValueError("Cannot recenter an absent 2:1 window")
            histories.append(
                dict(
                    targets_mhz=dict(config["bands_mhz"]),
                    tuning=tuned,
                    center_errors_mhz=errors,
                )
            )
            if max(map(abs, errors.values())) <= 0.0005 or iteration == 2:
                break
            config = {
                **config,
                "initial_half_lengths_ft": tuned["lengths_ft"],
                "bands_mhz": {
                    **config["bands_mhz"],
                    **{b: config["bands_mhz"][b] + errors[b] for b in BANDS},
                },
            }
        validation = [
            dict(
                material=material,
                spacing_in=spacing,
                kind="window_alignment",
                max_error_khz=1000 * max(map(abs, errors.values())),
                passed=max(map(abs, errors.values())) <= 0.0005,
            )
        ]
        for row in rows:
            band = row["band"]
            row["desired_fraction"] = coverage(
                row["full_swr2_window_mhz"], intervals[band]
            )
            fine = {**config, "max_segment_length_m": 0.08}
            for f in [row["frequency_mhz"], *row["full_swr2_window_mhz"]]:
                z = study.solve(tuned["lengths_ft"], spacing, f)[0].impedance_ohm
                zfine = study.solve(tuned["lengths_ft"], spacing, f, fine)[
                    0
                ].impedance_ohm
                validation.append(
                    dict(
                        material=material,
                        spacing_in=spacing,
                        band=band,
                        frequency_mhz=f,
                        kind="mesh",
                        delta_z_ohm=abs(z - zfine),
                        coarse_swr=float(swr(z)),
                        fine_swr=float(swr(zfine)),
                        passed=abs(z - zfine) <= 2,
                    )
                )
            deck = fan_deck(
                tuned["lengths_ft"], spacing, row["frequency_mhz"], fine, pattern=True
            )
            result = study.run(free_space_reactive_deck(deck))[0]
            error_db = 10 * math.log10(average_gain(result.pattern))
            validation.append(
                dict(
                    material=material,
                    spacing_in=spacing,
                    band=band,
                    kind="lossless_average_gain",
                    error_db=error_db,
                    passed=abs(error_db) <= 0.1,
                )
            )
        used.update(study.used_inputs)
        result = dict(
            material=material,
            spacing_in=spacing,
            config=config,
            tuning_history=histories,
            cases=rows,
            validation=validation,
        )
        write_json(output / f"{profile}-{material}-{spacing:g}in.json", result)
        print(
            f"{profile} {material} {spacing:g} in: "
            + ", ".join(
                f"{r['band']} {100 * r['desired_fraction']:.0f}%" for r in rows
            ),
            flush=True,
        )
        return result, used

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(run, tasks))
    write_json(output / f"{profile}.json", [r[0] for r in results])
    write_json(
        output / f"{profile}_metadata.json",
        dict(
            solver_sha256=sha256(executable),
            config=setup,
            used_nec_inputs={
                stem: dict(
                    deck_sha256=sha256(path),
                    output_sha256=sha256(path.with_suffix(".out")),
                )
                for _, used in results
                for stem, path in used.items()
            },
        ),
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=Path("configs/fan-bandwidth-v1.json"))
    p.add_argument("--nec2c", default="nec2c")
    p.add_argument("--output", type=Path, default=Path("build/fan-bandwidth-v1"))
    p.add_argument("--jobs", type=int, default=6)
    p.add_argument("--recenter-only", action="store_true")
    p.add_argument("--cw-first", action="store_true")
    args = p.parse_args()
    setup = json.loads(args.config.read_text())
    baseline = json.loads(Path(setup["base_config"]).read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    executable = find_nec2c(args.nec2c).resolve()
    if args.recenter_only or args.cw_first:
        recenter(
            setup,
            baseline,
            executable,
            args.output,
            args.jobs,
            "cw-first" if args.cw_first else "centered",
        )
        return
    tasks = [
        (material, conductivity, spacing)
        for material, conductivity in setup["materials"].items()
        for spacing in setup["spacings_in"]
    ]

    def run(task):
        material, conductivity, spacing = task
        config = {**baseline, "effective_conductivity_s_m": conductivity}
        study = FanStudy(config, executable, Path("build/fan-dipole-cache"))
        tuned = study.tune(spacing)
        if not tuned["converged"]:
            raise ValueError("Tuning did not converge")
        rows = evaluate(study, spacing, tuned)
        data = dict(material=material, spacing_in=spacing, tuning=tuned, cases=rows)
        write_json(args.output / f"{material}-{spacing:g}in.json", data)
        print(
            f"{material} {spacing:g} in: "
            + ", ".join(f"{r['band']} {r['width_khz']:.0f} kHz" for r in rows),
            flush=True,
        )
        return data, study.used_inputs

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run, tasks))
    data = [r[0] for r in results]
    inputs = {
        stem: dict(
            deck_sha256=sha256(path), output_sha256=sha256(path.with_suffix(".out"))
        )
        for _, used in results
        for stem, path in used.items()
    }
    write_json(args.output / "study.json", dict(config=setup, cases=data))
    write_csv(
        args.output / "summary.csv",
        [
            dict(
                material=case["material"],
                spacing_in=case["spacing_in"],
                band=row["band"],
                width_khz=row["width_khz"],
                window_low_mhz=None
                if row["full_swr2_window_mhz"] is None
                else row["full_swr2_window_mhz"][0],
                window_high_mhz=None
                if row["full_swr2_window_mhz"] is None
                else row["full_swr2_window_mhz"][1],
                whole_band_fraction=coverage(
                    row["full_swr2_window_mhz"], baseline["band_edges_mhz"][row["band"]]
                ),
            )
            for case in data
            for row in case["cases"]
        ],
    )
    write_json(
        args.output / "run_metadata.json",
        dict(
            solver_sha256=sha256(executable),
            config_sha256=sha256(args.config),
            used_nec_inputs=inputs,
        ),
    )


if __name__ == "__main__":
    main()
