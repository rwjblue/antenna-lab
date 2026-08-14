import math

import pytest

from antenna_lab.network import (
    NetworkStage,
    ideal_transformer,
    power_flow,
    series_impedance,
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
