"""Command-line interface for antenna-lab."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from antenna_lab.kh1_nec import run_study
from antenna_lab.measurements import load_impedance_measurements
from antenna_lab.optimization import (
    compare_candidate,
    run_optimization,
    verify_manifest,
)
from antenna_lab.plotting import plot_analytical_pattern
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
