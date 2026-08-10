# 58 ft portable doublet

Status: measured baseline plus provisional, measurement-anchored optimization.

## Construction

The physical antenna is a center-fed inverted V with 58 ft of total radiator,
29 ft per leg, and 28 ft of homebrew balanced feedline at approximately 14 mm
conductor center-to-center spacing. The feedline conductors continue directly
into the radiator legs: there is no splice or connector at the apex. The wire is
believed to be DX Engineering Poly-STEALTH copper-clad-steel wire, approximately
25-26 AWG; the exact installed construction is unverified.

The station end is a KX2/KXAT2 with a Mix 31 current choke at the radio/feedline
transition and a BNC binding-post adapter.

## Measured radio-end impedance

These RigExpert readings are measured facts at the radio end of the deployed
28 ft balanced line. They are not apex impedances and are not efficiency
measurements.

| Band | Frequency | Measured R+jX |
| --- | ---: | ---: |
| 40 m | 7.050 MHz | 35.5 - j211.0 ohm |
| 30 m | 10.120 MHz | 31.0 - j25.5 ohm |
| 20 m | 14.050 MHz | 5.8 - j71.8 ohm |
| 17 m | 18.080 MHz | 2.3 - j35.1 ohm |
| 15 m | 21.050 MHz | 49.1 + j2.3 ohm |
| 12 m | 24.910 MHz | 4.3 - j16.0 ohm |
| 10 m | 28.050 MHz | 4.1 - j21.4 ohm |

The canonical rows and complete provenance are in
`data/measured/58ft_doublet_2026-08-08.csv`; the unchanged source transcription
is retained under `data/measured/raw/` and in both source ZIP archives.

## KX2/KXAT2 observations

| Band | Best observed SWR | Observation |
| --- | ---: | --- |
| 80 m | no match | Outside the original design target. |
| 60 m | 1.6:1 | Matched. |
| 40 m | 1.8:1 | Matched. |
| 30 m | 1.0:1 | Matched. |
| 20 m | 1.0:1 | First search stopped near 2.7-3.0:1; a second ATU search within about 5 seconds resolved it. |
| 17 m | 1.0:1 | Matched. |
| 15 m | 1.0:1 | Matched. |
| 12 m | 1.0:1 | Matched. |
| 10 m | 1.3:1 | Matched. |

The resolved 20 m behavior is part of the current baseline and must not be
reintroduced as a matching failure.

## Radiation-pattern findings

The preserved pattern model is an **analytical thin-wire approximation**, not
NEC/MININEC and not a transmission-line model. It assumes sinusoidal current on
a symmetric 120-degree inverted V, numerical far-field integration, average
ground through complex Fresnel reflection, and negligible differential-mode
radiation from the close-spaced balanced line. Patterns are normalized to each
configuration's peak and therefore do not show realized gain or efficiency.

For the modeled 20 ft and 30 ft center heights, 40 m remains high-angle/NVIS.
Raising the center to 30 ft produces mid-angle broadside lobes around 41, 34,
and 33 degrees on 20, 17, and 15 m. At 12 m additional lobes appear; at 10 m
the useful low-angle response is strongly multi-lobed and diagonal rather than
a simple broadside dipole pattern. Actual terrain, asymmetry, and common-mode
current can materially alter these shapes.

## Optimization methodology

The completed v1.0 study swept total radiator length from 48 to 68 ft and
balanced feedline length from 18 to 38 ft, both in 0.25 ft steps, across
40/30/20/17/15/12/10 m. Each candidate used a passive feedline uncertainty
ensemble over Z0, VF, and loss plus six baseline-anchored radiator-change
surrogates. The primary score was the 10th percentile of worst-band modeled
balanced-line efficiency. A raw-SWR percentile was used only as a heuristic
KXAT2 stress screen.

Only the 58/28 terminal impedances are measured. Absolute line-efficiency
intervals are broad; nearby paired comparisons and the broad favorable region
are more credible than exact percentages or the quarter-foot winner.

## Baseline conclusion and next experiment

The existing 58/28 antenna is already close to a robust multiband optimum. The
broad favorable region lies around 56.75-57 ft of radiator with about 28 ft of
feedline. The exact numerical v1.0 winner, 56.75/28.25, does not justify an
awkward feedline change.

The practical experiment is 57/28: fold back 6 inches at each free radiator end,
leave the feedline unchanged, and do not cut yet. The model's predicted 17 m
improvement is modest and uncertain, not guaranteed. Repeat the seven RigExpert
readings and both first- and second-pass KXAT2 searches, then use the measured
delta to calibrate `dZ/dL`.

## Limitations and future measurements

The main unknowns are exact line Z0/VF, RF resistance of the stranded
copper-clad-steel wire, the unavailable apex reference plane, KXAT2 network
loss, common-mode current, and deployment environment. See
`MODEL_LIMITATIONS.md` and `NEXT_EXPERIMENT.md` for the complete interpretation
and validation plan.
