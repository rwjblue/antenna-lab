"""Passive RF two-port building blocks and power-flow accounting.

Voltages and currents use RMS phasors.  ABCD matrices follow the convention

    [V_in]   [A B] [V_out]
    [I_in] = [C D] [I_out]

where both currents point in the direction of power flow.  This convention
makes cascades read from transmitter to antenna and keeps real power equal to
``real(V * conj(I))`` at every reference plane.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from functools import reduce
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

Matrix = NDArray[np.complex128]


@dataclass(frozen=True)
class NetworkStage:
    """A named two-port used in an auditable cascade."""

    name: str
    matrix: Matrix

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix, dtype=np.complex128)
        if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
            raise ValueError("A network stage must be a finite 2x2 matrix")
        object.__setattr__(self, "matrix", matrix)


@dataclass(frozen=True)
class PowerPlane:
    """Voltage, current, and real power at one cascade reference plane."""

    name: str
    voltage_v: complex
    current_a: complex
    power_w: float


@dataclass(frozen=True)
class PowerFlow:
    """Power accounting from source available power through a passive cascade."""

    source_available_power_w: float
    source_delivered_power_w: float
    input_impedance_ohm: complex
    source_reflection_coefficient: complex
    source_swr: float
    planes: tuple[PowerPlane, ...]

    @property
    def residual_mismatch_efficiency(self) -> float:
        return self.source_delivered_power_w / self.source_available_power_w

    @property
    def load_power_w(self) -> float:
        return self.planes[-1].power_w

    @property
    def transducer_efficiency(self) -> float:
        return self.load_power_w / self.source_available_power_w

    @property
    def network_efficiency(self) -> float:
        if self.source_delivered_power_w <= 0:
            return 0.0
        return self.load_power_w / self.source_delivered_power_w

    @property
    def stage_loss_w(self) -> tuple[float, ...]:
        powers = [plane.power_w for plane in self.planes]
        return tuple(left - right for left, right in pairwise(powers))

    def assert_passive(self, tolerance_w: float = 1e-10) -> None:
        """Reject generated power or inconsistent source accounting."""

        if self.source_available_power_w <= 0:
            raise AssertionError("Source available power must be positive")
        if self.source_delivered_power_w < -tolerance_w:
            raise AssertionError("Network accepts negative power")
        if self.source_delivered_power_w > self.source_available_power_w + tolerance_w:
            raise AssertionError("Delivered power exceeds source available power")
        for loss in self.stage_loss_w:
            if loss < -tolerance_w:
                raise AssertionError("A network stage generated real power")


@dataclass(frozen=True)
class RadiatedPowerFlow:
    """Close the cascade power budget with a radiator-efficiency partition."""

    network: PowerFlow
    radiation_efficiency: float

    def __post_init__(self) -> None:
        if not 0 <= self.radiation_efficiency <= 1:
            raise ValueError("Radiation efficiency must be between zero and one")

    @property
    def source_mismatch_loss_w(self) -> float:
        return (
            self.network.source_available_power_w
            - self.network.source_delivered_power_w
        )

    @property
    def radiator_loss_w(self) -> float:
        return self.network.load_power_w * (1.0 - self.radiation_efficiency)

    @property
    def radiated_power_w(self) -> float:
        return self.network.load_power_w * self.radiation_efficiency

    @property
    def final_efficiency(self) -> float:
        return self.radiated_power_w / self.network.source_available_power_w

    @property
    def total_loss_db(self) -> float:
        if self.final_efficiency <= 0:
            return math.inf
        return -10.0 * math.log10(self.final_efficiency)

    def assert_energy_balance(self, tolerance_w: float = 1e-9) -> None:
        self.network.assert_passive(tolerance_w)
        accounted = (
            self.source_mismatch_loss_w
            + sum(self.network.stage_loss_w)
            + self.radiator_loss_w
            + self.radiated_power_w
        )
        if not math.isclose(
            accounted,
            self.network.source_available_power_w,
            rel_tol=0.0,
            abs_tol=tolerance_w,
        ):
            raise AssertionError("End-to-end RF power budget does not close")


def identity() -> Matrix:
    """Return a through connection."""

    return np.eye(2, dtype=np.complex128)


def cascade(*matrices: Matrix) -> Matrix:
    """Cascade ABCD matrices in transmitter-to-load order."""

    return reduce(np.matmul, matrices, identity())


def series_impedance(impedance_ohm: complex) -> Matrix:
    """Return the ABCD matrix of a series impedance."""

    if impedance_ohm.real < 0:
        raise ValueError("A passive series impedance cannot have negative resistance")
    return np.asarray([[1.0, impedance_ohm], [0.0, 1.0]], dtype=np.complex128)


def shunt_admittance(admittance_s: complex) -> Matrix:
    """Return the ABCD matrix of a shunt admittance."""

    if admittance_s.real < 0:
        raise ValueError("A passive shunt admittance cannot have negative conductance")
    return np.asarray([[1.0, 0.0], [admittance_s, 1.0]], dtype=np.complex128)


def ideal_transformer(turns_ratio_primary_to_secondary: float) -> Matrix:
    """Return a lossless ideal transformer (voltage ratio Np/Ns)."""

    ratio = float(turns_ratio_primary_to_secondary)
    if ratio <= 0:
        raise ValueError("Transformer turns ratio must be positive")
    return np.asarray([[ratio, 0.0], [0.0, 1.0 / ratio]], dtype=np.complex128)


def matched_attenuator(loss_db: float, reference_ohm: float = 50.0) -> Matrix:
    """Return a reciprocal pad with the requested matched power loss."""

    if loss_db < 0 or reference_ohm <= 0:
        raise ValueError("Pad loss must be non-negative and impedance positive")
    attenuation_np = loss_db / 8.685889638
    return np.asarray(
        [
            [
                math.cosh(attenuation_np),
                reference_ohm * math.sinh(attenuation_np),
            ],
            [
                math.sinh(attenuation_np) / reference_ohm,
                math.cosh(attenuation_np),
            ],
        ],
        dtype=np.complex128,
    )


def transformer_equivalent(
    turns_ratio_primary_to_secondary: float,
    *,
    primary_series_impedance_ohm: complex = 0j,
    secondary_series_impedance_ohm: complex = 0j,
    magnetizing_admittance_s: complex = 0j,
) -> Matrix:
    """Return a passive transformer equivalent circuit.

    The circuit is primary series impedance, shunt magnetizing branch, ideal
    transformer, then secondary series impedance. It can represent winding and
    core loss without collapsing mismatch and dissipation into one fixed dB.
    """

    return cascade(
        series_impedance(primary_series_impedance_ohm),
        shunt_admittance(magnetizing_admittance_s),
        ideal_transformer(turns_ratio_primary_to_secondary),
        series_impedance(secondary_series_impedance_ohm),
    )


def transmission_line(
    characteristic_impedance_ohm: float,
    propagation_constant_per_m: complex,
    length_m: float,
) -> Matrix:
    """Return a uniform lossy line ABCD matrix."""

    if characteristic_impedance_ohm <= 0 or length_m < 0:
        raise ValueError("Line impedance must be positive and length non-negative")
    if propagation_constant_per_m.real < 0:
        raise ValueError("A passive line cannot have negative attenuation")
    value = propagation_constant_per_m * length_m
    hyperbolic_sine = cmath.sinh(value)
    return np.asarray(
        [
            [cmath.cosh(value), characteristic_impedance_ohm * hyperbolic_sine],
            [hyperbolic_sine / characteristic_impedance_ohm, cmath.cosh(value)],
        ],
        dtype=np.complex128,
    )


def input_impedance(matrix: Matrix, load_impedance_ohm: complex) -> complex:
    """Return input impedance of a two-port terminated by ``load``."""

    a, b = matrix[0]
    c, d = matrix[1]
    denominator = c * load_impedance_ohm + d
    if abs(denominator) == 0:
        return complex(math.inf)
    return complex((a * load_impedance_ohm + b) / denominator)


def power_flow(
    stages: tuple[NetworkStage, ...],
    load_impedance_ohm: complex,
    source_resistance_ohm: float = 50.0,
    source_available_power_w: float = 1.0,
) -> PowerFlow:
    """Solve a cascade and report power at every reference plane.

    The reference plane immediately before the first stage is the requested
    pre-ATU transmitter plane when tuner stages are first in the tuple.
    """

    if load_impedance_ohm.real <= 0:
        raise ValueError("Load resistance must be positive")
    if source_resistance_ohm <= 0 or source_available_power_w <= 0:
        raise ValueError("Source resistance and available power must be positive")

    total = cascade(*(stage.matrix for stage in stages))
    impedance = input_impedance(total, load_impedance_ohm)
    if not math.isfinite(impedance.real) or impedance.real <= 0:
        raise ValueError("Cascade input impedance must be finite and passive")

    open_circuit_voltage = 2.0 * math.sqrt(
        source_available_power_w * source_resistance_ohm
    )
    input_current = open_circuit_voltage / (source_resistance_ohm + impedance)
    input_voltage = impedance * input_current
    delivered = float((input_voltage * input_current.conjugate()).real)
    reflection = (impedance - source_resistance_ohm) / (
        impedance + source_resistance_ohm
    )
    magnitude = abs(reflection)
    source_swr = math.inf if magnitude >= 1 else (1 + magnitude) / (1 - magnitude)

    planes = [
        PowerPlane("source/network input", input_voltage, input_current, delivered)
    ]
    voltage = input_voltage
    current = input_current
    for stage in stages:
        voltage, current = np.linalg.solve(
            stage.matrix, np.asarray([voltage, current], dtype=np.complex128)
        )
        power = float((voltage * current.conjugate()).real)
        planes.append(PowerPlane(stage.name, complex(voltage), complex(current), power))

    flow = PowerFlow(
        source_available_power_w=source_available_power_w,
        source_delivered_power_w=delivered,
        input_impedance_ohm=impedance,
        source_reflection_coefficient=complex(reflection),
        source_swr=source_swr,
        planes=tuple(planes),
    )
    flow.assert_passive(tolerance_w=max(1e-10, source_available_power_w * 1e-9))
    return flow
