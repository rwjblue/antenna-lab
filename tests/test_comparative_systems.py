from antenna_lab.comparative_systems import (
    compose_linked_counterpoise_rows,
    select_doublet_shortlist,
)


def _row(radiator, line, compatibility, line_efficiency):
    return {
        "radiator_ft": float(radiator),
        "feedline_ft": float(line),
        "total_wire_ft": float(radiator + 2 * line),
        "all_required_compatibility_fraction": compatibility,
        "minimum_required_band_compatibility_fraction": compatibility,
        "required_max_tuner_stress_p90": 1.0 / max(compatibility, 0.01),
        "required_max_q_p90": 10.0,
        "required_worst_line_efficiency_p10": line_efficiency,
    }


def test_doublet_shortlist_preserves_baselines_and_budget_leaders() -> None:
    rows = [
        _row(58, 28, 0.8, 0.2),
        _row(44, 28, 0.2, 0.5),
        _row(57, 28, 0.4, 0.4),
        _row(44, 10, 0.1, 0.7),
        _row(58, 31.75, 1.0, 0.18),
    ]

    selected = select_doublet_shortlist(rows)
    dimensions = {(row["radiator_ft"], row["feedline_ft"]) for row in selected}

    assert {(58.0, 28.0), (44.0, 28.0), (57.0, 28.0)} <= dimensions
    assert (58.0, 31.75) in dimensions
    assert (44.0, 10.0) in dimensions


def test_linked_counterpoise_uses_short_state_only_on_17m() -> None:
    rows = [
        {"candidate_id": candidate, "band": band, "marker": candidate}
        for candidate in ("direct-41r-28c-z1", "direct-41r-14c-z1")
        for band in ("40m", "17m", "15m")
    ]

    selected = compose_linked_counterpoise_rows(rows)

    assert [row["band"] for row in selected] == ["40m", "15m", "17m"]
    by_band = {row["band"]: row for row in selected}
    assert by_band["40m"]["marker"] == "direct-41r-28c-z1"
    assert by_band["15m"]["link_state"] == "closed_28ft"
    assert by_band["17m"]["marker"] == "direct-41r-14c-z1"
    assert by_band["17m"]["link_state"] == "open_14ft"
