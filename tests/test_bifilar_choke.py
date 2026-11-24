import numpy as np
import pytest

from antenna_lab.bifilar_choke import (
    CORES,
    bypass_capacitance,
    copper_loop_resistance,
    line_swr,
    material_impedance,
    part_impedance,
)


def test_lossless_line_matched_and_quarter_wave():
    f = np.array([10e6])
    assert line_swr(f, 1, 50, 0.8)[0] == pytest.approx(1)
    quarter_wave = 299792458 * 0.8 / (4 * f[0])
    assert line_swr(f, quarter_wave, 100, 0.8)[0] == pytest.approx(4)


def test_parallel_resonance_and_power_accounting():
    f = np.array([10e6])
    magnetic = np.array([1000 + 2000j])
    cap = -np.imag(1 / magnetic) / (2 * np.pi * f) * 1e12
    total = bypass_capacitance(magnetic, f, cap)
    assert total[0] == pytest.approx(5000 + 0j)
    # Core branch loss and terminal real power agree despite bypass current.
    assert (abs(10 / magnetic) ** 2 * magnetic.real)[0] == pytest.approx(
        (abs(10 / total) ** 2 * total.real)[0]
    )


def test_material_geometry_scaling_and_passivity():
    f = np.linspace(7e6, 22e6, 70)
    one = material_impedance(CORES[2], f, 1)
    two = material_impedance(CORES[3], f, 1)
    np.testing.assert_allclose(two, 2 * one)
    np.testing.assert_allclose(material_impedance(CORES[2], f, 12), 144 * one)
    for cap in (0, 1, 8, 20):
        z = bypass_capacitance(part_impedance(f, 12), f, cap)
        assert np.all(z.real > 0)
    with pytest.raises(ValueError, match="No extrapolation"):
        part_impedance(np.array([1]), 12)


def test_copper_skin_scaling():
    r = copper_loop_resistance(np.array([7e6, 28e6]), 0.6, 0.644)
    assert r[1] / r[0] == pytest.approx(2)
