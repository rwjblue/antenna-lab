import json
import math
from pathlib import Path

import numpy as np
import pytest

from antenna_lab.rigid_doublet_optimization import (
    aggregate,
    coarse_candidates,
    dry_lines,
    evaluate,
    frequencies,
    rank_key,
    shortlist,
)
from antenna_lab.transmission_line import C_FT_S


@pytest.fixture
def config() -> dict:
    return dict(
        bands_mhz={"40m": [7.0, 7.3], "20m": [14.0, 14.35]},
        reference_frequencies_mhz={"40m": 7.15, "20m": 14.175},
        geometry=dict(arm_length_ft=17, feed_height_ft=30),
        cases=[dict(id="nominal"), dict(id="lower", feed_height_ft=25)],
        routing=dict(tuner_height_ft=3, horizontal_offset_ft=6, slack_ft=2),
        line_sweep_ft=dict(start=30, stop=75, step=0.5),
        comparison_lengths_ft=[28, 32.808398950131235, 65.61679790026247],
        balun_impedance_ratios=[1, 4],
        compact_max_line_ft=45,
        shortlist_per_region_ratio=1,
        tuner_limits=dict(max_l_uh=20, max_c_pf=1300, target_swr=1.01),
        line_uncertainty=dict(
            air_z0_ohm=[480, 510],
            velocity_factors=[0.93, 0.97],
            loss_db_per_100ft_at_10mhz=[0.03, 0.11],
        ),
    )


def _cube(delivery, matched=None) -> dict:
    delivery = np.asarray(delivery, dtype=float)
    return dict(
        delivery=delivery,
        matched=np.ones_like(delivery, dtype=bool)
        if matched is None
        else np.asarray(matched, dtype=bool),
        raw_swr=np.full_like(delivery, 3.0),
    )


def test_frequency_grid_includes_edges_and_distinct_reference_samples(config) -> None:
    config["bands_mhz"] = {"a": [1, 3], "b": [4, 8]}
    config["reference_frequencies_mhz"] = {"a": 2, "b": 5}
    assert frequencies(config, 3) == [
        ("a", 1),
        ("a", 2),
        ("a", 3),
        ("b", 4),
        ("b", 5),
        ("b", 6),
        ("b", 8),
    ]


def test_frequency_grid_rejects_single_sample_and_backwards_bounds(config) -> None:
    with pytest.raises(ValueError, match="At least two"):
        frequencies(config, 1)
    config["bands_mhz"]["40m"] = [7.3, 7]
    with pytest.raises(ValueError, match="positive and increasing"):
        frequencies(config, 3)


def test_frequency_grid_deduplicates_aliases_at_nec_card_precision(config) -> None:
    config["bands_mhz"] = {"15m": [21.0, 21.45]}
    midpoint = float(np.linspace(21.0, 21.45, 5)[2])
    config["reference_frequencies_mhz"] = {
        "15m": float(np.nextafter(midpoint, math.inf))
    }
    points = frequencies(config, 5)
    assert len(points) == 5
    assert ("15m", round(midpoint, 9)) in points
    assert len({(band, f"{frequency:.9f}") for band, frequency in points}) == len(
        points
    )


@pytest.mark.parametrize(
    ("sample_key", "expected_count"),
    [("coarse_samples_per_band", 37), ("validation_samples_per_band", 65)],
)
def test_v2_frequency_grids_are_unique_and_retain_each_reference(
    sample_key, expected_count
) -> None:
    path = Path(__file__).parents[1] / "configs" / "rigid-v-line-optimization-v2.json"
    model = json.loads(path.read_text())
    points = frequencies(model, model[sample_key])
    assert len(points) == expected_count
    assert len({(band, f"{frequency:.9f}") for band, frequency in points}) == len(
        points
    )
    for band, reference in model["reference_frequencies_mhz"].items():
        assert (band, round(reference, 9)) in points
        actual = [frequency for name, frequency in points if name == band]
        low, high = model["bands_mhz"][band]
        assert actual[0] == low
        assert actual[-1] == high
        assert actual == sorted(actual)


