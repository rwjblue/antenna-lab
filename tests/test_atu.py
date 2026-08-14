import math

import pytest

from antenna_lab.atu import (
    LOSS_ENVELOPES,
    PROFILES,
    solve_switched_l_network,
    solve_zm2,
)


def test_published_elecraft_profiles_have_expected_binary_bank_totals() -> None:
    kxat2 = PROFILES["kxat2"]
    assert math.isclose(sum(kxat2.inductors_uH), 7.938)
    assert math.isclose(sum(kxat2.capacitors_pF), 1323.0)
    kxat3 = PROFILES["kxat3"]
    assert math.isclose(sum(kxat3.inductors_uH), 15.93)
    assert math.isclose(sum(kxat3.capacitors_pF), 2683.0)


def test_bypass_is_lossless_for_a_fifty_ohm_load() -> None:
    solution = solve_switched_l_network(
        PROFILES["kxat2"],
        50 + 0j,
        14_050_000,
        LOSS_ENVELOPES[1],
        objective="lowest_loss_under_target",
    )
    assert solution.topology == "bypass"
    assert solution.input_swr == 1.0
    assert solution.tuner_efficiency == 1.0
    assert solution.transducer_efficiency == 1.0


def test_kxat2_finds_a_passive_match_for_measured_40m_load() -> None:
    solution = solve_switched_l_network(
        PROFILES["kxat2"],
        35.5 - 211j,
        7_050_000,
        LOSS_ENVELOPES[1],
        objective="lowest_loss_under_target",
    )
    assert solution.input_swr <= 1.5
    assert 0 < solution.tuner_efficiency <= 1
    assert 0 < solution.transducer_efficiency <= solution.tuner_efficiency
    assert math.isclose(
        solution.accepted_power_w,
        solution.load_power_w + solution.tuner_dissipation_w,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def test_unsupported_profile_returns_explicit_result() -> None:
    solution = solve_switched_l_network(
        PROFILES["kxat2"],
        50 + 0j,
        50_100_000,
        LOSS_ENVELOPES[1],
    )
    assert not solution.supported
    assert solution.topology == "unsupported"
    assert math.isinf(solution.input_swr)


def test_zm2_equivalent_model_can_find_a_reasonable_midband_match() -> None:
    solution = solve_zm2(100 - 200j, 14_050_000, LOSS_ENVELOPES[1])
    assert solution["supported"]
    assert solution["input_swr"] <= 1.5
    assert 0 < solution["tuner_efficiency"] <= 1


def test_sharded_profile_pipeline_assembles_manifest(
    tmp_path, monkeypatch
) -> None:
    import csv

    import antenna_lab.atu as atu
    from antenna_lab.atu import (
        ATU_PROFILE_IDS,
        assemble_atu_loss_study,
        run_atu_profile_stage,
    )
    from antenna_lab.optimization import verify_manifest

    monkeypatch.setattr(
        atu, "DIRECT_DEPLOYMENTS", {"test": (0.5, 20.0, 0.1, 90.0)}
    )
    monkeypatch.setattr(atu, "GROUNDS", {"average": (13.0, 0.005)})
    monkeypatch.setattr(
        atu, "ATU_DIRECT_CONDUCTIVITIES", (("copper", 58_000_000.0),)
    )
    monkeypatch.setattr(
        atu, "EXTENDED_BANDS", (("20m", 14_050_000, True),)
    )

    input_dir = tmp_path / "inputs"
    direct_dir = input_dir / "direct"
    direct_dir.mkdir(parents=True)
    direct_csv = direct_dir / "atu-direct-nec.csv"
    direct_row = {
        "candidate": "41r-17c",
        "radiator_ft": 41.0,
        "counterpoise_ft": 17.0,
        "deployment": "test",
        "ground": "average",
        "conductivity": "copper",
        "band": "20m",
        "frequency_hz": 14_050_000,
        "resistance_ohm": 100.0,
        "reactance_ohm": -200.0,
        "nec_efficiency": 0.9,
    }
    with direct_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(direct_row))
        writer.writeheader()
        writer.writerow(direct_row)

    for profile_id in ATU_PROFILE_IDS:
        run_atu_profile_stage(
            input_dir / profile_id,
            direct_nec_csv=direct_csv,
            profile_id=profile_id,
        )

    output_dir = tmp_path / "assembled"
    summary = assemble_atu_loss_study(output_dir, input_dir=input_dir)
    assert summary["profiles"] == list(ATU_PROFILE_IDS)
    assert summary["solution_row_count"] > 0
    valid, failures = verify_manifest(output_dir)
    assert valid, failures


def test_direct_nec_validation_rejects_missing_and_duplicate_keys(
    monkeypatch,
) -> None:
    import antenna_lab.atu as atu

    monkeypatch.setattr(
        atu, "DIRECT_DEPLOYMENTS", {"test": (0.5, 20.0, 0.1, 90.0)}
    )
    monkeypatch.setattr(atu, "GROUNDS", {"average": (13.0, 0.005)})
    monkeypatch.setattr(
        atu, "ATU_DIRECT_CONDUCTIVITIES", (("copper", 58_000_000.0),)
    )
    monkeypatch.setattr(
        atu,
        "EXTENDED_BANDS",
        (("40m", 7_050_000, True), ("20m", 14_050_000, True)),
    )
    row = {
        "candidate": "41r-17c",
        "radiator_ft": 41.0,
        "counterpoise_ft": 17.0,
        "deployment": "test",
        "ground": "average",
        "conductivity": "copper",
        "band": "40m",
        "frequency_hz": 7_050_000,
    }

    with pytest.raises(ValueError, match="missing="):
        atu._validate_direct_41_17_ensemble([row])

    complete = [
        row,
        {**row, "band": "20m", "frequency_hz": 14_050_000},
    ]
    with pytest.raises(ValueError, match="duplicates="):
        atu._validate_direct_41_17_ensemble([*complete, row.copy()])


def test_direct_nec_validation_accepts_the_exact_expected_ensemble(
    monkeypatch,
) -> None:
    import antenna_lab.atu as atu

    monkeypatch.setattr(
        atu, "DIRECT_DEPLOYMENTS", {"test": (0.5, 20.0, 0.1, 90.0)}
    )
    monkeypatch.setattr(atu, "GROUNDS", {"average": (13.0, 0.005)})
    monkeypatch.setattr(
        atu, "ATU_DIRECT_CONDUCTIVITIES", (("copper", 58_000_000.0),)
    )
    monkeypatch.setattr(
        atu, "EXTENDED_BANDS", (("20m", 14_050_000, True),)
    )
    row = {
        "candidate": "41r-17c",
        "radiator_ft": 41.0,
        "counterpoise_ft": 17.0,
        "deployment": "test",
        "ground": "average",
        "conductivity": "copper",
        "band": "20m",
        "frequency_hz": 14_050_000,
    }

    assert atu._validate_direct_41_17_ensemble([row]) == [row]


def test_zm2_profile_matches_owned_prebuilt_range() -> None:
    from antenna_lab.atu import ZM2_PROFILE

    assert ZM2_PROFILE.label == "EMTECH ZM-2 BNC prebuilt coupled Z-match"
    assert ZM2_PROFILE.supports(3.5e6)
    assert ZM2_PROFILE.supports(30.0e6)
    assert not ZM2_PROFILE.supports(3.49e6)
    assert not ZM2_PROFILE.supports(30.01e6)
