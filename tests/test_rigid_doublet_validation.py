import math
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from antenna_lab.rigid_doublet import RigidDoublet
from antenna_lab.rigid_doublet_validation import (
    average_gain,
    free_space_lossless_deck,
    validate_geometry,
)


def test_average_gain_integrates_absolute_power_over_sphere() -> None:
    isotropic = [
        (elevation, azimuth, 3.0)
        for elevation in range(-90, 91, 5)
        for azimuth in range(0, 360, 5)
    ]
    assert average_gain(isotropic) == pytest.approx(10**0.3)

    # Normalized short-dipole pattern: G = 1.5 cos²(elevation).
    dipole = [
        (
            elevation,
            azimuth,
            10 * math.log10(max(1e-15, 1.5 * math.cos(math.radians(elevation)) ** 2)),
        )
        for elevation in range(-90, 91, 5)
        for azimuth in range(0, 360, 5)
    ]
    assert average_gain(dipole) == pytest.approx(1.0, abs=0.002)


def test_average_gain_rejects_partial_or_duplicate_sphere() -> None:
    hemisphere = [
        (elevation, azimuth, 0)
        for elevation in range(0, 91, 5)
        for azimuth in range(0, 360, 5)
    ]
    with pytest.raises(ValueError, match="full-sphere"):
        average_gain(hemisphere)
    with pytest.raises(ValueError, match="duplicate"):
        average_gain([(0, 0, 0), (0, 360, 0)])


def test_free_space_check_preserves_geometry_and_excitation() -> None:
    deck = "\n".join(
        [
            "CM test",
            "CE",
            "GW 1 61 0 0 0 1 0 0 .0015",
            "GE 0",
            "EK 0",
            "LD 5 0 0 0 1.4e6 0 0",
            "GN 2 0 0 0 13 .005",
            "FR 0 1 0 0 14.175 0",
            "EX 0 1 31 0 1.0 0.0",
            "RP 0 19 72 1001 0 0 5 5 1000 0",
            "EN",
        ]
    )
    checked = free_space_lossless_deck(deck)
    assert "LD " not in checked
    assert "GN -1\n" in checked
    assert "RP 0 37 72 1001 0 0 5 5 1000 0\n" in checked
    for card in ("GW 1 61 0 0 0 1 0 0 .0015", "EX 0 1 31 0 1.0 0.0"):
        assert card in checked


def test_source_power_balance_and_mesh_convergence_with_nec() -> None:
    executable = Path(__file__).resolve().parents[1] / "build/tools/nec2c"
    if not executable.is_file():
        pytest.skip("Local NEC solver is not built")
    # NEC's legacy filename buffer cannot hold macOS pytest's long temp path.
    with TemporaryDirectory(prefix="rv-", dir="/tmp") as cache:
        rows = validate_geometry(
            geometry=RigidDoublet(arm_elevation_deg=30, feed_gap_m=0.06),
            bands_mhz={"20m": 14.175},
            segment_counts=(91, 181),
            nec2c=executable,
            cache_dir=cache,
        )
    # A single short bridge segment at the bend falsely produced AG about 1.15
    # at 91 segments per arm, while reporting perfect radiation efficiency.
    assert all(row["average_gain_within_tolerance"] for row in rows)
    assert rows[1]["relative_z_change_from_previous"] < 0.01
