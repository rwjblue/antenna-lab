# antenna-lab

Reproducible amateur-radio antenna modeling, transmission-line analysis,
measurement calibration, optimization, and reporting. The first case study is
N1RWJ's portable 58 ft doublet with a 28 ft homebrew balanced feedline.

This project keeps observations separate from assumptions:

- RigExpert impedance and KXAT2 behavior are **measured/observed inputs**.
- Construction dimensions are **physical facts** with documented uncertainty.
- Feedline parameters and radiator changes are **modeled assumptions**.
- Line efficiency, SWR, and rankings are **derived/model outputs**, not measured
  radiation efficiency.

The current complete-system result recommends a **44 ft radiator, 14 ft explicit
counterpoise, compact 4:1 transformer, and separate choke** as the next KH1
build. It reaches 54.7% p10 worst-band pre-ATU-to-radiated efficiency in the
equal-weight model envelope, within 0.3 percentage point of the much longer
52/28 ft non-reference winner. The five-band resonant linked dipole remains the
absolute efficiency reference at 82.8%, but requires physical link changes.
See the [final decision report](results/kh1-portable-final-v1/REPORT.md) and
[evidence classification](docs/kh1-portable-system-evidence.md).

## Quick start

Requires Python 3.11 or newer.

```bash
uv sync --no-editable --extra plots --group dev
uv run antenna-lab analyze-baseline
uv run antenna-lab optimize-doublet --config configs/reference-small.json --output results/reference-small
uv run antenna-lab verify-results results/reference-small
```

Run the canonical full v1-compatible sweep:

```bash
uv run antenna-lab optimize-doublet \
  --config configs/58ft-doublet-v1.0.json \
  --output build/58ft-doublet-full
uv run antenna-lab verify-results build/58ft-doublet-full
```

Run a paired legacy-surrogate comparison when investigating radiator-length
changes:

```bash
uv run antenna-lab compare-configs --radiator-ft 57 --feedline-ft 28
```

This command belongs to the earlier surrogate optimizer; it is not the current
feedline-extension field recommendation.

Generate the analytical thin-wire pattern (this is not NEC/MININEC):

```bash
uv run antenna-lab plot-pattern --output build/pattern-17m.png --frequency-mhz 18.08 --center-height-ft 30
```

The same checks are exposed as file-based mise tasks:

```bash
mise run check
mise run reference
```

## Sharded NEC-2 study

The full KH1 study can still be run locally as one command:

```bash
sudo apt-get install nec2c
uv run antenna-lab run-kh1-nec-study \
  --output results/kh1-portable-nec-v2
```

GitHub Actions uses a shard-and-assemble pipeline instead. Two jobs calculate
doublet feedpoints, two jobs calculate the direct-fed cases, and eight jobs split
the expensive doublet uncertainty grid by radiator length. A final job merges
and validates every expected row, runs the smaller resonant-reference and
pattern calculations, creates `SHA256SUMS`, and uploads the canonical result
package.

