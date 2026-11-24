# Open-balun construction screen — 17 September 2026

All tables are calculations using stated scenarios, not measurements.
[Decision, sources and build/test instructions](../../docs/case-studies/balun-decision.md).

## Common-mode example: 2631801202, N=12

Exact-part N=1 series R+jX scaled by N², then shunted by assumed C.
Entries: band-min R; range of X; band-min |Z|, all kΩ. No confidence bounds.

| Band | 2 pF: R; X; magnitude | 8 pF: R; X; magnitude |
| --- | --- | --- |
| 40m | 5.43; +1.13…+1.27; 5.58 | 1.97; -2.78…-2.74; 3.38 |
| 30m | 6.33; -0.57…-0.54; 6.35 | 0.86; -2.19…-2.18; 2.34 |
| 20m | 5.41; -3.24…-3.08; 6.30 | 0.34; -1.57…-1.53; 1.57 |
| 17m | 3.53; -4.01…-4.01; 5.34 | 0.18; -1.19…-1.18; 1.20 |
| 15m | 2.35; -3.88…-3.84; 4.50 | 0.12; -1.01…-0.99; 1.00 |

## Differential line examples

0.60 m, assumed epsilon_eff=2 for enamel; 1.5 for FEP; 1.8 for Spec55. Solid-round skin + pair proximity only; no dielectric or ferrite loss.

| Scenario | Band | Z0 Ω | SWR | RL dB | IL dB | Heat W / 100 W incident |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 18 enamel touching scenario | 40m | 22.4 | 1.26 | 18.9 | 0.146 | 2.01 |
| 18 enamel touching scenario | 30m | 22.4 | 1.37 | 16.1 | 0.215 | 2.38 |
| 18 enamel touching scenario | 20m | 22.4 | 1.55 | 13.3 | 0.341 | 2.87 |
| 18 enamel touching scenario | 17m | 22.4 | 1.73 | 11.4 | 0.479 | 3.27 |
| 18 enamel touching scenario | 15m | 22.4 | 1.90 | 10.2 | 0.613 | 3.61 |
| 18 enamel spaced scenario | 40m | 55.4 | 1.03 | 37.1 | 0.040 | 0.91 |
| 18 enamel spaced scenario | 30m | 55.4 | 1.04 | 34.4 | 0.048 | 1.07 |
| 18 enamel spaced scenario | 20m | 55.4 | 1.05 | 31.5 | 0.058 | 1.26 |
| 18 enamel spaced scenario | 17m | 55.4 | 1.07 | 29.6 | 0.067 | 1.42 |
| 18 enamel spaced scenario | 15m | 55.4 | 1.08 | 28.3 | 0.074 | 1.53 |
| 22 heavy enamel touching | 40m | 35.4 | 1.10 | 26.7 | 0.101 | 2.08 |
| 22 heavy enamel touching | 30m | 35.4 | 1.14 | 24.0 | 0.126 | 2.45 |
| 22 heavy enamel touching | 20m | 35.4 | 1.19 | 21.1 | 0.164 | 2.92 |
| 22 heavy enamel touching | 17m | 35.4 | 1.25 | 19.2 | 0.200 | 3.30 |
| 22 heavy enamel touching | 15m | 35.4 | 1.29 | 17.8 | 0.234 | 3.60 |
| 22 heavy enamel spaced scenario | 40m | 61.4 | 1.06 | 31.2 | 0.061 | 1.33 |
| 22 heavy enamel spaced scenario | 30m | 61.4 | 1.08 | 28.5 | 0.075 | 1.56 |
| 22 heavy enamel spaced scenario | 20m | 61.4 | 1.11 | 25.6 | 0.093 | 1.84 |
| 22 heavy enamel spaced scenario | 17m | 61.4 | 1.14 | 23.7 | 0.109 | 2.05 |
| 22 heavy enamel spaced scenario | 15m | 61.4 | 1.17 | 22.3 | 0.123 | 2.22 |
| 22 BNTECHGO FEP bundle scenario | 40m | 122.8 | 1.26 | 18.9 | 0.093 | 0.82 |
| 22 BNTECHGO FEP bundle scenario | 30m | 122.8 | 1.37 | 16.1 | 0.151 | 0.96 |
| 22 BNTECHGO FEP bundle scenario | 20m | 122.8 | 1.56 | 13.2 | 0.262 | 1.10 |
| 22 BNTECHGO FEP bundle scenario | 17m | 122.8 | 1.74 | 11.4 | 0.387 | 1.19 |
| 22 BNTECHGO FEP bundle scenario | 15m | 122.8 | 1.91 | 10.1 | 0.509 | 1.25 |
| 22 Spec55 bundle scenario | 40m | 75.7 | 1.11 | 25.6 | 0.055 | 0.97 |
| 22 Spec55 bundle scenario | 30m | 75.7 | 1.16 | 22.8 | 0.073 | 1.14 |
| 22 Spec55 bundle scenario | 20m | 75.7 | 1.23 | 19.9 | 0.104 | 1.34 |
| 22 Spec55 bundle scenario | 17m | 75.7 | 1.29 | 17.9 | 0.137 | 1.49 |
| 22 Spec55 bundle scenario | 15m | 75.7 | 1.35 | 16.6 | 0.168 | 1.59 |
