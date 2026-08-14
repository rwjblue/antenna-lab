# Model limitations

The repository contains both the historical measurement-anchored doublet
surrogate and the current NEC-2/discrete-KH1 complete-system ensemble. They are
useful for designing the next measurement, not for asserting a uniquely correct
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

- The final KH1 ranking models its inferred discrete switched network. It does
  not turn the historical KXAT2 doublet optimizer into a KXAT2 loss simulation.
- Common-mode current has not been directly measured.
- Choke impedance and loss under the actual common-mode load are not modeled.
- Environment, soil, slope, vegetation, wire sag, and asymmetry can change both
  impedance and radiation pattern.
- Only the 58 ft physical radiator has measured terminal impedance. A second
  length is required to calibrate `dZ/dL`.

## Consequences for interpretation

- Absolute balanced-line efficiency is substantially less certain than the
  relative comparison of nearby candidates.
- The historical `published-v1.0` balanced-line efficiency excludes tuner,
  choke, radiator-conductor, common-mode, ground, and environmental losses. The
  new comparative result composes line, choke, KH1 tuner, mismatch, and NEC
  radiation efficiency, but common-mode current remains an unmeasured omission.
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

The ATU studies close the bookkeeping gap, but they do not make insertion loss a
measured quantity. KXAT2 and KXAT3 L/C banks come from published schematics;
their in-circuit Q, relay resistance, stray reactance, PCB loss, and current
dependence remain sensitivity inputs. KHATU1 topology is supported by Elecraft's
L/C/Z diagnostics and eight-relay description, while its 0.35 uH and 60 pF
binary increments are secondary-source corroborated rather than Elecraft
specifications. A wider profile is retained as sensitivity. Z-11Pro II values
are range-fit and ZM-2 is an uncalibrated equivalent circuit.

The final 2.5:1 `likely_power_rollback` field is a conservative engineering flag.
Elecraft documents protection-related power fallback but does not publish a
single SWR trip threshold. Treat the flag as a comparison aid, not firmware
reverse engineering.

Transformer and choke dB envelopes are source-backed but are not measurements
of the proposed 44/14 hardware. Dividing antenna impedance by turns ratio and
applying empirical dissipative loss is a screening approximation; leakage,
magnetizing current, parasitic capacitance, common mode, flux, and load-dependent
core loss require a measured equivalent circuit.

NEC cases include finite wire conductivity and real ground, but the solver's
single efficiency result does not provide a fully reconciled radiation/wire/
ground power ledger. Nearby people, wet foliage, support loss, wire sag, and
unintended counterpoises are not represented. The radial vertical, near-end-fed,
fan, and trap geometries are screening sentinels, not construction-optimized
commercial antenna replicas.
