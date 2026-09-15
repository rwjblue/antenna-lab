"""Cheap checks for exact, self-contained presentation of computed study data."""

import copy
import json
import re
from html.parser import HTMLParser

import pytest

from antenna_lab.linked_dipole_report import (
    GAIN_LIMITS,
    _cases,
    _cut,
    _gain,
    _viewer_html,
    _viewer_payload,
)


@pytest.fixture
def computed_data():
    case = {
        "case_id": "frozen-20m-5ft",
        "mode": "frozen",
        "band": "20m",
        "end_height_ft": 5,
        "frequency_mhz": 14.135,
        "mismatch_loss_db": 1.25,
        "efficiency_upper": 0.5,
        "pattern": [
            [20, 180, -5.5],
            [60, 90, 2.75],
            [20, 90, 4.125],
            [20, 0, -5.5],
            [20, 270, 4.125],
            [90, 90, -0.5],
            [22, 44, 1.2345],
        ],
        "power_budget": {"unused_by_viewer": 1.0},
        "sweep": [[14.0, 45.0, -12.0, 1.3], [14.135, 50.0, 0.0, 1.0]],
    }
    other = copy.deepcopy(case)
    other.update(case_id="retuned-20m-33ft", mode="retuned", end_height_ft=33)
    nominal = copy.deepcopy(case)
    nominal.update(case_id="frozen-20m-10ft", end_height_ft=10)
    return {
        "cases": [other, nominal, case],
        "config": {
            "measured_note": "</script><script>untrusted note</script>",
            "literal_placeholder": "__GAIN_LIMITS__",
            "nominal_end_height_ft": 10,
            "center_height_ft": 33,
            "bands_mhz": {"20m": 14.135},
        },
    }


class _ViewerElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.controls = {}
        self.export_targets = []
        self.external_scripts = []
        self.selected_options = {}
        self.embedded_data = ""
        self._reading_data = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.controls[attrs["id"]] = []
            self._current_control = attrs["id"]
        elif tag == "option":
            self.controls[self._current_control].append(attrs.get("value"))
            if "selected" in attrs:
                self.selected_options[self._current_control] = attrs.get("value")
        elif tag == "button" and "data-export" in attrs:
            self.export_targets.append(attrs["data-export"])
        elif tag == "script":
            if "src" in attrs:
                self.external_scripts.append(attrs["src"])
            self._reading_data = attrs.get("id") == "computed-data"

    def handle_endtag(self, tag):
        if tag == "script":
            self._reading_data = False

    def handle_data(self, data):
        if self._reading_data:
            self.embedded_data += data


def test_viewer_embeds_exact_values_and_escapes_script_boundary(computed_data):
    html = _viewer_html(computed_data)
    parsed = _ViewerElements()
    parsed.feed(html)
    payload = json.loads(parsed.embedded_data)
    assert payload["config"] == computed_data["config"]
    for actual, original in zip(payload["cases"], computed_data["cases"], strict=True):
        assert {key: value for key, value in actual.items() if key != "pattern"} == {
            key: value
            for key, value in original.items()
            if key not in {"pattern", "power_budget"}
        }
        assert [22, 44, 1.2345] not in actual["pattern"]
        assert actual["pattern"] == original["pattern"][:-1]
    assert "</script><script>untrusted note</script>" not in html
    assert not parsed.external_scripts
    assert _viewer_html(computed_data) == html


def test_all_selections_and_svg_exports_remain_available(computed_data):
    parsed = _ViewerElements()
    parsed.feed(_viewer_html(computed_data))
    assert parsed.controls["band"] == ["20m"]
    assert parsed.controls["height"] == ["5", "10", "33"]
    assert parsed.selected_options["height"] == "10"
    assert parsed.controls["mode"] == ["frozen", "retuned"]
    assert parsed.controls["reference"] == ["accepted", "realized"]
    assert "elevation" in parsed.controls
    assert parsed.export_targets == ["geometry", "broadside", "endon", "azimuth", "swr"]


