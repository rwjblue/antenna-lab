# 53 ft EFRW counterpoise, elevated-feed, and carbon-mast addendum

## What was compared

The same 53 ft, 26-AWG copper radiator, ideal 9:1 transformation, RG-316 model, Elecraft tuner models, and best-component 0.25 dB transformer + 0.10 dB choke envelope are retained. PA-forward efficiency includes NEC wire/ground loss, mismatch-enhanced coax loss, tuner dissipation and residual mismatch, transformer loss, and choke loss.

Ranking uses the common POTA bands 40/30/20/17/15/12/10 m that each radio supports. All of each radio's modeled bands remain in the detailed CSV. A 180-degree counterpoise slopes away exactly opposite the radiator projection; 135 degrees is diagonal and 90 degrees is sideways.

## Counterpoise length sweep on the 3-to-30 ft sloper

### KX2 / KXAT2

| band | best length | direction | match | PA→radiated | tuner dissipation | coax loss |
|---|---:|---:|---|---:|---:|---:|
| 80m | 53 ft | 180° | unlikely | 37.5% | 0.48 dB | 1.68 dB |
| 60m | 37 ft | 180° | likely | 63.9% | 0.13 dB | 0.99 dB |
| 40m | 13 ft | 180° | likely | 72.6% | 0.08 dB | 0.56 dB |
| 30m | 41 ft | 135° | likely | 73.6% | 0.08 dB | 0.56 dB |
| 20m | 49 ft | 90° | likely | 68.9% | 0.08 dB | 0.84 dB |
| 17m | 33 ft | 90° | likely | 58.2% | 0.12 dB | 1.48 dB |
| 15m | 41 ft | 90° | likely | 72.8% | 0.02 dB | 0.70 dB |
| 12m | 45 ft | 90° | likely | 70.3% | 0.04 dB | 0.79 dB |
| 10m | 13 ft | 90° | likely | 57.1% | 0.18 dB | 1.46 dB |

Best one-size compromise: **41 ft at 135°**, with 7/7 likely matches and 62.3% geometric-mean PA-forward efficiency on the comparison bands.

### KX3 / KXAT3

| band | best length | direction | match | PA→radiated | tuner dissipation | coax loss |
|---|---:|---:|---|---:|---:|---:|
| 160m | 37 ft | 180° | uncertain | 6.0% | 1.42 dB | 8.90 dB |
| 80m | 53 ft | 180° | likely | 49.7% | 0.40 dB | 1.68 dB |
| 60m | 37 ft | 180° | likely | 63.8% | 0.13 dB | 0.99 dB |
| 40m | 13 ft | 180° | likely | 72.6% | 0.08 dB | 0.56 dB |
| 30m | 41 ft | 180° | likely | 73.6% | 0.09 dB | 0.55 dB |
| 20m | 49 ft | 90° | likely | 68.8% | 0.08 dB | 0.84 dB |
| 17m | 33 ft | 90° | likely | 58.1% | 0.12 dB | 1.48 dB |
| 15m | 41 ft | 90° | likely | 72.8% | 0.02 dB | 0.70 dB |
| 12m | 45 ft | 90° | likely | 70.3% | 0.04 dB | 0.79 dB |
| 10m | 13 ft | 90° | likely | 57.3% | 0.18 dB | 1.46 dB |
| 6m | 37 ft | 90° | likely | 64.1% | 0.08 dB | 1.17 dB |

Best one-size compromise: **41 ft at 135°**, with 7/7 likely matches and 62.3% geometric-mean PA-forward efficiency on the comparison bands.

### KH1 / KHATU1

| band | best length | direction | match | PA→radiated | tuner dissipation | coax loss |
|---|---:|---:|---|---:|---:|---:|
| 40m | 13 ft | 180° | likely | 72.7% | 0.08 dB | 0.56 dB |
| 30m | 41 ft | 135° | likely | 73.8% | 0.08 dB | 0.56 dB |
| 20m | 49 ft | 90° | likely | 68.4% | 0.08 dB | 0.84 dB |
| 17m | 33 ft | 90° | likely | 57.7% | 0.10 dB | 1.48 dB |
| 15m | 41 ft | 90° | likely | 72.5% | 0.01 dB | 0.70 dB |

Best one-size compromise: **41 ft at 180°**, with 5/5 likely matches and 63.0% geometric-mean PA-forward efficiency on the comparison bands.

## Elevated feedpoint: coax vertical or counterpoise angled away

Each radiator runs from the elevated feedpoint down to a 3 ft far end. The coax is vertical in every case. With a feedpoint choke, a separate counterpoise is either vertical beside that feedline or slopes to 0.5 ft; without that counterpoise, the coax exterior is the vertical return and the choke is at the radio.

