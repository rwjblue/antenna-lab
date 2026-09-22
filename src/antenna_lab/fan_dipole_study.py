"""Reproducible compact fan spacing, sequential tuning and repeatability study."""

from __future__ import annotations

import argparse
import json
import math
import platform
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import brentq

from antenna_lab.fan_dipole import BANDS, fan_deck
from antenna_lab.linked_dipole_study import Study, sha256, write_csv, write_json
from antenna_lab.linked_dipole_validation import (
    free_space_reactive_deck,
    power_budget,
    reconciled_power_budget,
)
from antenna_lab.nec import INPUT_RE, find_nec2c
from antenna_lab.rigid_doublet_validation import average_gain, free_space_lossless_deck
from antenna_lab.transmission_line import swr


def common_port_impedance(output: str, expected_ports: int = 3) -> complex:
    """NEC prints V/I for each 1 V source; sum currents at the common port."""
    ports = [complex(float(r), float(x)) for r, x in INPUT_RE.findall(output)]
    if len(ports) != expected_ports:
        raise ValueError(
            f"Expected {expected_ports} source impedances, got {len(ports)}"
        )
    z = 1 / sum(1 / port for port in ports)
    if z.real <= 0 or not math.isfinite(abs(z)):
        raise ValueError("Nonpassive or nonfinite common-port impedance")
    return z


