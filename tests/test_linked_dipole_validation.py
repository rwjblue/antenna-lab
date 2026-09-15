import math
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from antenna_lab.linked_dipole import linked_deck, linked_network
from antenna_lab.linked_dipole_validation import (
    check_open_endpoints,
    free_space_reactive_deck,
    power_budget,
    reconciled_power_budget,
    upper_hemisphere_efficiency,
    upper_hemisphere_efficiency_from_fields,
)
from antenna_lab.nec import Wire, run_cached, wire_network_deck
from antenna_lab.rigid_doublet_validation import average_gain, free_space_lossless_deck


def _isotropic(gain_dbi: float = 0.0) -> list[tuple[float, float, float]]:
    return [
        (elevation, azimuth, gain_dbi)
        for elevation in range(0, 91, 5)
        for azimuth in range(0, 360, 5)
    ]


def test_hemisphere_integral_uses_four_pi_and_absolute_gain() -> None:
    assert upper_hemisphere_efficiency(_isotropic()) == pytest.approx(0.5)
    assert upper_hemisphere_efficiency(_isotropic(3.0)) == pytest.approx(10**0.3 / 2)
    cosine = [
        (el, az, 10 * math.log10(max(1e-100, 2 * math.sin(math.radians(el)))))
        for el, az, _ in _isotropic()
    ]
    assert upper_hemisphere_efficiency(cosine) == pytest.approx(0.5)


@pytest.mark.parametrize(
    "points",
    [
        [],
        _isotropic()[1:],
        [point for point in _isotropic() if point[0] != 0],
        [(-5, 0, 0), *_isotropic()],
        [(0, 360, 0), *_isotropic()],
        [(0, 0, math.nan)],
    ],
)
def test_hemisphere_integral_rejects_invalid_grids(points) -> None:
    with pytest.raises(ValueError):
        upper_hemisphere_efficiency(points)


_BUDGET = """
INPUT POWER = 1.0000E+00 Watts
RADIATED POWER = 8.0000E-01 Watts
STRUCTURE LOSS = 1.5000E-01 Watts
NETWORK LOSS = 5.0000E-02 Watts
EFFICIENCY = 80.00 Percent
POWER GAINS
"""


def test_printed_efficiency_is_separate_from_ground_reconciliation() -> None:
    budget = reconciled_power_budget(_BUDGET, _isotropic())
    assert budget["nec_printed_efficiency_fraction"] == 0.8
    assert budget["printed_balance_residual_w"] == pytest.approx(0.0)
    assert budget["upper_hemisphere_efficiency"] == pytest.approx(0.5)
    assert budget["ground_and_numerical_residual_w"] == pytest.approx(0.3)


def test_reconciliation_does_not_hide_nonphysical_efficiency() -> None:
    budget = reconciled_power_budget(_BUDGET, _isotropic(6.0))
    assert budget["upper_hemisphere_efficiency"] > 1
    assert budget["ground_and_numerical_residual_w"] < 0


def test_budget_and_normalization_fail_closed() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        power_budget(_BUDGET + _BUDGET)
    with pytest.raises(ValueError, match="positive"):
        power_budget(_BUDGET.replace("1.0000E+00", "0.0000E+00"))
    with pytest.raises(ValueError, match="power-gain"):
        reconciled_power_budget(_BUDGET.replace("POWER", "DIRECTIVE"), _isotropic())
    with pytest.raises(ValueError, match="explicit RP range"):
        upper_hemisphere_efficiency_from_fields(_BUDGET)


