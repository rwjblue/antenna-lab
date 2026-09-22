"""Geometry/port invariants that prevent misleading close-spaced fan results."""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from antenna_lab.fan_dipole import INCH, fan_deck, fan_network
from antenna_lab.fan_dipole_study import common_port_impedance


@pytest.fixture
def config():
    return json.loads(Path("configs/fan-dipole-v1.json").read_text())


def test_three_sources_and_common_impedance(config):
    deck = fan_deck([33, 23, 16], 0.5, 7.1, config)
    assert sum(line.startswith("EX ") for line in deck.splitlines()) == 3
    assert "EX 0 1 5 " in deck
    # NEC per-source input rows: Vreal Vimag Ireal Iimag R X Greal Gimag P.
    text = "\n".join(
        f"{n} {n} 1 0 0.01 0 {r} {x} 0 0 0.005"
        for n, r, x in [(1, 100, 50), (2, 200, -50), (3, 300, 0)]
    )
    expected = 1 / (1 / complex(100, 50) + 1 / complex(200, -50) + 1 / 300)
    assert common_port_impedance(text) == pytest.approx(expected)
    with pytest.raises(ValueError, match="Expected 3"):
        common_port_impedance(text.splitlines()[0])


def test_parallel_mesh_aligns_at_every_shared_coordinate(config):
    wires = fan_network([33, 23, 16], 0.5, config)
    arms = [w for w in wires if w.tag not in (1, 10001, 10002) and w.start[0] > 0]
    by_branch = {b: [] for b in range(3)}
    for w in arms:
        b = round(w.start[1] / (0.5 * INCH))
        assert w.end[1] == pytest.approx(w.start[1])
        by_branch[b].append(w)
    for short, long in [(2, 1), (1, 0)]:
        for a, b in zip(by_branch[short], by_branch[long], strict=False):
            assert a.segments == b.segments
            assert a.start[0] == pytest.approx(b.start[0])
            assert a.end[0] == pytest.approx(b.end[0])
            assert a.start[2] == pytest.approx(b.start[2])
            assert abs(a.start[1] - b.start[1]) == pytest.approx(0.5 * INCH)
    # No accidental electrical connections between the three balanced dipoles.
    endpoints = Counter(point for w in wires for point in (w.start, w.end))
    assert sum(count == 1 for count in endpoints.values()) == 6
    assert max(endpoints.values()) == 2
    assert min(w.end[2] for w in arms) == pytest.approx(10 * 0.3048)
    assert max(w.start[2] for w in arms) == pytest.approx(33 * 0.3048)
    assert all(
        np.linalg.norm(np.array(w.end) - w.start) / w.segments
        > 8 * config["metal_radius_m"]
        for w in wires
    )


@pytest.mark.parametrize(
    "lengths,spacing", [([23, 33, 16], 0.5), ([33, 23, 16], 0.001)]
)
def test_rejects_invalid_geometry(config, lengths, spacing):
    with pytest.raises(ValueError):
        fan_network(lengths, spacing, config)


def test_sequential_tuning_rechecks_coupled_bands_and_keeps_lengthening(config):
    from antenna_lab.fan_dipole_study import FanStudy
    from antenna_lab.nec import NecResult

    class CoupledStudy(FanStudy):
        def __init__(self):
            self.config = config

        def solve(self, lengths, spacing, frequency, config=None, pattern=False):
            index = list(self.config["bands_mhz"].values()).index(frequency)
            matrix = np.array([[60, 4, 1], [3, 100, 6], [2, 5, 130]])
            reactances = matrix @ (np.array(lengths) - [33, 23, 16])
            result = NecResult(frequency, complex(60, reactances[index]), None)
            return result, None, None, False

    result = CoupledStudy().tune(0.5)
    assert result["converged"]
    assert max(abs(x) for x in result["history"][-1]["reactances_ohm"]) <= 0.5
    assert any(h["delta_in"] > 0 for h in result["history"])
    assert result["lengths_ft"] == pytest.approx([33, 23, 16], abs=0.01)


def test_rejects_impedance_pole_as_tuning_root(config):
    from antenna_lab.fan_dipole_study import FanStudy
    from antenna_lab.nec import NecResult

    class PoleStudy(FanStudy):
        def __init__(self):
            self.config = config

        def solve(self, lengths, spacing, frequency, config=None, pattern=False):
            # Changes sign but never crosses X=0.
            x = 100 / (lengths[0] - 33.123456789)
            return NecResult(frequency, complex(50, x), None), None, None, False

    result = PoleStudy().tune(0.5)
    assert not result["converged"]
    assert result["error"] == "No continuous resonance root for 40m"
