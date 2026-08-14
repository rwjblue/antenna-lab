"""Command-line interface for antenna-lab."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from antenna_lab.atu import (
    ATU_PROFILE_IDS,
    LOSS_ENVELOPES,
    PROFILES,
    assemble_atu_loss_study,
    run_atu_direct_nec_stage,
    run_atu_loss_study,
    run_atu_profile_stage,
    solve_switched_l_network,
    solve_zm2,
)
from antenna_lab.comparative_systems import run_comparative_study
from antenna_lab.decision_report import run_final_decision
from antenna_lab.kh1_nec import run_study
from antenna_lab.kh1_pipeline import (
    assemble_study,
    run_direct_nec_shard,
    run_doublet_grid_shard,
    run_doublet_nec_shard,
)
from antenna_lab.measurements import load_impedance_measurements
from antenna_lab.optimization import (
    compare_candidate,
    run_optimization,
    verify_manifest,
)
from antenna_lab.plotting import plot_analytical_pattern
from antenna_lab.portable_systems import run_coarse_system_study
from antenna_lab.transmission_line import swr

DEFAULT_MEASUREMENTS = Path("data/measured/58ft_doublet_2026-08-08.csv")
DEFAULT_CONFIG = Path("configs/58ft-doublet-v1.0.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="antenna-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze-baseline", help="Summarize measured radio-end impedance and raw SWR"
    )
    analyze.add_argument("--measurements", type=Path, default=DEFAULT_MEASUREMENTS)

    optimize = subparsers.add_parser(
        "optimize-doublet", help="Run the deterministic uncertainty-aware grid"
    )
    optimize.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    optimize.add_argument("--output", type=Path, required=True)

    compare = subparsers.add_parser(
        "compare-configs", help="Compare a candidate with the measured baseline"
    )
    compare.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    compare.add_argument("--radiator-ft", type=float, required=True)
    compare.add_argument("--feedline-ft", type=float, required=True)

    pattern = subparsers.add_parser(
        "plot-pattern", help="Plot the analytical thin-wire pattern (not NEC)"
    )
    pattern.add_argument("--output", type=Path, required=True)
    pattern.add_argument("--frequency-mhz", type=float, required=True)
    pattern.add_argument("--center-height-ft", type=float, required=True)
    pattern.add_argument("--radiator-ft", type=float, default=58.0)
    pattern.add_argument("--apex-angle-deg", type=float, default=120.0)

    nec_study = subparsers.add_parser(
        "run-kh1-nec-study",
        help="Run the actual NEC-2 KH1 portable-antenna study",
    )
    nec_study.add_argument("--output", type=Path, required=True)
    nec_study.add_argument("--measurements", type=Path, default=DEFAULT_MEASUREMENTS)
    nec_study.add_argument("--nec2c", type=Path)
    nec_study.add_argument("--jobs", type=int)

    doublet_nec_shard = subparsers.add_parser(
        "run-kh1-doublet-nec-shard",
        help="Run one shard of the KH1 doublet NEC feedpoint cases",
    )
    doublet_nec_shard.add_argument("--output", type=Path, required=True)
    doublet_nec_shard.add_argument("--shard-index", type=int, required=True)
    doublet_nec_shard.add_argument("--shard-count", type=int, required=True)
    doublet_nec_shard.add_argument("--nec2c", type=Path)
    doublet_nec_shard.add_argument("--jobs", type=int)

    direct_nec_shard = subparsers.add_parser(
        "run-kh1-direct-nec-shard",
        help="Run one shard of the KH1 direct-fed NEC cases",
    )
    direct_nec_shard.add_argument("--output", type=Path, required=True)
    direct_nec_shard.add_argument("--shard-index", type=int, required=True)
    direct_nec_shard.add_argument("--shard-count", type=int, required=True)
    direct_nec_shard.add_argument("--nec2c", type=Path)
    direct_nec_shard.add_argument("--jobs", type=int)

    doublet_grid_shard = subparsers.add_parser(
        "run-kh1-doublet-grid-shard",
        help="Evaluate one shard of the KH1 doublet uncertainty grid",
    )
    doublet_grid_shard.add_argument("--input", type=Path, required=True)
    doublet_grid_shard.add_argument("--output", type=Path, required=True)
    doublet_grid_shard.add_argument(
        "--measurements", type=Path, default=DEFAULT_MEASUREMENTS
    )
    doublet_grid_shard.add_argument("--shard-index", type=int, required=True)
    doublet_grid_shard.add_argument("--shard-count", type=int, required=True)

    assemble_nec = subparsers.add_parser(
        "assemble-kh1-nec-study",
        help="Merge KH1 shard artifacts and produce the canonical result package",
    )
    assemble_nec.add_argument("--input", type=Path, required=True)
    assemble_nec.add_argument("--output", type=Path, required=True)
    assemble_nec.add_argument("--measurements", type=Path, default=DEFAULT_MEASUREMENTS)
    assemble_nec.add_argument("--nec2c", type=Path)

    solve_atu = subparsers.add_parser(
        "solve-atu-loss",
        help="Enumerate a tuner profile for one complex antenna load",
    )
    solve_atu.add_argument(
        "--profile", choices=sorted(PROFILES) + ["zm2"], required=True
    )
    solve_atu.add_argument("--frequency-mhz", type=float, required=True)
    solve_atu.add_argument("--resistance-ohm", type=float, required=True)
    solve_atu.add_argument("--reactance-ohm", type=float, required=True)
    solve_atu.add_argument(
        "--loss-envelope",
        choices=[item.id for item in LOSS_ENVELOPES],
        default="nominal",
    )
    solve_atu.add_argument(
        "--objective",
        choices=["best_swr", "lowest_loss_under_target"],
        default="lowest_loss_under_target",
    )

    atu_study = subparsers.add_parser(
        "run-atu-loss-study",
        help="Model tuner and end-to-end loss for the direct-fed 41/17 antenna",
    )
    atu_study.add_argument("--output", type=Path, required=True)
    atu_study.add_argument("--direct-nec-csv", type=Path)
    atu_study.add_argument("--nec2c", type=Path)
    atu_study.add_argument("--jobs", type=int, default=6)

    atu_direct = subparsers.add_parser(
        "run-atu-direct-nec",
        help="Generate the shared direct-fed 41/17 NEC load ensemble",
    )
    atu_direct.add_argument("--output", type=Path, required=True)
    atu_direct.add_argument("--nec2c", type=Path)
    atu_direct.add_argument("--jobs", type=int, default=6)

    atu_profile = subparsers.add_parser(
        "run-atu-profile-study",
        help="Evaluate one ATU profile against a generated NEC load ensemble",
    )
    atu_profile.add_argument("--output", type=Path, required=True)
    atu_profile.add_argument("--direct-nec-csv", type=Path, required=True)
    atu_profile.add_argument("--profile", choices=ATU_PROFILE_IDS, required=True)

    assemble_atu = subparsers.add_parser(
        "assemble-atu-loss-study",
        help="Assemble independently computed ATU profile artifacts",
    )
    assemble_atu.add_argument("--input", type=Path, required=True)
    assemble_atu.add_argument("--output", type=Path, required=True)

    coarse_systems = subparsers.add_parser(
        "run-kh1-portable-coarse-study",
        help="Run the cached-NEC multi-family KH1 system screen",
    )
    coarse_systems.add_argument(
        "--config",
        type=Path,
        default=Path("configs/kh1-portable-coarse-v1.json"),
    )
    coarse_systems.add_argument("--output", type=Path, required=True)
    coarse_systems.add_argument("--nec2c", type=Path)
    coarse_systems.add_argument("--jobs", type=int, default=6)

    comparative = subparsers.add_parser(
        "run-kh1-comparative-study",
        help="Compare refined portable candidates, doublets, and linked reference",
    )
    comparative.add_argument("--nec-artifact", type=Path, required=True)
    comparative.add_argument("--portable-study", type=Path, required=True)
    comparative.add_argument("--output", type=Path, required=True)
    comparative.add_argument(
        "--measurements", type=Path, default=DEFAULT_MEASUREMENTS
    )

    final_decision = subparsers.add_parser(
        "run-kh1-final-decision",
        help="Generate the durable seven-ranking KH1 decision package",
    )
    final_decision.add_argument(
        "--config", type=Path, default=Path("configs/kh1-portable-final-v1.json")
    )
    final_decision.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser(
        "verify-results", help="Verify a generated SHA256SUMS manifest"
    )
    verify.add_argument("result_directory", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "analyze-baseline":
        measurements = load_impedance_measurements(args.measurements)
        print("band frequency_mhz resistance_ohm reactance_ohm raw_swr_50ohm")
        for measurement in measurements:
            raw_swr = float(swr(measurement.impedance_ohm))
            print(
                f"{measurement.band:>3} {measurement.frequency_mhz:>13.3f} "
                f"{measurement.resistance_ohm:>14.1f} "
                f"{measurement.reactance_ohm:>14.1f} {raw_swr:>14.3f}"
            )
        print(f"reference_plane: {measurements[0].measurement_reference_plane}")
        return 0
    if args.command == "optimize-doublet":
        summary = run_optimization(args.config, args.output)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "compare-configs":
        comparison = compare_candidate(args.config, args.radiator_ft, args.feedline_ft)
        print(json.dumps(comparison, indent=2, sort_keys=True))
        return 0
    if args.command == "plot-pattern":
        plot_analytical_pattern(
            args.output,
            args.frequency_mhz * 1_000_000.0,
            args.center_height_ft,
            args.radiator_ft,
            args.apex_angle_deg,
        )
        print(args.output)
        return 0
    if args.command == "run-kh1-nec-study":
        summary = run_study(
            args.output,
            measurement_path=args.measurements,
            nec2c=args.nec2c,
            jobs=args.jobs,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "run-kh1-doublet-nec-shard":
        summary = run_doublet_nec_shard(
            args.output,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            nec2c=args.nec2c,
            jobs=args.jobs,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "run-kh1-direct-nec-shard":
        summary = run_direct_nec_shard(
            args.output,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            nec2c=args.nec2c,
            jobs=args.jobs,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "run-kh1-doublet-grid-shard":
        summary = run_doublet_grid_shard(
            args.output,
            input_dir=args.input,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            measurement_path=args.measurements,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "assemble-kh1-nec-study":
        summary = assemble_study(
            args.output,
            input_dir=args.input,
            measurement_path=args.measurements,
            nec2c=args.nec2c,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "solve-atu-loss":
        loss = next(
            item for item in LOSS_ENVELOPES if item.id == args.loss_envelope
        )
        load = complex(args.resistance_ohm, args.reactance_ohm)
        if args.profile == "zm2":
            result = solve_zm2(load, args.frequency_mhz * 1e6, loss)
        else:
            result = asdict(
                solve_switched_l_network(
                    PROFILES[args.profile],
                    load,
                    args.frequency_mhz * 1e6,
                    loss,
                    objective=args.objective,
                )
            )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=True))
        return 0
    if args.command == "run-atu-loss-study":
        summary = run_atu_loss_study(
            args.output,
            direct_nec_csv=args.direct_nec_csv,
            nec2c=args.nec2c,
            jobs=args.jobs,
        )
        print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True))
        return 0
    if args.command == "run-atu-direct-nec":
        summary = run_atu_direct_nec_stage(
            args.output, nec2c=args.nec2c, jobs=args.jobs
        )
        print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True))
        return 0
    if args.command == "run-atu-profile-study":
        summary = run_atu_profile_stage(
            args.output,
            direct_nec_csv=args.direct_nec_csv,
            profile_id=args.profile,
        )
        print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True))
        return 0
    if args.command == "assemble-atu-loss-study":
        summary = assemble_atu_loss_study(args.output, input_dir=args.input)
        print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=True))
        return 0
    if args.command == "run-kh1-portable-coarse-study":
        summary = run_coarse_system_study(
            args.config,
            args.output,
            nec2c=args.nec2c,
            jobs=args.jobs,
        )
        print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
        return 0
    if args.command == "run-kh1-comparative-study":
        summary = run_comparative_study(
            args.nec_artifact,
            args.portable_study,
            args.output,
            measurement_path=args.measurements,
        )
        print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
        return 0
    if args.command == "run-kh1-final-decision":
        summary = run_final_decision(args.config, args.output)
        print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
        return 0
    if args.command == "verify-results":
        valid, failures = verify_manifest(args.result_directory)
        if valid:
            print(f"verified: {args.result_directory}")
            return 0
        for failure in failures:
            print(failure)
        return 1
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
