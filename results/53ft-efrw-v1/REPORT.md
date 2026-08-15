# 53 ft 9:1 EFRW complete-system study

## Bottom line

This report gives **PA-forward radiating efficiency**, not merely NEC wire efficiency. The canonical best-component case multiplies the modeled tuner transducer efficiency (including residual mismatch), mismatch-enhanced RG-316 efficiency, a 0.25 dB 9:1 loss, a 0.10 dB choke loss, and NEC wire-plus-ground radiation efficiency.

A check mark means every tuner profile used for that radio found a state at or below 2.5:1 and, where Elecraft publishes one, the raw load is within the owner's-manual typical 20:1 range. `~` means a circuit-model match outside that published range, or only one of the two inferred KHATU1 profiles matched. Both cases are deliberately labeled uncertain.

## KX2 / KXAT2

### 17 ft dedicated 26-AWG counterpoise; choke at feedpoint

| deployment | 80m | 60m | 40m | 30m | 20m | 17m | 15m | 12m | 10m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 ft low horizontal | 5% ✕ | 33% ✓ | 66% ✓ | 43% ✓ | 57% ✓ | 53% ✓ | 66% ✓ | 50% ✓ | 46% ✓ |
| 3-to-20 ft sloper | 8% ✕ | 42% ✓ | 69% ✓ | 49% ✓ | 61% ✓ | 56% ✓ | 68% ✓ | 48% ✓ | 43% ✓ |
| 3-to-30 ft sloper | 9% ✕ | 45% ✓ | 71% ✓ | 53% ✓ | 61% ✓ | 55% ✓ | 67% ✓ | 48% ✓ | 43% ✓ |
| 20 ft apex inverted-V, 3 ft ends | 8% ✕ | 40% ✓ | 67% ✓ | 44% ✓ | 60% ✓ | 58% ✓ | 69% ✓ | 49% ✓ | 42% ✓ |
| 30 ft vertical / 26 ft horizontal inverted-L | 8% ✕ | 42% ✓ | 70% ✓ | 44% ✓ | 59% ✓ | 60% ✓ | 70% ✓ | 48% ✓ | 41% ✓ |
### 17 ft coax exterior as counterpoise; choke at radio

| deployment | 80m | 60m | 40m | 30m | 20m | 17m | 15m | 12m | 10m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 ft low horizontal | 6% ✕ | 38% ✓ | 67% ✓ | 43% ✓ | 60% ✓ | 52% ✓ | 70% ✓ | 55% ✓ | 48% ✓ |
| 3-to-20 ft sloper | 10% ✕ | 48% ✓ | 70% ✓ | 50% ✓ | 64% ✓ | 55% ✓ | 72% ✓ | 54% ✓ | 45% ✓ |
| 3-to-30 ft sloper | 10% ✕ | 50% ✓ | 71% ✓ | 53% ✓ | 64% ✓ | 54% ✓ | 71% ✓ | 54% ✓ | 45% ✓ |
| 20 ft apex inverted-V, 3 ft ends | 9% ✕ | 45% ✓ | 67% ✓ | 44% ✓ | 63% ✓ | 58% ✓ | 72% ✓ | 55% ✓ | 45% ✓ |
| 30 ft vertical / 26 ft horizontal inverted-L | 9% ✕ | 47% ✓ | 71% ✓ | 44% ✓ | 62% ✓ | 60% ✓ | 72% ✓ | 54% ✓ | 44% ✓ |

Loss-budget summary for the main profile (all supported bands):

| return | deployment | matches | efficiency geometric mean | worst band | median tuner dissipation |
|---|---|---:|---:|---:|---:|
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 3-to-30 ft sloper | 8/9 | 44.4% | 8.6% | 0.20 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 3-to-20 ft sloper | 8/9 | 43.7% | 8.4% | 0.19 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 30 ft vertical / 26 ft horizontal inverted-L | 8/9 | 42.9% | 7.9% | 0.18 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 20 ft apex inverted-V, 3 ft ends | 8/9 | 42.4% | 7.8% | 0.19 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 10 ft low horizontal | 8/9 | 39.5% | 5.4% | 0.19 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 3-to-30 ft sloper | 8/9 | 47.1% | 10.1% | 0.17 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 3-to-20 ft sloper | 8/9 | 46.4% | 9.9% | 0.17 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 30 ft vertical / 26 ft horizontal inverted-L | 8/9 | 45.7% | 9.3% | 0.17 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 20 ft apex inverted-V, 3 ft ends | 8/9 | 45.3% | 9.2% | 0.17 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 10 ft low horizontal | 8/9 | 42.0% | 6.5% | 0.19 dB |

## KX3 / KXAT3

### 17 ft dedicated 26-AWG counterpoise; choke at feedpoint

