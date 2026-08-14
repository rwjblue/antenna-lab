# Next experiment: validate the 44/14 ft KH1 system

## Primary build

Build a 44 ft radiator and 14 ft explicit counterpoise with a compact, measured
4:1 transformer and a separate common-mode choke. Use detachable counterpoise
extensions or taps at 12, 14, 16, 24, and 28 ft so the most important nearby
Pareto candidates can be compared without cutting wire.

The 44/14 system is the recommended compromise because its 54.7% p10 worst-band
final efficiency is within 0.3 percentage point of the 52/28 ft non-reference
winner while using 22 ft less wire. This is a model-directed prototype, not a
validated construction length.

Do not build the formerly recommended untransformed 41/17 ft system as the
primary article. Under the corrected discrete KH1 model it has 0% all-band
success at 2.5:1 and a 50.8% conservative rollback-flag rate. Retain an exact
41/17 measurement only as a useful falsification/control case.

## Bench characterization first

1. Measure the 4:1 transformer and choke independently with calibrated two-port
   fixtures into representative resistive and complex loads on all five bands.
2. Report mismatch and dissipative insertion loss separately. A low input SWR
   into a resistor is not an efficiency measurement.
3. Record construction details: core part/material, turns, winding geometry,
   wire, enclosure, connector, mass, and temperature rise at 5 W.
4. Reject or widen the model envelope if measured transformer plus choke loss
   falls outside 0.30/0.55/1.50 dB optimistic/nominal/conservative totals.

## Field matrix

For 44/12, 44/14, 44/16, and 52/28 ft:

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
5. Where instrumentation permits, record RF power immediately before the tuner
   and after the transformer/choke. Reconcile accepted, dissipated, delivered,
   and radiated/field-strength proxies.

## Reference and decision rule

Deploy the five-band resonant linked dipole on the same support as the efficiency
reference. Alternate the candidate and reference frequently in paired
field-strength or WSPR observations so propagation drift does not become an
antenna result.

Promote 44/14 only if repeated deployments meet the chosen operational SWR/power
criterion on all five bands and measured transformer/choke losses remain within
the modeled envelope. Otherwise choose among the detachable 12/16/24/28 ft
counterpoise variants using measured pre-ATU-to-delivered power, not lowest SWR.

The existing 58 ft balanced-doublet feedline-extension test remains a separate
KX2/KXAT2 case-study experiment. It is no longer the recommended path for the
compact KH1 system objective because its discrete-KH1/mismatch-loss lower tail
is poor.
