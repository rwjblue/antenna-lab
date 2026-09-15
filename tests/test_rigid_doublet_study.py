import csv
import hashlib
import json
import math
from copy import deepcopy

import pytest

from antenna_lab.nec import NecResult
from antenna_lab.rigid_doublet_study import (
    continuous_l_match,
    line_rows,
    minimum_routed_length,
    rank_lengths,
    run_rigid_doublet_study,
)
from antenna_lab.transmission_line import C_FT_S, LineParameters, input_impedance


@pytest.mark.parametrize("frequency", [7.1e6, 14.2e6, 28.5e6])
@pytest.mark.parametrize(
    "load", [complex(12.5), complex(200), 25 - 100j, 25 + 100j, 800 - 1200j]
)
def test_continuous_l_match_reconstructs_50_ohms(load, frequency) -> None:
    result = continuous_l_match(load, frequency, 1e6, 1e6)
    series_z = 2j * math.pi * frequency * result["ideal_l_uh"] * 1e-6
    shunt_y = 2j * math.pi * frequency * result["ideal_c_pf"] * 1e-12
    if result["ideal_topology"] == "source_shunt":
        matched = 1 / (1 / (load + series_z) + shunt_y)
    else:
        assert result["ideal_topology"] == "load_shunt"
        matched = series_z + 1 / (1 / load + shunt_y)

    assert result["ideal_l_uh"] >= 0
    assert result["ideal_c_pf"] >= 0
    assert result["continuous_lc_screen"]
    assert matched == pytest.approx(50 + 0j, abs=1e-9)


def test_50_ohm_load_needs_no_components() -> None:
    result = continuous_l_match(50 + 0j, 7.1e6, 20, 1300)
    assert result["ideal_l_uh"] == 0
    assert result["ideal_c_pf"] == 0
    assert result["continuous_lc_screen"]


@pytest.mark.parametrize(
    ("load", "topology"), [(25 + 100j, "load_shunt"), (25 - 100j, "source_shunt")]
)
def test_match_avoids_topology_requiring_negative_component(load, topology) -> None:
    result = continuous_l_match(load, 14.2e6, 20, 1300)
    assert result["ideal_topology"] == topology
    assert result["ideal_l_uh"] > 0
    assert result["ideal_c_pf"] > 0


def test_exact_component_limits_pass_and_each_smaller_limit_fails() -> None:
    frequency = 7.1e6
    # A 25-ohm resistor requires series +j25 ohms, then source shunt +j0.02 S.
    inductance = 25 / (2 * math.pi * frequency) * 1e6
    capacitance = 0.02 / (2 * math.pi * frequency) * 1e12
    exact = continuous_l_match(25 + 0j, frequency, inductance, capacitance)
    too_little_l = continuous_l_match(
        25 + 0j, frequency, inductance * 0.99, capacitance
    )
    too_little_c = continuous_l_match(
        25 + 0j, frequency, inductance, capacitance * 0.99
    )

    assert exact["continuous_lc_screen"]
    assert not too_little_l["continuous_lc_screen"]
    assert not too_little_c["continuous_lc_screen"]
    assert too_little_l["ideal_l_uh"] == pytest.approx(inductance)
    assert too_little_c["ideal_c_pf"] == pytest.approx(capacitance)


@pytest.mark.parametrize(
    "arguments",
    [
        (-1 + 0j, 7.1e6, 20, 1300),
        (0 + 100j, 7.1e6, 20, 1300),
        (50 + 0j, 0, 20, 1300),
        (50 + 0j, -7.1e6, 20, 1300),
        (50 + 0j, 7.1e6, 0, 1300),
        (50 + 0j, 7.1e6, 20, -1300),
        (complex(math.nan), 7.1e6, 20, 1300),
        (complex(50, math.inf), 7.1e6, 20, 1300),
        (50 + 0j, math.inf, 20, 1300),
        (50 + 0j, 7.1e6, math.nan, 1300),
    ],
)
def test_matching_rejects_invalid_inputs(arguments) -> None:
    with pytest.raises(ValueError):
        continuous_l_match(*arguments)


def test_lossless_line_repeats_every_electrical_half_wavelength() -> None:
    line = LineParameters(480, 0.97, 0)
    frequency = 14.2e6
    half_wave_ft = C_FT_S * line.velocity_factor / (2 * frequency)
    load = 25 - 600j
    initial = input_impedance(load, frequency, 31, line)
    repeated = input_impedance(load, frequency, 31 + half_wave_ft, line)
    quarter_turn = input_impedance(load, frequency, 31 + half_wave_ft / 2, line)

    assert repeated == pytest.approx(initial, rel=1e-11, abs=1e-9)
    assert quarter_turn == pytest.approx(line.characteristic_impedance_ohm**2 / initial)