| deployment | 160m | 80m | 60m | 40m | 30m | 20m | 17m | 15m | 12m | 10m | 6m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 ft low horizontal | 2% ~ | 8% ~ | 37% ✓ | 66% ✓ | 43% ✓ | 57% ✓ | 53% ✓ | 66% ✓ | 50% ✓ | 46% ✓ | 57% ✓ |
| 3-to-20 ft sloper | 3% ~ | 13% ~ | 45% ✓ | 69% ✓ | 49% ✓ | 61% ✓ | 56% ✓ | 68% ✓ | 48% ✓ | 43% ✓ | 59% ✓ |
| 3-to-30 ft sloper | 3% ~ | 13% ~ | 47% ✓ | 71% ✓ | 53% ✓ | 61% ✓ | 55% ✓ | 67% ✓ | 48% ✓ | 43% ✓ | 59% ✓ |
| 20 ft apex inverted-V, 3 ft ends | 3% ~ | 12% ~ | 43% ✓ | 67% ✓ | 44% ✓ | 60% ✓ | 58% ✓ | 69% ✓ | 49% ✓ | 42% ✓ | 63% ✓ |
| 30 ft vertical / 26 ft horizontal inverted-L | 2% ~ | 12% ~ | 44% ✓ | 70% ✓ | 44% ✓ | 59% ✓ | 60% ✓ | 70% ✓ | 48% ✓ | 41% ✓ | 64% ✓ |
### 17 ft coax exterior as counterpoise; choke at radio

| deployment | 160m | 80m | 60m | 40m | 30m | 20m | 17m | 15m | 12m | 10m | 6m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 ft low horizontal | 2% ~ | 10% ~ | 41% ✓ | 67% ✓ | 43% ✓ | 60% ✓ | 52% ✓ | 70% ✓ | 55% ✓ | 48% ✓ | 62% ✓ |
| 3-to-20 ft sloper | 3% ~ | 15% ~ | 50% ✓ | 70% ✓ | 50% ✓ | 64% ✓ | 55% ✓ | 72% ✓ | 54% ✓ | 45% ✓ | 64% ✓ |
| 3-to-30 ft sloper | 3% ~ | 15% ~ | 52% ✓ | 71% ✓ | 53% ✓ | 64% ✓ | 54% ✓ | 71% ✓ | 54% ✓ | 46% ✓ | 64% ✓ |
| 20 ft apex inverted-V, 3 ft ends | 3% ~ | 14% ~ | 48% ✓ | 67% ✓ | 44% ✓ | 63% ✓ | 58% ✓ | 72% ✓ | 55% ✓ | 45% ✓ | 66% ✓ |
| 30 ft vertical / 26 ft horizontal inverted-L | 3% ~ | 14% ~ | 49% ✓ | 71% ✓ | 44% ✓ | 62% ✓ | 60% ✓ | 72% ✓ | 54% ✓ | 44% ✓ | 67% ✓ |

Loss-budget summary for the main profile (all supported bands):

| return | deployment | matches | efficiency geometric mean | worst band | median tuner dissipation |
|---|---|---:|---:|---:|---:|
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 3-to-30 ft sloper | 9/11 | 36.9% | 2.7% | 0.20 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 3-to-20 ft sloper | 9/11 | 36.6% | 2.8% | 0.20 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 20 ft apex inverted-V, 3 ft ends | 9/11 | 35.7% | 2.7% | 0.19 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 30 ft vertical / 26 ft horizontal inverted-L | 9/11 | 35.7% | 2.4% | 0.18 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 10 ft low horizontal | 9/11 | 32.0% | 1.6% | 0.19 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 3-to-30 ft sloper | 9/11 | 39.6% | 3.3% | 0.18 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 3-to-20 ft sloper | 9/11 | 39.3% | 3.4% | 0.17 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 20 ft apex inverted-V, 3 ft ends | 9/11 | 38.5% | 3.2% | 0.17 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 30 ft vertical / 26 ft horizontal inverted-L | 9/11 | 38.3% | 2.9% | 0.17 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 10 ft low horizontal | 9/11 | 34.5% | 1.9% | 0.19 dB |

## KH1 / KHATU1

### 17 ft dedicated 26-AWG counterpoise; choke at feedpoint

| deployment | 40m | 30m | 20m | 17m | 15m |
|---|---:|---:|---:|---:|---:|
| 10 ft low horizontal | 66% ✓ | 31% ✕ | 56% ✓ | 51% ✓ | 65% ✓ |
| 3-to-20 ft sloper | 69% ✓ | 40% ✕ | 60% ✓ | 54% ✓ | 67% ✓ |
| 3-to-30 ft sloper | 71% ✓ | 43% ~ | 60% ✓ | 53% ✓ | 66% ✓ |
| 20 ft apex inverted-V, 3 ft ends | 67% ✓ | 32% ✕ | 59% ✓ | 54% ✓ | 66% ✓ |
| 30 ft vertical / 26 ft horizontal inverted-L | 70% ✓ | 30% ✕ | 58% ✓ | 57% ✓ | 66% ✓ |
### 17 ft coax exterior as counterpoise; choke at radio

