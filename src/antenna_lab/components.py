"""Frequency-dependent passive component and antenna-network bricks."""

from __future__ import annotations

import math

from antenna_lab.network import NetworkStage, series_impedance, shunt_admittance


def series_inductor(
    name: str, inductance_h: float, quality_factor: float, frequency_hz: float
) -> NetworkStage:
    """Return a finite-Q series inductor stage."""

    if inductance_h <= 0 or quality_factor <= 0 or frequency_hz <= 0:
        raise ValueError("Inductance, Q, and frequency must be positive")
    reactance = 2.0 * math.pi * frequency_hz * inductance_h
    return NetworkStage(
        name, series_impedance(reactance / quality_factor + 1j * reactance)
    )


def series_capacitor(
    name: str, capacitance_f: float, quality_factor: float, frequency_hz: float
) -> NetworkStage:
    """Return a finite-Q series capacitor stage."""

    if capacitance_f <= 0 or quality_factor <= 0 or frequency_hz <= 0:
        raise ValueError("Capacitance, Q, and frequency must be positive")
    reactance = 1.0 / (2.0 * math.pi * frequency_hz * capacitance_f)
    return NetworkStage(
        name, series_impedance(reactance / quality_factor - 1j * reactance)
    )


def series_resonant_trap(
    name: str,
    inductance_h: float,
    capacitance_f: float,
    inductor_q: float,
    capacitor_q: float,
    frequency_hz: float,
) -> NetworkStage:
    """Return a finite-Q series L-C branch used as a lumped loading element."""

    inductor = series_inductor(
        f"{name} inductor", inductance_h, inductor_q, frequency_hz
    )
    capacitor = series_capacitor(
        f"{name} capacitor", capacitance_f, capacitor_q, frequency_hz
    )
    return NetworkStage(name, inductor.matrix @ capacitor.matrix)


def parallel_resonant_trap_impedance(
    inductance_h: float,
    capacitance_f: float,
    inductor_q: float,
    capacitor_q: float,
    frequency_hz: float,
) -> complex:
    """Return impedance of a practical parallel L-C antenna trap."""

    inductor = series_inductor("inductor", inductance_h, inductor_q, frequency_hz)
    capacitor = series_capacitor("capacitor", capacitance_f, capacitor_q, frequency_hz)
    z_l = complex(inductor.matrix[0, 1])
    z_c = complex(capacitor.matrix[0, 1])
    return complex(1.0 / (1.0 / z_l + 1.0 / z_c))


def shunt_loss_resistance(name: str, resistance_ohm: float) -> NetworkStage:
    """Return a finite shunt loss such as a magnetizing/core-loss branch."""

    if resistance_ohm <= 0:
        raise ValueError("Resistance must be positive")
    return NetworkStage(name, shunt_admittance(1.0 / resistance_ohm))
