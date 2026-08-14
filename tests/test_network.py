import math

import pytest

from antenna_lab.network import (
    NetworkStage,
    RadiatedPowerFlow,
    ideal_transformer,
    matched_attenuator,
    power_flow,
    series_impedance,
    transformer_equivalent,
)


def test_matched_through_delivers_all_available_power() -> None:
    flow = power_flow((), 50 + 0j)

    assert flow.source_swr == pytest.approx(1.0)
    assert flow.residual_mismatch_efficiency == pytest.approx(1.0)
    assert flow.transducer_efficiency == pytest.approx(1.0)


def test_residual_mismatch_equals_one_minus_gamma_squared() -> None:
    flow = power_flow((), 100 + 50j)

    expected = 1.0 - abs((100 + 50j - 50) / (100 + 50j + 50)) ** 2
    assert flow.residual_mismatch_efficiency == pytest.approx(expected)
    assert flow.network_efficiency == pytest.approx(1.0)


def test_ideal_transformer_matches_impedance_without_loss() -> None:
    stage = NetworkStage("4:1 impedance transformer", ideal_transformer(2.0))
    flow = power_flow((stage,), 12.5 + 0j)

    assert flow.input_impedance_ohm == pytest.approx(50 + 0j)
    assert flow.transducer_efficiency == pytest.approx(1.0)
    assert flow.stage_loss_w == pytest.approx((0.0,))


def test_series_resistor_has_analytical_loss_and_is_passive() -> None:
    stage = NetworkStage("resistor", series_impedance(50 + 0j))
    flow = power_flow((stage,), 50 + 0j)

    assert flow.source_swr == pytest.approx(2.0)
    assert flow.source_delivered_power_w == pytest.approx(8.0 / 9.0)
    assert flow.load_power_w == pytest.approx(4.0 / 9.0)
    assert flow.stage_loss_w == pytest.approx((4.0 / 9.0,))
    assert math.isclose(
        flow.source_available_power_w,
        flow.source_available_power_w
        - flow.source_delivered_power_w
        + sum(flow.stage_loss_w)
        + flow.load_power_w,
    )


def test_active_series_element_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative resistance"):
        series_impedance(-1 + 1j)


@pytest.mark.parametrize(("swr", "expected"), ((1.5, 0.96), (2.5, 0.8163265306122449)))
def test_mismatch_efficiency_at_study_thresholds(swr: float, expected: float) -> None:
    flow = power_flow((), 50.0 * swr + 0j)

    assert flow.residual_mismatch_efficiency == pytest.approx(expected)


def test_matched_attenuator_has_requested_power_loss() -> None:
    flow = power_flow(
        (NetworkStage("0.5 dB transformer envelope", matched_attenuator(0.5)),),
        50 + 0j,
    )

    assert flow.source_swr == pytest.approx(1.0)
    assert flow.transducer_efficiency == pytest.approx(10 ** (-0.5 / 10.0))


def test_transformer_primary_resistance_matches_analytical_efficiency() -> None:
    stage = NetworkStage(
        "lossy 4:1",
        transformer_equivalent(2.0, primary_series_impedance_ohm=5 + 0j),
    )
    flow = power_flow((stage,), 12.5 + 0j)

    assert flow.input_impedance_ohm == pytest.approx(55 + 0j)
    assert flow.network_efficiency == pytest.approx(50.0 / 55.0)


def test_radiated_power_budget_closes() -> None:
    flow = power_flow((NetworkStage("series loss", series_impedance(2 + 0j)),), 48 + 0j)
    radiated = RadiatedPowerFlow(flow, radiation_efficiency=0.8)

    radiated.assert_energy_balance()
    assert radiated.final_efficiency == pytest.approx(0.8 * flow.load_power_w)
    assert radiated.total_loss_db == pytest.approx(
        -10.0 * math.log10(radiated.final_efficiency)
    )
