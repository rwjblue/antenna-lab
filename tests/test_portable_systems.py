from antenna_lab.portable_systems import (
    _aggregate_systems,
    build_designs,
    build_system_candidates,
    load_coarse_config,
)


def test_coarse_config_covers_every_required_candidate_family() -> None:
    config = load_coarse_config("configs/kh1-portable-coarse-v1.json")
    designs = build_designs(config)

    assert {design.family for design in designs} == {
        "direct_counterpoise",
        "ocfd",
        "efhw",
        "radial_vertical",
        "fan_dipole",
        "trap_loaded",
    }
    systems = build_system_candidates(designs, config)
    ratios = {system.transformer_ratio for system in systems}
    assert {0.25, 1.0, 4.0, 6.0, 9.0, 49.0} <= ratios


def test_aggregate_ranks_by_robust_worst_band_efficiency() -> None:
    config = load_coarse_config("configs/kh1-portable-coarse-v1.json")
    systems = build_system_candidates(build_designs(config), config)[:2]
    rows = []
    for system, efficiency in zip(systems, (0.8, 0.6), strict=True):
        for band in config["bands"]:
            rows.append(
                {
                    "candidate_id": system.id,
                    "objective": "best_swr",
                    "profile": "khatu1",
                    "tuner_loss_envelope": "nominal",
                    "component_loss_envelope": 1,
                    "band": band,
                    "final_efficiency": efficiency,
                    "target_met": True,
                    "likely_power_rollback": False,
                    "input_swr": 1.2,
                }
            )

    ranked = _aggregate_systems(systems, rows)

    assert ranked[0]["candidate_id"] == systems[0].id
    assert ranked[0]["worst_band_final_efficiency_p10"] == 0.8