| radio | feed | return choice | selected CP | likely matches | geometric mean | worst band |
|---|---:|---|---:|---:|---:|---:|
| KX2 | 20 ft | coax exterior | 19.5 ft vertical | 7/7 | 54.5% | 43.3% |
| KX2 | 20 ft | vertical CP | 19.5 ft vertical | 7/7 | 52.2% | 41.6% |
| KX2 | 20 ft | best angled CP | 41 ft @ 90° | 7/7 | 57.2% | 46.1% |
| KX2 | 30 ft | coax exterior | 29.5 ft vertical | 7/7 | 48.0% | 40.1% |
| KX2 | 30 ft | vertical CP | 29.5 ft vertical | 7/7 | 46.5% | 37.6% |
| KX2 | 30 ft | best angled CP | 41 ft @ 90° | 7/7 | 50.2% | 39.6% |
| KX2 | 40 ft | coax exterior | 39.5 ft vertical | 7/7 | 44.8% | 32.1% |
| KX2 | 40 ft | vertical CP | 39.5 ft vertical | 7/7 | 43.2% | 31.8% |
| KX2 | 40 ft | best angled CP | 41 ft @ 180° | 7/7 | 45.8% | 34.3% |
| KX3 | 20 ft | coax exterior | 19.5 ft vertical | 7/7 | 54.4% | 43.3% |
| KX3 | 20 ft | vertical CP | 19.5 ft vertical | 7/7 | 52.1% | 41.6% |
| KX3 | 20 ft | best angled CP | 41 ft @ 90° | 7/7 | 57.2% | 46.1% |
| KX3 | 30 ft | coax exterior | 29.5 ft vertical | 7/7 | 47.9% | 40.1% |
| KX3 | 30 ft | vertical CP | 29.5 ft vertical | 7/7 | 46.4% | 37.6% |
| KX3 | 30 ft | best angled CP | 41 ft @ 90° | 7/7 | 50.1% | 39.5% |
| KX3 | 40 ft | coax exterior | 39.5 ft vertical | 7/7 | 44.8% | 32.2% |
| KX3 | 40 ft | vertical CP | 39.5 ft vertical | 7/7 | 43.1% | 31.8% |
| KX3 | 40 ft | best angled CP | 41 ft @ 180° | 7/7 | 45.8% | 34.3% |
| KH1 | 20 ft | coax exterior | 19.5 ft vertical | 4/5 | 53.6% | 39.4% |
| KH1 | 20 ft | vertical CP | 19.5 ft vertical | 4/5 | 52.2% | 39.2% |
| KH1 | 20 ft | best angled CP | 41 ft @ 90° | 5/5 | 56.0% | 40.5% |
| KH1 | 30 ft | coax exterior | 29.5 ft vertical | 4/5 | 44.5% | 39.4% |
| KH1 | 30 ft | vertical CP | 29.5 ft vertical | 4/5 | 43.0% | 37.4% |
| KH1 | 30 ft | best angled CP | 33 ft @ 180° | 4/5 | 44.7% | 40.2% |
| KH1 | 40 ft | coax exterior | 39.5 ft vertical | 4/5 | 44.3% | 28.3% |
| KH1 | 40 ft | vertical CP | 39.5 ft vertical | 4/5 | 43.4% | 27.6% |
| KH1 | 40 ft | best angled CP | 41 ft @ 180° | 5/5 | 45.9% | 32.3% |

## The 20-to-40 ft sloper and carbon-fiber mast

The radiator slopes gently upward from the 20 ft feedpoint to the 40 ft far end. The coax drops vertically to 0.5 ft. For each mast condition, the table selects the strongest multi-band angled counterpoise separately; this is useful as a deployment recommendation, but `case_rankings.csv` also permits exact same-geometry mast comparisons.