def test_minimum_route_includes_horizontal_reach_and_slack() -> None:
    routing = dict(tuner_height_ft=3, horizontal_offset_ft=6, slack_ft=2)
    assert minimum_routed_length(30, routing) == pytest.approx(math.hypot(27, 6) + 2)
    assert minimum_routed_length(30, routing) > 29


@pytest.mark.parametrize(
    "routing",
    [
        dict(tuner_height_ft=3, horizontal_offset_ft=6, slack_ft=-2),
        dict(tuner_height_ft=3, horizontal_offset_ft=math.nan, slack_ft=2),
        dict(tuner_height_ft=math.inf, horizontal_offset_ft=6, slack_ft=2),
    ],
)
def test_minimum_route_rejects_unphysical_inputs(routing) -> None:
    with pytest.raises(ValueError):
        minimum_routed_length(30, routing)


@pytest.fixture
def study_config() -> dict:
    return dict(
        study_id="rigid-test",
        geometry=dict(
            arm_length_ft=17,
            feed_height_ft=30,
            arm_elevation_deg=30,
            radius_m=0.0015,
            arm_segments=31,
        ),
        conductivity_s_m=1.4e6,
        grounds={"average": dict(epsilon_r=13, conductivity_s_m=0.005)},
        cases=[dict(id="reference"), dict(id="flat", arm_elevation_deg=0)],
        reference_case="reference",
        bands_mhz={"40m": 7.1, "20m": 14.2},
        line_sweep_ft=dict(start=28, stop=32, step=2),
        spot_lengths_ft=[31, 32],
        tuner_limits=dict(max_l_uh=20, max_c_pf=1300, advertised_swr=10),
        routing=dict(tuner_height_ft=3, horizontal_offset_ft=6, slack_ft=2),
        line_scenarios=[
            dict(
                id="homebrew_nominal",
                z0_ohm=480,
                velocity_factor=0.97,
                loss_db_per_100ft_at_10mhz=0.05,
            ),
            dict(
                id="wet_stress",
                z0_ohm=450,
                velocity_factor=0.9,
                loss_db_per_100ft_at_10mhz=0.3,
            ),
        ],
        balun_impedance_ratios=[1, 4],
        sources={},
        assumptions=["Test fixture only."],
    )


@pytest.fixture
def fake_nec_rows(study_config) -> list[dict]:
    return [
        dict(
            case_id=case["id"],
            band=band,
            frequency_mhz=frequency,
            feed_height_ft=30,
            feedpoint_r_ohm=25,
            feedpoint_x_ohm=-200,
        )
        for case in study_config["cases"]
        for band, frequency in study_config["bands_mhz"].items()
    ]


def test_line_rows_counts_transform_ratio_and_routing(
    study_config, fake_nec_rows
) -> None:
    rows = line_rows(study_config, fake_nec_rows)
    # Reference: 4 lengths × 2 bands × 2 lines × 2 ratios; flat: 2 spot lengths.
    assert len(rows) == 48
    reference = [row for row in rows if row["case_id"] == "reference"]
    alternate = [row for row in rows if row["case_id"] == "flat"]
    assert len(reference) == 32
    assert len(alternate) == 16
    assert {row["length_ft"] for row in alternate} == {31, 32}
    assert rows == line_rows(study_config, fake_nec_rows)
    assert all(row["route_feasible"] == (row["length_ft"] >= 30) for row in rows)
    for row in rows:
        assert row["tuner_load_r_ohm"] == pytest.approx(
            row["line_input_r_ohm"] / row["balun_impedance_ratio"]
        )
        assert row["tuner_load_x_ohm"] == pytest.approx(
            row["line_input_x_ohm"] / row["balun_impedance_ratio"]
        )
        assert row["length_m"] == pytest.approx(row["length_ft"] * 0.3048)
        assert 0 < row["line_efficiency"] < 1
        assert row["line_loss_db"] > 0


def test_length_ranking_counts_reference_cases_and_filters_short_routes(
    study_config, fake_nec_rows
) -> None:
    rows = line_rows(study_config, fake_nec_rows)
    ranking = rank_lengths(study_config, rows)
    assert len(ranking) == 6
    assert {row["length_ft"] for row in ranking} == {30, 31, 32}
    assert all(row["dry_cases"] == 2 and row["all_cases"] == 4 for row in ranking)
    assert ranking == rank_lengths(study_config, list(reversed(rows)))


