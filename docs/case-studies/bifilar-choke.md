# Open dipole-center 1:1 current balun

**Later reassessment, same date:** [pragmatic build decision](balun-decision.md)
supersedes the provisional wire selection below. It recommends testing a
controlled-spacing owned 18 AWG pair against FEP before purchasing 22 AWG,
and adds differential loss, proximity, fit and verified termination details.
The original magnetic screen remains useful as an uncalibrated sensitivity.

Initial baseline, 17 September 2026: **one Fair-Rite 2631801202
(29 × 19 × 13.85 mm, mix 31), 12 bifilar turns of heavy-build 22 AWG enamelled
copper wire**. Leave the core exposed, with thin abrasion protection, two
compliant mounting pads and nylon ties. Cut two 700 mm lengths, then trim leads
after fitting. This is a prototype for a resonant/linked center-fed dipole,
primarily 40/20 m with 30/17/15 m, normally 12/50 W CW and a 100 W design goal.
It is **not yet qualified for 100 W**.

**Owned-wire update:** use the newly confirmed BNTECHGO 18 AWG magnet wire
as the first available-stock experiment, with 12 turns and short 22 AWG FEP
termination pigtails if needed. The original 22 AWG magnet-wire baseline above
is a comparison, not a confirmed owned spool. See [owned wire](owned-balun-wire.md)
for the eight products and why FEP/silicone are not automatic 50 ohm substitutes.

