from pathlib import Path

from antenna_lab.measurements import load_impedance_measurements
from antenna_lab.optimization import (
    build_scenarios,
    load_config,
    run_optimization,
    verify_manifest,
)

CONFIG = Path("configs/reference-small.json")
MEASUREMENTS = Path("data/measured/58ft_doublet_2026-08-08.csv")


def test_deembedded_scenarios_are_passive() -> None:
    config = load_config(CONFIG)
    measurements = load_impedance_measurements(MEASUREMENTS)

    scenarios = build_scenarios(measurements, config)

    assert scenarios
    assert all(
        scenario.minimum_baseline_load_resistance_ohm
        > config["line_uncertainty"]["passivity_min_load_r_ohm"]
        for scenario in scenarios
    )
    assert all((scenario.baseline_loads_ohm.real > 0).all() for scenario in scenarios)


def test_small_optimizer_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_summary = run_optimization(CONFIG, first)
    second_summary = run_optimization(CONFIG, second)

    assert first_summary == second_summary
    assert first_summary["candidate_count"] == 9
    for first_file in sorted(first.iterdir()):
        second_file = second / first_file.name
        assert second_file.read_bytes() == first_file.read_bytes()
    assert verify_manifest(first) == (True, [])


def test_small_optimizer_includes_baseline_and_reversible_region(
    tmp_path: Path,
) -> None:
    summary = run_optimization(CONFIG, tmp_path / "result")

    assert summary["baseline"]["radiator_total_ft"] == 58.0
    assert summary["baseline"]["feedline_ft"] == 28.0
    assert summary["recommended_reversible_test"]["feedline_ft"] == 28.0
    assert summary["recommended_reversible_test"]["radiator_total_ft"] <= 58.0
