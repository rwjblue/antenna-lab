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

The current practical conclusion is deliberately modest: the existing 58/28
antenna is already near a broad robust region. The next experiment is a
reversible 57/28 configuration made by folding back 6 inches at each free end;
do not cut the antenna yet.

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

Compare the measured baseline with the reversible experiment:

```bash
uv run antenna-lab compare-configs --radiator-ft 57 --feedline-ft 28
```

Generate the analytical thin-wire pattern (this is not NEC/MININEC):

```bash
uv run antenna-lab plot-pattern --output build/pattern-17m.png --frequency-mhz 18.08 --center-height-ft 30
```

The same checks are exposed as file-based mise tasks:

```bash
mise run check
mise run reference
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