def test_nec_ground_power_and_field_normalization() -> None:
    executable = Path(__file__).resolve().parents[1] / "build/tools/nec2c"
    if not executable.is_file():
        pytest.skip("Local NEC solver is not built")
    deck = wire_network_deck(
        title="Power audit straight dipole",
        wires=(Wire(1, 121, (-5, 0, 10), (5, 0, 10), 0.0002),),
        source_tag=1,
        source_segment=61,
        frequency_mhz=14.135,
        conductivity_s_m=1e7,
        epsilon_r=13,
        ground_conductivity_s_m=0.005,
        pattern=True,
    ).replace("RP 0 19 72 1001 0 0 5 5", "RP 0 46 180 1001 0 0 2 2")
    with TemporaryDirectory(prefix="lp-", dir="/tmp") as cache:
        ground, _, output, _ = run_cached(deck, Path(cache), executable)
        text = output.read_text()
        budget = reconciled_power_budget(text, ground.pattern)
        from_fields = upper_hemisphere_efficiency_from_fields(text)
        free, _, _, _ = run_cached(
            free_space_lossless_deck(deck), Path(cache), executable
        )
        perfect = (
            "\n".join(
                "GN 1" if card.startswith("GN ") else card
                for card in deck.splitlines()
                if not card.startswith("LD ")
            )
            + "\n"
        )
        perfect_ground, _, _, _ = run_cached(perfect, Path(cache), executable)
    assert abs(10 * math.log10(average_gain(free.pattern))) < 0.02
    assert upper_hemisphere_efficiency(perfect_ground.pattern) == pytest.approx(
        1.0, abs=0.003
    )
    assert budget["input_power_w"] == pytest.approx(
        0.5 * (1.0 / ground.impedance_ohm).real, rel=0.0002
    )
    assert budget["upper_hemisphere_efficiency"] == pytest.approx(
        from_fields, abs=0.001
    )
    assert 0 < budget["upper_hemisphere_efficiency"] < 1
    assert budget["ground_and_numerical_residual_fraction"] > 0.05
    assert (
        budget["nec_printed_efficiency_fraction"]
        > budget["upper_hemisphere_efficiency"] + 0.05
    )


_LINKED_CONFIG = {
    "center_height_ft": 33,
    "metal_radius_m": 0.0002413,
    "source_length_m": 0.10,
    "open_gap_m": 0.01,
    "max_segment_length_m": 0.12,
    "contact_resistance_ohm": 0.02,
    "effective_conductivity_s_m": 1e7,
    "insulation_outer_radius_m": 0.0005207,
    "insulation_relative_permittivity": 2.3,
    "insulation_loading_scale": 1.0,
    "grounds": {"average": {"epsilon_r": 13, "conductivity_s_m": 0.005}},
}


def test_lossless_validation_keeps_reactive_loads() -> None:
    deck = "\n".join(
        [
            "GN 2 0 0 0 13 .005",
            "LD 5 0 0 0 1e7 0 0",
            "LD 2 10 0 0 0 99e-9 0",
            "LD 4 13 1 1 .02 4.0 0",
            "RP 0 19 72 1001 0 0 5 5 1000 0",
        ]
    )
    lossless = free_space_reactive_deck(deck)
    assert "LD 5" not in lossless
    assert "LD 2 10 0 0 0 99e-9 0" in lossless
    assert "LD 4 13 1 1 0 4.0 0" in lossless
    assert "GN -1" in lossless
    assert "RP 0 37 72 1001" in lossless


@pytest.mark.parametrize(
    ("band", "outer_closed", "open_ends", "closed_links"),
    [
        ("20m", False, 8, 0),
        ("30m", False, 4, 2),
        ("40m", False, 0, 4),
        ("20m", True, 4, 2),
    ],
)
def test_solver_preserves_open_gaps_and_closed_connections(
    band, outer_closed, open_ends, closed_links
) -> None:
    executable = Path(__file__).resolve().parents[1] / "build/tools/nec2c"
    if not executable.is_file():
        pytest.skip("Local NEC solver is not built")
    frequency = {"20m": 14.135, "30m": 10.12, "40m": 7.10}[band]
    deck = linked_deck(
        [16.5, 6.8, 9.8],
        5,
        band,
        frequency,
        _LINKED_CONFIG,
        pattern_step_deg=5,
        outer_closed_on_20m=outer_closed,
    )
    wires, _ = linked_network(
        [16.5, 6.8, 9.8],
        5,
        band,
        _LINKED_CONFIG,
        outer_closed_on_20m=outer_closed,
    )
    with TemporaryDirectory(prefix="lc-", dir="/tmp") as cache:
        _, _, output, _ = run_cached(deck, Path(cache), executable)
        actual = check_open_endpoints(output.read_text(), wires, band)
        # Retaining the insulation L checks loaded currents and normalization.
        free, _, _, _ = run_cached(
            free_space_reactive_deck(deck), Path(cache), executable
        )
    assert actual["passed"], actual
    assert actual["open_link_endpoint_count"] == open_ends
    assert actual["closed_link_count"] == closed_links
    assert abs(10 * math.log10(average_gain(free.pattern))) < 0.1


def test_connectivity_rejects_missing_segmentation_output() -> None:
    assert not check_open_endpoints("", (), "20m")["passed"]
