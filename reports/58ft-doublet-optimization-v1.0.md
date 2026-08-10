# Joint Radiator / Feedline Optimization Report

Generated: 2026-08-08T22:53:00Z

## Result

The model found a narrow favorable region around a **56.75–57.0 ft total radiator** and roughly **28 ft of balanced feedline**. It did **not** find a compelling several-foot feedline change or a radically shorter/longer radiator that remained low-stress across all seven target bands.

The purely numerical winner under the configured matchability proxy is:

- Radiator: **56.75 ft total**
- Feedline: **28.25 ft**
- 10th-percentile worst-band line efficiency: **24.4%**
- 90th-percentile maximum raw-SWR proxy: **48.1:1**

The recommended first experiment is simpler and reversible:

- Leave the feedline at **28.00 ft**.
- Reduce the radiator from 58 ft to **57.00 ft** by folding back **6.0 inches at each radiating end**.
- Do not cut initially.

That recommendation gives up little of the numerical optimum, avoids changing the continuous feedline/radiator transition, and keeps the tuner-stress proxy below the configured recommended threshold.

## Selected candidates

| selection_category | radiator_total_ft | feedline_ft | trim_per_end_in | feedline_split_shift_in | robust_worst_eff_pct | median_worst_eff_pct | maximum_raw_swr_p90 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| measured_baseline | 58.000 | 28.000 | 0.000 | 0.000 | 15.671 | 54.106 | 32.467 |
| recommended_reversible_trim_test | 57.000 | 28.000 | 6.000 | 0.000 | 23.351 | 69.682 | 43.233 |
| model_best_under_match_proxy | 56.750 | 28.250 | 4.500 | 3.000 | 24.361 | 69.389 | 48.106 |
| highest_robust_efficiency_without_match_proxy | 56.750 | 18.000 | 127.500 | -120.000 | 33.575 | 78.059 | 2476.089 |

## Baseline versus recommended reversible test

| band | baseline_eff_p10_pct | baseline_eff_median_pct | recommended_eff_p10_pct | recommended_eff_median_pct | paired_change_db_p10 | paired_change_db_median | paired_change_db_p90 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40m | 95.971 | 97.793 | 94.400 | 97.097 | -0.087 | -0.017 | 0.004 |
| 30m | 95.313 | 97.449 | 95.654 | 97.625 | -0.006 | 0.009 | 0.039 |
| 20m | 70.048 | 83.688 | 65.342 | 86.571 | -0.386 | -0.084 | 0.648 |
| 17m | 15.671 | 54.106 | 23.351 | 77.999 | 0.148 | 0.794 | 3.936 |
| 15m | 95.721 | 97.670 | 96.304 | 98.000 | 0.002 | 0.016 | 0.043 |
| 12m | 47.264 | 71.304 | 36.524 | 72.775 | -1.354 | -0.310 | 1.578 |
| 10m | 41.261 | 68.037 | 45.959 | 83.488 | -0.000 | 0.231 | 2.224 |

The paired model comparison is more useful than comparing two unrelated percentile endpoints. For 17 m, the 57/28 candidate produces a paired median improvement of **0.79 dB**, with a 10–90% model interval of **0.15 to 3.94 dB**. The model therefore favors the trim, but it does not justify claiming a guaranteed 3 dB recovery.

The main tradeoff is 12 m. Its paired median change is **-0.31 dB**, with a broad interval of **-1.35 to 1.58 dB**.

## What the optimization actually did

The optimization evaluated **6,561 physical length combinations**:

- total radiator: 48.0–68.0 ft in 0.25 ft steps;
- balanced line: 18.0–38.0 ft in 0.25 ft steps.

Each candidate was evaluated over **390 ensemble members** combining:

- 4 velocity factors;
- 3 air-geometry characteristic-impedance values, coupled to VF as `Z0 = Z0_air × VF`;
- 6 candidate matched-loss values, with non-passive de-embeddings rejected;
- 6 passive baseline-anchored radiator-change surrogate models.

The score is not raw SWR. The primary objective is the 10th percentile of the minimum balanced-line efficiency across 40/30/20/17/15/12/10 m. Primary bands 40/30/20 receive larger weight in the secondary geometric-mean objective.

## Why this is not a definitive full-wave answer

Only one physical radiator length has been measured. A different radiator length changes the unknown apex feedpoint impedance; that cannot be derived exactly from the seven terminal measurements alone. The model therefore uses multiple passive, measurement-anchored surrogate families rather than pretending one uncalibrated formula is exact.

Consequences:

1. **The broad region is more trustworthy than the exact quarter-foot winner.**
2. **Relative changes near 58 ft are more trustworthy than absolute efficiency percentages.**
3. Candidate lengths far from the measured 58 ft baseline have much greater model risk.
4. A real remeasurement after a reversible foldback is the required next calibration point.

## Matchability proxy

The KXAT2 is a seven-inductor/seven-capacitor switched L-network with a typical matching range stated as 20:1 or greater. The current antenna demonstrates that a raw SWR above 20:1 can sometimes be matched, especially after the documented second ATU search. The model therefore uses a 90th-percentile maximum raw SWR of 50.0:1 as a heuristic screening value—not as an Elecraft specification.

No KXAT2 insertion-loss model is included because the relay states, component values, and component Q for each candidate match are not known.

## Validation procedure

1. Select the alternate KXAT2 ATU data set so the existing antenna matches remain available.
2. Fold back 6.0 inches at each radiating end, keeping the folded sections close to the active wire.
3. Leave the 28 ft balanced feedline and deployment geometry unchanged.
4. Measure R+jX at the same seven frequencies with the RigExpert.
5. Record first-pass and second-pass KXAT2 tuned SWR.
6. Compare those values with `results/selected_candidate_band_metrics.csv`.
7. Only cut after the reversible test demonstrates useful 17 m improvement without losing tuner coverage elsewhere.

## Bottom line

The optimization supports a **small radiator trim**, not a major redesign. The best practical next experiment is **57 ft total radiator / 28 ft feedline**. Because model disagreement remains material, the present 58/28 antenna is still a reasonable finished antenna if convenience and proven tuner coverage matter more than chasing a possible sub-1 dB median improvement on 17 m.

## Files

- `results/full_candidate_grid.csv.gz`: every 0.25 ft candidate and aggregate metrics.
- `results/ensemble_metrics_compact.npz`: compact float16 per-ensemble metrics; maximum SWR is stored as log10(SWR).
- `results/ensemble_scenarios.csv`: every uncertainty/model ensemble member.
- `results/selected_candidates.csv`: selected designs.
- `results/selected_candidate_band_metrics.csv`: per-band predicted ranges.
- `results/paired_improvements_vs_baseline.csv`: paired dB changes.
- `results/pareto_frontier.csv`: efficiency/match-proxy frontier.
- `figures/`: PNG and SVG plots.
- `src/optimize_doublet.py`: complete model source.

## References

- Elecraft KX2 Owner's Manual, KXAT2 specifications and ATU behavior.
- RigExpert MATCH Owner's Manual, complex-impedance measurement modes.
- M. Cerveny and P. Hazdra, “Evaluation of the Input Impedance and Impedance Quality Factor of a Dipole in Spatial and Spectral Domains,” Radioengineering 26(4), 2017, DOI 10.13164/re.2017.0968.
- Poly-STEALTH 26 AWG product description: 7-strand copper-clad steel, polyethylene jacket, approximately 1.32 mm OD. Exact conductor construction for the installed spool remains unverified.
