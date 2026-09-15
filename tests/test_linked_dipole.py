"""Protect the physical assembly assumptions that distinguish this study."""

import json
import math
from pathlib import Path

import pytest

from antenna_lab.linked_dipole import (
    geometry_dimensions,
    insulation_inductance_h_m,
    linked_deck,
    linked_network,
)
from antenna_lab.nec import FT, Wire


@pytest.fixture
def config():
    return json.loads(
        (Path(__file__).parents[1] / "configs/linked-dipole-v1.json").read_text()
    )


def _connected_components(wires: tuple[Wire, ...]) -> list[set[int]]:
    """Join electrical endpoints, without joining conductors across open gaps."""
    groups = [{wire.tag} for wire in wires]
    for first in wires:
        for second in wires:
            if first.tag == second.tag:
                continue
            if any(
                math.dist(a, b) < 1e-9
                for a in (first.start, first.end)
                for b in (second.start, second.end)
            ):
                left = next(group for group in groups if first.tag in group)
                right = next(group for group in groups if second.tag in group)
                if left is not right:
                    left.update(right)
                    groups.remove(right)
    return groups


@pytest.mark.parametrize("end_height", [5, 10, 15, 20])
def test_link_heights_follow_full_40m_leg_and_cord_reaches_ground(config, end_height):
    lengths = (16.0, 7.0, 10.0)
    dimensions = geometry_dimensions(lengths, end_height, config)
    drop = 33 - end_height
    half_source_ft = config["source_length_m"] / (2 * FT)
    run = math.sqrt(33**2 - drop**2)
    assert dimensions["link_a_height_ft"] == pytest.approx(33 - drop * 16 / 33)
    assert dimensions["link_b_height_ft"] == pytest.approx(33 - drop * 23 / 33)
    assert dimensions["link_a_height_ft"] > dimensions["link_b_height_ft"]
    assert dimensions["link_b_height_ft"] > end_height
    assert dimensions["span_ft"] == pytest.approx(2 * (half_source_ft + run))
    # The extra cord is collinear with the wire and has the same vertical slope.
    cord = dimensions["cord_length_ft"]
    stake = dimensions["stake_distance_ft"]
    assert end_height - cord * drop / 33 == pytest.approx(0)
    assert stake - half_source_ft - run == pytest.approx(cord * run / 33)
    left = (-run, 0, -drop)
    right = (run, 0, -drop)
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    angle = math.degrees(math.acos(dot / 33**2))
    assert dimensions["apex_angle_deg"] == pytest.approx(angle)


def test_flat_top_requires_elevated_supports(config):
    dimensions = geometry_dimensions((16, 7, 10), 33, config)
    assert dimensions["link_a_height_ft"] == 33
    assert dimensions["link_b_height_ft"] == 33
    assert dimensions["apex_angle_deg"] == 180
    assert dimensions["stake_distance_ft"] is None
    assert dimensions["cord_length_ft"] is None


@pytest.mark.parametrize(
    "band,components,contacts", [("20m", 5, 0), ("30m", 3, 2), ("40m", 1, 4)]
)
def test_all_sections_remain_and_closed_links_alone_connect_them(
    config, band, components, contacts
):
    wires, loads = linked_network((16, 7, 10), 5, band, config)
    by_tag = {wire.tag: wire for wire in wires}
    section_tags = {10, 11, 12, 20, 21, 22}
    assert section_tags <= by_tag.keys()
    assert len(_connected_components(wires)) == components
    assert len(loads) == contacts
    # Refining the mesh changes the number of wires, not the deployed path.
    total_conductor_m = sum(math.dist(wire.start, wire.end) for wire in wires)
    assert total_conductor_m == pytest.approx(
        2 * 33 * FT + config["source_length_m"] - (4 - contacts) * config["open_gap_m"]
    )
    for side in (10, 20):
        for before, after in ((side, side + 1), (side + 1, side + 2)):
            assert math.dist(by_tag[before].end, by_tag[after].start) == pytest.approx(
                config["open_gap_m"]
            )
        assert by_tag[side + 2].end[2] == pytest.approx(5 * FT)
    for load in loads:
        assert load.tag not in section_tags | {1}
        assert load.impedance_ohm == complex(config["contact_resistance_ohm"])
        assert load.segment == 1


