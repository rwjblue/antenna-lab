import math

from antenna_lab.nec import (
    InvertedV,
    SeriesLoad,
    Wire,
    asymmetric_inverted_v_deck,
    direct_wire_deck,
    doublet_deck,
    fan_dipole_deck,
    loaded_inverted_v_deck,
    parse,
    radial_vertical_deck,
    run_cached,
    wire_network_deck,
)


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


def test_generic_wire_deck_emits_lumped_series_load() -> None:
    deck = wire_network_deck(
        title="loaded test",
        wires=(Wire(1, 3, (0, 0, 1), (1, 0, 1), 0.001),),
        source_tag=1,
        source_segment=1,
        frequency_mhz=14.05,
        conductivity_s_m=58e6,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
        loads=(SeriesLoad(1, 2, 1.5 + 20j),),
    )

    assert "LD 4 1 2 2 1.500000000e+00 2.000000000e+01 0" in deck
    assert "EX 0 1 1 0 1.0 0.0" in deck


def test_generic_wire_deck_supports_per_wire_conductivity() -> None:
    deck = wire_network_deck(
        title="carbon parasitic",
        wires=(
            Wire(1, 3, (0, 0, 1), (1, 0, 1), 0.001),
            Wire(2, 3, (0, 0.1, 0.1), (0, 0.1, 2), 0.006),
        ),
        source_tag=1,
        source_segment=1,
        frequency_mhz=14.05,
        conductivity_s_m=58e6,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
        wire_conductivity_s_m={2: 5e4},
    )

    assert "LD 5 0 0 0 5.800000000e+07 0 0" in deck
    assert "LD 5 2 0 0 5.000000000e+04 0 0" in deck


def test_asymmetric_deck_moves_feedpoint_without_changing_total_wire() -> None:
    deck = asymmetric_inverted_v_deck(
        title="ocfd",
        total_length_ft=66.0,
        feed_fraction=0.2,
        center_height_ft=30.0,
        apex_angle_deg=120.0,
        frequency_mhz=7.05,
        radius_m=0.0005,
        conductivity_s_m=58e6,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
    )

    assert math.isclose(
        _wire_length_m(deck, 1) + _wire_length_m(deck, 3),
        66.0 * 0.3048,
        abs_tol=1e-8,
    )


def test_fan_deck_has_one_feed_and_two_arms_per_band() -> None:
    deck = fan_dipole_deck(
        title="fan",
        total_lengths_ft=(66.0, 33.0, 22.0),
        azimuths_deg=(-10.0, 0.0, 10.0),
        center_height_ft=30.0,
        apex_angle_deg=120.0,
        frequency_mhz=14.05,
        radius_m=0.0005,
        conductivity_s_m=58e6,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
    )

    assert sum(line.startswith("GW ") for line in deck.splitlines()) == 7
    assert sum(line.startswith("EX ") for line in deck.splitlines()) == 1


def test_radial_vertical_has_explicit_counterpoise_wires() -> None:
    deck = radial_vertical_deck(
        title="rybakov",
        radiator_ft=25.0,
        radial_ft=16.0,
        radial_count=4,
        feed_height_ft=1.0,
        radial_end_height_ft=0.1,
        frequency_mhz=14.05,
        radius_m=0.0005,
        conductivity_s_m=58e6,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
    )

    assert sum(line.startswith("GW ") for line in deck.splitlines()) == 6
    for tag in range(3, 7):
        assert math.isclose(
            _wire_length_m(deck, tag), 16.0 * 0.3048, abs_tol=1e-8
        )


def test_loaded_dipole_places_equal_impedances_in_both_arms() -> None:
    deck = loaded_inverted_v_deck(
        title="trap dipole",
        total_length_ft=55.0,
        loads_from_center_ft=((10.0, 1.9 + 120j),),
        geometry=InvertedV(30.0, apex_angle_deg=120.0),
        frequency_mhz=14.05,
        radius_m=0.0005,
        conductivity_s_m=58e6,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
    )

    loads = [line for line in deck.splitlines() if line.startswith("LD 4")]
    assert len(loads) == 2
    assert "1.900000000e+00 1.200000000e+02" in loads[0]
    assert "1.900000000e+00 1.200000000e+02" in loads[1]


def test_nec_cache_keys_only_solver_and_deck(tmp_path, monkeypatch) -> None:
    import antenna_lab.nec as nec

    executable = tmp_path / "nec2c"
    executable.write_bytes(b"solver-v1")
    calls = []
    sample = """
FREQUENCY : 1.4050E+01 MHz
 2 63 1.0 0.0 0.01 -0.02 20.0 40.0 0.01 -0.02 0.005
EFFICIENCY = 93.25 Percent
"""

    def fake_run(deck, work_dir, stem, nec2c=None):
        calls.append(deck)
        work_dir.mkdir(parents=True, exist_ok=True)
        deck_path = work_dir / f"{stem}.nec"
        output_path = work_dir / f"{stem}.out"
        deck_path.write_text(deck)
        output_path.write_text(sample)
        return parse(sample), deck_path, output_path

    monkeypatch.setattr(nec, "find_nec2c", lambda explicit=None: executable)
    monkeypatch.setattr(nec, "run", fake_run)
    first = run_cached("CM same deck\n", tmp_path / "cache", executable)
    second = run_cached("CM same deck\n", tmp_path / "cache", executable)

    assert not first[3]
    assert second[3]
    assert len(calls) == 1