def test_uneven_frequency_counts_do_not_weight_one_band_more(config) -> None:
    points = [("40m", 7.15), ("20m", 14), ("20m", 14.175), ("20m", 14.35)]
    # One sample in 40m, three identical samples in 20m. Each band has weight 1/2.
    delivery = np.array([[0.25, 0.49], [0.81, 0.36], [0.81, 0.36], [0.81, 0.36]])
    cube = _cube(delivery[None, :, None, None, :])
    candidates = [(30, 1), (40, 4)]
    summary, band_rows = aggregate(config, 17, points, candidates, cube, phase="test")
    by_length = {row["length_ft"]: row for row in summary}
    assert by_length[30]["band_median_geometric_mean"] == pytest.approx(0.45)
    assert by_length[40]["band_median_geometric_mean"] == pytest.approx(0.42)
    assert by_length[30]["worst_band_p10_delivery"] == pytest.approx(0.25)
    assert by_length[40]["worst_band_p10_delivery"] == pytest.approx(0.36)
    assert by_length[30]["limiting_band"] == "40m"
    assert by_length[40]["limiting_band"] == "20m"
    assert len(band_rows) == 4
    # Ranking prioritizes worst-band delivery, before the geometric mean.
    assert summary[0]["length_ft"] == 40


def test_match_fraction_is_band_normalized_despite_uneven_samples(config) -> None:
    points = [("40m", 7.15), ("20m", 14), ("20m", 14.175), ("20m", 14.35)]
    cube = _cube(np.full((1, 4, 1, 1, 1), 0.9))
    cube["matched"][0, 0, 0, 0, 0] = False
    summary, _ = aggregate(config, 17, points, [(30, 1)], cube, phase="test")
    assert summary[0]["mean_band_match_fraction"] == 0.5
    assert summary[0]["all_band_match_fraction"] == 0


def test_all_band_match_keeps_one_fixed_candidate_and_coherent_scenario(config) -> None:
    points = [("40m", 7.15), ("20m", 14.175)]
    matched = np.array(
        [
            [[True, True, True], [False, True, True]],
            [[False, False, True], [True, False, True]],
        ]
    )[:, :, None, None, :]
    # First candidate can match either band, but never both in the same scenario.
    # Second matches both only in scenario zero. Third matches both in both.
    delivery = np.broadcast_to([0.99, 0.8, 0.2], matched.shape)
    cube = _cube(delivery, matched)
    candidates = [(30, 1), (40, 4), (35, 1)]
    summary, _ = aggregate(config, 17, points, candidates, cube, phase="test")
    by_length = {row["length_ft"]: row for row in summary}
    assert by_length[30]["mean_band_match_fraction"] == 0.5
    assert by_length[40]["mean_band_match_fraction"] == 0.5
    assert by_length[30]["all_band_match_fraction"] == 0
    assert by_length[40]["all_band_match_fraction"] == 0.5
    assert by_length[35]["all_band_match_fraction"] == 1
    assert [row["length_ft"] for row in summary] == [35, 40, 30]


def test_coherent_scenario_keeps_line_and_q_fixed_across_frequencies(config) -> None:
    points = [("40m", 7.15), ("20m", 14.175)]
    matched = np.zeros((1, 2, 2, 2, 1), dtype=bool)
    matched[:, 0, :, :, :] = [[[[True], [True]], [[False], [False]]]]
    matched[:, 1, :, :, :] = [[[[False], [True]], [[True], [False]]]]
    cube = _cube(np.full(matched.shape, 0.8), matched)
    summary, _ = aggregate(config, 17, points, [(30, 1)], cube, phase="test")
    # Only line zero / Q profile one matches both bands: one of four scenarios.
    assert summary[0]["all_band_match_fraction"] == 0.25
    assert summary[0]["mean_band_match_fraction"] == 0.5
    assert summary[0]["samples"] == 8


