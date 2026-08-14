# KH1 portable antenna system decision

## Executive summary

**Absolute winner:** the resonant linked dipole at 82.8% p10 worst-band efficiency; it needs link changes for every band.

**Best no-touch system:** 52/28 ft through a 4:1 transformer at 55.0% p10 and 69.6% p50 worst-band efficiency.

**Recommended for this operator:** a direct-fed 41 ft radiator + 28 ft counterpoise, opened at 14 ft only on 17 m. It achieves 69.1% p10 worst-band efficiency and 100% all-band success at 2.5:1.

For weights 40/20 = 5, 30 = 3, and 17/15 = 2, weighted p10/p50/p90 efficiency is 77.8%/82.9%/88.1%. The 40/20 efficiency floor is 74.8%/81.6%/88.2%, with 100% modeled match success on those must bands.

Relative to the resonant reference, the recommendation retains 83.4% of robust radiated power, a 0.79 dB deficit.

**Legacy 41/17:** rejected: 0% all-band success at 2.5:1 and 50.8% rollback flags.

## What p10, p50, and p90 physically look like

These are points in an equal-weight engineering sensitivity set, not weather probabilities. P10 means only 10% of modeled cases scored lower; p50 is the middle case; p90 means 90% scored lower.

| Case | Deployment | Ground | Wire | Tuner profile/loss | Weighted | 40 m | 30 m | 20 m | 17 m | 15 m |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| p10 | table_collinear_30 | average | ccs_mid | khatu1/conservative | 77.8% | 81.9% | 68.8% | 76.4% | 82.4% | 79.6% |
| p50 | ground_side_20 | poor | ccs_mid | khatu1/nominal | 83.0% | 83.7% | 73.4% | 86.3% | 84.1% | 85.9% |
| p90 | table_side_30 | average | copper | khatu1/optimistic | 88.1% | 90.1% | 82.4% | 88.2% | 89.6% | 89.6% |

The low tail is a combination, not a single poor-ground switch. Conductor resistance and the conservative KHATU1 loss envelope are usually the largest modeled penalties. Deployment and ground also change the impedance presented to the tuner. Poor soil is not automatically the worst case because an impedance shift can reduce tuner loss even while earth loss increases.

## Why counterpoise length still matters

The counterpoise is the other half of the RF circuit, not an ideal zero-ohm ground. It carries current, radiates, and couples capacitively to earth. On 17 m, 28 ft is about one-half wavelength while 14 ft is about one-quarter wavelength, so opening the link substantially changes current phase and feed impedance. Earth coupling shifts and damps that behavior; it does not erase electrical length.

The model places the counterpoise close to real ground rather than bonding it to earth. A disconnected outer tail is a clean open in the model. In the field, separate and stow that tail away from the active 14 ft section; folding it alongside the active wire creates a coupled stub not represented here.

## Family screen

| Family | Winner | p10 worst-band | p50 worst-band | Median | All-band <=2.5 | Rollback |
|---|---|---:|---:|---:|---:|---:|
| linked_dipole_reference | `linked-dipole-five-band` | 82.8% | 82.8% | 88.0% | 100.0% | 0.0% |
| linked_counterpoise | `direct-41r-28c-linked14` | 69.1% | 76.8% | 83.3% | 100.0% | 0.0% |
| direct_counterpoise | `direct-52r-28c-z4` | 55.0% | 69.6% | 72.7% | 100.0% | 0.0% |
| radial_vertical | `vertical-32r-4x12-z1` | 53.2% | 59.2% | 78.2% | 0.0% | 30.0% |
| ocfd | `ocfd-68ft-f0.36-z4` | 50.5% | 63.5% | 68.7% | 93.8% | 1.2% |
| trap_loaded | `trap-60ft-20m-traps-z1` | 21.1% | 28.9% | 45.3% | 0.0% | 51.2% |
| balanced_doublet | `doublet-58r-32l` | 11.9% | 15.7% | 62.1% | 24.1% | 21.9% |
| efhw | `efhw-62ft-f0.01-z49` | 4.9% | 7.7% | 17.3% | 0.0% | 80.8% |

## What failed

- `direct-41r-17c-z1`: 31.7% p10 worst-band, 0.0% all-band <=2.5, 50.8% rollback flags.
- `efhw-62ft-f0.01-z49`: 4.9% p10 worst-band, 0.0% all-band <=2.5, 80.8% rollback flags.
- `trap-60ft-20m-traps-z1`: 21.1% p10 worst-band, 0.0% all-band <=2.5, 51.2% rollback flags.
- `doublet-58r-32l`: 11.9% p10 worst-band, 24.1% all-band <=2.5, 21.9% rollback flags.
- `fan-five-band-z1`: 7.4% p10 worst-band, 50.0% all-band <=2.5, 10.0% rollback flags.

The EFHW result applies to the modeled compact 49:1 implementation, not every EFHW. Fan and trap entries are coarse sentinels, not impossibility proofs.

## Build next

Build 41 ft of radiator and 28 ft of counterpoise with a low-resistance connector or banana-plug break 14 ft from the feed. Leave it closed on 40/30/20/15 and open it only on 17 m. Add strain relief and physically separate the open outer tail. No 4:1 transformer is part of this recommendation.

## Physical validation plan

1. Measure raw R+jX at the antenna and tuner planes with the 28 ft link closed and the 14 ft link open, tuner bypassed.
2. Repeat ground-side, ground-collinear, table-side, and table-collinear deployments over poor and average ground; record heights, soil, weather, routing, and conductor.
3. Record KH1 L/C/Z states, residual SWR, tune power, and power fallback on all five bands.
4. Compare closed versus open contact resistance and test the open tail both separated and folded nearby to measure the coupling omitted by the model.
5. Run paired field-strength or WSPR tests against a resonant linked dipole without moving the support or receiver.
6. Replace model envelopes with measurements and accept the build only if 40/20 always meet the operational match threshold and all five bands remain usable.

## Reproduce

```sh
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

Quantiles are equal-weight engineering sensitivities, not probabilities. The 2.5:1 rollback flag is conservative, not an Elecraft-published trip point. Ground/common-mode behavior and the open link are simplified; connector loss, people, wet foliage, and coupled-tail routing require field validation.

See the adjacent CSV files for rankings, per-band p10/p50/p90, representative power budgets, factor sensitivity, percentile scenarios, complexity, and linked-reference delta.
