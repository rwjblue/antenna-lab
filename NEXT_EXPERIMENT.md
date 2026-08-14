# Next experiment: validate the linked-counterpoise KH1 system

## Primary build

Build a 41 ft radiator and 28 ft explicit counterpoise. Put a low-resistance,
strain-relieved connector or banana-plug break 14 ft from the feedpoint. Leave
the full 28 ft connected on 40/30/20/15 m and disconnect the outer 14 ft only on
17 m. Stow the disconnected tail away from the active wire.

This composition has 69.1% p10 worst-band efficiency, 100% modeled all-band
success at 2.5:1, and weighted p10/p50/p90 efficiency of about 77.8/82.9/88.1%
for the operator's 40/20-first priorities. This is a model-directed prototype,
not a validated construction length.

Do not build the formerly recommended untransformed 41/17 ft system as the
primary article. Under the corrected discrete KH1 model it has 0% all-band
success at 2.5:1 and a 50.8% conservative rollback-flag rate. Retain an exact
41/17 measurement only as a useful falsification/control case.

## Link characterization first

1. Measure closed-link resistance and verify stable contact after repeated
   mating, flexing, and field contamination.
2. Measure isolation with the link open on all five bands.
3. Compare the open tail physically separated, hanging, and folded alongside
   the active 14 ft section; the last two expose coupling omitted by the model.
4. Record connector type, strain relief, spacing, routing, and weather state.

## Field matrix

For 41/28 closed and 41/14 open-link states:

1. Measure tuner-bypassed R+jX at the antenna feedpoint when practical and at
   the KH1 tuner output plane on 7.050, 10.120, 14.050, 18.080, and 21.050 MHz.
2. Repeat ground-side, ground-collinear, table-side, and table-collinear
   deployments. Record feed/support/counterpoise heights, soil, slope, weather,
   wire routing, and nearby objects.
3. Preserve native analyzer files plus a canonical dated CSV with reference
   plane and calibration method.
4. Record KH1 L/C/Z diagnostic values, residual SWR, tune time, transmit power,
   supply voltage, temperature, and any power fallback for first and recalled
   tunes.
5. Where instrumentation permits, record RF power immediately before and after
   the tuner. Reconcile accepted, dissipated, delivered, and field-strength
   proxies.

## Reference and decision rule

Deploy the five-band resonant linked dipole on the same support as the efficiency
reference. Alternate the candidate and reference frequently in paired
field-strength or WSPR observations so propagation drift does not become an
antenna result.

Promote the linked 41/28 build only if 40/20 always meet the chosen operational
SWR/power criterion, all five bands remain usable, and nearby-tail tests do not
materially degrade the open 17 m state. Otherwise compare nearby detachable
counterpoise lengths using measured pre-ATU-to-delivered power, not lowest SWR.

The existing 58 ft balanced-doublet feedline-extension test remains a separate
KX2/KXAT2 case-study experiment. It is no longer the recommended path for the
compact KH1 system objective because its discrete-KH1/mismatch-loss lower tail
is poor.
