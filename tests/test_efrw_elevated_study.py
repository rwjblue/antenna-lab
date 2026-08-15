import math

import pytest

from antenna_lab.efrw_elevated_study import (
    build_cases,
    case_wires,
    load_elevated_config,
)


def _configs():
    return load_elevated_config("configs/53ft-efrw-elevated-v1.json")


def test_case_grid_covers_requested_families_and_mast_bounds() -> None:
    extension, base = _configs()
    cases = build_cases(extension, base)

    assert len(cases) == 218
    assert {case["family"] for case in cases} == {
        "low_sloper_cp_sweep",
        "elevated_tree",
        "sloper_20_to_40",
    }
    specific = [case for case in cases if case["family"] == "sloper_20_to_40"]
    assert {case["mast_condition"] for case in specific} == set(
        extension["carbon_mast"]["conditions"]
    )


def test_elevated_return_lengths_reach_ground_endpoint() -> None:
    extension, base = _configs()
    case = next(
        case
        for case in build_cases(extension, base)
        if case["family"] == "elevated_tree"
        and case["feed_height_ft"] == 30
        and case["return_kind"] == "dedicated_angled"
        and case["return_length_ft"] == 37
        and case["return_azimuth_deg"] == 180
    )
    wires, source_tag, overrides = case_wires(extension, base, case)

    assert source_tag == 2
    assert overrides == {}
    assert math.dist(wires[0].start, wires[0].end) == pytest.approx(53 * 0.3048)
    assert math.dist(wires[2].start, wires[2].end) == pytest.approx(37 * 0.3048)
    assert wires[2].start[0] < 0
    assert wires[2].start[2] == pytest.approx(0.5 * 0.3048)


def test_carbon_mast_is_floating_and_has_conductivity_override() -> None:
    extension, base = _configs()
    case = next(
        case
        for case in build_cases(extension, base)
        if case["family"] == "sloper_20_to_40"
        and case["return_kind"] == "coax_return"
        and case["mast_condition"] == "cfrp_5e4_3in"
    )
    wires, _, overrides = case_wires(extension, base, case)

    assert len(wires) == 4
    assert overrides == {4: 50_000.0}
    assert wires[3].start[1] == pytest.approx(3 * 0.0254)
    assert wires[3].start not in {wire.start for wire in wires[:3]}