class FanStudy(Study):
    def solve(self, lengths, spacing, frequency, config=None, pattern=False):
        config = config or self.config
        deck = fan_deck(lengths, spacing, frequency, config, pattern=pattern)
        result, path, output, hit = self.run(deck)
        ports = 3 if config.get("feed_model", "equal_voltage") == "equal_voltage" else 1
        z = common_port_impedance(output.read_text(), ports)
        return replace(result, impedance_ohm=z), path, output, hit

    def reactances(self, lengths, spacing, config=None):
        return [
            self.solve(lengths, spacing, self.config["bands_mhz"][b], config)[
                0
            ].impedance_ohm.imag
            for b in BANDS
        ]

    def tune(self, spacing):
        c = self.config
        lengths = list(c["initial_half_lengths_ft"])
        history = [
            dict(
                step=0,
                cycle=0,
                adjusted_band="initial",
                lengths_ft=list(lengths),
                reactances_ohm=self.reactances(lengths, spacing),
                delta_in=0,
            )
        ]
        converged = False
        error = None
        for cycle in range(1, c["max_tuning_cycles"] + 1):
            for index in c["tuning_order"]:
                old = lengths[index]
                freq = c["bands_mhz"][BANDS[index]]
                lo, hi = c["length_bounds_ft"][index]
                if index > 0:
                    hi = min(hi, lengths[index - 1] - 0.2)
                if index < 2:
                    lo = max(lo, lengths[index + 1] + 0.2)

                def objective(length, index=index, freq=freq):
                    trial = list(lengths)
                    trial[index] = length
                    return self.solve(trial, spacing, freq)[0].impedance_ohm.imag

                # Search outward from the current setting. Check the root residual
                # to reject sign changes across impedance poles/antiresonances.
                root = None
                samples = {old: objective(old)}
                if abs(samples[old]) <= c["tuning_tolerance_ohm"] / 10:
                    root = old
                for radius in (0.15, 0.4, 0.8, 1.5, 3, 6, 12):
                    if root is not None:
                        break
                    for value in (max(lo, old - radius), min(hi, old + radius)):
                        if value not in samples:
                            samples[value] = objective(value)
                    ordered = sorted(samples)
                    pairs = [
                        (a, b)
                        for a, b in zip(ordered[:-1], ordered[1:], strict=True)
                        if samples[a] * samples[b] <= 0
                    ]
                    pairs.sort(key=lambda ab: abs(sum(ab) / 2 - old))
                    for a, b in pairs:
                        candidate = float(brentq(objective, a, b, xtol=1e-5))
                        if abs(objective(candidate)) < 0.1:
                            root = candidate
                            break
                if root is None:
                    error = f"No continuous resonance root for {BANDS[index]}"
                    break
                lengths[index] = root
                history.append(
                    dict(
                        step=len(history),
                        cycle=cycle,
                        adjusted_band=BANDS[index],
                        lengths_ft=list(lengths),
                        delta_in=12 * (root - old),
                        reactances_ohm=self.reactances(lengths, spacing),
                    )
                )
            if error:
                break
            if (
                max(abs(x) for x in history[-1]["reactances_ohm"])
                <= c["tuning_tolerance_ohm"]
            ):
                converged = True
                break
        return dict(
            spacing_in=spacing,
            lengths_ft=lengths,
            converged=converged,
            cycles=cycle,
            error=error,
            history=history,
        )

    def scan(self, lengths, spacing, band, config=None):
        target = self.config["bands_mhz"][band]
        lo, hi = self.config["band_edges_mhz"][band]
        values = {}

        def z(f):
            f = round(float(f), 8)
            if f not in values:
                values[f] = self.solve(lengths, spacing, f, config)[0].impedance_ohm
            return values[f]

        grid = sorted(
            set(
                np.linspace(lo, hi, 31).tolist()
                + np.linspace(target * 0.94, target * 1.06, 41).tolist()
                + [target]
            )
        )
        for f in grid:
            z(f)
        roots = []
        for a, b in zip(grid[:-1], grid[1:], strict=True):
            if z(a).imag * z(b).imag < 0:
                root = float(brentq(lambda f: z(f).imag, a, b, xtol=1e-6))
                if abs(z(root).imag) < 0.2:
                    roots.append(root)
        crossings = []
        for a, b in zip(grid[:-1], grid[1:], strict=True):
            if (swr(z(a)) - 2) * (swr(z(b)) - 2) < 0:
                crossings.append(
                    float(brentq(lambda f: float(swr(z(f))) - 2, a, b, xtol=1e-6))
                )
        edges = sorted([lo, hi] + [f for f in crossings if lo < f < hi])
        windows = [
            [a, b]
            for a, b in zip(edges[:-1], edges[1:], strict=True)
            if swr(z((a + b) / 2)) <= 2
        ]
        near = min(roots, key=lambda f: abs(f - target)) if roots else None
        zz = z(target)
        return dict(
            band=band,
            frequency_mhz=target,
            r_ohm=zz.real,
            x_ohm=zz.imag,
            swr=float(swr(zz)),
            resonance_mhz=near,
            all_resonances_mhz=roots,
            in_band_swr2_windows_mhz=windows,
            in_band_max_swr=max(float(swr(z(f))) for f in np.linspace(lo, hi, 31)),
            sweep=[
                [f, v.real, v.imag, float(swr(v))] for f, v in sorted(values.items())
            ],
        )


