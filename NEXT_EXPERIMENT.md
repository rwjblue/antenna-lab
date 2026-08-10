# Next experiment: reversible 57/28 validation

## Objective

Measure how the real antenna changes after a one-foot total radiator reduction,
then use that second physical anchor to calibrate the model's impedance slope
with length (`dZ/dL`).

## Procedure

1. Record the current 58 ft radiator / 28 ft feedline as the baseline.
2. Do not cut any wire. Fold back 6 inches at each free radiator end so the
   effective total radiator is approximately 57 ft.
3. Keep center height, apex angle, endpoint height, wire orientation, ground,
   feedline routing, choke, and nearby objects as constant as practical.
4. Repeat RigExpert R+jX measurements at the radio end of the deployed balanced
   line on 7.050, 10.120, 14.050, 18.080, 21.050, 24.910, and 28.050 MHz.
5. Save the native analyzer export if available, plus a new canonical dated CSV.
6. Repeat and separately record first-pass and second-pass KXAT2 tuning on all
   seven bands. Retain the known 20 m behavior: the second search previously
   resolved the apparent failure and produced 1.0:1.
7. Compare measured 57/28 minus 58/28 impedance changes with the model's paired
   predictions. Do not compare only tuner-side SWR.
8. Fit/calibrate per-band `dZ/dL` using the two physical radiator lengths and
   rerun uncertainty analysis.

## Decision rule

Cut nothing until repeated deployments show a useful, stable 17 m improvement
without unacceptable tuner coverage or regressions on the other bands. A null
or mixed result is valuable because it constrains the surrogate model.