@pytest.mark.parametrize("end_height", [5, 10, 15, 20, 33])
def test_band_changes_preserve_section_locations_and_33ft_feedpoint(config, end_height):
    networks = [
        linked_network((16, 7, 10), end_height, band, config)[0]
        for band in ("20m", "30m", "40m")
    ]
    reference = {wire.tag: wire for wire in networks[0]}
    for wires in networks:
        by_tag = {wire.tag: wire for wire in wires}
        for tag in reference:
            assert by_tag[tag] == reference[tag]
        source = by_tag[1]
        assert source.segments == 3
        assert source.start[2] == pytest.approx(33 * FT)
        assert source.end[2] == pytest.approx(33 * FT)
        assert source.start[0] == -source.end[0]


def test_closing_outer_20m_links_leaves_active_section_isolated(config):
    wires, loads = linked_network(
        (16, 7, 10), 5, "20m", config, outer_closed_on_20m=True
    )
    assert {load.tag for load in loads} == {14, 24}
    components = _connected_components(wires)
    fed_component = next(group for group in components if 1 in group)
    near_source_tags = {wire.tag for wire in wires if wire.tag >= 1000}
    assert fed_component == {1, 10, 20} | near_source_tags
    assert {11, 12, 14} in components
    assert {21, 22, 24} in components


def test_graded_source_mesh_preserves_path_and_avoids_abrupt_length_changes(config):
    wires, _ = linked_network((16, 7, 10), 5, "20m", config)
    by_tag = {wire.tag: wire for wire in wires}
    source = by_tag[1]
    for side, first_tag in ((10, 1000), (20, 2000)):
        near = sorted(
            [wire for wire in wires if first_tag <= wire.tag < first_tag + 1000],
            key=lambda wire: wire.tag,
        )
        assert len(near) > 1
        assert near[0].start == (source.start if side == 10 else source.end)
        assert near[-1].end == by_tag[side].start
        segment_lengths = [math.dist(wire.start, wire.end) for wire in near]
        assert segment_lengths[0] == pytest.approx(config["source_length_m"] / 3)
        segment_lengths.append(
            math.dist(by_tag[side].start, by_tag[side].end) / by_tag[side].segments
        )
        for a, b in zip(near[:-1], near[1:], strict=True):
            assert a.end == b.start
        for previous, current in zip(
            segment_lengths[:-1], segment_lengths[1:], strict=True
        ):
            assert 1 <= current / previous <= 1.4 + 1e-10


def test_metal_diameter_and_insulation_loads_are_distinct(config):
    assert config["metal_radius_m"] == pytest.approx(0.019 * 0.0254 / 2)
    assert config["insulation_outer_radius_m"] == pytest.approx(0.041 * 0.0254 / 2)
    wires, _ = linked_network((16, 7, 10), 5, "40m", config)
    assert all(wire.radius_m == config["metal_radius_m"] for wire in wires)
    deck = linked_deck((16, 7, 10), 5, "40m", 7.1, config)
    coating = [line.split() for line in deck.splitlines() if line.startswith("LD 2 ")]
    jacketed_tags = {wire.tag for wire in wires} - {1, 13, 14, 23, 24}
    assert {int(card[2]) for card in coating} == jacketed_tags
    assert all(float(card[5]) == 0 and float(card[7]) == 0 for card in coating)
    assert len([line for line in deck.splitlines() if line.startswith("LD 4 ")]) == 4
    assert "EX 0 1 2 0 1.0 0.0" in deck


def test_sheath_approximation_matches_published_equation_and_bare_limit(config):
    assert insulation_inductance_h_m(config) == pytest.approx(9.93634924365046e-8)
    assert insulation_inductance_h_m({**config, "insulation_loading_scale": 0}) == 0
    assert (
        insulation_inductance_h_m({**config, "insulation_relative_permittivity": 1})
        == 0
    )
    assert (
        insulation_inductance_h_m(
            {**config, "insulation_outer_radius_m": config["metal_radius_m"]}
        )
        == 0
    )


@pytest.mark.parametrize("gap", [0.0, 0.0005, 3.0])
def test_unresolved_or_section_spanning_gap_is_rejected(config, gap):
    with pytest.raises(ValueError):
        linked_network((16, 7, 10), 5, "20m", {**config, "open_gap_m": gap})
