import math

from antenna_lab.nec import InvertedV, direct_wire_deck, doublet_deck, parse


def test_pulaski_geometry() -> None:
    geometry = InvertedV(30.0, end_height_ft=10.0)
    horizontal, end_height = geometry.endpoints(58.0)
    assert math.isclose(horizontal * 2.0, 42.0, rel_tol=1e-12)
    assert end_height == 10.0
    assert math.isclose(geometry.included_angle_deg(58.0), 92.79436205459275)


def test_deck_has_real_nec_cards() -> None:
    deck = doublet_deck(
        title="test",
        total_length_ft=58.0,
        geometry=InvertedV(30.0, end_height_ft=10.0),
        frequency_mhz=14.05,
        radius_m=0.0002415,
        conductivity_s_m=15_000_000.0,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
    )
    assert "GW 2 1" in deck
    assert "EX 0 2 1 0 1.0 0.0" in deck
    assert "GN 2" in deck
    assert deck.endswith("EN\n")


def test_parser_reads_impedance_efficiency_and_pattern() -> None:
    text = """
FREQUENCY : 1.4050E+01 MHz
ANTENNA INPUT PARAMETERS
 2 63 1.0 0.0 0.01 -0.02 20.0 40.0 0.01 -0.02 0.005
POWER BUDGET
EFFICIENCY = 93.25 Percent
RADIATION PATTERNS
 0.00 0.00 1.0 -20.0 2.0 0.0 0.0 LINEAR 1 0 0 0
 90.00 5.00 1.0 -20.0 3.0 0.0 0.0 LINEAR 1 0 0 0
"""
    result = parse(text)
    assert result.impedance_ohm == 20 + 40j
    assert result.efficiency == 0.9325
    assert result.pattern == ((90.0, 0.0, 2.0), (0.0, 5.0, 3.0))


def _wire_length_m(deck: str, tag: int) -> float:
    card = next(line for line in deck.splitlines() if line.startswith(f"GW {tag} "))
    fields = card.split()
    start = tuple(float(value) for value in fields[3:6])
    end = tuple(float(value) for value in fields[6:9])
    return math.dist(start, end)


def test_direct_wire_counterpoise_azimuth_preserves_wire_length() -> None:
    common = dict(
        title="direct",
        radiator_ft=35.0,
        counterpoise_ft=17.0,
        feed_height_ft=0.5,
        support_height_ft=20.0,
        counterpoise_height_ft=0.1,
        frequency_mhz=14.05,
        radius_m=0.0002415,
        conductivity_s_m=15_000_000.0,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
    )
    side = direct_wire_deck(counterpoise_azimuth_deg=90.0, **common)
    collinear = direct_wire_deck(counterpoise_azimuth_deg=180.0, **common)
    assert side != collinear
    assert math.isclose(_wire_length_m(side, 1), 17.0 * 0.3048, abs_tol=1e-9)
    assert math.isclose(
        _wire_length_m(collinear, 1), 17.0 * 0.3048, abs_tol=1e-9
    )


def test_direct_wire_rejects_impossible_counterpoise_height() -> None:
    common = dict(
        title="direct",
        radiator_ft=35.0,
        counterpoise_ft=2.0,
        feed_height_ft=0.5,
        support_height_ft=20.0,
        counterpoise_height_ft=2.5,
        counterpoise_azimuth_deg=90.0,
        frequency_mhz=14.05,
        radius_m=0.0002415,
        conductivity_s_m=15_000_000.0,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
    )
    try:
        direct_wire_deck(**common)
    except ValueError as error:
        assert str(error) == "Counterpoise cannot reach requested endpoint height"
    else:
        raise AssertionError("Expected invalid counterpoise geometry to fail")