def test_unmatched_delivery_is_scored_zero_without_erasing_physical_delivery(config):
    points = [("40m", 7.15), ("20m", 14.175)]
    cube = _cube(np.full((1, 2, 1, 1, 1), 0.9))
    cube["matched"][:] = False
    summary, bands = aggregate(config, 17, points, [(30, 1)], cube, phase="test")
    assert summary[0]["worst_band_p10_delivery"] == 0
    assert summary[0]["band_median_geometric_mean"] == 0
    assert summary[0]["all_band_match_fraction"] == 0
    assert all(row["delivery_median"] == row["worst_delivery"] == 0 for row in bands)
    assert np.all(cube["delivery"] == 0.9)


def test_route_filter_uses_tallest_case_and_preserves_feasible_baselines(config):
    config["cases"] = [
        dict(id="low", feed_height_ft=10),
        dict(id="high", feed_height_ft=40),
    ]
    config["line_sweep_ft"] = dict(start=20, stop=50, step=10)
    expected_minimum = math.hypot(37, 6) + 2
    assert 30 < expected_minimum < 40
    choices = coarse_candidates(config)
    assert set(choices) == {
        (length, ratio)
        for length in (40, 50, config["comparison_lengths_ft"][2])
        for ratio in (1, 4)
    }
    assert all(length >= expected_minimum for length, _ in choices)


def test_aggregate_marks_short_baseline_infeasible_against_tallest_case(config):
    config["cases"].append(dict(id="high", feed_height_ft=40))
    cube = _cube(np.full((1, 2, 1, 1, 2), 0.9))
    summary, _ = aggregate(
        config,
        17,
        [("40m", 7.15), ("20m", 14.175)],
        [(30, 1), (40, 1)],
        cube,
        phase="test",
    )
    assert [row["route_feasible"] for row in summary] == [True, False]
    assert [row["length_ft"] for row in summary] == [40, 30]


def test_shortlist_retains_all_baselines_both_ratios_and_neighbors(config):
    coarse = [
        dict(length_ft=40, balun_ratio=ratio, region="compact", route_feasible=True)
        for ratio in (1, 4)
    ] + [
        dict(length_ft=60, balun_ratio=ratio, region="long", route_feasible=True)
        for ratio in (1, 4)
    ]
    selected = shortlist(config, coarse)
    assert selected == sorted(set(selected))
    for ratio in (1, 4):
        assert all(
            (length, ratio) in selected for length in config["comparison_lengths_ft"]
        )
        assert all(
            (length + offset, ratio) in selected
            for length in (40, 60)
            for offset in (-2, -1, -0.5, 0, 0.5, 1, 2)
        )
    # The physically too-short baseline is retained as a clearly flagged comparison.
    assert (28, 1) in selected and (28, 4) in selected


def test_rank_ties_resolve_by_length_then_ratio_and_feasibility_first() -> None:
    common = dict(
        route_feasible=True,
        all_band_match_fraction=1.0,
        worst_band_p10_delivery=0.5,
        band_median_geometric_mean=0.8,
    )
    rows = [
        common | dict(length_ft=40, balun_ratio=1),
        common | dict(length_ft=30, balun_ratio=4),
        common | dict(length_ft=30, balun_ratio=1),
        common | dict(length_ft=28, balun_ratio=1, route_feasible=False),
    ]
    ranked = sorted(rows, key=rank_key)
    assert ranked == sorted(reversed(rows), key=rank_key)
    assert [(row["length_ft"], row["balun_ratio"]) for row in ranked] == [
        (30, 1),
        (30, 4),
        (40, 1),
        (28, 1),
    ]


