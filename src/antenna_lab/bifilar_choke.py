"""Small-signal choke screening, not a calibrated winding or thermal model.

Run from the repository root with `mise run bifilar-choke`.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/reference/ferrite"
OUT = ROOT / "results/bifilar-choke-v1"
MU0 = 4e-7 * np.pi
# part, mix, OD, ID, total ferrite height, total catalog mass, stack count
CORES = [
    ("2631801802", 31, 22.1, 13.7, 6.35, 7, 1),
    ("2631801802x2", 31, 22.1, 13.7, 12.7, 14, 2),
    ("2631801202", 31, 29, 19, 13.85, 24, 1),
    ("2631801202x2", 31, 29, 19, 27.7, 48, 2),
    ("5943001001", 43, 29, 19, 7.5, 13, 1),
    ("5943002701", 43, 35.55, 23, 12.7, 33, 1),
    ("2631803802", 31, 61, 35.55, 12.7, 118, 1),
]
BANDS = {
    "40m": (7, 7.3),
    "30m": (10.1, 10.15),
    "20m": (14, 14.35),
    "17m": (18.068, 18.168),
    "15m": (21, 21.45),
}
TURNS = (10, 11, 12, 13, 14)
CAPS_PF = (1, 2, 4, 8)  # Deliberate sensitivity points, NOT measured bounds.


def numeric_csv(path: Path) -> np.ndarray:
    rows = []
    for row in csv.reader(path.read_text(encoding="latin1").splitlines()):
        try:
            values = [float(value) for value in row]
        except ValueError:
            continue
        if len(values) >= 3 and values[0] > 0:
            rows.append(values)
    result = np.array(rows)
    if len(result) < 2 or np.any(np.diff(result[:, 0]) <= 0):
        raise ValueError("Expected increasing frequency data")
    return result


def interpolate(data: np.ndarray, frequency: np.ndarray, column: int):
    if np.any(frequency < data[0, 0]) or np.any(frequency > data[-1, 0]):
        raise ValueError("No extrapolation of manufacturer data")
    return np.interp(np.log(frequency), np.log(data[:, 0]), data[:, column])


def material_impedance(core, frequency: np.ndarray, turns: int):
    _, mix, od, inner, height, *_ = core
    data = numeric_csv(DATA / f"mix{mix}.csv")
    mu_real = interpolate(data, frequency, 1)
    mu_loss = interpolate(data, frequency, 2)
    vacuum_l = MU0 * height / 1000 / (2 * np.pi) * np.log(od / inner)
    return 2 * np.pi * frequency * turns**2 * vacuum_l * (mu_loss + 1j * mu_real)


def part_impedance(frequency: np.ndarray, turns: int):
    # N=1 complex series impedance of the exact selected part. N^2 is applied
    # BEFORE the winding bypass capacitance, not to a resonant HF assembly.
    data = numeric_csv(DATA / "2631801202.csv")
    return turns**2 * (
        interpolate(data, frequency, 3) + 1j * interpolate(data, frequency, 4)
    )


def bypass_capacitance(z_magnetic, frequency, capacitance_pf):
    return 1 / (1 / z_magnetic + 1j * 2 * np.pi * frequency * capacitance_pf * 1e-12)


def line_swr(frequency, length_m, z0, vf, load=50):
    tangent = np.tan(2 * np.pi * frequency * length_m / (299792458 * vf))
    zin = z0 * (load + 1j * z0 * tangent) / (z0 + 1j * load * tangent)
    gamma = abs((zin - 50) / (zin + 50))
    return (1 + gamma) / (1 - gamma)


def copper_loop_resistance(frequency, length_per_wire_m, diameter_mm):
    """Skin-effect estimate for two straight round copper wires; no proximity."""
    rho = 1.724e-8
    skin_depth = np.sqrt(rho / (np.pi * frequency * MU0))
    radius = diameter_mm / 2000
    dc = 2 * rho * length_per_wire_m / (np.pi * radius**2)
    ac = 2 * rho * length_per_wire_m / (2 * np.pi * radius * skin_depth)
    return np.maximum(dc, ac)


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    rows = []
    for core in CORES:
        sources = ["material"] + (["part_N1"] if core[0] == "2631801202" else [])
        for source in sources:
            for turns in TURNS:
                for cap in CAPS_PF:
                    for band, (low, high) in BANDS.items():
                        f = np.linspace(low, high, 41) * 1e6
                        magnetic = (
                            part_impedance(f, turns)
                            if source == "part_N1"
                            else material_impedance(core, f, turns)
                        )
                        z = bypass_capacitance(magnetic, f, cap)
                        rows.append(
                            dict(
                                part=core[0],
                                source=source,
                                turns=turns,
                                cap_pf=cap,
                                band=band,
                                min_abs_z_ohm=float(min(abs(z))),
                                min_r_ohm=float(min(z.real)),
                                min_x_ohm=float(min(z.imag)),
                                max_x_ohm=float(max(z.imag)),
                                ferrite_mass_g=core[5],
                            )
                        )
    write_csv(OUT / "band-screen.csv", rows)
    # The combined ranges below span both magnetic estimates AND the entire
    # selected C sweep. They are scenario ranges, never confidence intervals.
    report = [
        "# Bifilar 1:1 choke screening — 17 September 2026",
        "",
        "Uncalibrated small-signal scenarios. No measured balun rating.",
        "",
        "## Selected 29 mm mix 31 core",
        "",
        "Band minima across each band, both magnetic models and 1–8 pF scenarios:",
        "",
        "| Turns | Band | Range of minimum magnitude (Ω) | Range of minimum R (Ω) |",
        "| ---: | --- | ---: | ---: |",
    ]
    for turns in (12, 13):
        for band in BANDS:
            subset = [
                r
                for r in rows
                if r["part"] == "2631801202"
                and r["turns"] == turns
                and r["band"] == band
            ]
            zs = [r["min_abs_z_ohm"] for r in subset]
            rs = [r["min_r_ohm"] for r in subset]
            report.append(
                f"| {turns} | {band} | {min(zs):.0f}–{max(zs):.0f} | "
                f"{min(rs):.0f}–{max(rs):.0f} |"
            )
    report += [
        "",
        "## Equal-winding comparison",
        "",
        "Material model, 12 turns, assumed 2 pF. This common C assumption",
        "isolates core geometry/material; actual builds will have different C.",
        "",
        "| Core | Ferrite g | 40 m min magnitude / R (Ω) "
        "| 20 m min magnitude / R (Ω) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for core in CORES:
        subset = [
            next(
                r
                for r in rows
                if r["part"] == core[0]
                and r["source"] == "material"
                and r["turns"] == 12
                and r["cap_pf"] == 2
                and r["band"] == band
            )
            for band in ("40m", "20m")
        ]
        report.append(
            f"| {core[0]} | {core[5]} | "
            + " | ".join(
                f"{r['min_abs_z_ohm']:.0f} / {r['min_r_ohm']:.0f}" for r in subset
            )
            + " |"
        )
    line_rows = []
    for awg, diameter in [(28, 0.321), (22, 0.644), (20, 0.812), (18, 1.024)]:
        for band, (low, high) in BANDS.items():
            f = np.linspace(low, high, 41) * 1e6
            resistance = float(max(copper_loop_resistance(f, 0.60, diameter)))
            line_rows.append(
                dict(
                    awg=awg,
                    band=band,
                    length_each_m=0.60,
                    loop_skin_only_ohm=resistance,
                    copper_w_at_100w_50ohm=2 * resistance,
                    copper_w_at_50w_50ohm=resistance,
                    copper_w_at_12w_50ohm=0.24 * resistance,
                )
            )
    write_csv(OUT / "copper-screen.csv", line_rows)
    line_match = []
    for z0 in (25, 30, 40, 50, 60, 70, 100, 120, 150):
        for vf in (0.65, 0.8):
            for band, (low, high) in BANDS.items():
                f = np.linspace(low, high, 41) * 1e6
                line_match.append(
                    dict(
                        z0_ohm=z0,
                        vf=vf,
                        length_m=0.60,
                        band=band,
                        max_swr=float(max(line_swr(f, 0.60, z0, vf))),
                    )
                )
    write_csv(OUT / "line-match-screen.csv", line_match)
    report += [
        "",
        "See [method and interpretation](../../docs/case-studies/bifilar-choke.md)",
        "for selection, assumptions, provenance and bench acceptance.",
        "",
        "![Turn/capacitance sensitivity](turns.png)",
        "",
    ]
    (OUT / "README.md").write_text("\n".join(report))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f = np.linspace(6, 23, 500) * 1e6
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharex=True)
    for turns, color in [(10, "#8c8c8c"), (12, "#087f8c"), (13, "#c65527")]:
        curves = [
            bypass_capacitance(model(f, turns), f, cap)
            for model in [
                part_impedance,
                lambda f, n: material_impedance(CORES[2], f, n),
            ]
            for cap in CAPS_PF
        ]
        for ax, transform in zip(axes, [np.abs, np.real], strict=True):
            values = np.array([transform(z) / 1000 for z in curves])
            ax.fill_between(
                f / 1e6, values.min(axis=0), values.max(axis=0), alpha=0.15, color=color
            )
            nominal = bypass_capacitance(part_impedance(f, turns), f, 2)
            ax.plot(
                f / 1e6, transform(nominal) / 1000, color=color, label=f"{turns} turns"
            )
    for ax, label, target in zip(axes, ["|Zcm| (kΩ)", "Rcm (kΩ)"], [2, 1], strict=True):
        for low, high in BANDS.values():
            ax.axvspan(low, high, color="#d6deed", alpha=0.5)
        ax.axhline(target, color="#555", linestyle=":", label="Screening target")
        ax.set(xlabel="MHz", ylabel=label, ylim=(0, 9), xlim=(6, 23))
        ax.grid(alpha=0.2)
    axes[0].legend(fontsize=8)
    fig.suptitle("29 mm mix 31: capacitance uncertainty exceeds the 12→13 turn change")
    fig.text(
        0.5,
        0.01,
        "Lines: part N=1 model + 2 pF. Shading: two magnetic models, "
        "1–8 pF scenarios. NOT measured performance.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(OUT / "turns.png", dpi=170)
    plt.close(fig)
    files = [*sorted(DATA.glob("*.csv")), Path(__file__)]
    (OUT / "provenance.json").write_text(
        json.dumps(
            {
                "status": "uncalibrated_sensitivity_not_power_rating",
                "input_sha256": {
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in files
                },
                "band_samples": 41,
                "turns": TURNS,
                "capacitance_pf": CAPS_PF,
                "rows": len(rows),
            },
            indent=2,
        )
        + "\n"
    )
    print(OUT / "README.md")


if __name__ == "__main__":
    main()
