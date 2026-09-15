"""Pipeline checks using cheap analytic loads instead of a NEC installation."""

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import antenna_lab.linked_dipole_study as pipeline
import antenna_lab.linked_dipole_validation as validation
from antenna_lab.optimization import verify_manifest
from antenna_lab.transmission_line import swr


@pytest.fixture
def config():
    return json.loads(
        (Path(__file__).parents[1] / "configs/linked-dipole-v1.json").read_text()
    )


def _analytic_study(config, tmp_path, impedance):
    study = pipeline.Study(config, tmp_path / "solver", tmp_path / "cache")
    study.solve = lambda lengths, height, band, frequency, *a, **kw: (
        SimpleNamespace(impedance_ohm=impedance(frequency)),
    )
    return study


def test_repository_default_tunes_at_10ft_and_keeps_all_five_deployments(config):
    assert config["nominal_end_height_ft"] == 10
    assert config["center_height_ft"] == 33
    assert config["outer_end_heights_ft"] == [5, 10, 15, 20, 33]


def test_sequential_tuning_rechecks_earlier_bands_after_extensions_change(
    config, tmp_path
):
    study = pipeline.Study(config, tmp_path / "solver", tmp_path / "cache")
    target = [16.2, 6.5, 10.0]

    def reactance(lengths, band):
        errors = [a - b for a, b in zip(lengths, target, strict=True)]
        # The disconnected extensions perturb the earlier bands as conductors.
        return {
            "20m": 100 * errors[0] + 5 * errors[1] + 2 * errors[2],
            "30m": 100 * sum(errors[:2]) + 2 * errors[2],
            "40m": 100 * sum(errors),
        }[band]

    def solve(lengths, height, band, frequency):
        assert height == config["nominal_end_height_ft"]
        return (SimpleNamespace(impedance_ohm=50 + 1j * reactance(lengths, band)),)

    study.solve = solve
    initial = [16.5, 6.8, 9.8]
    tuned = study.tune(config["nominal_end_height_ft"], initial)
    assert initial == [16.5, 6.8, 9.8]
    assert tuned["converged"] is True
    assert tuned["end_height_ft"] == 10
    assert len(tuned["history"]) > 1
    assert tuned["section_lengths_ft"] == pytest.approx(target, abs=0.003)
    for band in config["bands_mhz"]:
        x = reactance(tuned["section_lengths_ft"], band)
        assert abs(x) <= config["tuning_reactance_tolerance_ohm"]
        assert tuned["history"][-1]["rechecked_reactance_ohm"][band] == pytest.approx(x)


def test_scan_expands_past_initial_search_and_reports_out_of_band_minimum(
    config, tmp_path
):
    resonance = 12.2  # Deliberately beyond both 30m and the initial search range.
    study = _analytic_study(config, tmp_path, lambda f: 50 + 400j * (f - resonance))
    scan = study.frequency_scan((16, 7, 10), 5, "30m")
    half_width = math.sqrt(1250) / 400
    assert scan["resonance_mhz"] == pytest.approx(resonance, abs=3e-6)
    assert scan["min_swr_frequency_mhz"] == pytest.approx(resonance, abs=3e-6)
    assert scan["min_swr"] == pytest.approx(1, abs=3e-5)
    assert scan["swr2_low_mhz"] == pytest.approx(resonance - half_width, abs=3e-6)
    assert scan["swr2_high_mhz"] == pytest.approx(resonance + half_width, abs=3e-6)
    assert scan["swr2_bandwidth_khz"] == pytest.approx(2000 * half_width, abs=0.005)
    assert scan["in_band_swr2_interval_mhz"] == []
    assert max(row[0] for row in scan["sweep"]) > 12.2


def test_exact_sampled_resonance_is_retained_and_distinguished_from_minimum(
    config, tmp_path
):
    resonance = config["bands_mhz"]["30m"]
    study = _analytic_study(
        config, tmp_path, lambda f: 40 + (200 + 1000j) * (f - resonance)
    )
    scan = study.frequency_scan((16, 7, 10), 5, "30m")
    assert scan["resonance_mhz"] == pytest.approx(resonance, abs=1e-6)
    assert any(abs(root - resonance) < 1e-6 for root in scan["all_resonances_mhz"])
    assert scan["min_swr_frequency_mhz"] > resonance + 0.0001
    assert scan["min_swr"] < swr(40 + 0j)