def test_line_ensemble_is_cartesian_and_applies_velocity_to_air_impedance(config):
    coarse = dry_lines(config, coarse=True)
    fine = dry_lines(config, coarse=False)
    assert len(coarse) == 4
    assert len(fine) == 8
    assert {row["loss_db_per_100ft_at_10mhz"] for row in coarse} == {0.07}
    assert {row["loss_db_per_100ft_at_10mhz"] for row in fine} == {0.03, 0.11}
    assert all(
        any(
            math.isclose(row["z0_ohm"], air * row["velocity_factor"])
            for air in config["line_uncertainty"]["air_z0_ohm"]
        )
        for row in fine
    )


def test_small_evaluation_cube_preserves_ratio_frequency_and_loss_axes(config):
    points = [("40m", 10.0), ("20m", 20.0)]
    cases = [dict(id="fifty"), dict(id="two_hundred")]
    loads = [
        dict(
            scenario_id=case["id"],
            band=band,
            frequency_mhz=frequency,
            feedpoint_r_ohm=resistance,
            feedpoint_x_ohm=0,
        )
        for case, resistance in zip(cases, (50, 200), strict=True)
        for band, frequency in points
    ]
    halfwave_ft = C_FT_S / (2 * 10e6)
    candidates = [(halfwave_ft, 1), (halfwave_ft, 4)]
    lines = [
        dict(z0_ohm=z0, velocity_factor=1, loss_db_per_100ft_at_10mhz=0)
        for z0 in (50, 100)
    ]
    profiles = [
        dict(
            id="lossless",
            inductor_q=math.inf,
            capacitor_q=math.inf,
            series_contact_r_ohm=0,
        ),
        dict(id="nominal", inductor_q=70, capacitor_q=2000, series_contact_r_ohm=0.1),
    ]
    cube = evaluate(config, loads, points, cases, candidates, lines, profiles)
    assert set(cube) == {
        "delivery",
        "swr",
        "raw_swr",
        "line_eta",
        "tuner_eta",
        "matched",
    }
    assert all(values.shape == (2, 2, 2, 2, 2) for values in cube.values())
    # A half wave at 10 MHz is a full wave at 20 MHz: both preserve the load.
    assert cube["raw_swr"][0, ...] == pytest.approx(
        np.broadcast_to([1, 4], (2, 2, 2, 2))
    )
    assert cube["raw_swr"][1, ...] == pytest.approx(
        np.broadcast_to([4, 1], (2, 2, 2, 2))
    )
    assert cube["line_eta"] == pytest.approx(np.ones((2, 2, 2, 2, 2)))
    assert cube["delivery"][:, :, :, 0, :] == pytest.approx(np.ones((2, 2, 2, 2)))
    assert np.all(cube["delivery"][:, :, :, 1, :] < 1)
    assert np.all(cube["delivery"] <= cube["tuner_eta"] + 1e-6)
    assert np.all(cube["matched"])


def test_nec_load_jobs_keep_scenario_order_and_override_arm_length(config, monkeypatch):
    import antenna_lab.rigid_doublet_optimization as optimization

    points = [("20m", 14.175), ("40m", 7.15)]
    cases = [dict(id="first"), dict(id="second", feed_height_ft=25)]

    def fake_nec_case(job):
        model, case, band, frequency, executable, cache = job
        assert model["geometry"]["arm_length_ft"] == 25
        assert executable == Path("solver")
        assert cache == Path("cache")
        return dict(case_id=case["id"], band=band, frequency_mhz=frequency)

    monkeypatch.setattr(optimization, "_nec_case", fake_nec_case)
    rows = optimization._loads(
        config, 25, points, cases, Path("solver"), Path("cache"), 2
    )
    assert [row["case_id"] for row in rows] == [
        "25ft_first",
        "25ft_first",
        "25ft_second",
        "25ft_second",
    ]
    assert [row["scenario_id"] for row in rows] == [
        "first",
        "first",
        "second",
        "second",
    ]
    assert [(row["band"], row["frequency_mhz"]) for row in rows] == points * 2
    assert config["geometry"]["arm_length_ft"] == 17