Every compute job uploads its CSV, metadata, manifest, and runner log as a
separate workflow artifact. The final job uploads the complete result tree as
`kh1-portable-nec-v2-<run-id>`. Consequently, successful intermediate work is
still retrievable when a later shard or assembly job fails. Artifacts are kept
for 90 days, subject to the repository's Actions retention limit. Full generated
study trees are not checked into `results/`; reproduce them under `build/` or use
the corresponding verified workflow artifact. The final comparison uses the
newer manifest-verified source ensemble from
[run 31750551947](https://github.com/rwjblue/antenna-lab/actions/runs/31750551947).

The stage commands are also available for local or alternate CI orchestration:

```bash
antenna-lab run-kh1-doublet-nec-shard --help
antenna-lab run-kh1-direct-nec-shard --help
antenna-lab run-kh1-doublet-grid-shard --help
antenna-lab assemble-kh1-nec-study --help
```

## Project map

- `src/antenna_lab/`: reusable, typed Python package and CLI.
- `data/measured/`: immutable source transcription plus canonical normalized data.
- `data/reference/`: construction facts and provenance metadata.
- `models/`: model descriptions and machine-readable status labels.
- `configs/`: explicit optimization uncertainty and sweep definitions.
- `results/reference-small/`: fast deterministic regression result and hashes.
- `results/published-v1.0/`: selected canonical results imported from v1.0.
- `results/kh1-portable-final-v1/`: manifest-verified complete-system decision package.
- `reports/`: preserved v1.0 optimization and analytical-pattern artifacts.
- `docs/case-studies/`: interpretation for the physical 58 ft doublet.
- `archive/source-bundles/`: the two original ZIP archives, byte-for-byte.

Read [MODEL_LIMITATIONS.md](MODEL_LIMITATIONS.md) before treating modeled
efficiency or an exact quarter-foot optimum as authoritative. The historical
ChatGPT v0.1 archive is provenance only; v1.0 supersedes it for current results.

## Scientific status

The optimizer is a measurement-anchored, passive transmission-line and
radiator-surrogate ensemble. It is not a full-wave solver. The pattern command
uses an analytical thin-wire sinusoidal-current approximation with a Fresnel
ground-reflection model. These two models answer different questions and are
not relabeled as NEC or MININEC.

## License

Code and documentation are available under the MIT License. Measured antenna
data remain attributable to Rob Jackson / N1RWJ; preserve its provenance when
reusing it.

## Extended-band NEC coverage

The portable-wire study keeps its original hard objective—KH1 compatibility on
40/30/20/17/15 m—but now also runs direct-fed wires and resonant reference
dipoles on 80/60/12/10 m and an exploratory 6 m case. The measured-reference-
plane doublet optimization remains anchored to the seven measured 40–10 m
points; 80/60/6 m doublet results are NEC-only feedpoint/pattern results rather
than measured station-end predictions.

The assembled artifact includes `direct_candidates_by_band.csv`, with impedance,
raw SWR, NEC efficiency, and the existing generic topology/range proxy for every
candidate and modeled band. Device-specific tuner loss is intentionally handled
by the separate ATU-loss study rather than folded into antenna efficiency.

## ATU loss study

The antenna NEC result reports radiation efficiency at the antenna feedpoint; it
does not include tuner dissipation. The historical ATU study enumerates lossy
tuner states for the NEC 41/17 ft ensemble. The final multi-family study retests
that geometry and rejects it as a build recommendation: the untransformed
version has 0% all-band success at 2.5:1 and a 50.8% rollback-flag rate.

```bash
sudo apt-get install nec2c
uv run antenna-lab run-atu-loss-study --output build/atu-loss
uv run antenna-lab verify-results build/atu-loss
```

Device profiles currently cover the schematic-derived Elecraft KXAT2 and KXAT3,
an explicitly inferred KHATU1, a specification-range-fit LDG Z-11Pro II, and an
exploratory equivalent-circuit EMTECH ZM-2 model. See
[docs/atu-loss-model.md](docs/atu-loss-model.md) for equations, provenance,
interpretation, and the measurement plan needed to replace inferred inputs.
GitHub Actions computes the common NEC loads once, evaluates each tuner in a
separate matrix job, and publishes both intermediate and canonical artifacts.

## Multi-family system decision

The current study compares complete pre-ATU systems across direct wires
with explicit counterpoises, transformer-fed variants, OCFD and near-end-fed
wires, radial verticals, a five-wire fan dipole, and trap-loaded dipoles. It
retains separate best-SWR and maximum-final-efficiency tuner states at 1.5:1 and
2.5:1.

```bash
uv run antenna-lab run-kh1-portable-coarse-study \
  --config configs/kh1-portable-refine-v1.json \
  --output build/kh1-portable-refine-v1 \
  --nec2c /path/to/nec2c \
  --jobs 8
uv run antenna-lab run-kh1-comparative-study \
  --nec-artifact build/upstream-artifacts-31750551947 \
  --portable-study build/kh1-portable-refine-v1 \
  --output build/kh1-portable-comparative-v1
uv run antenna-lab run-kh1-final-decision \
  --config configs/kh1-portable-final-v1.json \
  --output results/kh1-portable-final-v1
uv run antenna-lab verify-results results/kh1-portable-final-v1
```

The final objective is radiated RF power divided by transmitter-available RF
power immediately before the tuner. It includes residual mismatch, tuner,
transformer/choke, mismatch-enhanced line, lumped loading, conductor, and NEC
radiator/ground loss where applicable. Scenario quantiles are equal-weight
sensitivity envelopes, not probabilities. The NEC cache is keyed by exact deck
and solver binary, so downstream network and ranking changes reuse antenna loads.
