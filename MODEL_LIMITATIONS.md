# Model limitations

The active optimizer is a measurement-anchored surrogate ensemble. It is useful
for designing the next measurement, not for asserting a uniquely correct
electromagnetic solution.

## Uncertain physical and electrical inputs

- Exact balanced-line characteristic impedance (`Z0`) has not been measured.
- Exact feedline velocity factor (`VF`) has not been measured.
- RF resistance of the installed stranded copper-clad-steel wire is unknown.
- Feedline and radiator are continuous conductors with no apex splice, so there
  is no direct feedpoint measurement.
- The exact installed Poly-STEALTH spool/strand/plating construction is not
  independently verified.

## Missing system models and observations

- There is no complete KXAT2 matching-network or insertion-loss simulation.
  Raw-SWR thresholds are heuristic screens, not tuner specifications.
- Common-mode current has not been directly measured.
- Choke impedance and loss under the actual common-mode load are not modeled.
- Environment, soil, slope, vegetation, wire sag, and asymmetry can change both
  impedance and radiation pattern.
- Only the 58 ft physical radiator has measured terminal impedance. A second
  length is required to calibrate `dZ/dL`.

## Consequences for interpretation

- Absolute balanced-line efficiency is substantially less certain than the
  relative comparison of nearby candidates.
- Balanced-line efficiency excludes tuner, choke, radiator-conductor,
  common-mode, ground, and environmental losses.
- The earlier conversational estimate of about 47% efficiency on 17 m was not
  measured and is retained only as disclaimed history.
- The six radiator surrogates are passive and exactly anchored at 58/28, but
  they are not independent experimental observations. PCHIP/global interpolation
  across bands is especially weak physically and is used only to widen model
  disagreement.
- The broad 56.75-57 ft by roughly 28 ft favorable region is more meaningful
  than the exact 56.75/28.25 numerical winner.
- Even the predicted 17 m improvement for 57/28 is modest and uncertain; it is
  not guaranteed.

The next reversible measurement described in `NEXT_EXPERIMENT.md` is required
before promoting provisional length-response conclusions to calibrated ones.

## Extended bands

The 80 m, 60 m, and 6 m additions are exploratory. They have no measured
58/28-doublet station-end anchor in this repository. Direct-fed-wire and linked-
dipole values on those bands are native NEC results; doublet values are radiator
feedpoint and pattern results only. The 6 m case also exceeds the transmit range
of the KH1 and KX2, but is retained for KX3/external-tuner comparison.

## ATU-loss model

The ATU study closes the earlier missing-system-model gap, but it does not make
insertion loss a directly measured quantity. KXAT2 and KXAT3 L/C banks come from
published schematics; their in-circuit component Q, relay resistance, stray
reactance, PCB loss, and current dependence remain sensitivity inputs. KHATU1
bank values are inferred pending `ATU PARAM` observations. Z-11Pro II bank
values are range-fit because public service data were not found. The ZM-2 model
is an uncalibrated coupled-resonator equivalent. Treat predicted loss as an
explicit uncertainty interval and design the next bench measurement from it.