def test_case_applies_mismatch_once_to_gain_and_available_power(
    config, tmp_path, monkeypatch
):
    study = pipeline.Study(config, tmp_path / "solver", tmp_path / "cache")
    deck, output = tmp_path / "case.nec", tmp_path / "case.out"
    deck.write_text("deck")
    output.write_text("output")
    pattern = tuple((e, a, 6.0) for e in (10, 20, 30, 60, 90) for a in (0, 90))
    study.solve = lambda *a, **kw: (
        SimpleNamespace(impedance_ohm=100 + 50j, pattern=pattern),
        deck,
        output,
        False,
    )
    monkeypatch.setattr(
        pipeline,
        "reconciled_power_budget",
        lambda *args: {"upper_hemisphere_efficiency": 0.6},
    )
    row = study.case((16, 7, 10), 5, "20m", scan=False)
    # This load accepts 80% of the available power from a 50-ohm source.
    mismatch_db = -10 * math.log10(0.8)
    assert row["accepted_power_fraction_50ohm"] == pytest.approx(0.8)
    assert row["efficiency_upper"] == 0.6
    assert row["available_to_upper_efficiency"] == pytest.approx(0.48)
    assert row["mismatch_loss_db"] == pytest.approx(mismatch_db)
    assert row["peak_gain_dbi"] == 6
    assert row["realized_peak_gain_dbi"] == pytest.approx(6 - mismatch_db)
    assert row["realized_broadside_20deg_dbi"] == pytest.approx(6 - mismatch_db)


def test_case_scan_keeps_scenario_ground_material_and_link_state(
    config, tmp_path, monkeypatch
):
    study = pipeline.Study(config, tmp_path / "solver", tmp_path / "cache")
    deck, output = tmp_path / "case.nec", tmp_path / "case.out"
    deck.write_text("deck")
    output.write_text("output")
    calls = []
    pattern = tuple((e, a, 6.0) for e in (10, 20, 30, 60, 90) for a in (0, 90))

    def solve(lengths, height, band, frequency, supplied_config=None, **kwargs):
        calls.append((supplied_config, kwargs))
        return (
            SimpleNamespace(
                impedance_ohm=50 + 1000j * (frequency - 14.2), pattern=pattern
            ),
            deck,
            output,
            False,
        )

    study.solve = solve
    monkeypatch.setattr(
        pipeline,
        "reconciled_power_budget",
        lambda *args: {"upper_hemisphere_efficiency": 0.6},
    )
    variant = {**config, "effective_conductivity_s_m": 1_400_000}
    study.case(
        (16, 7, 10), 5, "20m", config=variant, ground="poor", outer_closed_on_20m=True
    )
    assert len(calls) > 2
    assert all(supplied is variant for supplied, _ in calls)
    assert all(kwargs["ground"] == "poor" for _, kwargs in calls)
    assert all(kwargs["outer_closed_on_20m"] is True for _, kwargs in calls)


def test_run_uses_one_frozen_assembly_and_separate_retuned_assemblies(
    config, tmp_path, monkeypatch
):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    solver = tmp_path / "solver"
    solver.write_text("fake solver")
    tuned_calls = []
    captured = {}
    nominal_lengths = [16.0, 7.0, 10.0]

    class InexpensiveStudy:
        def __init__(self, config, executable, cache):
            self.config = config
            self.used_inputs = {}

        def tune(self, height, initial):
            tuned_calls.append((height, list(initial)))
            return dict(
                end_height_ft=height,
                section_lengths_ft=[
                    value + (height - self.config["nominal_end_height_ft"]) / 100
                    for value in nominal_lengths
                ],
                converged=True,
            )

        def case(self, lengths, height, band, mode):
            return dict(
                mode=mode,
                band=band,
                end_height_ft=height,
                section_lengths_ft=list(lengths),
            )

    def sensitivities(study, lengths, jobs):
        assert lengths == nominal_lengths
        return []

    def validate(study, lengths, cases, jobs):
        assert lengths == nominal_lengths
        assert len(cases) == 30
        # A failed numerical check must survive orchestration and artifact output.
        return [{"kind": "open_connectivity", "passed": False}]

    monkeypatch.setattr(pipeline, "Study", InexpensiveStudy)
    monkeypatch.setattr(pipeline, "find_nec2c", lambda path: solver)
    monkeypatch.setattr(pipeline, "sensitivity_study", sensitivities)
    monkeypatch.setattr(pipeline, "validate_study", validate)
    monkeypatch.setattr(
        pipeline, "finish_artifacts", lambda output, data, *args: captured.update(data)
    )
    result = pipeline.run_linked_dipole_study(
        config_path, tmp_path / "run", jobs=1, cache_dir=tmp_path / "cache"
    )
    cases = captured["cases"]
    frozen = [case for case in cases if case["mode"] == "frozen"]
    retuned = [case for case in cases if case["mode"] == "retuned"]
    expected_pairs = {
        (height, band)
        for height in config["outer_end_heights_ft"]
        for band in config["bands_mhz"]
    }
    assert {(c["end_height_ft"], c["band"]) for c in frozen} == expected_pairs
    assert {(c["end_height_ft"], c["band"]) for c in retuned} == expected_pairs
    assert all(case["section_lengths_ft"] == nominal_lengths for case in frozen)
    assert captured["nominal_tuning"]["end_height_ft"] == 10
    for case in retuned:
        adjustment = (case["end_height_ft"] - 10) / 100
        assert case["section_lengths_ft"] == [v + adjustment for v in nominal_lengths]
    assert tuned_calls[0] == (10, config["initial_section_lengths_ft"])
    assert {height for height, _ in tuned_calls[1:]} == {5, 15, 20, 33}
    assert len(tuned_calls) == 5  # The nominal assembly is reused at 10ft.
    assert all(initial == nominal_lengths for _, initial in tuned_calls[1:])
    assert result["validation_passed"] is False
    assert captured["validation"][0]["passed"] is False


