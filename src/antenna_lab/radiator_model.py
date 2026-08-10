"""Explicitly provisional radiator-length surrogate models."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import PchipInterpolator
from scipy.special import sici

C_M_S = 299_792_458.0
C_FT_S = C_M_S / 0.3048
ETA0 = 376.730313668
EULER_GAMMA = 0.5772156649015329


def thin_dipole_impedance(
    total_length_ft: float, frequency_hz: float, radius_m: float
) -> complex:
    """Induced-EMF thin-dipole approximation used only for relative motion."""

    total_length_m = total_length_ft * 0.3048
    k = 2.0 * math.pi * frequency_hz / C_M_S
    x = k * total_length_m
    si_x, ci_x = sici(x)
    si_2x, ci_2x = sici(2.0 * x)
    _, ci_small = sici(max(2.0 * k * radius_m**2 / total_length_m, 1e-15))
    denominator = 2.0 * math.pi * math.sin(x / 2.0) ** 2
    if abs(denominator) < 1e-12:
        denominator = math.copysign(1e-12, denominator or 1.0)
    resistance = (
        EULER_GAMMA
        + math.log(x)
        - ci_x
        + 0.5 * math.sin(x) * (si_2x - 2.0 * si_x)
        + 0.5 * math.cos(x) * (ci_2x - 2.0 * ci_x + EULER_GAMMA + math.log(x / 2.0))
    )
    reactance = (
        si_x
        + 0.5 * math.cos(x) * (-si_2x + 2.0 * si_x)
        + 0.5 * math.sin(x) * (ci_2x - 2.0 * ci_x + ci_small)
    )
    impedance = ETA0 * complex(resistance, reactance) / denominator
    return impedance if abs(impedance) <= 1e7 else impedance / abs(impedance) * 1e7


def candidate_loads(
    baseline_loads: NDArray[np.complex128],
    frequencies_hz: NDArray[np.float64],
    characteristic_impedance_ohm: float,
    baseline_radiator_ft: float,
    candidate_radiator_ft: float,
    model_name: str,
    conductor_radius_m: float,
) -> NDArray[np.complex128]:
    """Move baseline loads with a passive, exactly anchored surrogate."""

    z0 = characteristic_impedance_ohm
    if model_name.startswith("mobius_"):
        scale = float(model_name.split("_", 1)[1])
        result = []
        for frequency, baseline_load in zip(
            frequencies_hz, baseline_loads, strict=True
        ):
            theory_baseline = thin_dipole_impedance(
                baseline_radiator_ft, frequency, conductor_radius_m
            )
            theory_candidate = thin_dipole_impedance(
                candidate_radiator_ft, frequency, conductor_radius_m
            )
            real_gamma = _z_to_gamma(baseline_load, z0)
            start = _z_to_gamma(theory_baseline, z0)
            finish = _z_to_gamma(theory_candidate, z0)
            displacement = (finish - start) / (1.0 - np.conj(start) * finish)
            radius = min(abs(displacement), 0.999999)
            if radius:
                scaled_radius = math.tanh(scale * math.atanh(radius))
                displacement = displacement / abs(displacement) * scaled_radius
            gamma = (real_gamma + displacement) / (
                1.0 + np.conj(real_gamma) * displacement
            )
            result.append(_gamma_to_z(gamma, z0))
        return np.asarray(result, dtype=np.complex128)

    electrical_baseline = baseline_radiator_ft * frequencies_hz / C_FT_S
    electrical_candidate = candidate_radiator_ft * frequencies_hz / C_FT_S
    gamma_baseline = np.asarray(
        [_z_to_gamma(load, z0) for load in baseline_loads], dtype=np.complex128
    )
    if model_name == "pchip":
        real = PchipInterpolator(
            electrical_baseline, gamma_baseline.real, extrapolate=True
        )(electrical_candidate)
        imag = PchipInterpolator(
            electrical_baseline, gamma_baseline.imag, extrapolate=True
        )(electrical_candidate)
        gamma_candidate = real + 1j * imag
    elif model_name == "linear_global":
        gamma_candidate = _linear_complex_extrapolation(
            electrical_baseline, gamma_baseline, electrical_candidate
        )
    else:
        raise ValueError(f"Unknown surrogate model: {model_name}")
    return np.asarray(
        [_gamma_to_z(value, z0) for value in gamma_candidate],
        dtype=np.complex128,
    )


def _z_to_gamma(impedance: complex, reference: float) -> complex:
    return complex((impedance - reference) / (impedance + reference))


def _gamma_to_z(gamma: complex, reference: float) -> complex:
    magnitude = abs(gamma)
    if magnitude >= 0.999999:
        gamma = gamma / magnitude * 0.999999
    result = reference * (1.0 + gamma) / (1.0 - gamma)
    return complex(max(result.real, 1e-9), result.imag)


def _linear_complex_extrapolation(
    x: NDArray[np.float64],
    y: NDArray[np.complex128],
    targets: NDArray[np.float64],
) -> NDArray[np.complex128]:
    result = np.empty_like(targets, dtype=np.complex128)
    for index, target in enumerate(targets):
        if target < x[0]:
            result[index] = y[0] + (target - x[0]) / (x[1] - x[0]) * (y[1] - y[0])
        elif target > x[-1]:
            result[index] = y[-1] + (target - x[-1]) / (x[-1] - x[-2]) * (y[-1] - y[-2])
        else:
            result[index] = complex(
                np.interp(target, x, y.real), np.interp(target, x, y.imag)
            )
    return result