| radio | mast model | return | selected CP | likely matches | geometric mean | worst band |
|---|---|---|---:|---:|---:|---:|
| KX2 | no mast | coax exterior | 19.5 ft vertical | 7/7 | 57.9% | 46.0% |
| KX2 | no mast | vertical CP | 19.5 ft vertical | 7/7 | 55.6% | 44.9% |
| KX2 | no mast | best angled CP | 41 ft @ 90° | 7/7 | 58.3% | 49.6% |
| KX2 | continuous CFRP, 5e3 S/m, 3 in away | coax exterior | 19.5 ft vertical | 7/7 | 48.1% | 28.0% |
| KX2 | continuous CFRP, 5e3 S/m, 3 in away | vertical CP | 19.5 ft vertical | 7/7 | 43.5% | 17.6% |
| KX2 | continuous CFRP, 5e3 S/m, 3 in away | best angled CP | 41 ft @ 135° | 7/7 | 57.4% | 50.1% |
| KX2 | continuous CFRP, 5e4 S/m, 3 in away | coax exterior | 19.5 ft vertical | 7/7 | 48.3% | 26.8% |
| KX2 | continuous CFRP, 5e4 S/m, 3 in away | vertical CP | 19.5 ft vertical | 7/7 | 43.7% | 16.9% |
| KX2 | continuous CFRP, 5e4 S/m, 3 in away | best angled CP | 41 ft @ 135° | 7/7 | 58.2% | 50.4% |
| KX2 | continuous CFRP, 5e4 S/m, 12 in away | coax exterior | 19.5 ft vertical | 7/7 | 50.8% | 35.6% |
| KX2 | continuous CFRP, 5e4 S/m, 12 in away | vertical CP | 19.5 ft vertical | 7/7 | 47.3% | 26.8% |
| KX2 | continuous CFRP, 5e4 S/m, 12 in away | best angled CP | 41 ft @ 135° | 7/7 | 58.1% | 49.9% |
| KX3 | no mast | coax exterior | 19.5 ft vertical | 7/7 | 57.8% | 46.0% |
| KX3 | no mast | vertical CP | 19.5 ft vertical | 7/7 | 55.6% | 44.9% |
| KX3 | no mast | best angled CP | 41 ft @ 90° | 7/7 | 58.2% | 49.6% |
| KX3 | continuous CFRP, 5e3 S/m, 3 in away | coax exterior | 19.5 ft vertical | 7/7 | 48.0% | 27.8% |
| KX3 | continuous CFRP, 5e3 S/m, 3 in away | vertical CP | 19.5 ft vertical | 7/7 | 43.4% | 17.4% |
| KX3 | continuous CFRP, 5e3 S/m, 3 in away | best angled CP | 41 ft @ 135° | 7/7 | 57.3% | 50.1% |
| KX3 | continuous CFRP, 5e4 S/m, 3 in away | coax exterior | 19.5 ft vertical | 7/7 | 48.2% | 26.7% |
| KX3 | continuous CFRP, 5e4 S/m, 3 in away | vertical CP | 19.5 ft vertical | 7/7 | 43.6% | 16.8% |
| KX3 | continuous CFRP, 5e4 S/m, 3 in away | best angled CP | 41 ft @ 135° | 7/7 | 58.1% | 50.4% |
| KX3 | continuous CFRP, 5e4 S/m, 12 in away | coax exterior | 19.5 ft vertical | 7/7 | 50.8% | 35.7% |
| KX3 | continuous CFRP, 5e4 S/m, 12 in away | vertical CP | 19.5 ft vertical | 7/7 | 47.3% | 26.8% |
| KX3 | continuous CFRP, 5e4 S/m, 12 in away | best angled CP | 41 ft @ 135° | 7/7 | 58.1% | 49.9% |
| KH1 | no mast | coax exterior | 19.5 ft vertical | 4/5 | 58.9% | 45.4% |
| KH1 | no mast | vertical CP | 19.5 ft vertical | 4/5 | 57.3% | 45.4% |
| KH1 | no mast | best angled CP | 41 ft @ 90° | 5/5 | 58.2% | 49.5% |
| KH1 | continuous CFRP, 5e3 S/m, 3 in away | coax exterior | 19.5 ft vertical | 4/5 | 52.5% | 40.4% |
| KH1 | continuous CFRP, 5e3 S/m, 3 in away | vertical CP | 19.5 ft vertical | 4/5 | 50.2% | 37.9% |
| KH1 | continuous CFRP, 5e3 S/m, 3 in away | best angled CP | 37 ft @ 90° | 5/5 | 58.5% | 47.3% |
| KH1 | continuous CFRP, 5e4 S/m, 3 in away | coax exterior | 19.5 ft vertical | 4/5 | 52.9% | 40.6% |
| KH1 | continuous CFRP, 5e4 S/m, 3 in away | vertical CP | 19.5 ft vertical | 4/5 | 50.8% | 38.4% |
| KH1 | continuous CFRP, 5e4 S/m, 3 in away | best angled CP | 37 ft @ 90° | 5/5 | 59.0% | 48.5% |
| KH1 | continuous CFRP, 5e4 S/m, 12 in away | coax exterior | 19.5 ft vertical | 4/5 | 53.8% | 44.4% |
| KH1 | continuous CFRP, 5e4 S/m, 12 in away | vertical CP | 19.5 ft vertical | 4/5 | 51.7% | 41.3% |
| KH1 | continuous CFRP, 5e4 S/m, 12 in away | best angled CP | 41 ft @ 135° | 5/5 | 58.1% | 48.9% |

