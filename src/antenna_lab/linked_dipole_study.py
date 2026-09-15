"""Reproducible frozen-length and retuned linked dipole deployment study."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import brentq, minimize_scalar

from antenna_lab.efrw_study import _write_manifest as write_manifest
from antenna_lab.linked_dipole import geometry_dimensions, linked_deck, linked_network
from antenna_lab.linked_dipole_validation import (
    free_space_reactive_deck,
    reconciled_power_budget,
    upper_hemisphere_efficiency,
    upper_hemisphere_efficiency_from_fields,
)
from antenna_lab.nec import find_nec2c, run_cached
from antenna_lab.rigid_doublet_validation import average_gain, free_space_lossless_deck
from antenna_lab.transmission_line import swr


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remove_obsolete_generated_files(directory: Path, retained: set[str]) -> None:
    """Remove only formerly manifested artifacts superseded by this generation."""
    manifest = directory / "SHA256SUMS"
    if not manifest.is_file():
        return
    for line in manifest.read_text().splitlines():
        _, relative = line.split("  ", 1)
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Generated manifest must contain relative artifact paths")
        artifact = directory / path
        if not artifact.resolve().is_relative_to(directory.resolve()):
            raise ValueError(
                "Generated manifest artifact must stay within its directory"
            )
        if relative not in retained and artifact.is_file():
            artifact.unlink()


class Study:
    def __init__(self, config: dict[str, Any], executable: Path, cache: Path):
        self.config = config
        self.executable = executable
        self.cache = cache
        self.used_inputs: dict[str, Path] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def run(self, deck):
        key = hashlib.sha256(deck.encode()).hexdigest()
        with self._lock:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            result = run_cached(deck, self.cache, self.executable)
            with self._lock:
                self.used_inputs[result[1].stem] = result[1]
            return result

    def solve(self, lengths, height, band, frequency, config=None, **kwargs):
        deck = linked_deck(
            lengths, height, band, frequency, config or self.config, **kwargs
        )
        return self.run(deck)

    def tune(self, height: float, initial: list[float]) -> dict[str, Any]:
        """Coordinate-wise resonance tuning, always rechecking the full assembly."""
        lengths = list(initial)
        history = []
        for iteration in range(16):
            for section, (band, frequency) in enumerate(
                self.config["bands_mhz"].items()
            ):

                def reactance(length, section=section, band=band, frequency=frequency):
                    trial = list(lengths)
                    trial[section] = length
                    return self.solve(trial, height, band, frequency)[
                        0
                    ].impedance_ohm.imag

                lower, upper = self.config["section_bounds_ft"][section]
                lower = max(
                    lower,
                    self.config["center_height_ft"]
                    - height
                    - sum(lengths)
                    + lengths[section]
                    + 0.15,
                )
                # Search locally first to avoid selecting a remote parasitic root.
                candidates = sorted(
                    set(
                        [
                            lower,
                            upper,
                            lengths[section],
                            max(lower, lengths[section] - 0.7),
                            min(upper, lengths[section] + 0.7),
                        ]
                    )
                )
                samples = [(length, reactance(length)) for length in candidates]
                brackets = [
                    (a, b)
                    for a, b in zip(samples[:-1], samples[1:], strict=True)
                    if a[1] * b[1] <= 0
                ]
                if not brackets:
                    raise ValueError(
                        f"No tuning root for {band} at {height}ft: {samples}"
                    )
                a, b = min(
                    brackets,
                    key=lambda pair: abs(
                        (pair[0][0] + pair[1][0]) / 2 - lengths[section]
                    ),
                )
                lengths[section] = float(brentq(reactance, a[0], b[0], xtol=2e-5))
            recheck = {
                band: self.solve(lengths, height, band, frequency)[0].impedance_ohm.imag
                for band, frequency in self.config["bands_mhz"].items()
            }
            history.append(
                dict(
                    iteration=iteration + 1,
                    section_lengths_ft=list(lengths),
                    rechecked_reactance_ohm=recheck,
                )
            )
            if (
                max(abs(value) for value in recheck.values())
                <= self.config["tuning_reactance_tolerance_ohm"]
            ):
                return dict(
                    end_height_ft=height,
                    section_lengths_ft=lengths,
                    history=history,
                    converged=True,
                )
        raise ValueError(f"Sequential tuning failed to converge at {height}ft")

    def frequency_scan(
        self,
        lengths,
        height,
        band,
        config=None,
        ground="average",
        outer_closed_on_20m=False,
    ) -> dict[str, Any]:
        config = config or self.config
        frequency = config["bands_mhz"][band]
        band_lo, band_hi = config["band_edges_mhz"][band]
        samples = {}

        def impedance(f):
            f = round(float(f), 8)
            if f not in samples:
                samples[f] = self.solve(
                    lengths,
                    height,
                    band,
                    f,
                    config,
                    ground=ground,
                    outer_closed_on_20m=outer_closed_on_20m,
                )[0].impedance_ohm
            return samples[f]

        def mismatch(f):
            return float(swr(impedance(f)))

        fraction = config["sweep_search_fraction"]
        for _ in range(5):
            grid = sorted(
                set(
                    np.linspace(
                        band_lo, band_hi, config["sweep_samples_in_band"]
                    ).tolist()
                    + np.linspace(
                        frequency * (1 - fraction), frequency * (1 + fraction), 33
                    ).tolist()
                    + [frequency]
                )
            )
            values = [mismatch(f) for f in grid]
            best = int(np.argmin(values))
            if 0 < best < len(grid) - 1 and values[0] > 2 and values[-1] > 2:
                break
            fraction *= 1.5
        else:
            raise ValueError(f"SWR search not bracketed: {height} {band}")
        minimum = minimize_scalar(
            mismatch,
            bounds=(grid[best - 1], grid[best + 1]),
            method="bounded",
            options={"xatol": 2e-6},
        )
        min_frequency = float(minimum.x)
        roots = [
            float(brentq(lambda f: impedance(f).imag, a, b, xtol=2e-6))
            for a, b in zip(grid[:-1], grid[1:], strict=True)
            if impedance(a).imag * impedance(b).imag < 0
        ]
        roots.extend(f for f in grid if abs(impedance(f).imag) <= 1e-9)
        roots = sorted(set(round(f, 6) for f in roots))
        resonance = min(roots, key=lambda f: abs(f - frequency)) if roots else None
        crossings = [
            float(brentq(lambda f: mismatch(f) - 2, a, b, xtol=2e-6))
            for a, b in zip(grid[:-1], grid[1:], strict=True)
            if (mismatch(a) - 2) * (mismatch(b) - 2) < 0
        ]
        crossings.extend(f for f in grid if math.isclose(mismatch(f), 2, abs_tol=1e-10))
        crossings = sorted(set(round(f, 6) for f in crossings))
        below = [f for f in crossings if f < min_frequency]
        above = [f for f in crossings if f > min_frequency]
        low = max(below) if below else None
        high = min(above) if above else None
        intervals = []
        if low is not None and high is not None:
            intervals = [max(band_lo, low), min(band_hi, high)]
            if intervals[1] < intervals[0]:
                intervals = []
        return dict(
            resonance_mhz=resonance,
            all_resonances_mhz=roots,
            min_swr_frequency_mhz=min_frequency,
            min_swr=mismatch(min_frequency),
            swr2_low_mhz=low,
            swr2_high_mhz=high,
            swr2_bandwidth_khz=None
            if low is None or high is None
            else (high - low) * 1000,
            in_band_swr2_interval_mhz=intervals,
            in_band_max_swr=max(mismatch(f) for f in np.linspace(band_lo, band_hi, 31)),
            sweep=[
                [f, z.real, z.imag, float(swr(z))] for f, z in sorted(samples.items())
            ],
        )

    def case(
        self,
        lengths,
        height,
        band,
        mode="frozen",
        config=None,
        ground="average",
        scan=True,
        step=None,
        outer_closed_on_20m=False,
    ):
        config = config or self.config
        frequency = config["bands_mhz"][band]
        result, deck_path, output_path, _ = self.solve(
            lengths,
            height,
            band,
            frequency,
            config,
            ground=ground,
            pattern_step_deg=step or config["pattern_step_deg"],
            outer_closed_on_20m=outer_closed_on_20m,
        )
        z = result.impedance_ohm
        accepted = 1 - abs((z - 50) / (z + 50)) ** 2
        mismatch_loss = -10 * math.log10(accepted)
        power = reconciled_power_budget(output_path.read_text(), result.pattern)
        peak = max(result.pattern, key=lambda point: point[2])
        row = dict(
            case_id=f"{mode}-{band}-{height:g}ft",
            mode=mode,
            band=band,
            end_height_ft=height,
            frequency_mhz=frequency,
            section_lengths_ft=list(lengths),
            geometry=geometry_dimensions(lengths, height, config),
            ground=ground,
            r_ohm=z.real,
            x_ohm=z.imag,
            swr=float(swr(z)),
            accepted_power_fraction_50ohm=accepted,
            mismatch_loss_db=mismatch_loss,
            efficiency_upper=power["upper_hemisphere_efficiency"],
            available_to_upper_efficiency=power["upper_hemisphere_efficiency"]
            * accepted,
            power_budget=power,
            peak_gain_dbi=peak[2],
            peak_elevation_deg=peak[0],
            peak_azimuth_deg=peak[1],
            realized_peak_gain_dbi=peak[2] - mismatch_loss,
            pattern=list(result.pattern),
            nec_deck_sha256=sha256(deck_path),
            nec_output_sha256=sha256(output_path),
            nec_cache_stem=deck_path.stem,
        )
        for elevation in (10, 20, 30, 60, 90):
            for direction, azimuth in (("broadside", 90), ("end_on", 0)):
                gain = next(
                    p[2]
                    for p in result.pattern
                    if p[0] == elevation and p[1] == azimuth
                )
                row[f"gain_{direction}_{elevation}deg_dbi"] = gain
                row[f"realized_{direction}_{elevation}deg_dbi"] = gain - mismatch_loss
        if scan:
            row.update(
                self.frequency_scan(
                    lengths, height, band, config, ground, outer_closed_on_20m
                )
            )
        return row


def validate_study(study: Study, lengths, cases, jobs):
    """Mesh, source, actual open endpoints, free space, and angular checks."""
    config = study.config
    checks = config["validation"]
    tasks = [
        (height, band)
        for height in config["outer_end_heights_ft"]
        for band in config["bands_mhz"]
    ]

    def validate(task):
        height, band = task
        frequency = config["bands_mhz"][band]
        rows = []
        meshes = []
        for segment in checks["max_segment_lengths_m"]:
            variant = {**config, "max_segment_length_m": segment}
            deck = linked_deck(
                lengths, height, band, frequency, variant, pattern_step_deg=5
            )
            result, path, output, _ = study.run(deck)
            free, free_path, _, _ = study.run(free_space_lossless_deck(deck))
            ag_error = 10 * math.log10(average_gain(free.pattern))
            reactive, reactive_path, _, _ = study.run(free_space_reactive_deck(deck))
            reactive_ag_error = 10 * math.log10(average_gain(reactive.pattern))
            meshes.append((result.impedance_ohm, max(p[2] for p in result.pattern)))
            rows.append(
                dict(
                    kind="mesh_and_free_space",
                    band=band,
                    end_height_ft=height,
                    max_segment_length_m=segment,
                    average_gain_error_db=ag_error,
                    reactive_average_gain_error_db=reactive_ag_error,
                    r_ohm=result.impedance_ohm.real,
                    x_ohm=result.impedance_ohm.imag,
                    peak_gain_dbi=meshes[-1][1],
                    passed=max(abs(ag_error), abs(reactive_ag_error))
                    <= checks["average_gain_tolerance_db"],
                    nec_deck_sha256=sha256(path),
                    free_space_deck_sha256=sha256(free_path),
                    reactive_free_space_deck_sha256=sha256(reactive_path),
                )
            )
        dz = abs(meshes[-1][0] - meshes[-2][0])
        dg = abs(meshes[-1][1] - meshes[-2][1])
        rows.append(
            dict(
                kind="mesh_convergence",
                band=band,
                end_height_ft=height,
                impedance_change_ohm=dz,
                gain_change_db=dg,
                passed=dz <= checks["mesh_impedance_tolerance_ohm"]
                and dg <= checks["mesh_gain_tolerance_db"],
            )
        )
        reference = next(
            c
            for c in cases
            if c["band"] == band
            and c["end_height_ft"] == height
            and c["mode"] == "frozen"
        )
        fine, _, fine_path, _ = study.solve(
            lengths,
            height,
            band,
            frequency,
            pattern_step_deg=checks["fine_pattern_step_deg"],
        )
        fine_eta = upper_hemisphere_efficiency(fine.pattern)
        fields_eta = upper_hemisphere_efficiency_from_fields(fine_path.read_text())
        difference = abs(fine_eta - reference["efficiency_upper"])
        field_difference = abs(fine_eta - fields_eta)
        pin = reference["power_budget"]["input_power_w"]
        source_z = complex(reference["r_ohm"], reference["x_ohm"])
        source_power_error = abs(pin - 0.5 * (1 / source_z).real) / pin
        residual = reference["power_budget"]["ground_and_numerical_residual_fraction"]
        rows.append(
            dict(
                kind="angular_and_power",
                band=band,
                end_height_ft=height,
                coarse_efficiency=reference["efficiency_upper"],
                fine_efficiency=fine_eta,
                field_efficiency=fields_eta,
                efficiency_change=difference,
                field_gain_difference=field_difference,
                source_power_relative_error=source_power_error,
                ground_residual_fraction=residual,
                peak_gain_change_db=abs(
                    max(p[2] for p in fine.pattern) - reference["peak_gain_dbi"]
                ),
                passed=difference < checks["angular_efficiency_tolerance"]
                and field_difference < 0.002
                and source_power_error < 0.0001
                and -checks["power_residual_tolerance"] <= residual <= 1
                and 0 <= fine_eta <= 1.002,
            )
        )
        if height in (5, 33):
            source_z = []
            source_gain = []
            for source in checks["source_lengths_m"]:
                # Preserve total conductor path length when changing bridge size;
                # tiny endpoint and bend-location differences remain.
                variant = {**config, "source_length_m": source}
                adjusted = list(lengths)
                adjusted[0] += (config["source_length_m"] - source) / (2 * 0.3048)
                row = study.case(
                    adjusted, height, band, config=variant, scan=False, step=5
                )
                source_z.append(complex(row["r_ohm"], row["x_ohm"]))
                source_gain.append(row["peak_gain_dbi"])
            spread = max(abs(a - b) for a in source_z for b in source_z)
            gain_spread = max(source_gain) - min(source_gain)
            rows.append(
                dict(
                    kind="source_length",
                    band=band,
                    end_height_ft=height,
                    impedance_spread_ohm=spread,
                    gain_spread_db=gain_spread,
                    passed=spread < 3 and gain_spread < 0.2,
                )
            )
        return rows

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows = [row for group in pool.map(validate, tasks) for row in group]
    # NEC endpoint auto-connection tolerance is 0.001 segment length. Examine
    # printed connectivity in the output as well as the constructed network.
    from antenna_lab.linked_dipole_validation import check_open_endpoints

    for band in config["bands_mhz"]:
        for gap in (min(config["sensitivity"]["open_gaps_m"]), config["open_gap_m"]):
            variant = {**config, "open_gap_m": gap}
            _, _, output, _ = study.solve(
                lengths, 5, band, config["bands_mhz"][band], variant
            )
            wires, _ = linked_network(lengths, 5, band, variant)
            rows.append(
                dict(
                    kind="open_connectivity",
                    band=band,
                    open_gap_m=gap,
                    **check_open_endpoints(output.read_text(), wires, band),
                )
            )
    # The smallest and largest assumed gaps also need a convergence test;
    # preserving endpoint connectivity alone cannot validate short bridges.
    for band in config["bands_mhz"]:
        for gap in config["sensitivity"]["open_gaps_m"]:
            for height in (5, 33):
                solutions = []
                errors = []
                for mesh in checks["max_segment_lengths_m"][-2:]:
                    variant = {
                        **config,
                        "open_gap_m": gap,
                        "max_segment_length_m": mesh,
                    }
                    deck = linked_deck(
                        lengths,
                        height,
                        band,
                        config["bands_mhz"][band],
                        variant,
                        pattern_step_deg=5,
                    )
                    result = study.run(deck)[0]
                    free = study.run(free_space_reactive_deck(deck))[0]
                    errors.append(abs(10 * math.log10(average_gain(free.pattern))))
                    solutions.append(
                        (result.impedance_ohm, max(p[2] for p in result.pattern))
                    )
                dz = abs(solutions[1][0] - solutions[0][0])
                dg = abs(solutions[1][1] - solutions[0][1])
                rows.append(
                    dict(
                        kind="gap_mesh",
                        band=band,
                        end_height_ft=height,
                        open_gap_m=gap,
                        impedance_change_ohm=dz,
                        gain_change_db=dg,
                        average_gain_error_db=max(errors),
                        passed=dz < checks["mesh_impedance_tolerance_ohm"]
                        and dg < checks["mesh_gain_tolerance_db"]
                        and max(errors) < checks["average_gain_tolerance_db"],
                    )
                )
    return rows


def sensitivity_study(study, lengths, jobs):
    config = study.config
    variants = []
    for soil in config["grounds"]:
        for conductivity in config["sensitivity"]["conductivities_s_m"]:
            variants.append(
                (
                    f"soil-wire-{soil}-{conductivity:g}",
                    {**config, "effective_conductivity_s_m": conductivity},
                    soil,
                    False,
                )
            )
    for key, values in (
        ("open_gap_m", config["sensitivity"]["open_gaps_m"]),
        ("contact_resistance_ohm", config["sensitivity"]["contact_resistances_ohm"]),
        (
            "insulation_loading_scale",
            config["sensitivity"]["insulation_loading_scales"],
        ),
    ):
        variants.extend(
            (f"{key}-{value:g}", {**config, key: value}, "average", False)
            for value in values
        )
    tasks = [
        (variant, height, band)
        for variant in variants
        for height in config["outer_end_heights_ft"]
        for band in config["bands_mhz"]
    ]
    tasks.extend(
        (("outer-links-closed-20m", config, "average", True), height, "20m")
        for height in config["outer_end_heights_ft"]
    )

    def evaluate(task):
        (name, variant, soil, outer_closed), height, band = task
        row = study.case(
            lengths,
            height,
            band,
            mode="sensitivity",
            config=variant,
            ground=soil,
            scan=False,
            step=5,
            outer_closed_on_20m=outer_closed,
        )
        row.pop("pattern")
        row.update(
            variant=name,
            effective_conductivity_s_m=variant["effective_conductivity_s_m"],
            open_gap_m=variant["open_gap_m"],
            contact_resistance_ohm=variant["contact_resistance_ohm"],
            insulation_loading_scale=variant["insulation_loading_scale"],
        )
        return row

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(evaluate, tasks))


def run_linked_dipole_study(
    config_path,
    output_dir,
    nec2c=None,
    cache_dir="build/linked-nec-cache",
    jobs=6,
    compact_dir=None,
):
    config_path, output_dir = Path(config_path), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text())
    executable = find_nec2c(nec2c).resolve()
    study = Study(config, executable, Path(cache_dir))
    print(
        "Tuning complete assembly sequentially at "
        f"{config['center_height_ft']:g}/{config['nominal_end_height_ft']:g} ft...",
        flush=True,
    )
    nominal = study.tune(
        config["nominal_end_height_ft"], config["initial_section_lengths_ft"]
    )
    lengths = nominal["section_lengths_ft"]
    print(f"Frozen provisional sections per leg (ft): {lengths}", flush=True)
    write_json(output_dir / "nominal_tuning.json", nominal)
    print(
        "Tuning alternative assemblies for the separate retuned comparison...",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        tuned = list(
            pool.map(
                lambda h: (
                    nominal
                    if h == config["nominal_end_height_ft"]
                    else study.tune(h, lengths)
                ),
                config["outer_end_heights_ft"],
            )
        )
    write_json(output_dir / "tuning.json", tuned)
    tasks = [
        (
            mode,
            height,
            band,
            lengths
            if mode == "frozen"
            else next(
                t["section_lengths_ft"] for t in tuned if t["end_height_ft"] == height
            ),
        )
        for mode in ("frozen", "retuned")
        for height in config["outer_end_heights_ft"]
        for band in config["bands_mhz"]
    ]
    print(
        "Computing 30 primary/retuned patterns, frequency scans and bandwidths...",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        cases = list(pool.map(lambda t: study.case(t[3], t[1], t[2], t[0]), tasks))
    data = dict(config=config, nominal_tuning=nominal, tuning=tuned, cases=cases)
    write_json(output_dir / "study.json", data)
    print(
        "Computing soil, wire, coating, gap/contact and outer-link sensitivity...",
        flush=True,
    )
    data["sensitivity"] = sensitivity_study(study, lengths, jobs)
    write_json(output_dir / "study.json", data)
    print(
        "Validating mesh/source/gaps, angular sampling and free-space gain...",
        flush=True,
    )
    data["validation"] = validate_study(study, lengths, cases, jobs)
    data["used_nec_inputs"] = sorted(study.used_inputs)
    write_json(output_dir / "study.json", data)
    finish_artifacts(
        output_dir, data, config_path, executable, Path(cache_dir), compact_dir
    )
    return dict(
        output=str(output_dir),
        provisional_section_lengths_ft=lengths,
        primary_cases=15,
        retuned_cases=15,
        sensitivity_cases=len(data["sensitivity"]),
        validation_checks=len(data["validation"]),
        validation_passed=all(r["passed"] for r in data["validation"]),
    )


def finish_artifacts(output, data, config_path, executable, cache, compact_dir=None):
    from antenna_lab.linked_dipole_report import render_artifacts
    from antenna_lab.linked_dipole_summary import write_report

    write_json(output / "config.json", data["config"])
    write_json(output / "study.json", data)
    excluded = {
        "pattern",
        "sweep",
        "geometry",
        "power_budget",
        "section_lengths_ft",
        "all_resonances_mhz",
        "in_band_swr2_interval_mhz",
    }
    write_csv(
        output / "summary.csv",
        [{k: v for k, v in row.items() if k not in excluded} for row in data["cases"]],
    )
    write_csv(
        output / "geometry.csv",
        [dict(mode=t["mode"], band=t["band"], **t["geometry"]) for t in data["cases"]],
    )
    write_csv(
        output / "sensitivity.csv",
        [
            {k: v for k, v in row.items() if k not in excluded}
            for row in data["sensitivity"]
        ],
    )
    write_csv(output / "validation.csv", data["validation"])
    write_json(output / "numerical_validation.json", data["validation"])
    write_csv(
        output / "patterns.csv",
        [
            dict(
                case_id=row["case_id"],
                elevation_deg=e,
                azimuth_deg=a,
                gain_dbi=g,
                realized_gain_dbi=g - row["mismatch_loss_db"],
            )
            for row in data["cases"]
            for e, a, g in row["pattern"]
        ],
    )
    write_csv(
        output / "sweeps.csv",
        [
            dict(case_id=row["case_id"], frequency_mhz=f, r_ohm=r, x_ohm=x, swr=s)
            for row in data["cases"]
            for f, r, x, s in row["sweep"]
        ],
    )
    metadata = dict(
        study_id=data["config"]["study_id"],
        python=platform.python_version(),
        solver_path=str(executable),
        solver_sha256=sha256(executable),
        config_sha256=sha256(config_path),
        source_sha256={p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
        solver_source_sha256={
            p.name: sha256(p) for p in Path("build/nec2c-src").glob("*.c")
        },
        cache=str(cache),
        cache_identity="sha256(solver_binary_sha256 + NUL + exact_deck)",
        gain_reference="4pi U / accepted feedpoint power; no directivity normalization",
        efficiency_reference=(
            "upper hemisphere far-field space-wave flux / accepted feedpoint power"
        ),
        realized_reference="gain + 10log10(1-|Gamma50|^2), exactly once",
        checks_passed=all(r["passed"] for r in data["validation"]),
    )
    # Retain input/output provenance for every solve (including tuning and sweep)
    # in the full run. The cache remains reusable between runs.
    provenance = output / "nec"
    provenance.mkdir(exist_ok=True)
    used_inputs = set(data["used_nec_inputs"])
    for path in provenance.iterdir():
        if path.suffix in (".nec", ".out") and path.stem not in used_inputs:
            path.unlink()
    for stem in data["used_nec_inputs"]:
        for suffix in (".nec", ".out"):
            path = cache / (stem + suffix)
            destination = provenance / path.name
            if not destination.exists() or sha256(path) != sha256(destination):
                shutil.copy2(path, destination)
    metadata["used_nec_input_count"] = len(data["used_nec_inputs"])
    metadata["used_nec_inputs"] = data["used_nec_inputs"]
    write_json(output / "run_metadata.json", metadata)
    write_json(
        output / "full_run.json",
        dict(path=str(output), scope="complete_generated_run", manifest="SHA256SUMS"),
    )
    # The canonical report is now a GitHub-rendered directory README.
    (output / "REPORT.md").unlink(missing_ok=True)
    render_artifacts(output, data)
    write_report(output, data)
    write_manifest(output)
    if compact_dir:
        compact = Path(compact_dir)
        compact.mkdir(parents=True, exist_ok=True)
        compact_files = (
            "README.md",
            "viewer.html",
            "summary.csv",
            "geometry.csv",
            "sensitivity.csv",
            "run_metadata.json",
            "numerical_validation.json",
            "config.json",
            "tuning.json",
        )
        figures = [
            path
            for path in (output / "figures").iterdir()
            if path.suffix in (".png", ".svg")
        ]
        remove_obsolete_generated_files(
            compact,
            {
                *compact_files,
                "full_run.json",
                *(f"figures/{path.name}" for path in figures),
            },
        )
        for name in compact_files:
            shutil.copy2(output / name, compact / name)
        (compact / "figures").mkdir(exist_ok=True)
        for path in figures:
            shutil.copy2(path, compact / "figures" / path.name)
        write_json(
            compact / "full_run.json",
            dict(path=str(output), manifest_sha256=sha256(output / "SHA256SUMS")),
        )
        write_manifest(compact)
