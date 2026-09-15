"""Numerical checks for the rigid doublet's NEC source and segmentation.

A free-space, perfectly conducting antenna must have unit average power gain.
This checks the solver's power balance independently of its reported wire-loss
efficiency. It does not validate the physical antenna, mast, or feedline.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from antenna_lab.nec import find_nec2c, run_cached
from antenna_lab.rigid_doublet import RigidDoublet, rigid_doublet_deck


def average_gain(pattern: Iterable[tuple[float, float, float]]) -> float:
    """Integrate absolute dBi gain over a full sphere and divide by 4 pi.

    Points are (elevation degrees, azimuth degrees, gain dBi), as returned by
    ``nec.parse``. A complete rectangular grid, including both elevation poles,
    is required. Azimuth is periodic; omit a duplicate 360-degree column.
    Trapezoidal integration in sin(elevation) uses the solid-angle measure and
    integrates an isotropic pattern exactly. Finite angular resolution and the
    solver's rounded dBi output still introduce small quadrature errors.
    """
    points = list(pattern)
    if not points or any(
        len(point) != 3 or not all(math.isfinite(value) for value in point)
        for point in points
    ):
        raise ValueError("Average gain requires finite spherical pattern points")
    grid: dict[tuple[float, float], float] = {}
    for elevation, azimuth, gain in points:
        if not -90 <= elevation <= 90:
            raise ValueError("Pattern elevation must lie between -90 and 90 degrees")
        key = (elevation, azimuth % 360)
        if key in grid:
            raise ValueError("Pattern contains duplicate angular coordinates")
        grid[key] = gain
    elevations = sorted({elevation for elevation, _ in grid})
    azimuths = sorted({azimuth for _, azimuth in grid})
    if (
        len(elevations) < 3
        or len(azimuths) < 3
        or not math.isclose(elevations[0], -90, abs_tol=1e-8)
        or not math.isclose(elevations[-1], 90, abs_tol=1e-8)
        or len(grid) != len(elevations) * len(azimuths)
    ):
        raise ValueError("Average gain requires a complete full-sphere grid")
    linear_gain = np.power(
        10.0,
        np.array(
            [
                [grid[elevation, azimuth] for azimuth in azimuths]
                for elevation in elevations
            ]
        )
        / 10.0,
    )
    polar_integral = np.trapezoid(linear_gain, x=np.sin(np.radians(elevations)), axis=0)
    periodic_azimuths = np.radians([*azimuths, azimuths[0] + 360])
    integral = np.trapezoid(
        np.append(polar_integral, polar_integral[0]), x=periodic_azimuths
    )
    return float(integral / (4 * math.pi))


def free_space_lossless_deck(deck: str) -> str:
    """Keep the geometry/source, remove resistive loads, and sample the sphere."""
    cards = deck.splitlines()
    if (
        sum(card.startswith("GN ") for card in cards) != 1
        or sum(card.startswith("RP ") for card in cards) != 1
    ):
        raise ValueError("Validation expects one ground card and one pattern card")
    return (
        "\n".join(
            "GN -1"
            if card.startswith("GN ")
            else "RP 0 37 72 1001 0 0 5 5 1000 0"
            if card.startswith("RP ")
            else card
            for card in cards
            if not card.startswith("LD ")
        )
        + "\n"
    )


def validate_geometry(
    *,
    geometry: RigidDoublet,
    bands_mhz: Mapping[str, float] | None = None,
    segment_counts: tuple[int, ...] = (91, 181, 259),
    conductivity_s_m: float = 1.4e6,
    epsilon_r: float = 13.0,
    ground_conductivity_s_m: float = 0.005,
    average_gain_tolerance_db: float = 0.1,
    nec2c: str | Path | None = None,
    cache_dir: str | Path = "build/rigid-v-validation-cache",
    output_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Check lossless power balance and real-ground mesh convergence.

    Each mesh/frequency is solved twice: a lossless full-sphere free-space
    average-gain check and the specified lossy radiator over real ground.
    Changes compare each mesh with its immediately preceding coarser mesh;
    the relative impedance change uses the finer mesh's |Z| as denominator.
    Optional output writes ``numerical_validation.json`` and ``.csv``.
    """
    bands_mhz = bands_mhz or {"40m": 7.15, "20m": 14.175, "10m": 28.5}
    if (
        not segment_counts
        or any(
            isinstance(n, bool) or not isinstance(n, int) or n < 1
            for n in segment_counts
        )
        or list(segment_counts) != sorted(set(segment_counts))
    ):
        raise ValueError("Segment counts must be positive, unique and increasing")
    if not math.isfinite(average_gain_tolerance_db) or average_gain_tolerance_db <= 0:
        raise ValueError("Average-gain tolerance must be positive and finite")
    executable = find_nec2c(nec2c)
    cache = Path(cache_dir)
    rows: list[dict[str, Any]] = []
    previous: dict[str, tuple[complex, float]] = {}
    for segments in segment_counts:
        candidate = replace(geometry, arm_segments=segments)
        for band, frequency in bands_mhz.items():
            ground_deck = rigid_doublet_deck(
                title=f"Rigid doublet validation {band} n={segments}",
                geometry=candidate,
                frequency_mhz=frequency,
                conductivity_s_m=conductivity_s_m,
                epsilon_r=epsilon_r,
                ground_conductivity_s_m=ground_conductivity_s_m,
                pattern=True,
            )
            ground, ground_path, _, _ = run_cached(ground_deck, cache, executable)
            free, free_path, _, _ = run_cached(
                free_space_lossless_deck(ground_deck), cache, executable
            )
            ag = average_gain(free.pattern)
            gain = min(
                ground.pattern,
                key=lambda point: abs(point[0] - 20) + abs(point[1] - 90),
            )[2]
            impedance = ground.impedance_ohm
            old = previous.get(band)
            error_db = 10 * math.log10(ag)
            rows.append(
                {
                    "band": band,
                    "frequency_mhz": frequency,
                    "arm_segments": segments,
                    "free_space_average_gain": ag,
                    "free_space_average_gain_error_db": error_db,
                    "average_gain_within_tolerance": abs(error_db)
                    <= average_gain_tolerance_db,
                    "average_gain_tolerance_db": average_gain_tolerance_db,
                    "ground_feedpoint_r_ohm": impedance.real,
                    "ground_feedpoint_x_ohm": impedance.imag,
                    "ground_broadside_gain_20deg_dbi": gain,
                    "relative_z_change_from_previous": None
                    if old is None
                    else abs(impedance - old[0]) / abs(impedance),
                    "broadside_gain_change_db_from_previous": None
                    if old is None
                    else gain - old[1],
                    "ground_deck_sha256": hashlib.sha256(
                        ground_path.read_bytes()
                    ).hexdigest(),
                    "free_space_deck_sha256": hashlib.sha256(
                        free_path.read_bytes()
                    ).hexdigest(),
                }
            )
            previous[band] = impedance, gain
    if output_dir is not None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / "numerical_validation.json").write_text(
            json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        with (output / "numerical_validation.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return rows
