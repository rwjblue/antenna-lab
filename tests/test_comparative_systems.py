from antenna_lab.comparative_systems import select_doublet_shortlist


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
