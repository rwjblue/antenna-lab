import math

import pytest

from antenna_lab.transmission_line import (
    C_FT_S,
    LineParameters,
    input_impedance,
    line_efficiency,
    load_impedance,
    swr,
)


def test_lossless_quarter_wave_transform() -> None:
    frequency_hz = 10_000_000.0
    line = LineParameters(450.0, 0.95, 0.0)
    quarter_wave_ft = C_FT_S * line.velocity_factor / (4.0 * frequency_hz)

    transformed = complex(input_impedance(100.0, frequency_hz, quarter_wave_ft, line))

    assert transformed.real == pytest.approx(450.0**2 / 100.0, rel=1e-12)
    assert transformed.imag == pytest.approx(0.0, abs=1e-10)


@pytest.mark.parametrize(
    ("frequency_hz", "load"),
    [(7_050_000.0, 35.5 - 211j), (18_080_000.0, 2.3 - 35.1j), (28_050_000.0, 49 + 12j)],
)
def test_deembed_reembed_round_trip(frequency_hz: float, load: complex) -> None:
    line = LineParameters(480.0, 0.97, 0.05)
    input_value = complex(input_impedance(load, frequency_hz, 28.0, line))

    reconstructed_load = load_impedance(input_value, frequency_hz, 28.0, line)

    assert reconstructed_load == pytest.approx(load, rel=1e-11, abs=1e-9)


def test_passive_lossy_line_efficiency_bounds() -> None:
    line = LineParameters(480.0, 0.97, 0.05)
    efficiency = float(line_efficiency(25 - 300j, 18_080_000.0, 28.0, line))

    assert 0.0 < efficiency < 1.0


@pytest.mark.parametrize(
    ("impedance", "expected"),
    [(50 + 0j, 1.0), (100 + 0j, 2.0), (25 + 0j, 2.0)],
)
def test_swr_known_values(impedance: complex, expected: float) -> None:
    assert float(swr(impedance)) == pytest.approx(expected)


def test_swr_is_infinite_for_non_passive_reflection() -> None:
    assert math.isinf(float(swr(-10 + 0j)))