The companion printable project is
[`scad-lab/models/ham_radio/balun_dipole_center`](https://github.com/rwjblue/scad-lab/tree/main/models/ham_radio/balun_dipole_center).
The local file path is `../scad-lab/models/ham_radio/balun_dipole_center/` from
the antenna-lab root. The prior studies used generic choke-loss envelopes;
this new study adds small-signal winding scenarios without changing those
published antenna results.

## Why this core and winding

The [parts bin](https://rwjblue.com/radio/equipment/parts-bin/) lists the selected
core; the webpage still marks the August order incoming. Physical stock needs
counting, but no new ferrite type is required by the design.

- The single 22.1 mm mix 31 core is 7 g and offers less ferrite cross section,
  thermal capacity and aperture. Its 12-turn screening values are useful, but
  it is a less conservative starting point for the requested power envelope.
- Two stacked 22.1 mm cores total 14 g. Their magnetic geometry is competitive
  with the 24 g selected core, but the 13.7 mm aperture is tighter for paired
  wire and they add a core interface. This is a worthwhile later weight-saving
  experiment; the screen does not rule it out or certify either option.
- The 29 mm mix 31 core has a 19 mm aperture, greater thermal capacity, and
  direct published measurements of that exact part. It balances size, winding
  access and evidence. A 34 × 18 mm wound-envelope allowance fits the CAD.
- FT114-43 is a lighter same-aperture alternative. FT140-43 is larger; the
  61 mm mix 31 core weighs 118 g. Neither larger option earns its bulk for
  this first compact prototype. Two stacked 29 mm cores also add height/mass
  without establishing a better upper-band choke once capacitance dominates.

Mix 43 is also a valid choking material. Mix 31 is a reasonable preference
for this 40 m emphasis, not a rule separating all chokes from transformers.

**12 versus 13:** 13 turns increases the underlying magnetic impedance by
17.4%, before capacitance. It also adds conductor length and may change
capacitance. The 1–8 pF scenarios change the answer more than that extra turn:
some 20 m cases miss even a 2 kΩ magnitude target, for both turn counts.
Use 12 as the first build, preserve photographs/spacing, and measure it.
Try 13 only if 40 m needs improvement and a new five-band sweep still passes.
The calculations do not identify a statistically meaningful unique optimum.
An external BNC choke is a useful option if 17/15 m needs help, but its
installed effect must be checked; separated chokes and coax form a network.
An external choke does not repair poor differential match through the pair.

## Reproducible model

Run `mise run bifilar-choke`. Outputs are in
[`results/bifilar-choke-v1`](../../results/bifilar-choke-v1/README.md).

Two independent small-signal starting estimates are retained:

1. Fair-Rite material CSVs for μ′ and μ″, with the rectangular-section toroid
   integral `L0 = μ0 h ln(OD/ID)/(2π)`. Then
   `Zm = 2π f N² L0 (μ″ + j μ′)`. Stacked cores add ferrite height.
2. For the selected part only, the manufacturer's N=1 measured series R+jX
   CSV, scaled by N² **before** adding the winding bypass capacitance. This
   retains some one-turn fixture effects; it is not de-embedded intrinsic μ.

Each estimate is shunted with `Cp`:
`Zcm = 1 / (1/Zm + j 2π f Cp)`.
Cp values of 1, 2, 4 and 8 pF are **chosen sensitivity scenarios**, not measured
capacitances, confidence bounds or a guarantee the real winding lies within
them. They are held fixed across turn counts and core sizes to expose the
tradeoff, not to claim that physically different windings have identical Cp.
The material curves come from a standard specimen, so geometry scaling and
part variation are further uncertainties. No N² scaling of a measured
multi-turn resonant curve is used.

The sweep covers 10–14 turns and 41 frequencies in each specified band.
It reports minimum R, minimum |Z| and X extrema, keeping the two magnetic
estimates separate in the CSV. There is no probability-based score or power
rating. Interpolation is linear in log frequency, with no extrapolation.

The line-match screen treats 0.60 m of pair as a lossless line, terminated
in 50 Ω, with Z0=25/30/40/50/60/70/100/120/150 Ω and VF=0.65/0.8. These are scenarios,
not wire specifications. Thick-insulated hookup wire can have an unsuitable
line impedance despite an adequate conductor gauge. A tight heavy-enamel
pair is the compact starting construction; **gauge does not specify Z0**.

The copper screen uses 0.60 m per conductor, bulk copper resistivity
1.724×10⁻⁸ Ωm and the high-frequency round-wire skin approximation. At a
matched 100 W/50 Ω it estimates about 0.84 W on 40 m and 1.17 W on 20 m
for the pair of 22 AWG wires, before proximity effects, joints and mismatch.
20 AWG reduces these estimates by about 21%, not by an order of magnitude.
22 AWG also fits the specified 26–22 AWG ring-terminal conductor range;
20 AWG would need a suitable alternate termination. Use 20 AWG if measurements
show wire heating is limiting, then recheck pair Z0, winding space and match.
These conductor calculations are not ferrite-heating predictions.

Tests cover the quarter-wave line identity, matched-line identity, complex
parallel resonance, passivity, power accounting, core-stack/turn scaling,
out-of-range data rejection and copper skin scaling.

## Evidence and limitations

The [Fair-Rite source manifest](../../data/reference/ferrite/README.md) contains
download URLs and explains the raw data. Source hashes accompany the result.
[KN5L's original exact-part measurements](https://www.kn5l.net/Balun-CM/BalunMeasure/)
show a ten-turn assembly with resonance near 17.3 MHz. This is a useful warning
against ignoring capacitance, not a calibration for our pair.
[VE5REV's exact-part test](https://mjarc.ca/docs/T31-2631801202-TestData.pdf)
uses 12 turns of RG-316 and a crossover. It supports trying the core/turn
combination but supplies neither our bifilar winding's complex impedance nor
its differential match or thermal limit. Fixture S21 magnitude is not
installed common-mode current suppression.

The model does not solve three-dimensional fields, winding capacitance,
nonlinear ferrite behavior, temperature-dependent permeability, thermal
resistance, rain, nearby metal, or the antenna/coax common-mode source.
It cannot infer ferrite loss from transmitter output power. In ideal balance,
the two signal currents cancel core flux. Real common-mode current dissipates
power according to the **net common-mode terminal current** and `Re(Zcm)`;
do not confuse that current with differential current in either wire.
For a resistive 5 kΩ choke, 10/20/50 mA RMS net common-mode current corresponds
to 0.5/2/12.5 W. These illustrative current scenarios show why core size and
air exposure alone do not assign a wattage.

## Bench acceptance and the 100 W goal

1. Wind both conductors together in the same direction; **12 passages of the
   pair through the hole means 12 turns per conductor**, not 24. Protect the
   bare ferrite with thin PTFE tape, keep a gap between the input/output ends,
   keep leads short, and keep the pair close until the antenna-side split.
   Do not add a series join or a direct shell-to-leg bypass.
2. With no antenna connected, check continuity separately through each wire
   and isolation between wires and between wires and exposed ferrite.
   Repeat after mounting and gentle flexing. Inspect enamel at bends and ties.
3. Use a 50 Ω load across the antenna terminals to measure the differential
   path. The parts-bin 49.9 Ω, 0.25 W resistor is **analyser-only**. Target
   SWR ≤1.3 across all five bands with that load, and low insertion loss
   compared with the fixture/load directly. A calibrated two-port fixture
   should distinguish mismatch from dissipation.
4. Measure common-mode impedance separately: temporarily join A+B at each
   end, insert those two junctions between the centre pins of a calibrated
   50 Ω VNA series fixture, and join the two port shields directly. Neither
   winding junction goes to shield. Use complex linear S21:
   `Zcm = 100(1/S21 − 1) Ω`. De-embed the fixture, assess its residual bypass
   capacitance/dynamic range, and inspect R, X and |Z|. These are demanding
   high-impedance measurements; magnitude-only S21 cannot recover R and X.
   Prototype targets: |Z| ≥2 kΩ and R ≥1 kΩ on 40/20 m, preferably several
   kΩ resistive, and the same screen on 30/17/15 m before claiming coverage.
   Remove the temporary joins before normal operation.
5. Repeat the RF checks after mounting; pads, ties and nearby hardware can
   change capacitance. Log failures as well as passes. Add/adjust an external
   choke if needed, and measure the final installation.
6. Use a transmitter-rated load for power tests, then the intended resonant
   dipole and coax routing. Test 12 → 50 → 100 W, on 40 and 20 m first, then
   the other bands. Log ambient, core and wire/joint temperatures over repeated
   normal CW sending cycles until temperature stabilizes, plus the longest
   key-down/tune period actually intended. A balanced dummy load alone does
   not exercise deployment common-mode stress. Stay below the lowest verified
   wire/pad/print material temperature limit with margin; stop on continuing
   rise, odor, softening, changing SWR or insulation damage. Choose a numerical
   stop limit from the actual material specifications before transmitting.

Only the measured, mounted assembly in its tested duty cycle and deployment
can earn the requested 100 W qualification. The CAD and this screen make
that experiment concrete; they do not replace it.