### Exact same-geometry mast penalty

These cells show **geometric-mean / worst-band dB change** relative to the no-mast optimum while holding the return geometry fixed. Thus they isolate mast interaction instead of granting each mast a newly optimized counterpoise.

| return geometry | mast model | KX2 | KX3 | KH1 |
|---|---|---:|---:|---:|
| 19.5 ft vertical coax exterior | continuous CFRP, 5e3 S/m, 3 in away | -0.80 / -2.15 dB | -0.81 / -2.18 dB | -0.50 / -0.50 dB |
| 19.5 ft vertical coax exterior | continuous CFRP, 5e4 S/m, 3 in away | -0.79 / -2.34 dB | -0.80 / -2.37 dB | -0.47 / -0.48 dB |
| 19.5 ft vertical coax exterior | continuous CFRP, 5e4 S/m, 12 in away | -0.56 / -1.11 dB | -0.56 / -1.10 dB | -0.39 / -0.09 dB |
| 19.5 ft vertical copper CP | continuous CFRP, 5e3 S/m, 3 in away | -1.07 / -4.07 dB | -1.07 / -4.11 dB | -0.57 / -0.78 dB |
| 19.5 ft vertical copper CP | continuous CFRP, 5e4 S/m, 3 in away | -1.04 / -4.24 dB | -1.05 / -4.27 dB | -0.52 / -0.73 dB |
| 19.5 ft vertical copper CP | continuous CFRP, 5e4 S/m, 12 in away | -0.70 / -2.24 dB | -0.70 / -2.24 dB | -0.44 / -0.41 dB |
| no-mast-optimum angled CP | continuous CFRP, 5e3 S/m, 3 in away | -0.08 / +0.05 dB | -0.09 / +0.05 dB | -0.04 / -0.02 dB |
| no-mast-optimum angled CP | continuous CFRP, 5e4 S/m, 3 in away | -0.03 / +0.09 dB | -0.03 / +0.09 dB | -0.01 / -0.02 dB |
| no-mast-optimum angled CP | continuous CFRP, 5e4 S/m, 12 in away | -0.06 / +0.11 dB | -0.06 / +0.11 dB | -0.10 / +0.09 dB |

## Interpretation and limits

A dedicated counterpoise need not be resonant, and no single length is best on every band. Length changes both feedpoint impedance and the tuner/coax loss budget; use the per-band optima as evidence of sensitivity, not as quarter-wave cutting instructions.

The continuous-carbon cases deliberately bracket a strong interaction. Published CFRP longitudinal conductivity spans roughly 5e3 to 5e4 S/m, but a real telescoping mast is tapered, anisotropic, resin-rich, and may have electrically discontinuous joints. The NEC mast is a uniform, continuous floating wire, so an actual mast measurement can land anywhere between 'almost absent' and these modeled cases.

The coax exterior and differential transmission line are represented separately; their mutual mode conversion is not solved. Chokes are ideal common-mode boundaries plus insertion loss. Trees, wet bark, the transformer enclosure, the operator, and mast hardware are omitted. Efficiency is not gain or takeoff angle.

## Reproduce

```bash
uv run antenna-lab run-efrw-elevated-study --config configs/53ft-efrw-elevated-v1.json --output results/53ft-efrw-elevated-v1 --nec2c /path/to/nec2c
uv run antenna-lab verify-results results/53ft-efrw-elevated-v1
```

## Sources

- [antenna](https://www.relianceantennas.com/product/efrw-9-to-1-bugout-mini-160-6m-53-ft-wire-antenna/)
- [kx2](https://ftp.elecraft.com/KX2/Manuals%20Downloads/KX2%20owner%27s%20man%20B2.pdf)
- [kx3](https://ftp.elecraft.com/KX3/Manuals%20Downloads/E740163%20KX3%20Owner%27s%20man%20Rev%20C5.pdf)
- [kh1](https://ftp.elecraft.com/KH1/Manuals%20Downloads/KH1%20Owner%27s%20Manual,%20rev%20B7.pdf)
- [coax](https://www.belden.com/products/cable/coax-triax-cable/50-ohm-coax-cable/84316)
- [solver](https://github.com/KJ7LNW/nec2c)
- [carbon_conductivity](https://pmc.ncbi.nlm.nih.gov/articles/PMC9185562/)
