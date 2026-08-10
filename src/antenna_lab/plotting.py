"""Analytical thin-wire radiation-pattern calculation and plotting."""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

C_M_S = 299_792_458.0
EPSILON_0 = 8.854_187_8128e-12
FT_M = 0.3048


def analytical_pattern(
    frequency_hz: float,
    center_height_ft: float,
    radiator_total_ft: float = 58.0,
    apex_angle_deg: float = 120.0,
    ground_relative_permittivity: float = 13.0,
    ground_conductivity_s_m: float = 0.005,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Return normalized upper-hemisphere power in dB.

    This is the archived analytical thin-wire approximation, not NEC/MININEC.
    Equal-and-opposite balanced-line currents are omitted from the far field.
    """

    if frequency_hz <= 0 or center_height_ft <= 0 or radiator_total_ft <= 0:
        raise ValueError("Frequency, height, and radiator length must be positive")
    leg_m = radiator_total_ft * FT_M / 2.0
    droop = math.radians((180.0 - apex_angle_deg) / 2.0)
    horizontal = leg_m * math.cos(droop)
    drop = leg_m * math.sin(droop)
    apex = np.asarray([0.0, 0.0, center_height_ft * FT_M])
    west = np.asarray([-horizontal, 0.0, apex[2] - drop])
    east = np.asarray([horizontal, 0.0, apex[2] - drop])
    nodes, weights = np.polynomial.legendre.leggauss(180)
    distance = (nodes + 1.0) * leg_m / 2.0
    quadrature = weights * leg_m / 2.0
    left_direction = (apex - west) / leg_m
    right_direction = (east - apex) / leg_m
    left_positions = west + distance[:, None] * left_direction
    right_positions = apex + distance[:, None] * right_direction
    wave_number = 2.0 * math.pi * frequency_hz / C_M_S
    left_current = np.sin(wave_number * distance)
    right_current = np.sin(wave_number * (leg_m - distance))
    positions = np.vstack((left_positions, right_positions))
    currents = np.vstack(
        (
            left_current[:, None] * left_direction * quadrature[:, None],
            right_current[:, None] * right_direction * quadrature[:, None],
        )
    )

    elevations_deg = np.arange(1.0, 91.0, 1.0)
    azimuths_deg = np.arange(0.0, 360.0, 2.0)
    elevation, azimuth = np.meshgrid(
        np.radians(elevations_deg), np.radians(azimuths_deg), indexing="ij"
    )
    horizontal_component = np.cos(elevation)
    upward = np.stack(
        (
            horizontal_component * np.sin(azimuth),
            horizontal_component * np.cos(azimuth),
            np.sin(elevation),
        ),
        axis=-1,
    ).reshape(-1, 3)
    downward = upward.copy()
    downward[:, 2] *= -1.0
    direct = _far_field(positions, currents, wave_number, upward)
    incident = _far_field(positions, currents, wave_number, downward)

    flat_azimuth = azimuth.ravel()
    flat_elevation = elevation.ravel()
    te_hat = np.stack(
        (-np.cos(flat_azimuth), np.sin(flat_azimuth), np.zeros_like(flat_azimuth)),
        axis=1,
    )
    tm_incident_hat = np.cross(te_hat, downward)
    tm_reflected_hat = np.cross(te_hat, upward)
    incident_te = np.sum(incident * te_hat, axis=1)
    incident_tm = np.sum(incident * tm_incident_hat, axis=1)
    complex_er = ground_relative_permittivity - 1j * ground_conductivity_s_m / (
        2.0 * math.pi * frequency_hz * EPSILON_0
    )
    root = np.sqrt(complex_er - np.cos(flat_elevation) ** 2)
    gamma_te = (np.sin(flat_elevation) - root) / (np.sin(flat_elevation) + root)
    gamma_tm = (complex_er * np.sin(flat_elevation) - root) / (
        complex_er * np.sin(flat_elevation) + root
    )
    reflected = (
        gamma_te[:, None] * incident_te[:, None] * te_hat
        + gamma_tm[:, None] * incident_tm[:, None] * tm_reflected_hat
    )
    total = direct + reflected
    power = np.sum(np.abs(total) ** 2, axis=1).reshape(elevation.shape)
    relative_db = 10.0 * np.log10(np.maximum(power / np.max(power), 1e-12))
    return elevations_deg, azimuths_deg, relative_db


def plot_analytical_pattern(
    output_path: Path,
    frequency_hz: float,
    center_height_ft: float,
    radiator_total_ft: float = 58.0,
    apex_angle_deg: float = 120.0,
) -> None:
    """Write a deterministic sky-view PNG using the optional plots dependency."""

    try:
        os.environ.setdefault(
            "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "antenna-lab-mpl")
        )
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError("Install the 'plots' extra to generate patterns") from error

    elevations, azimuths, relative_db = analytical_pattern(
        frequency_hz,
        center_height_ft,
        radiator_total_ft,
        apex_angle_deg,
    )
    theta = np.radians(np.append(azimuths - 1.0, 360.0 - 1.0))
    radii = np.arange(0.0, 91.0, 1.0)
    data = np.clip(relative_db[::-1], -30.0, 0.0)
    fig = plt.figure(figsize=(7.0, 6.0))
    axis = fig.add_subplot(111, projection="polar")
    axis.grid(False)
    mesh = axis.pcolormesh(theta, radii, data, shading="flat", vmin=-30, vmax=0)
    axis.set_theta_zero_location("N")
    axis.set_theta_direction(-1)
    axis.set_ylim(0, 90)
    axis.set_yticks(
        (0, 30, 60, 90), labels=("zenith", "60° elev", "30° elev", "horizon")
    )
    axis.grid(True)
    axis.set_title(
        f"Analytical thin-wire pattern: {frequency_hz / 1e6:.3f} MHz\n"
        f"{radiator_total_ft:g} ft inverted V, {center_height_ft:g} ft center; "
        "wire E-W"
    )
    fig.colorbar(mesh, ax=axis, pad=0.1, label="Relative power (dB)")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, metadata={"Software": "antenna-lab"})
    plt.close(fig)


def _far_field(
    positions: NDArray[np.float64],
    currents: NDArray[np.float64],
    wave_number: float,
    directions: NDArray[np.float64],
) -> NDArray[np.complex128]:
    result = np.empty((len(directions), 3), dtype=np.complex128)
    for start in range(0, len(directions), 2500):
        chunk = directions[start : start + 2500]
        vector_potential = np.exp(1j * wave_number * (chunk @ positions.T)) @ currents
        longitudinal = np.sum(vector_potential * chunk, axis=1)
        result[start : start + 2500] = vector_potential - longitudinal[:, None] * chunk
    return result
