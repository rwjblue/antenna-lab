"""Lossy transmission-line transformations and derived quantities."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

C_FT_S = 299_792_458.0 / 0.3048


@dataclass(frozen=True)
class LineParameters:
    """A uniform balanced-line scenario."""

    characteristic_impedance_ohm: float
    velocity_factor: float
    loss_db_per_100ft_at_10mhz: float

    def __post_init__(self) -> None:
        if self.characteristic_impedance_ohm <= 0:
            raise ValueError("Characteristic impedance must be positive")
        if not 0 < self.velocity_factor <= 1:
            raise ValueError("Velocity factor must be in (0, 1]")
        if self.loss_db_per_100ft_at_10mhz < 0:
            raise ValueError("Loss cannot be negative")


def abcd(
    frequency_hz: float,
    length_ft: ArrayLike,
    line: LineParameters,
) -> tuple[NDArray[np.complex128], ...]:
    """Return the lossy-line ABCD matrix entries."""

    if frequency_hz <= 0:
        raise ValueError("Frequency must be positive")
    lengths = np.asarray(length_ft, dtype=float)
    loss_db_per_ft = (
        line.loss_db_per_100ft_at_10mhz / 100.0 * math.sqrt(frequency_hz / 10_000_000.0)
    )
    alpha_np_per_ft = loss_db_per_ft / 8.685889638
    beta_rad_per_ft = 2.0 * math.pi * frequency_hz / (C_FT_S * line.velocity_factor)
    propagation = (alpha_np_per_ft + 1j * beta_rad_per_ft) * lengths
    a = np.cosh(propagation)
    sinh = np.sinh(propagation)
    b = line.characteristic_impedance_ohm * sinh
    c = sinh / line.characteristic_impedance_ohm
    return a, b, c, a


def input_impedance(
    load_impedance_ohm: ArrayLike,
    frequency_hz: float,
    length_ft: ArrayLike,
    line: LineParameters,
) -> NDArray[np.complex128]:
    """Transform a load impedance toward the transmitter."""

    load = np.asarray(load_impedance_ohm, dtype=np.complex128)
    a, b, c, d = abcd(frequency_hz, length_ft, line)
    return np.asarray((a * load + b) / (c * load + d), dtype=np.complex128)


def load_impedance(
    input_impedance_ohm: complex,
    frequency_hz: float,
    length_ft: float,
    line: LineParameters,
) -> complex:
    """De-embed an input impedance to the load end of the line."""

    a, b, c, d = abcd(frequency_hz, length_ft, line)
    value = (b - d * input_impedance_ohm) / (c * input_impedance_ohm - a)
    return complex(value)


def line_efficiency(
    load_impedance_ohm: ArrayLike,
    frequency_hz: float,
    length_ft: ArrayLike,
    line: LineParameters,
) -> NDArray[np.float64]:
    """Return real power at the load divided by power entering the line.

    This excludes tuner, choke, common-mode, radiator, ground, and environmental
    losses. It must not be labeled total antenna efficiency.
    """

    load = np.asarray(load_impedance_ohm, dtype=np.complex128)
    a, b, c, d = abcd(frequency_hz, length_ft, line)
    input_current = c * load + d
    input_voltage = a * load + b
    input_power = np.real(input_voltage * np.conj(input_current))
    return np.asarray(np.real(load) / input_power, dtype=float)


def swr(impedance_ohm: ArrayLike, reference_ohm: float = 50.0) -> NDArray[np.float64]:
    """Calculate SWR at the stated reference impedance."""

    if reference_ohm <= 0:
        raise ValueError("Reference impedance must be positive")
    impedance = np.asarray(impedance_ohm, dtype=np.complex128)
    gamma = np.abs((impedance - reference_ohm) / (impedance + reference_ohm))
    return np.asarray(
        np.where(gamma < 1.0, (1.0 + gamma) / (1.0 - gamma), np.inf),
        dtype=float,
    )
