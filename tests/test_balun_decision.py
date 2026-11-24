import numpy as np
import pytest

from antenna_lab.balun_decision import line_sparameters, metrics, twin_lead
from antenna_lab.bifilar_choke import line_swr


def test_lossless_scattering_conserves_power_and_agrees_with_existing_screen():
    f = np.linspace(7e6, 22e6, 100)
    for z0 in (25, 50, 150):
        s11, s21 = line_sparameters(f, 0.6, z0, 0.8)
        np.testing.assert_allclose(abs(s11) ** 2 + abs(s21) ** 2, 1)
        np.testing.assert_allclose(metrics(s11, s21)["swr"], line_swr(f, 0.6, z0, 0.8))


def test_distortionless_lossy_line_has_known_attenuation():
    # R/L = G/C gives gamma = R/Z0 + j*omega/v, Zc=Z0 exactly.
    f = np.array([10e6])
    z0, vf, resistance = 50, 0.8, 2.0
    inductance = z0 / (299792458 * vf)
    tangent = resistance / (2 * np.pi * f * inductance)
    s11, s21 = line_sparameters(f, 0.6, z0, vf, resistance, tangent)
    assert abs(s11[0]) < 1e-14
    assert abs(s21[0]) == pytest.approx(np.exp(-resistance * 0.6 / z0))
    assert metrics(s11, s21)["dissipated_fraction_incident"][0] > 0


def test_geometry_has_expected_dielectric_and_surface_loss_limits():
    air = twin_lead(1, 2, 1)
    dielectric = twin_lead(1, 2, 4)
    assert air[0] / dielectric[0] == pytest.approx(2)
    assert air[1] / dielectric[1] == pytest.approx(2)
    assert air[2] == dielectric[2]
    assert twin_lead(1, 1000, 1)[2] == pytest.approx(1, rel=1e-6)
    assert twin_lead(1, 1.01, 1)[2] > 7
    with pytest.raises(ValueError):
        twin_lead(1, 1, 1)