def test_viewer_and_static_patterns_share_absolute_gain_scale(computed_data):
    html = _viewer_html(computed_data)
    limits = re.search(r"const GAIN_LIMITS=(\[[^;]+\]);", html)
    assert limits is not None
    assert json.loads(limits[1]) == list(GAIN_LIMITS) == [-30, 12]
    assert "y:GAIN_LIMITS" in html
    assert "no curve is normalized to its own peak" in html


def test_elevation_cut_preserves_absolute_gain_and_sample_locations(computed_data):
    case = _cases(computed_data, "20m")[0]
    assert _cut(case, azimuth=90) == [(20, 4.125), (60, 2.75), (90, -0.5)]
    with pytest.raises(ValueError, match="Missing pattern cut"):
        _cut(case, azimuth=89)


def test_azimuth_cut_closes_periodically_with_same_absolute_gain(computed_data):
    case = _cases(computed_data, "20m")[0]
    assert _cut(case, elevation=20) == [
        (0, -5.5),
        (90, 4.125),
        (180, -5.5),
        (270, 4.125),
        (360, -5.5),
    ]
    with pytest.raises(ValueError, match="exactly one"):
        _cut(case, elevation=20, azimuth=90)


def test_gain_uses_mismatch_once_without_subtracting_efficiency(computed_data):
    case = _cases(computed_data, "20m")[0]
    assert _gain(case, 20, 90) == 4.125
    assert _gain(case, 20, 90, realized=True) == 2.875
    # NEC gain already contains this efficiency; changing the annotation must
    # not apply a second loss correction to the sampled accepted/realized gain.
    case["efficiency_upper"] = 0.25
    assert _gain(case, 20, 90, realized=True) == 2.875


def test_selection_keeps_frozen_and_retuned_experiments_separate(computed_data):
    assert [c["case_id"] for c in _cases(computed_data, "20m")] == [
        "frozen-20m-5ft",
        "frozen-20m-10ft",
    ]
    assert [c["case_id"] for c in _cases(computed_data, "20m", "retuned")] == [
        "retuned-20m-33ft"
    ]


def test_nonfinite_computed_values_cannot_silently_enter_viewer(computed_data):
    computed_data["cases"][0]["mismatch_loss_db"] = float("nan")
    with pytest.raises(ValueError, match="Out of range float"):
        _viewer_html(computed_data)


def test_nominal_tuning_labels_and_default_follow_config(computed_data):
    html = _viewer_html(computed_data)
    assert "33 ft center / 10 ft outer-end geometry" in html
    assert "33 ft center / 5 ft outer-end geometry" not in html
    assert 'href="README.md"' in html
    computed_data["config"]["nominal_end_height_ft"] = 5
    html = _viewer_html(computed_data)
    parsed = _ViewerElements()
    parsed.feed(html)
    assert "33 ft center / 5 ft outer-end geometry" in html
    assert parsed.selected_options["height"] == "5"


def test_compact_grid_preserves_every_displayed_cut_and_stays_below_one_mb(
    computed_data,
):
    case = computed_data["cases"][0]
    case["pattern"] = [
        [elevation, azimuth, round(elevation / 23 - azimuth / 42, 2)]
        for elevation in range(0, 92, 2)
        for azimuth in range(0, 360, 2)
    ]
    computed_data["cases"] = [case] * 30
    compact = _viewer_payload(computed_data)["cases"][0]
    assert len(compact["pattern"]) < len(case["pattern"]) / 10
    for azimuth in (0, 90):
        assert _cut(compact, azimuth=azimuth) == _cut(case, azimuth=azimuth)
    for elevation in (10, 20, 30, 60):
        assert _cut(compact, elevation=elevation) == _cut(case, elevation=elevation)
    for elevation in (10, 20, 30, 60, 90):
        for azimuth in (0, 90):
            assert _gain(compact, elevation, azimuth) == _gain(case, elevation, azimuth)
    assert len(_viewer_html(computed_data).encode()) < 1_000_000