@pytest.mark.parametrize(
    "override",
    [
        dict(line_sweep_ft=dict(start=28, stop=32, step=0)),
        dict(line_sweep_ft=dict(start=32, stop=28, step=2)),
        dict(spot_lengths_ft=[-1]),
        dict(spot_lengths_ft=[math.nan]),
        dict(balun_impedance_ratios=[0]),
        dict(balun_impedance_ratios=[math.inf]),
    ],
)
def test_line_rows_reject_invalid_sweep_inputs(study_config, fake_nec_rows, override):
    study_config.update(override)
    with pytest.raises(ValueError):
        line_rows(study_config, fake_nec_rows)


def test_study_writes_reproducible_outputs_with_source_hashes(
    tmp_path, monkeypatch, study_config
) -> None:
    import antenna_lab.rigid_doublet_study as study

    config_path = tmp_path / "study.json"
    config_path.write_text(json.dumps(study_config))
    solver = tmp_path / "nec2c"
    solver.write_bytes(b"fake solver binary for provenance")
    cache = tmp_path / "cache"
    output = tmp_path / "output"
    generated_decks = {}

    def fake_run_cached(deck, cache_dir, executable):
        assert executable == solver
        cache_dir.mkdir(exist_ok=True)
        digest = hashlib.sha256(deck.encode()).hexdigest()
        deck_path = cache_dir / f"{digest[:16]}.nec"
        deck_path.write_text(deck)
        output_path = deck_path.with_suffix(".out")
        output_path.write_text(f"Fake output for {digest}\n")
        generated_decks[digest] = deck_path
        frequency = float(
            next(
                card.split()[5] for card in deck.splitlines() if card.startswith("FR ")
            )
        )
        return (
            NecResult(
                frequency,
                25 - 200j,
                0.85,
                ((20, 90, 1.5), (45, 90, 4.0), (90, 90, 2.5)),
            ),
            deck_path,
            output_path,
            False,
        )

    monkeypatch.setattr(study, "run_cached", fake_run_cached)
    monkeypatch.setattr(study, "_solver_version", lambda executable: "fake-nec2c v1")
    first = run_rigid_doublet_study(
        config_path, output, nec2c=solver, cache_dir=cache, jobs=1
    )
    contents = {path.name: path.read_bytes() for path in output.iterdir()}
    # Disabled optional outputs from a previous run must not survive the manifest.
    for filename in (
        "line-length-sensitivity.png",
        "numerical_validation.json",
        "numerical_validation.csv",
    ):
        (output / filename).write_text("stale generated artifact")
    second = run_rigid_doublet_study(
        config_path, output, nec2c=solver, cache_dir=cache, jobs=2
    )

    assert first == second
    assert first["nec_cases"] == 4
    assert first["line_cases"] == 48
    assert (
        first["config_sha256"] == hashlib.sha256(config_path.read_bytes()).hexdigest()
    )
    assert first["solver_sha256"] == hashlib.sha256(solver.read_bytes()).hexdigest()
    assert first["solver_version"] == "fake-nec2c v1"
    assert first["assumptions"] == study_config["assumptions"]
    assert json.loads((output / "config.json").read_text()) == study_config
    assert contents == {path.name: path.read_bytes() for path in output.iterdir()}
    with (output / "nec_loads.csv").open() as handle:
        nec_rows = list(csv.DictReader(handle))
    assert len(nec_rows) == 4
    for row in nec_rows:
        deck_path = generated_decks[row["nec_deck_sha256"]]
        assert (
            row["nec_output_sha256"]
            == hashlib.sha256(deck_path.with_suffix(".out").read_bytes()).hexdigest()
        )
    for entry in (output / "SHA256SUMS").read_text().splitlines():
        digest, filename = entry.split("  ", 1)
        assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == digest
    compact = run_rigid_doublet_study(
        config_path, output, nec2c=solver, cache_dir=cache, jobs=1, compact=True
    )
    assert not compact["full_line_sweep_included"]
    assert not (output / "line_sweep.csv").exists()
    assert (output / "reference_spot_checks.csv").is_file()


@pytest.mark.parametrize("invalid", ["duplicate", "no_reference"])
def test_study_rejects_ambiguous_case_provenance(
    tmp_path, study_config, invalid
) -> None:
    config = deepcopy(study_config)
    if invalid == "duplicate":
        config["cases"].append(dict(id="reference"))
    else:
        config["reference_case"] = "absent"
    config_path = tmp_path / "invalid.json"
    config_path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="unique IDs and contain the reference"):
        run_rigid_doublet_study(config_path, tmp_path / "output")
