import math

import numpy as np
import pytest

from antenna_lab.rigid_matching import evaluate_network, screen_matching


@pytest.mark.parametrize("topology", ["source_shunt", "load_shunt"])
def test_network_accounts_for_all_dissipative_power(topology: str) -> None:
    load, frequency, inductance, capacitance = 12 + 200j, 7.15e6, 4.0, 180.0
    ql, qc, contact, r0 = 35, 800, 0.25, 50
    result = evaluate_network(
        load,
        frequency,
        inductance,
        capacitance,
        topology=topology,
        inductor_q=ql,
        capacitor_q=qc,
        series_contact_r_ohm=contact,
    )
    omega = 2 * math.pi * frequency
    series = contact + omega * inductance * 1e-6 / ql + 1j * omega * inductance * 1e-6
    capacitor = omega * capacitance * 1e-12 / qc + 1j * omega * capacitance * 1e-12
    # Independently calculate currents from a one-volt RMS Thevenin source.
    if topology == "source_shunt":
        input_z = 1 / (1 / (load + series) + capacitor)
        input_voltage = input_z / (r0 + input_z)
        branch_current = input_voltage / (load + series)
        capacitor_power = abs(input_voltage) ** 2 * capacitor.real
        load_power = abs(branch_current) ** 2 * load.real
        series_power = abs(branch_current) ** 2 * series.real
    else:
        parallel = 1 / (1 / load + capacitor)
        input_z = series + parallel
        branch_current = 1 / (r0 + input_z)
        load_voltage = branch_current * parallel
        load_power = abs(load_voltage) ** 2 * (1 / load).real
        capacitor_power = abs(load_voltage) ** 2 * capacitor.real
        series_power = abs(branch_current) ** 2 * series.real
    accepted = load_power + capacitor_power + series_power
    assert result["input_impedance_ohm"] == pytest.approx(input_z)
    assert result["tuner_efficiency"] == pytest.approx(load_power / accepted)
    assert result["transducer_efficiency"] == pytest.approx(load_power / (1 / (4 * r0)))
    losses = sum(
        result[f"{component}_loss_fraction_of_accepted"]
        for component in ("inductor", "capacitor", "contact")
    )
    assert losses + result["tuner_efficiency"] == pytest.approx(1)
    assert result["capacitor_loss_fraction_of_accepted"] == pytest.approx(
        capacitor_power / accepted
    )


def test_lossless_exact_matches_and_bypass() -> None:
    result = screen_matching(
        np.array([5 - 400j, 200 + 300j, 50]),
        14e6,
        inductor_q=np.inf,
        capacitor_q=np.inf,
        series_contact_r_ohm=0,
        refinement_steps=(),
    )
    assert np.all(result["matched"])
    np.testing.assert_allclose(result["input_swr"], 1, atol=5e-8)
    np.testing.assert_allclose(result["tuner_efficiency"], 1)
    np.testing.assert_allclose(result["transducer_efficiency"], 1)
    assert result["topology"][-1] == "bypass"


def test_finite_q_seeds_solve_lossy_match_and_refinement_retains_good_states() -> None:
    loads = np.array([5.314 + 258.75j, 12 - 500j, 2000 + 500j, 50 + 10j])
    result = screen_matching(loads, 7.15e6, refinement_steps=())
    assert np.all(result["matched"])
    np.testing.assert_allclose(result["input_swr"][:3], 1, atol=5e-8)
    assert np.all(result["transducer_efficiency"] < 1)
    refined = screen_matching(loads, 7.15e6)
    assert np.all(refined["matched"])
    assert np.all(
        refined["transducer_efficiency"] >= result["transducer_efficiency"] - 1e-12
    )


def test_broadcasting_component_bounds_and_passivity() -> None:
    loads = np.array([1 - 3000j, 100 + 20j, 5000 + 1000j])[None, :]
    result = screen_matching(
        loads,
        np.array([7.15e6, 14.175e6, 28.5e6])[None, :],
        inductor_q=np.array([35, 70, np.inf])[:, None],
        capacitor_q=np.array([800, 2000, np.inf])[:, None],
        series_contact_r_ohm=np.array([0.25, 0.1, 0])[:, None],
        max_l_uh=2,
        max_c_pf=100,
    )
    for key, value in result.items():
        assert value.shape == (3, 3), key
    assert np.all(
        (result["inductance_uh"] >= 0) & (result["inductance_uh"] <= 2 + 1e-12)
    )
    assert np.all(
        (result["capacitance_pf"] >= 0) & (result["capacitance_pf"] <= 100 + 1e-12)
    )
    assert np.all(result["transducer_efficiency"] > 0)
    assert np.all(result["transducer_efficiency"] <= result["tuner_efficiency"] + 1e-12)
    assert np.all(result["tuner_efficiency"] <= 1)
    assert np.any(~result["matched"])


@pytest.mark.parametrize(
    "parameters",
    [
        {"inductor_q": 0},
        {"capacitor_q": -1},
        {"inductor_q": np.nan},
        {"series_contact_r_ohm": -0.1},
        {"max_l_uh": 0},
        {"target_swr": 0.9},
    ],
)
def test_invalid_component_parameters_are_rejected(parameters: dict) -> None:
    with pytest.raises(ValueError):
        screen_matching(50, 14e6, **parameters)


def test_contact_resistance_is_present_in_bypass() -> None:
    result = evaluate_network(
        50, 14e6, 0, 0, topology="bypass", series_contact_r_ohm=10
    )
    assert result["input_impedance_ohm"] == pytest.approx(60)
    assert result["tuner_efficiency"] == pytest.approx(50 / 60)
    assert result["transducer_efficiency"] == pytest.approx(4 * 50 * 50 / 110**2)