def run_study(config_path, output, executable, jobs):
    config = json.loads(config_path.read_text())
    output.mkdir(parents=True, exist_ok=True)
    study = FanStudy(config, executable, Path("build/fan-dipole-cache"))
    with ThreadPoolExecutor(max_workers=jobs) as pool:

        def tune(d):
            t = study.tune(d)
            write_json(output / f"tuning-{d:g}in.json", t)
            print(
                f"{d:g} in: converged={t['converged']}, cycles={t['cycles']}, "
                f"lengths={t['lengths_ft']}",
                flush=True,
            )
            return t

        tuning = list(pool.map(tune, config["spacings_in"]))
    write_json(output / "tuning.json", tuning)
    cases = []
    tasks = [(t, b) for t in tuning for b in config["bands_mhz"]]
    with ThreadPoolExecutor(max_workers=jobs) as pool:

        def case(task):
            t, b = task
            row = study.scan(t["lengths_ft"], t["spacing_in"], b)
            row.update(spacing_in=t["spacing_in"], tuning_converged=t["converged"])
            if t["spacing_in"] in (0.5, 2):
                result, _, out, _ = study.solve(
                    t["lengths_ft"],
                    t["spacing_in"],
                    config["bands_mhz"][b],
                    pattern=True,
                )
                budget = reconciled_power_budget(out.read_text(), result.pattern)
                row["upper_efficiency"] = budget["upper_hemisphere_efficiency"]
                row["structure_loss_fraction"] = budget["structure_loss_fraction"]
                row["pattern"] = list(result.pattern)
                row["mismatch_loss_db"] = -10 * math.log10(
                    1
                    - abs((result.impedance_ohm - 50) / (result.impedance_ohm + 50))
                    ** 2
                )

            return row

        cases = list(pool.map(case, tasks))
    write_json(output / "cases.json", cases)
    print(
        "SWR scans complete; evaluating tuning Jacobians and deployment changes...",
        flush=True,
    )
    sensitivity = []
    jacobians = []
    for t in tuning:
        lengths, spacing = t["lengths_ft"], t["spacing_in"]
        # dX_i/dL_j and dX_i/df_i -> resonance shift from a symmetric 1 inch trim.
        # Holding all other lengths fixed; both ends trimmed by 1 inch.
        dxdl = np.zeros((3, 3))
        dxdf = []
        for b in BANDS:
            f = config["bands_mhz"][b]
            dxdf.append(
                (
                    study.solve(lengths, spacing, f + 0.002)[0].impedance_ohm.imag
                    - study.solve(lengths, spacing, f - 0.002)[0].impedance_ohm.imag
                )
                / 0.004
            )
        for j in range(3):
            plus = list(lengths)
            minus = list(lengths)
            plus[j] += 0.01
            minus[j] -= 0.01
            dxdl[:, j] = (
                np.array(study.reactances(plus, spacing))
                - np.array(study.reactances(minus, spacing))
            ) / 0.02
        shifts = dxdl / np.array(dxdf)[:, None] * (1000 / 12)
        diagonal = np.diag(dxdl)
        normalized = dxdl / diagonal[:, None]
        jacobians.append(
            dict(
                spacing_in=spacing,
                dx_dlength_ohm_per_ft=dxdl.tolist(),
                shift_khz_per_inch_trim=shifts.tolist(),
                normalized_cross_coupling=normalized.tolist(),
                condition_number=float(np.linalg.cond(normalized)),
            )
        )
        variants = [
            ("spacing -25%", spacing * 0.75, config),
            ("spacing +25%", spacing * 1.25, config),
            ("ends 5 ft", spacing, {**config, "end_height_ft": 5}),
            ("ends 15 ft", spacing, {**config, "end_height_ft": 15}),
        ]
        if spacing in (0.5, 2):
            variants += [
                ("poor ground", spacing, {**config, "ground": "poor"}),
                ("good ground", spacing, {**config, "ground": "good"}),
                ("bare wire", spacing, {**config, "insulation_loading_scale": 0}),
                ("1.5x sheath L", spacing, {**config, "insulation_loading_scale": 1.5}),
                (
                    "solid copper proxy",
                    spacing,
                    {**config, "effective_conductivity_s_m": 58e6},
                ),
            ]
        for label, d, c in variants:
            for b in BANDS:
                f = config["bands_mhz"][b]
                z = study.solve(lengths, d, f, c)[0].impedance_ohm
                sensitivity.append(
                    dict(
                        spacing_in=spacing,
                        scenario=label,
                        band=b,
                        r_ohm=z.real,
                        x_ohm=z.imag,
                        swr=float(swr(z)),
                    )
                )
    write_json(output / "jacobians.json", jacobians)
    write_csv(output / "sensitivity.csv", sensitivity)
    # Retune a lower-loss same-diameter copper comparator, rather than treating
    # the original CCS proxy's impedance as a universal spacing limitation.
    material_cases = []
    material_tuning = []
    material_sensitivity = []
    copper_config = {**config, "effective_conductivity_s_m": 58e6}
    copper = FanStudy(copper_config, executable, study.cache)
    print(
        "Retuning same-diameter smooth copper at half-inch and two inches...",
        flush=True,
    )
    for spacing in (0.5, 2):
        tuned = copper.tune(spacing)
        tuned["overrides"] = {"effective_conductivity_s_m": 58e6}
        material_tuning.append(tuned)
        for band, frequency in config["bands_mhz"].items():
            row = copper.scan(tuned["lengths_ft"], spacing, band)
            result, _, out, _ = copper.solve(
                tuned["lengths_ft"], spacing, frequency, pattern=True
            )
            budget = reconciled_power_budget(out.read_text(), result.pattern)
            row.update(
                spacing_in=spacing,
                material="smooth_copper_58MS_m",
                lengths_ft=tuned["lengths_ft"],
                upper_efficiency=budget["upper_hemisphere_efficiency"],
                structure_loss_fraction=budget["structure_loss_fraction"],
                pattern=list(result.pattern),
                mismatch_loss_db=-10
                * math.log10(
                    1
                    - abs((result.impedance_ohm - 50) / (result.impedance_ohm + 50))
                    ** 2
                ),
            )
            material_cases.append(row)
        if spacing == 0.5:
            for label, d, variant in (
                ("spacing -25%", spacing * 0.75, copper_config),
                ("spacing +25%", spacing * 1.25, copper_config),
                ("ends 5 ft", spacing, {**copper_config, "end_height_ft": 5}),
                ("ends 15 ft", spacing, {**copper_config, "end_height_ft": 15}),
            ):
                for band in BANDS:
                    z = copper.solve(
                        tuned["lengths_ft"], d, config["bands_mhz"][band], variant
                    )[0].impedance_ohm
                    material_sensitivity.append(
                        dict(
                            spacing_in=spacing,
                            scenario=label,
                            band=band,
                            r_ohm=z.real,
                            x_ohm=z.imag,
                            swr=float(swr(z)),
                        )
                    )
    write_csv(output / "material_sensitivity.csv", material_sensitivity)
    study.used_inputs.update(copper.used_inputs)
    write_json(output / "material_cases.json", material_cases)
    write_json(output / "material_tuning.json", material_tuning)
    write_csv(
        output / "material_summary.csv",
        [
            {
                k: v
                for k, v in row.items()
                if k not in ("sweep", "pattern", "all_resonances_mhz")
            }
            for row in material_cases
        ],
    )
    print(
        "Validating three meshes, source length and full-sphere lossless power...",
        flush=True,
    )
    validation = []
    tasks = [(t, b) for t in tuning + material_tuning for b in config["bands_mhz"]]

    def validate(task):
        t, b = task
        rows = []
        zs = []
        for mesh in config["validation_meshes_m"]:
            c = {**config, **t.get("overrides", {}), "max_segment_length_m": mesh}
            result, _, out, _ = study.solve(
                t["lengths_ft"], t["spacing_in"], config["bands_mhz"][b], c, True
            )
            zs.append(result.impedance_ohm)
            pin = power_budget(out.read_text())["input_power_w"]
            power_error = abs(pin - 0.5 * (1 / result.impedance_ohm).real) / pin
            rows.append(
                dict(
                    kind="source_power",
                    spacing_in=t["spacing_in"],
                    band=b,
                    mesh_m=mesh,
                    relative_error=power_error,
                    passed=power_error < 0.001,
                )
            )
            deck = fan_deck(
                t["lengths_ft"],
                t["spacing_in"],
                config["bands_mhz"][b],
                c,
                pattern=True,
            )
            errors = []
            for transform in (free_space_lossless_deck, free_space_reactive_deck):
                free = study.run(transform(deck))[0]
                errors.append(10 * math.log10(average_gain(free.pattern)))
            rows.append(
                dict(
                    kind="average_gain",
                    spacing_in=t["spacing_in"],
                    band=b,
                    mesh_m=mesh,
                    bare_error_db=errors[0],
                    coated_error_db=errors[1],
                    passed=max(map(abs, errors))
                    <= config["validation_average_gain_tolerance_db"],
                )
            )
        dz = abs(zs[-1] - zs[-2])
        rows.append(
            dict(
                kind="mesh",
                spacing_in=t["spacing_in"],
                band=b,
                delta_z_ohm=dz,
                passed=dz <= config["validation_impedance_tolerance_ohm"],
            )
        )
        for row in rows:
            row["material"] = (
                "smooth_copper_58MS_m" if t.get("overrides") else "CCS_proxy_10MS_m"
            )
        return rows

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for rows in pool.map(validate, tasks):
            validation.extend(rows)
    # Feed-gap/source variation keeps total tip-to-tip conductor path fixed.
    for t in [t for t in tuning + material_tuning if t["spacing_in"] in (0.5, 2)]:
        for b in config["bands_mhz"]:
            zs = []
            for source in (0.06, 0.1, 0.14):
                lengths = [
                    length + (0.1 - source) / (2 * 0.3048) for length in t["lengths_ft"]
                ]
                c = {**config, **t.get("overrides", {}), "source_length_m": source}
                z = study.solve(lengths, t["spacing_in"], config["bands_mhz"][b], c)[
                    0
                ].impedance_ohm
                zs.append(z)
            dz = max(abs(a - b) for a in zs for b in zs)
            validation.append(
                dict(
                    kind="source_length",
                    material="smooth_copper_58MS_m"
                    if t.get("overrides")
                    else "CCS_proxy_10MS_m",
                    spacing_in=t["spacing_in"],
                    band=b,
                    delta_z_ohm=dz,
                    passed=dz <= 2,
                )
            )
    write_json(output / "validation.json", validation)
    data = dict(
        config=config,
        tuning=tuning,
        cases=cases,
        jacobians=jacobians,
        sensitivity=sensitivity,
        validation=validation,
        material_cases=material_cases,
        material_tuning=material_tuning,
        material_sensitivity=material_sensitivity,
    )
    write_json(output / "study.json", data)
    write_json(output / "config.json", config)
    write_csv(
        output / "summary.csv",
        [
            {
                k: v
                for k, v in r.items()
                if k
                not in (
                    "sweep",
                    "pattern",
                    "all_resonances_mhz",
                    "in_band_swr2_windows_mhz",
                )
            }
            for r in cases
        ],
    )
    write_csv(
        output / "sweeps.csv",
        [
            dict(
                spacing_in=r["spacing_in"],
                band=r["band"],
                frequency_mhz=f,
                r_ohm=rr,
                x_ohm=x,
                swr=s,
            )
            for r in cases
            for f, rr, x, s in r["sweep"]
        ],
    )
    write_json(
        output / "run_metadata.json",
        dict(
            solver_path=str(executable),
            python=platform.python_version(),
            numpy=np.__version__,
            scipy=scipy.__version__,
            solver_sha256=sha256(executable),
            config_sha256=sha256(config_path),
            source_sha256={
                p.name: sha256(p)
                for p in (
                    Path("src/antenna_lab") / name
                    for name in (
                        "fan_dipole.py",
                        "fan_dipole_study.py",
                        "fan_dipole_report.py",
                        "linked_dipole.py",
                        "linked_dipole_study.py",
                        "nec.py",
                        "linked_dipole_validation.py",
                        "rigid_doublet_validation.py",
                        "transmission_line.py",
                        "efrw_study.py",
                    )
                )
            },
            used_nec_inputs={
                stem: dict(
                    deck_sha256=sha256(p), output_sha256=sha256(p.with_suffix(".out"))
                )
                for stem, p in sorted(study.used_inputs.items())
            },
            cache=str(study.cache),
            validation_passed=all(r["passed"] for r in validation),
        ),
    )
    print(
        f"Finished: {sum(r['passed'] for r in validation)}/{len(validation)} "
        "numerical checks pass",
        flush=True,
    )
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/fan-dipole-v1.json")
    )
    parser.add_argument("--output", type=Path, default=Path("build/fan-dipole-v1"))
    parser.add_argument("--nec2c", default="nec2c")
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    run_study(args.config, args.output, find_nec2c(args.nec2c).resolve(), args.jobs)


if __name__ == "__main__":
    main()