def test_validation_covers_every_primary_geometry_band_and_checks_real_open_ends(
    config, tmp_path, monkeypatch
):
    deck, output = tmp_path / "case.nec", tmp_path / "case.out"
    deck.write_text("deck")
    output.write_text("output")
    result = SimpleNamespace(impedance_ohm=50 + 0j, pattern=((90, 0, 6.0),))
    solved = (result, deck, output, False)
    source_case_heights = []

    def source_case(lengths, height, band, **kwargs):
        source_case_heights.append(height)
        return {"r_ohm": 50, "x_ohm": 0, "peak_gain_dbi": 6}

    study = SimpleNamespace(
        config=config,
        cache=tmp_path / "cache",
        executable=tmp_path / "solver",
        solve=lambda *a, **kw: solved,
        run=lambda *args: solved,
        case=source_case,
    )
    monkeypatch.setattr(pipeline, "run_cached", lambda *args: solved)
    monkeypatch.setattr(pipeline, "average_gain", lambda pattern: 1)
    monkeypatch.setattr(pipeline, "upper_hemisphere_efficiency", lambda pattern: 0.6)
    monkeypatch.setattr(
        pipeline, "upper_hemisphere_efficiency_from_fields", lambda text: 0.6
    )
    monkeypatch.setattr(
        validation, "check_open_endpoints", lambda *args: {"passed": False}
    )
    cases = [
        dict(
            mode="frozen",
            band=band,
            end_height_ft=height,
            efficiency_upper=0.6,
            peak_gain_dbi=6,
            r_ohm=50,
            x_ohm=0,
            power_budget={
                "ground_and_numerical_residual_fraction": 0.4,
                "input_power_w": 0.01,
            },
        )
        for height in config["outer_end_heights_ft"]
        for band in config["bands_mhz"]
    ]
    rows = pipeline.validate_study(study, [16, 7, 10], cases, jobs=1)
    for case in cases:
        matched = [
            row
            for row in rows
            if row.get("end_height_ft") == case["end_height_ft"]
            and row["band"] == case["band"]
        ]
        assert sum(row["kind"] == "mesh_and_free_space" for row in matched) == 3
        assert sum(row["kind"] == "mesh_convergence" for row in matched) == 1
        assert sum(row["kind"] == "angular_and_power" for row in matched) == 1
        assert all(row["passed"] for row in matched)
    source_rows = [row for row in rows if row["kind"] == "source_length"]
    assert len(source_rows) == 6
    assert {row["end_height_ft"] for row in source_rows} == {5, 33}
    assert set(source_case_heights) == {5, 33}
    open_checks = [row for row in rows if row["kind"] == "open_connectivity"]
    assert {row["band"] for row in open_checks} == {"20m", "30m", "40m"}
    assert {row["open_gap_m"] for row in open_checks} == {
        config["open_gap_m"],
        min(config["sensitivity"]["open_gaps_m"]),
    }
    assert all(row["passed"] is False for row in open_checks)