| deployment | 40m | 30m | 20m | 17m | 15m |
|---|---:|---:|---:|---:|---:|
| 10 ft low horizontal | 67% ✓ | 30% ✕ | 60% ✓ | 51% ✓ | 68% ✓ |
| 3-to-20 ft sloper | 70% ✓ | 40% ✕ | 64% ✓ | 54% ✓ | 70% ✓ |
| 3-to-30 ft sloper | 71% ✓ | 43% ~ | 63% ✓ | 53% ✓ | 69% ✓ |
| 20 ft apex inverted-V, 3 ft ends | 67% ✓ | 32% ✕ | 62% ✓ | 53% ✓ | 69% ✓ |
| 30 ft vertical / 26 ft horizontal inverted-L | 71% ✓ | 29% ✕ | 61% ✓ | 56% ✓ | 70% ✓ |

Loss-budget summary for the main profile (all supported bands):

| return | deployment | matches | efficiency geometric mean | worst band | median tuner dissipation |
|---|---|---:|---:|---:|---:|
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 3-to-30 ft sloper | 4/5 | 57.9% | 43.5% | 0.09 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 3-to-20 ft sloper | 4/5 | 57.0% | 39.5% | 0.09 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 30 ft vertical / 26 ft horizontal inverted-L | 4/5 | 54.0% | 30.1% | 0.10 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 20 ft apex inverted-V, 3 ft ends | 4/5 | 53.6% | 31.9% | 0.12 dB |
| 17 ft dedicated 26-AWG counterpoise; choke at feedpoint | 10 ft low horizontal | 4/5 | 52.0% | 30.9% | 0.10 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 3-to-30 ft sloper | 4/5 | 58.9% | 43.4% | 0.09 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 3-to-20 ft sloper | 4/5 | 58.0% | 39.6% | 0.09 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 30 ft vertical / 26 ft horizontal inverted-L | 4/5 | 54.9% | 29.4% | 0.10 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 20 ft apex inverted-V, 3 ft ends | 4/5 | 54.7% | 31.8% | 0.10 dB |
| 17 ft coax exterior as counterpoise; choke at radio | 10 ft low horizontal | 4/5 | 53.0% | 30.5% | 0.10 dB |

## Component and model sensitivity

The best hardware envelope is 0.25 dB transformer + 0.10 dB choke. The nominal envelope is 0.60 + 0.20 dB, and the conservative envelope is 1.20 + 0.50 dB. `system_results.csv` contains all three hardware envelopes and all three tuner-Q envelopes.

The detailed CSV separates NEC efficiency, coax loss, transformer loss, choke loss, tuner dissipation, residual mismatch, and final PA-forward efficiency. `nec_loads.csv` also includes poor-ground cases; tuner calculations use the canonical average-ground cases.

The tables use the loss-minimizing discrete tuner state that still reaches 2.5:1. A firmware-like lowest-SWR state is also retained in the CSV; across this sweep, the largest modeled benefit from choosing the loss-minimizing state is only 0.14 dB.

## Interpretation

The radio-end choke case is not truly a counterpoise-free antenna: the coax exterior is the 17 ft return conductor. Moving or changing that cable changes the antenna. The feedpoint-choke case makes the dedicated wire the intended return and should be more repeatable and less coupled to the radio/operator, even when a particular coax-return cell happens to be more efficient.

A high efficiency number on 160 or 80 m does not make this short antenna competitive with a full-size radiator: efficiency is only the fraction of accepted power radiated, while gain and useful launch angle also depend on the electrically short/current-distribution geometry. This study does not rank patterns.

## Reproduce

```bash
uv run antenna-lab run-efrw-study --config configs/53ft-efrw-v1.json --output results/53ft-efrw-v1 --nec2c /path/to/nec2c
uv run antenna-lab verify-results results/53ft-efrw-v1
```

## Limitations

- The 17 ft return and 17 ft RG-316 line are explicit assumptions, not Reliance-supplied dimensions.
- The no-counterpoise case treats the coax exterior as a NEC wire and the differential coax as a separate transmission line; coupling between those modes is not solved.
- The choke is an ideal common-mode boundary plus a fixed differential insertion-loss envelope; finite choking impedance is not modeled.
- The 9:1 transformer is an ideal impedance transformation plus a fixed loss envelope; its loss and impedance transformation should be measured on the actual unit.
- KHATU1 bank values and all tuner component-Q values remain inferred sensitivity inputs; KXAT2/KXAT3 bank values are schematic-derived.
- NEC uses bare-wire geometry and omits insulation loading, trees, supports, the operator, radio chassis, connectors, and nearby objects.
- Best-case efficiency is not gain: deployment shape can redirect radiation even when the percentage of power radiated is high.

## Sources

- [antenna](https://www.relianceantennas.com/product/efrw-9-to-1-bugout-mini-160-6m-53-ft-wire-antenna/)
- [kx2](https://ftp.elecraft.com/KX2/Manuals%20Downloads/KX2%20owner%27s%20man%20B2.pdf)
- [kx3](https://ftp.elecraft.com/KX3/Manuals%20Downloads/E740163%20KX3%20Owner%27s%20man%20Rev%20C5.pdf)
- [kh1](https://ftp.elecraft.com/KH1/Manuals%20Downloads/KH1%20Owner%27s%20Manual,%20rev%20B7.pdf)
- [coax](https://www.belden.com/products/cable/coax-triax-cable/50-ohm-coax-cable/84316)
- [solver](https://github.com/KJ7LNW/nec2c)
