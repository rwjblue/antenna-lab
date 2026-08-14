import pytest

from antenna_lab.decision_report import (
    _dominates,
    _match_safe,
    _operator_priority_rankings,
    _swr,
)


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


def test_operator_priority_weights_must_bands_and_groups_scenarios() -> None:
    rows = []
    efficiencies = {"40m": 0.9, "30m": 0.5, "20m": 0.8, "17m": 0.4, "15m": 0.3}
    for band, efficiency in efficiencies.items():
        rows.append(
            {
                "candidate_id": "wire",
                "band": band,
                "deployment": "table",
                "ground": "average",
                "conductor": "copper",
                "profile": "khatu1",
                "tuner_loss_envelope": "nominal",
                "component_loss_envelope": 0,
                "final_efficiency": efficiency,
                "input_swr": 1.5 if band != "20m" else 2.6,
            }
        )

    rankings = _operator_priority_rankings(
        rows,
        {
            "band_weights": {"40m": 5, "30m": 3, "20m": 5, "17m": 2, "15m": 2},
            "must_bands": ["40m", "20m"],
            "must_match_swr": 2.5,
        },
    )

    assert len(rankings) == 1
    assert rankings[0]["weighted_efficiency_p50"] == pytest.approx(0.6705882353)
    assert rankings[0]["must_band_floor_p50"] == 0.8
    assert rankings[0]["must_band_match_fraction"] == 0.0
