import math

import pytest

from antenna_lab.nec import FT
from antenna_lab.rigid_doublet import (
    FloatingMast,
    RigidDoublet,
    rigid_doublet_deck,
    rigid_doublet_wires,
)


@pytest.mark.parametrize("elevation", [-60.0, -30.0, 0.0, 30.0, 60.0])
def test_rigid_arms_preserve_length_and_symmetry(elevation: float) -> None:
    geometry = RigidDoublet(arm_elevation_deg=elevation)
    left, bridge, right = rigid_doublet_wires(geometry)

    assert math.dist(left.start, left.end) == pytest.approx(17.0 * FT)
    assert math.dist(right.start, right.end) == pytest.approx(17.0 * FT)
    assert math.dist(bridge.start, bridge.end) == pytest.approx(geometry.feed_gap_m)
    assert bridge.segments == 3
    assert left.end == bridge.start
    assert right.start == bridge.end
    assert left.start[0] == -right.end[0]
    assert left.start[1:] == right.end[1:]
    assert right.end[2] / FT == pytest.approx(
        30.0 + 17.0 * math.sin(math.radians(elevation))
    )
    assert (right.end[0] - left.start[0]) / FT == pytest.approx(geometry.span_ft)


def test_arm_elevation_sign_controls_v_direction() -> None:
    up = RigidDoublet(arm_elevation_deg=30.0)
    down = RigidDoublet(arm_elevation_deg=-30.0)
    flat = RigidDoublet(arm_elevation_deg=0.0)

    assert up.tip_height_ft == 38.5
    assert down.tip_height_ft == 21.5
    assert flat.tip_height_ft == 30.0
    assert up.span_ft == down.span_ft


@pytest.mark.parametrize(
    "override",
    [
        {"arm_length_ft": 0.0},
        {"arm_length_ft": math.inf},
        {"feed_height_ft": -1.0},
        {"arm_elevation_deg": 90.0},
        {"arm_elevation_deg": -90.0},
        {"arm_elevation_deg": math.nan},
        {"feed_height_ft": 8.0, "arm_elevation_deg": -30.0},
        {"radius_m": 0.0},
        {"radius_m": 0.01},
        {"feed_gap_m": -0.02},
        {"arm_segments": 0},
        {"arm_segments": 2.5},
        {"arm_segments": True},
    ],
)
def test_invalid_rigid_geometry_is_rejected(override: dict) -> None:
    with pytest.raises(ValueError):
        RigidDoublet(**override)


def test_floating_mast_has_separate_tag_and_no_junction() -> None:
    geometry = RigidDoublet()
    mast = FloatingMast(height_ft=30.0, bottom_height_ft=0.25, offset_m=0.20)
    *radiator, mast_wire = rigid_doublet_wires(geometry, mast)

    assert mast_wire.tag == 4
    assert math.dist(mast_wire.start, mast_wire.end) == pytest.approx(30.0 * FT)
    assert mast_wire.start == pytest.approx((0.0, 0.20, 0.25 * FT))
    assert mast_wire.end == pytest.approx((0.0, 0.20, 30.25 * FT))
    assert all(mast_wire.start != wire.start for wire in radiator)
    assert all(mast_wire.end != wire.end for wire in radiator)


def test_mast_may_be_centered_below_feedpoint_with_clearance() -> None:
    wires = rigid_doublet_wires(RigidDoublet(), FloatingMast(offset_m=0.0))
    assert len(wires) == 4


def test_mast_can_break_left_right_symmetry() -> None:
    mast = FloatingMast(x_offset_m=0.2, offset_m=0.3)
    wire = rigid_doublet_wires(RigidDoublet(), mast)[3]
    assert wire.start[:2] == (0.2, 0.3)
    assert wire.end[:2] == (0.2, 0.3)


@pytest.mark.parametrize("offset", [0.0, 0.01, -0.01])
def test_floating_mast_cannot_touch_source_bridge(offset: float) -> None:
    mast = FloatingMast(height_ft=30.0, offset_m=offset)
    with pytest.raises(ValueError, match="must not touch or intersect"):
        rigid_doublet_wires(RigidDoublet(), mast)


def test_mast_cannot_touch_downward_arm_near_feed() -> None:
    # The mast is below the source bridge; the downward arm passes its tip.
    mast = FloatingMast(
        bottom_height_ft=0.5,
        height_ft=29.38,
        offset_m=0.0,
        radius_m=0.015,
        x_offset_m=0.05,
    )
    with pytest.raises(ValueError, match="must not touch or intersect"):
        rigid_doublet_wires(RigidDoublet(arm_elevation_deg=-60.0), mast)


@pytest.mark.parametrize(
    "override",
    [
        {"height_ft": 0.0},
        {"bottom_height_ft": 0.0},
        {"offset_m": math.nan},
        {"x_offset_m": math.inf},
        {"radius_m": -1.0},
        {"segments": -3},
        {"conductivity_s_m": math.inf},
        {"conductivity_s_m": 0.0},
    ],
)
def test_invalid_mast_geometry_is_rejected(override: dict) -> None:
    with pytest.raises(ValueError):
        FloatingMast(**override)


def test_mast_deck_assigns_conductivity_to_mast_only() -> None:
    common = dict(
        title="rigid 17ft whips",
        geometry=RigidDoublet(arm_segments=41),
        frequency_mhz=7.1,
        conductivity_s_m=1.4e6,
        epsilon_r=13.0,
        ground_conductivity_s_m=0.005,
    )
    bare = rigid_doublet_deck(**common)
    with_mast = rigid_doublet_deck(
        **common, mast=FloatingMast(conductivity_s_m=2e4), pattern=True
    )

    assert sum(line.startswith("GW ") for line in bare.splitlines()) == 3
    assert sum(line.startswith("GW ") for line in with_mast.splitlines()) == 4
    assert "GW 1 41" in with_mast
    assert "GW 3 41" in with_mast
    assert "GW 2 3" in with_mast
    assert "EX 0 2 2 0 1.0 0.0" in with_mast
    assert "LD 5 0 0 0 1.400000000e+06 0 0" in with_mast
    assert "LD 5 4 0 0 2.000000000e+04 0 0" in with_mast
    assert "LD 5 4" not in bare
    assert "RP 0" in with_mast
