"""Construction sensitivities for the open balun; no measured DUT predictions.

Run with `mise run balun-decision`. See docs/case-studies/balun-decision.md.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .bifilar_choke import (
    BANDS,
    CORES,
    DATA,
    ROOT,
    bypass_capacitance,
    copper_loop_resistance,
    material_impedance,
    part_impedance,
    write_csv,
)

OUT = ROOT / "results/balun-decision-v1"
C = 299792458


def twin_lead(diameter_mm, spacing_mm, epsilon_eff):
    """Homogeneous, nonmagnetic, straight two-cylinder TEM approximation.

    Spacing is center-to-center. An effective epsilon is an assumption, not
    the bulk jacket epsilon or a solution for coated wires beside ferrite.
    Proximity factor is the high-frequency two-cylinder surface-loss result.
    """
    if diameter_mm <= 0 or spacing_mm <= diameter_mm or epsilon_eff < 1:
        raise ValueError("Require separated cylinders and epsilon >= 1")
    u = np.arccosh(spacing_mm / diameter_mm)
    return 120 * u / np.sqrt(epsilon_eff), 1 / np.sqrt(epsilon_eff), 1 / np.tanh(u)


def line_sparameters(frequency, length_m, z0, vf, r_per_m=0, tan_delta=0):
    """Uniform RLGC line, equal real 50-ohm port references.

    z0 and vf describe the lossless line. R is the TWO-conductor loop R/m;
    G = omega*C*tan_delta. This handles mismatch and dissipative loss together.
    """
    omega = 2 * np.pi * np.asarray(frequency)
    inductance = z0 / (C * vf)
    capacitance = 1 / (z0 * C * vf)
    series = r_per_m + 1j * omega * inductance
    shunt = omega * capacitance * (tan_delta + 1j)
    gamma = np.sqrt(series * shunt)
    zc = np.sqrt(series / shunt)
    a = np.cosh(gamma * length_m)
    b = zc * np.sinh(gamma * length_m)
    c = np.sinh(gamma * length_m) / zc
    denominator = 2 * a + b / 50 + 50 * c
    return (b / 50 - 50 * c) / denominator, 2 / denominator


def metrics(s11, s21):
    reflected = abs(s11) ** 2
    transmitted = abs(s21) ** 2
    return {
        "swr": (1 + abs(s11)) / (1 - abs(s11)),
        "return_loss_db": -10 * np.log10(np.maximum(reflected, 1e-30)),
        "insertion_loss_db": -10 * np.log10(transmitted),
        "dissipated_fraction_incident": 1 - reflected - transmitted,
        "dissipation_db_accepted": -10 * np.log10(transmitted / (1 - reflected)),
    }


def fit_screen(od, inner, height, wire_od, spacing, turns):
    """Ideal flat pair, tight rectangular-core path; no bend-radius guarantee.

    Nominal values exclude tape, tolerances, free leads and crossover detour.
    The face-stacking column adds one wire layer on one face only.
    """
    return {
        "wound_od_mm": od + 2 * wire_od,
        "wound_height_mm": height + 2 * wire_od,
        "one_face_crossing_height_mm": height + 3 * wire_od,
        "rim_occupancy_fraction": turns
        * (spacing + wire_od)
        / (np.pi * (inner - wire_od)),
        "aperture_area_fraction": 2 * turns * (wire_od / inner) ** 2,
        "winding_length_each_m": turns
        * (2 * height + od - inner + np.pi * wire_od)
        / 1000,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cm_rows = []
    all_cores = CORES + [
        ("2631800302", 31, 12.7, 7.15, 4.78, 1.9, 1),
        ("5943000301", 43, 12.7, 7.15, 4.9, 2, 1),
        ("5943000601", 43, 21, 13.2, 6.35, 6.4, 1),
        ("2631250202", 31, 6.35, 2.95, 25.4, 2.9, 1),
    ]
    for core in all_cores:
        sources = ["material"] + (["part_N1"] if core[0] == "2631801202" else [])
        for source in sources:
            for n in (1,) if core[0] == "2631250202" else (8, 10, 11, 12, 13, 14, 16):
                for cap in (0, 1, 2, 4, 8):
                    for band, (low, high) in BANDS.items():
                        f = np.linspace(low, high, 41) * 1e6
                        zm = (
                            part_impedance(f, n)
                            if source == "part_N1"
                            else material_impedance(core, f, n)
                        )
                        z = bypass_capacitance(zm, f, cap)
                        cm_rows.append(
                            dict(
                                part=core[0],
                                source=source,
                                turns=n,
                                cap_pf=cap,
                                band=band,
                                min_r_ohm=float(min(z.real)),
                                min_x_ohm=float(min(z.imag)),
                                max_x_ohm=float(max(z.imag)),
                                min_abs_z_ohm=float(min(abs(z))),
                            )
                        )
    write_csv(OUT / "common-mode.csv", cm_rows)

    # Geometry-anchored SENSITIVITIES. No product is assigned a measured epsilon.
    # Stranded bundle diameters are envelopes, not copper-equivalent diameters.
    pairs = [
        ("18 enamel touching scenario", 1.024, 1.06, (1, 2, 3, 4)),
        ("18 enamel spaced scenario", 1.024, 1.25, (1.5, 2, 3)),
        ("22 heavy enamel touching", 0.644, 0.701, (1, 2, 3, 4)),
        ("22 heavy enamel spaced scenario", 0.644, 0.82, (1.5, 2, 3)),
        ("22 BNTECHGO FEP bundle scenario", 0.75, 1.42, (1, 1.5, 2.1)),
        ("22 Spec55 bundle scenario", 0.79, 1.09, (1, 1.8, 2.6)),
    ]
    pair_rows = []
    for name, diameter, spacing, epsilons in pairs:
        for epsilon in epsilons:
            z0, vf, proximity = twin_lead(diameter, spacing, epsilon)
            for length in (0.50, 0.60, 0.70):
                for band, (low, high) in BANDS.items():
                    f = np.linspace(low, high, 41) * 1e6
                    # Solid-round approximation is especially uncertain for
                    # stranded/plated wire. No tin, strand-contact, core loss.
                    loop_r_per_m = copper_loop_resistance(f, 1, diameter) * proximity
                    m = metrics(*line_sparameters(f, length, z0, vf, loop_r_per_m))
                    pair_rows.append(
                        dict(
                            scenario=name,
                            diameter_mm=diameter,
                            spacing_mm=spacing,
                            epsilon_eff=epsilon,
                            z0_ohm=float(z0),
                            vf=float(vf),
                            proximity_factor=float(proximity),
                            length_m=length,
                            band=band,
                            max_swr=float(max(m["swr"])),
                            min_return_loss_db=float(min(m["return_loss_db"])),
                            max_insertion_loss_db=float(max(m["insertion_loss_db"])),
                            max_dissipation_db_accepted=float(
                                max(m["dissipation_db_accepted"])
                            ),
                            max_dissipated_w_100w_incident=float(
                                100 * max(m["dissipated_fraction_incident"])
                            ),
                        )
                    )
    write_csv(OUT / "pair-scenarios.csv", pair_rows)

    geometry = []
    for name, d, spacing in [
        ("18 enamel spaced", 1.06, 1.25),
        ("22 heavy enamel spaced", 0.701, 0.82),
        ("22 FEP", 1.42, 1.42),
        ("22 silicone", 1.7, 1.7),
        ("18 silicone", 2.3, 2.3),
        ("28 silicone", 1.2, 1.2),
        ("22 Spec55", 1.09, 1.09),
    ]:
        for n in (12, 13):
            geometry.append(
                dict(wire=name, turns=n, **fit_screen(29, 19, 13.85, d, spacing, n))
            )
    write_csv(OUT / "geometry.csv", geometry)

    report = [
        "# Open-balun construction screen — 17 September 2026",
        "",
        "All tables are calculations using stated scenarios, not measurements.",
        "[Decision, sources and build/test instructions]"
        "(../../docs/case-studies/balun-decision.md).",
        "",
        "## Common-mode example: 2631801202, N=12",
        "",
        "Exact-part N=1 series R+jX scaled by N², then shunted by assumed C.",
        "Entries: band-min R; range of X; band-min |Z|, all kΩ. No confidence bounds.",
        "",
        "| Band | 2 pF: R; X; magnitude | 8 pF: R; X; magnitude |",
        "| --- | --- | --- |",
    ]
    for band in BANDS:
        row = f"| {band} |"
        for cap in (2, 8):
            r = next(
                r
                for r in cm_rows
                if r["part"] == "2631801202"
                and r["source"] == "part_N1"
                and r["turns"] == 12
                and r["cap_pf"] == cap
                and r["band"] == band
            )
            row += (
                f" {r['min_r_ohm'] / 1000:.2f}; "
                f"{r['min_x_ohm'] / 1000:+.2f}…{r['max_x_ohm'] / 1000:+.2f}; "
                f"{r['min_abs_z_ohm'] / 1000:.2f} |"
            )
        report.append(row)
    report += [
        "",
        "## Differential line examples",
        "",
        "0.60 m, assumed epsilon_eff=2 for enamel; 1.5 for FEP; 1.8 for Spec55. "
        "Solid-round skin + pair proximity only; no dielectric or ferrite loss.",
        "",
        "| Scenario | Band | Z0 Ω | SWR | RL dB | IL dB | Heat W / 100 W incident |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in pair_rows:
        epsilon = 1.5 if "FEP" in r["scenario"] else 2
        if "Spec55" in r["scenario"]:
            epsilon = 1.8
        if r["length_m"] == 0.6 and r["epsilon_eff"] == epsilon:
            report.append(
                f"| {r['scenario']} | {r['band']} | {r['z0_ohm']:.1f} | "
                f"{r['max_swr']:.2f} | {r['min_return_loss_db']:.1f} | "
                f"{r['max_insertion_loss_db']:.3f} | "
                f"{r['max_dissipated_w_100w_incident']:.2f} |"
            )
    (OUT / "README.md").write_text("\n".join(report) + "\n")
    files = [
        Path(__file__),
        Path(__file__).with_name("bifilar_choke.py"),
        *sorted(DATA.glob("*.csv")),
    ]
    (OUT / "provenance.json").write_text(
        json.dumps(
            {
                "status": "uncalibrated_construction_scenarios_not_power_rating",
                "input_sha256": {
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in files
                },
                "limitations": (
                    "No fitted epsilon/Cp, crossover solver, "
                    "strand model or thermal model"
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(OUT / "README.md")


if __name__ == "__main__":
    main()
