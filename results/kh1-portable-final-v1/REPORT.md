# KH1 portable antenna system decision

## Executive summary

**Absolute winner:** the resonant linked dipole, at 82.8% p10 worst-band final efficiency. It requires physical link changes on every band transition.

**Best no-touch system:** 52/28 ft direct radiator/counterpoise through a compact 4:1 transformer, at 55.0% p10 and 69.6% p50 worst-band efficiency.

**Recommended overall:** 44/14 ft with the same 4:1 interface. Its 54.7% robust result gives up only 0.3% absolute efficiency while removing 22 ft of wire.

Relative to the resonant reference, the recommendation retains 66.0% of robust radiated power: a 34.0% sacrifice or 1.80 dB.

**Legacy 41/17 result:** rejected. The untransformed build has 0% all-band success at 2.5:1 and a 50.8% rollback-flag rate.

## What surprised us

- A lossy 4:1 interface improves total radiated power because it moves the loads into the actual KH1 discrete network's useful range. Low transformer SWR alone was never the objective.
- The balanced doublet can have a good median but a very poor lower tail; mismatch-enhanced feedline loss dominates hostile 20/17 m cases.
- The direct 44/14 system is nearly tied with much longer wires once deployment, ground, conductor, transformer, tuner, and mismatch envelopes are composed.
- The raw highest-median non-reference designs often miss 2.5:1. Rankings therefore require the documented match-safe gate.

## Family screen

| Family | Winner | p10 worst-band | p50 worst-band | Median | All-band <=2.5 | Rollback flag |
|---|---|---:|---:|---:|---:|---:|
| linked_dipole_reference | `linked-dipole-five-band` | 82.8% | 82.8% | 88.0% | 100.0% | 0.0% |
| direct_counterpoise | `direct-52r-28c-z4` | 55.0% | 69.6% | 72.7% | 100.0% | 0.0% |
| radial_vertical | `vertical-32r-4x12-z1` | 53.2% | 59.2% | 78.2% | 0.0% | 30.0% |
| ocfd | `ocfd-68ft-f0.36-z4` | 50.5% | 63.5% | 68.7% | 93.8% | 1.2% |
| trap_loaded | `trap-60ft-20m-traps-z1` | 21.1% | 28.9% | 45.3% | 0.0% | 51.2% |
| balanced_doublet | `doublet-58r-32l` | 11.9% | 15.7% | 62.1% | 24.1% | 21.9% |
| efhw | `efhw-62ft-f0.01-z49` | 4.9% | 7.7% | 17.3% | 0.0% | 80.8% |

## What failed

- `direct-41r-17c-z1`: 31.7% p10 worst-band, 0.0% all-band <=2.5, 50.8% rollback flag.
- `efhw-62ft-f0.01-z49`: 4.9% p10 worst-band, 0.0% all-band <=2.5, 80.8% rollback flag.
- `trap-60ft-20m-traps-z1`: 21.1% p10 worst-band, 0.0% all-band <=2.5, 51.2% rollback flag.
- `doublet-58r-32l`: 11.9% p10 worst-band, 24.1% all-band <=2.5, 21.9% rollback flag.
- `fan-five-band-z1`: 7.4% p10 worst-band, 50.0% all-band <=2.5, 10.0% rollback flag.

The EFHW result applies to the modeled compact 49:1 implementation, not every EFHW. The fan and trap entries are coarse sentinels, sufficient to pivot effort but not universal impossibility proofs.

## Build next

Build the 44 ft radiator + 14 ft counterpoise with a measured 4:1 transformer and separate choke. Also retain taps or extension points for 12, 16, and 28 ft counterpoises. Measure the tuner-plane complex impedance and RF power budget before changing lengths.

## Physical validation plan

1. Characterize the 4:1 transformer and choke independently with calibrated two-port measurements into representative complex loads; separate mismatch from dissipation.
2. Measure raw R+jX at both antenna and KH1 tuner planes for 44/12, 44/14, 44/16, and 52/28 on all five bands, with tuner bypassed.
3. Repeat ground-side, ground-collinear, table-side, and table-collinear deployments over poor and average ground; record wire height, soil, weather, and conductor.
4. Record KH1 L/C/Z diagnostic states, residual SWR, tune power, and any power fallback. Compare the actual state with the model's minimum-SWR and maximum-transducer states.
5. Measure forward/reflected power before the tuner and delivered power after the transformer/choke with calibrated couplers; use thermal or calorimetric checks for transformer loss where feasible.
6. Run paired field-strength or WSPR tests against the linked resonant dipole without moving the support or receiver, alternating frequently to suppress propagation drift.
7. Update the profile and loss envelopes from measurements, rerun the committed commands, and accept the 44/14 build only if every band stays below the chosen rollback threshold in the deployment matrix.

## Reproduce

```sh
PYTHONPATH=src uv run antenna-lab run-kh1-portable-coarse-study \
  --config configs/kh1-portable-refine-v1.json \
  --output build/kh1-portable-refine-v1 --nec2c /path/to/nec2c --jobs 8
gh run download 31750551947 \
  --name kh1-portable-nec-v2-31750551947 \
  --dir build/upstream-artifacts-31750551947
PYTHONPATH=src uv run antenna-lab run-kh1-comparative-study \
  --nec-artifact build/upstream-artifacts-31750551947 \
  --portable-study build/kh1-portable-refine-v1 \
  --output build/kh1-portable-comparative-v1
PYTHONPATH=src uv run antenna-lab run-kh1-final-decision \
  --config configs/kh1-portable-final-v1.json \
  --output results/kh1-portable-final-v1
uv run antenna-lab verify-results results/kh1-portable-final-v1
```

## Interpretation limits

All quantiles are equal-weight engineering sensitivities, not probabilities. Exact KH1 L/C bank values remain secondary-source corroborated. The 2.5:1 rollback flag is conservative and not an Elecraft-published trip point. Ground and common-mode behavior are simplified NEC/system models; human coupling, wet foliage, and routing remain field-validation items.

See the CSV files beside this report for the seven rankings, Pareto shortlist, per-band power budgets, deployment sensitivity, complexity, linked-reference delta, and failed sentinels.
