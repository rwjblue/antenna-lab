"""Polar coordinates preserve computed direction and absolute power gain."""

import copy

import pytest

from antenna_lab.linked_dipole_polar import (
    azimuth_polar_cut,
    elevation_polar_cut,
    radial_gain,
)


@pytest.fixture
def asymmetric_case():
    # Opposite azimuths deliberately differ; mirroring one cut would invent
    # gains. At zenith all azimuths describe the same physical direction.
    cuts = {
        0: [(0, -2), (20, 13.75), (30, 4), (60, 2), (90, -5.25)],
        90: [(0, -35), (20, 4.125), (30, 3.75), (60, 1), (90, -5.25)],
        180: [(0, -6), (20, -2.5), (30, 0.5), (60, 7), (90, -5.25)],
        270: [(0, -41), (20, 2.5), (30, -1.75), (60, 6.5), (90, -5.25)],
    }
    return {
        "case_id": "synthetic-asymmetric-pattern",
        "mismatch_loss_db": 1.25,
        "efficiency_upper": 0.5,
        # Scramble input order so angular ordering is a checked behavior.
        "pattern": [
            (elevation, azimuth, gain)
            for azimuth, points in reversed(list(cuts.items()))
            for elevation, gain in reversed(points)
        ],
    }


def test_elevation_polar_uses_actual_opposite_azimuth_and_one_zenith(asymmetric_case):
    assert elevation_polar_cut(asymmetric_case) == [
        (0, -35),
        (20, 4.125),
        (30, 3.75),
        (60, 1),
        (90, -5.25),
        (120, 6.5),
        (150, -1.75),
        (160, 2.5),
        (180, -41),
    ]


def test_end_on_elevation_polar_uses_zero_and_180_degree_samples(asymmetric_case):
    assert elevation_polar_cut(asymmetric_case, azimuth_deg=0) == [
        (0, -2),
        (20, 13.75),
        (30, 4),
        (60, 2),
        (90, -5.25),
        (120, 7),
        (150, 0.5),
        (160, -2.5),
        (180, -6),
    ]


def test_opposite_elevation_azimuth_wraps_and_reverses_the_cut(asymmetric_case):
    broadside = elevation_polar_cut(asymmetric_case, azimuth_deg=90)
    reverse_broadside = elevation_polar_cut(asymmetric_case, azimuth_deg=270)
    assert reverse_broadside == sorted((180 - angle, gain) for angle, gain in broadside)


def test_elevation_polar_never_adds_below_ground_radiation(asymmetric_case):
    expected = elevation_polar_cut(asymmetric_case)
    asymmetric_case["pattern"].extend([(-15, 90, 8), (-15, 270, 3)])
    actual = elevation_polar_cut(asymmetric_case)
    assert actual == expected
    assert all(0 <= angle <= 180 for angle, _ in actual)


def test_azimuth_polar_preserves_asymmetry_and_closes_at_360(asymmetric_case):
    assert azimuth_polar_cut(asymmetric_case) == [
        (0, 13.75),
        (90, 4.125),
        (180, -2.5),
        (270, 2.5),
        (360, 13.75),
    ]
    assert azimuth_polar_cut(asymmetric_case, elevation_deg=60) == [
        (0, 2),
        (90, 1),
        (180, 7),
        (270, 6.5),
        (360, 2),
    ]


@pytest.mark.parametrize("cut", [elevation_polar_cut, azimuth_polar_cut])
def test_polar_gain_applies_mismatch_once_without_efficiency_or_normalization(
    asymmetric_case, cut
):
    original = copy.deepcopy(asymmetric_case)
    accepted = cut(asymmetric_case)
    realized = cut(asymmetric_case, realized=True)
    assert realized == [(angle, gain - 1.25) for angle, gain in accepted]
    assert asymmetric_case == original
    asymmetric_case["efficiency_upper"] = 0.1
    assert cut(asymmetric_case) == accepted
    assert cut(asymmetric_case, realized=True) == realized


def test_missing_opposite_elevation_cut_cannot_be_replaced_with_a_mirror(
    asymmetric_case,
):
    asymmetric_case["pattern"] = [
        point for point in asymmetric_case["pattern"] if point[1] != 270
    ]
    with pytest.raises(ValueError):
        elevation_polar_cut(asymmetric_case)


@pytest.mark.parametrize(
    ("gain", "radius"),
    [
        (-999.99, 0),
        (-30, 0),
        (-29.75, 0.25),
        (-10, 20),
        (0, 30),
        (6, 36),
        (12, 42),
        (22, 42),
    ],
)
def test_common_radial_display_offsets_db_gain_and_clips_only_at_limits(gain, radius):
    assert radial_gain(gain) == pytest.approx(radius)
