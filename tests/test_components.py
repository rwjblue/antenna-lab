import math

import pytest

from antenna_lab.components import (
    parallel_resonant_trap_impedance,
    series_inductor,
)


def test_inductor_q_sets_series_resistance() -> None:
    stage = series_inductor("loading coil", 10e-6, 100.0, 7_050_000.0)
    impedance = complex(stage.matrix[0, 1])

    assert impedance.real == pytest.approx(impedance.imag / 100.0)


def test_parallel_trap_is_resistive_at_ideal_resonance() -> None:
    inductance_h = 3.3e-6
    capacitance_f = 17.4e-12
    frequency_hz = 1.0 / (2.0 * math.pi * math.sqrt(inductance_h * capacitance_f))
    impedance = parallel_resonant_trap_impedance(
        inductance_h,
        capacitance_f,
        inductor_q=235.0,
        capacitor_q=3000.0,
        frequency_hz=frequency_hz,
    )

    assert impedance.real > 0
    assert abs(impedance.imag) < impedance.real * 0.01