def test_compact_package_retains_useful_artifacts_and_hashes_nested_figures(
    config, tmp_path, monkeypatch
):
    import antenna_lab.linked_dipole_report as rendering
    import antenna_lab.linked_dipole_summary as reporting

    output, compact = tmp_path / "full", tmp_path / "maintained"
    output.mkdir()
    config_path, solver = tmp_path / "config.json", tmp_path / "solver"
    config_path.write_text(json.dumps(config))
    solver.write_text("fake solver")
    tuning = {"end_height_ft": 10, "section_lengths_ft": [16, 7, 10]}
    pipeline.write_json(output / "tuning.json", [tuning])
    pipeline.write_json(output / "nominal_tuning.json", tuning)

    def render(directory, data):
        (directory / "figures").mkdir()
        (directory / "figures" / "comparison.png").write_bytes(b"PNG fixture")
        (directory / "figures" / "comparison.svg").write_text("<svg>fixture</svg>")
        (directory / "viewer.html").write_text("<html>offline viewer fixture</html>")

    def report(directory, data):
        (directory / "README.md").write_text("# Maintained study fixture\n")
        (directory / "REPORT.md").write_text("# Illustrated report fixture\n")

    monkeypatch.setattr(rendering, "render_artifacts", render)
    monkeypatch.setattr(reporting, "write_report", report)
    case = dict(
        case_id="frozen-20m-10ft",
        mode="frozen",
        band="20m",
        geometry={"end_height_ft": 10},
        pattern=[(90, 0, 6)],
        sweep=[(14.135, 50, 0, 1)],
        mismatch_loss_db=0,
    )
    data = dict(
        config=config,
        nominal_tuning=tuning,
        tuning=[tuning],
        cases=[case],
        sensitivity=[case],
        validation=[{"kind": "mesh", "passed": True}],
        used_nec_inputs=[],
    )
    pipeline.finish_artifacts(
        output, data, config_path, solver, tmp_path / "cache", compact
    )
    expected = {
        "README.md",
        "viewer.html",
        "summary.csv",
        "geometry.csv",
        "sensitivity.csv",
        "config.json",
        "tuning.json",
        "numerical_validation.json",
        "run_metadata.json",
        "figures/comparison.png",
        "figures/comparison.svg",
    }
    maintained_files = {
        path.relative_to(compact).as_posix()
        for path in compact.rglob("*")
        if path.is_file()
    }
    assert expected <= maintained_files
    assert not maintained_files & {"study.json", "patterns.csv", "sweeps.csv"}
    assert not (compact / "nec").exists()
    assert not (compact / "cache").exists()
    assert verify_manifest(output) == (True, [])
    assert verify_manifest(compact) == (True, [])
    manifest_files = {
        line.split("  ", 1)[1]
        for line in (compact / "SHA256SUMS").read_text().splitlines()
    }
    assert manifest_files == maintained_files - {"SHA256SUMS"}
    (compact / "figures" / "comparison.svg").write_text("tampered")
    assert verify_manifest(compact) == (
        False,
        ["hash mismatch: figures/comparison.svg"],
    )


def test_cleanup_removes_only_previously_manifested_obsolete_artifacts(tmp_path):
    maintained = tmp_path / "maintained"
    figures = maintained / "figures"
    figures.mkdir(parents=True)
    retained = maintained / "README.md"
    retained.write_text("current report")
    obsolete = maintained / "REPORT.md"
    obsolete.write_text("superseded report")
    old_figure = figures / "old.svg"
    old_figure.write_text("superseded figure")
    current_figure = figures / "current.svg"
    current_figure.write_text("current figure")
    pipeline.write_manifest(maintained)
    # A user-created note added after generation has no manifest ownership.
    note = maintained / "field-notes.md"
    note.write_text("Keep my measured dimensions")

    pipeline.remove_obsolete_generated_files(
        maintained, {"README.md", "figures/current.svg"}
    )

    assert not obsolete.exists()
    assert not old_figure.exists()
    assert retained.read_text() == "current report"
    assert current_figure.read_text() == "current figure"
    assert note.read_text() == "Keep my measured dimensions"


def test_cleanup_without_prior_manifest_preserves_existing_files(tmp_path):
    note = tmp_path / "README.md"
    note.write_text("Existing content without generated provenance")
    pipeline.remove_obsolete_generated_files(tmp_path, set())
    assert note.read_text() == "Existing content without generated provenance"


@pytest.mark.parametrize(
    "entry", ["../outside.md", "figures/../../outside.md", "absolute"]
)
def test_cleanup_rejects_manifest_paths_outside_result_directory(tmp_path, entry):
    maintained = tmp_path / "maintained"
    maintained.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Outside file must survive")
    relative = str(outside) if entry == "absolute" else entry
    (maintained / "SHA256SUMS").write_text(f"{'0' * 64}  {relative}\n")

    with pytest.raises(ValueError):
        pipeline.remove_obsolete_generated_files(maintained, set())
    assert outside.read_text() == "Outside file must survive"


def test_cleanup_rejects_directory_symlinks_that_escape_result_directory(tmp_path):
    maintained, external = tmp_path / "maintained", tmp_path / "external"
    maintained.mkdir()
    external.mkdir()
    outside = external / "outside.md"
    outside.write_text("Outside file must survive a symlinked parent")
    (maintained / "linked_dir").symlink_to(external, target_is_directory=True)
    (maintained / "SHA256SUMS").write_text(f"{'0' * 64}  linked_dir/outside.md\n")

    with pytest.raises(ValueError):
        pipeline.remove_obsolete_generated_files(maintained, set())
    assert outside.read_text() == "Outside file must survive a symlinked parent"
