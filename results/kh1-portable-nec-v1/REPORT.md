# KH1 portable antenna NEC-2 study

Solver: `nec2c 1.3.1`

## Method

The radiator and direct-wire impedance, loss, and pattern calculations in this result set were executed by NEC-2. The measured 58 ft / 28 ft radio-end impedances remain exact anchors because a bare-wire NEC deck cannot reproduce the installed insulation, trees, choke, connectors, and operator. NEC supplies the physical impedance change as radiator length/deployment changes; a lossy balanced-line ensemble carries that result to the radio.

An ideal L-match reactive-power metric separates the observed KH1 cases: hardest success **4.98**, easiest failure **8.27**, separator **6.42**. This is an empirical classifier, not a KH1 specification.

## Doublets

| case | radiator | line | all 40/30/20/17/15 | weakest band | Q p90 | worst line eff p10 |
|---|---:|---:|---:|---:|---:|---:|
| current 58/28 | 58.0 ft | 28.0 ft | 0.0% | 0.0% | 10.71 | 21.4% |
| classic 44/28 | 44.0 ft | 28.0 ft | 0.0% | 0.0% | 86.00 | 1.8% |
| 44 ft optimized line | 44.0 ft | 31.0 ft | 0.0% | 37.0% | 81.14 | 1.6% |
| 58 ft + 3 ft line | 58.0 ft | 31.0 ft | 100.0% | 100.0% | 5.70 | 19.7% |
| robust model best | 58.0 ft | 30.5 ft | 100.0% | 100.0% | 4.67 | 20.6% |

The percentages are fractions of the explicit NEC-geometry, line-parameter, reference-plane, and anchoring ensemble. They are not tune probabilities.

## Direct-fed wires

| case | wire | all five bands | weakest band | Q p90 | worst NEC efficiency p10 |
|---|---:|---:|---:|---:|---:|
| 35r-17c | 35/17 ft | 0.0% | 0.0% | 8.29 | 87.0% |
| 35r-25c | 35/25 ft | 0.0% | 0.0% | 7.68 | 86.2% |

## Resonant linked-dipole reference

| band | total length | R+jX | raw SWR | NEC efficiency |
|---|---:|---:|---:|---:|
| 40m | 67.41 ft | 56.0 -0.0j | 1.12 | 83.1% |
| 30m | 47.32 ft | 65.4 -0.0j | 1.31 | 87.8% |
| 20m | 34.38 ft | 64.9 -0.0j | 1.30 | 89.5% |
| 17m | 26.72 ft | 53.9 -0.0j | 1.08 | 88.9% |
| 15m | 22.84 ft | 51.1 -0.0j | 1.02 | 89.2% |

## Practical conclusion

**First reversible field test:** reversible 58.0 ft radiator / 30.5 ft line trial.

Measure radio-end R+jX and final KH1 SWR on all five bands before cutting the existing antenna.

## Reproduce

```bash
sudo apt-get install nec2c
uv sync --no-editable --extra plots --group dev
uv run antenna-lab run-kh1-nec-study --output results/kh1-portable-nec-v1
uv run antenna-lab verify-results results/kh1-portable-nec-v1
```

## Limitations

- NEC geometry omits trees, operator, choke, connectors, insulation and sparse spacers.
- Doublet station impedances are measured-reference-plane anchored; NEC supplies radiator changes.
- The KH1 Q separator is fitted to only three observed successes and two failures.
- Line efficiency excludes tuner/choke/common-mode/radiator loss; direct-wire NEC efficiency includes modeled wire and ground loss only.
