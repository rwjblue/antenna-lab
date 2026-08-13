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

The current NEC-2 result is deliberately field-testable rather than final. For
the existing 58 ft radiator, first test detachable balanced-line additions from
3.75 to 4.50 ft; do not cut the antenna yet. For a separate compact antenna, the
model-led trial is a 41 ft radiator with an explicit 17 ft counterpoise; 35/17
remains the shorter field-evidence control. Resonant linked dipoles remain the
matching and efficiency references.

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

The full KH1/KX2 portable-antenna study can still be run locally as one command:

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
package. Direct-fed wires and resonant references cover 80, 60, 40, 30, 20, 17,
15, 12, 10, and 6 meters. The measured-reference-plane doublet optimization
remains anchored on 40 through 10 meters; 80, 60, and 6 meter doublet results are
radiator-only NEC cases until matching station-end measurements exist.

Every compute job uploads its CSV, metadata, manifest, and runner log as a
separate workflow artifact. The final job uploads the complete result tree as
`kh1-portable-nec-v2-<run-id>`. Consequently, successful intermediate work is
still retrievable when a later shard or assembly job fails. Artifacts are kept
for 90 days, subject to the repository's Actions retention limit. Full generated
study trees are not checked into `results/`; reproduce them under `build/` or use
the corresponding verified workflow artifact. The review-corrected reference
run is [31714329681](https://github.com/rwjblue/antenna-lab/actions/runs/31714329681).

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
