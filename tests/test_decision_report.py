from antenna_lab.decision_report import _dominates, _match_safe, _swr


def test_pareto_dominance_requires_no_tradeoff() -> None:
    better = {
        "total_wire_ft": 50.0,
        "worst_band_final_efficiency_p10": 0.6,
        "worst_band_final_efficiency_p50": 0.7,
        "median_final_efficiency": 0.8,
    }
    worse = {
        "total_wire_ft": 60.0,
        "worst_band_final_efficiency_p10": 0.5,
        "worst_band_final_efficiency_p50": 0.6,
        "median_final_efficiency": 0.7,
    }
    tradeoff = {**worse, "worst_band_final_efficiency_p10": 0.7}

    assert _dominates(better, worse)
    assert not _dominates(better, tradeoff)


def test_match_safe_gate_and_swr_reference() -> None:
    config = {
        "match_safe_all_band_fraction": 0.9,
        "match_safe_rollback_fraction": 0.05,
    }
    assert _match_safe(
        {"all_band_target_fraction": 0.9, "rollback_fraction": 0.05}, config
    )
    assert not _match_safe(
        {"all_band_target_fraction": 0.89, "rollback_fraction": 0.0}, config
    )
    assert _swr(50 + 0j) == 1.0
