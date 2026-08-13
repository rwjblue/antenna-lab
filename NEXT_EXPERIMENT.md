# Next experiment: reversible feedline-extension validation

## Objective

Test the NEC-2 study's broad favorable region without cutting or rebuilding the
existing 58 ft radiator / 28 ft balanced-line antenna. The first experiment is
to add detachable balanced-line sections between 3.75 and 4.50 ft and measure
the actual radio-end impedance and KH1 tuning behavior on every required band.

## Procedure

1. Record the current 58 ft radiator / 28 ft feedline as the baseline.
2. Keep center height, apex angle, endpoint height, wire orientation, ground,
   feedline routing, choke, and nearby objects as constant as practical.
3. Measure radio-end R+jX on 7.050, 10.120, 14.050, 18.080, and 21.050 MHz.
   Also record 24.910 and 28.050 MHz when convenient.
4. Record KH1 tuning success and final SWR on 40, 30, 20, 17, and 15 m. Keep
   first and repeated tune attempts separate.
5. Insert a detachable balanced-line extension. Test at least 3.75, 4.00, 4.25,
   and 4.50 ft additions, or the nearest accurately measured lengths that the
   connector and strain-relief design permits.
6. Repeat the same R+jX and KH1 measurements for each extension. Save native
   analyzer exports when available plus a canonical dated CSV.
7. Compare measured changes against the modeled ensemble by band. Do not judge
   only by tuner-side SWR; retain R+jX and deployment notes.
8. Remove the extension and repeat the baseline once to estimate deployment and
   measurement repeatability.

## Decision rule

Select an extension only if repeated deployments show stable KH1 coverage on all
five required bands without an unacceptable efficiency or matching regression.
Treat the model's 3.75-4.50 ft interval as a test window, not a cutting length.

## Secondary build

After the extension experiment, a separate compact direct-fed trial may use a
35 ft radiator with an explicit 17 ft counterpoise. Test it against the same
five-band measurement protocol. A 35/25 ft version is the modeled robustness
reference but uses more wire; the 35/17 ft build is the compact field trial.

## Extended-band measurements

For the 41/17 direct-fed trial, collect raw feedpoint `R+jX` and tuner outcome on
80/60/40/30/20/17/15/12/10 m with the KX2. Record 6 m only with equipment that
supports it. Keep deployment geometry, counterpoise orientation, and ground
condition in the notes; those variables are part of the modeled ensemble.

## Tuner-loss validation

The 41/17 direct-fed build is the preferred system-level validation article
because it removes mismatched feedline loss. For each available tuner—KXAT2,
KXAT3, KHATU1, Z-11Pro II, and ZM-2—record raw feedpoint `R+jX`, final SWR, and
selected tuner state when exposed by the device. Populate
`data/measured/atu_states_template.csv`. Then measure low-power insertion loss
with a calibrated VNA or power-meter fixture. Compare both the lowest-SWR state
and any alternate state below 1.5:1; the lowest-SWR state is not necessarily the
lowest-loss state.
