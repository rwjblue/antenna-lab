# Portable linked dipole: construction, assumptions, and field validation

This study represents **one physical, symmetrical 20/30/40 m antenna**. Every
wire section remains deployed on every band. The default is **tune once with a
33 ft feedpoint and 10 ft outer ends, then keep the wire lengths fixed** when
changing deployments. Read the [computed comparison](../../results/linked-dipole-v1/README.md)
with
the repository's [model limitations](../../MODEL_LIMITATIONS.md) and
[SWR/efficiency distinctions](../efficiency-and-swr.md). All finished model
lengths are provisional; they are not a cutting schedule.

## Practical starting point

- Preserve the existing tuned 20m legs and folded ends.
- Cut two **8 ft raw blanks** for the 30m extensions, one per side.
- Cut two **11 ft 6 in raw blanks** for the 40m extensions, one per side.

These extension blanks include tuning and construction allowance. The generated
README shows the provisional section dimensions for the 10 ft default alongside
the actual raw-cut recommendation. Do not transfer model dimensions directly
to cuts: link-center references, wire threading, connector tails and folded ends
are different physical measurements. Recheck the existing 20m match after adding
the disconnected but deployed extensions, then finish tuning 30m and 40m and
recheck all bands. Changing end height does **not** require trimming the antenna
again. The fixed-length SWR table and full-band sweeps show the resulting match;
the separate retuned comparison is optional.

## Construction evidence

The [construction note](https://rwjblue.com/notes/2026-09-13-compact-20-meter-dipole/)
describes approximately 17 ft raw cuts per leg with folded ends and field tuning
in an inverted V whose center was estimated at 40 ft. The published 1.09:1
minimum at 14.135 MHz and 1.42:1 at 14.315 MHz are observational context.
Unknown end positions, folds, feedline and measurement reference plane prevent
using them as a precise calibration or efficiency measurement.

The user's new extension blanks are 8 ft per leg for 30 m and 11 ft 6 in per leg
for 40 m, including tuning allowance. Neither is a finished extension length.
The [printed insulator](https://www.printables.com/model/1842032-linked-dipole-link-insulators)
dimensions, approximately 38 × 10 × 2.6 mm, and relaxed connector tails are
user-supplied construction details; that page could not be independently read
through its access challenge. The 2 mm connector specification is **contact
diameter**, not connector length or unplugged spacing.

[DX Engineering's manufacturer-hosted specifications](https://www.dxengineering.com/search/part-type/wire?GroupBy=ProductName&SortBy=BestKeywordMatch&SortOrder=Ascending&keyword=insulators),
checked on 2026-09-14, distinguish the metal and jacket:

| Property | Nominal specification | Model input |
|---|---|---|
| Metal | Seven-strand, 26 AWG copper-coated steel | Effective round conductor |
| Metal bundle diameter | 0.019 in / 0.4826 mm | Radius 0.2413 mm |
| Insulation | Black, UV-resistant high-density polyethylene | Approximate lossless sheath loading |
| Jacket thickness | 0.011 in / 0.2794 mm | Separate from metal radius |
| Overall diameter | 0.041 in / 1.0414 mm | Jacket radius 0.5207 mm |

Copper thickness, RF resistance, strand-to-strand behavior and magnetic
properties are unavailable. The baseline effective conductivity of 10 MS/m
is an uncalibrated loss proxy. Sensitivities at 1.4 and 58 MS/m bracket a broad
range; the latter is an optimistic homogeneous copper comparator. These are
exploratory assumptions, not established limits for this product. In the
strong skin-effect limit, resistance scales approximately with
`1 / sqrt(conductivity)`, so these scenarios correspond to roughly 6.4×,
2.4× and 1× the smooth-copper reference resistance. Actual plated strands
need not follow that model exactly.

## Insulation approximation

The NEC2 model retains the **metal** radius and applies lossless distributed
series inductance only to the six jacketed sections. Source and link bridges
receive no sheath loading. This follows the empirical equation 1A in
[Cebik's insulation-model comparison](https://hamwaves.com/wire/doc/Insulated%20Wires:%20The%20NEC-2%20Way.html):

```text
L' = 2 × 10⁻⁷ × [(R/r) εr]^(1/12) × (1 − 1/εr) × ln(R/r) H/m
```

Here `r` is metal radius, `R` jacket radius, and `εr` assumed relative
permittivity. The nominal `εr = 2.3` gives approximately **99.36 nH/m** for
the manufacturer dimensions, before the configurable loading multiplier.
The approximation has the correct zero-loading limit for a bare wire.
Cebik compared this method with NEC4's insulated-sheath calculation for a
different wire and frequency. That correspondence does not validate this
particular product, dielectric dissipation, or fields around connector tails.
The study varies the loading from zero to 1.5 times nominal. Do not interpret
those settings as measured dry/wet polyethylene properties.

## Geometry and electrical links

Let `L` be the sum of the three per-leg section dimensions, `H = 33 ft`,
`h` the outer 40 m end height, and `d = H − h`. Section dimensions run from
the edge of the source bridge to a link center, between link centers, and
from the outer link center to the wire end. A short horizontal source bridge
is specified separately. For distance `s` along a leg:

```text
height(s) = H − d s/L
horizontal leg run = sqrt(L² − d²)
included apex angle = 2 acos(d/L)
```

Evaluate the height at the first section length for link A and at the first
two sections combined for link B. The outer-end constraint consequently
raises the shorter active-section endpoints well above `h` on 20 and 30 m.
The angle describes the two straight leg slopes extrapolated across the
small horizontal source bridge.

With a cord continuing along each leg's slope to level ground:

```text
cord length beyond wire = L h/d
stake distance from mast = half source bridge + sqrt(L² − d²) H/d
```

These are geometric lengths; add practical allowance for knots, wrapping and
slack. The flat-top case has `d = 0`: its cords cannot reach ground while
continuing horizontally, so ground-stake and cord lengths are undefined.
It requires elevated end supports.

Both A links are open on 20 m; both B links are normally open on 20 and 30 m.
Closed links have explicit conducting bridges and one contact resistance per
link. Open links remove only those bridges, leaving disconnected sections in
the NEC interaction matrix. A separate 20 m sensitivity closes both B links
while leaving A open. The nominal 38 mm open gap is an explicit assumption,
not an inference from the insulator length; the sensitivity changes its size.
Collinear breaks cannot reproduce unmeasured loops, folded wire, connector
bodies, plastic insulators or arbitrary tail routing.

NEC's endpoint-connection threshold is 0.001 times segment length in the
local solver source. Numerical validation checks that open endpoints remain
disconnected, and varies the mesh and source dimensions. A continuous
source segment is required by the
[NEC User's Guide](https://www.nec2.org/other/nec2prt3.pdf), even though the
physical BNC presents a feed gap. Small bridges and the thin-wire source
approximation require convergence checks; resolving a gap in the input file
alone does not establish numerical accuracy.

Sequential nominal tuning adjusts 20 m, then 30 m, then 40 m in the 33/10 ft
geometry, with all three bands rechecked using the completed assembly.
The default tuning height is configurable. The primary comparison then freezes
those dimensions across 5/10/15/20/33 ft outer ends. Comparisons from 5 ft to flat
describe those physical deployments of the same antenna; they do not identify
5 ft as the tuning reference. Retuned comparisons require different section
dimensions or reversible adjustments and are optional.

The ideal balanced feed is the reference plane. Feedline/common-mode
currents, mast coupling and actual coax/choke/tuner losses remain absent
because their physical inputs are unknown. Pattern azimuth 0° is along the
wire span; 90° is broadside. Neither low SWR nor high gain in one direction
establishes high radiation efficiency. Use the study's integrated
upper-hemisphere power accounting rather than NEC's printed efficiency
percentage alone. Pattern differences do not imply guaranteed contact ranges.

## Reading the polar radiation plots

The [computed report](../../results/linked-dipole-v1/README.md#read-the-radiation-shape-at-a-glance)
starts with the 10 ft default against the flat top, then compares all five
deployments. Its polar plots and the viewer use the saved computed samples;
changing the display does not rerun the solver or change the antenna model.

Read outward as stronger radiation. Every polar panel uses the same absolute
gain rings from **−30 to +12 dBi**; each curve keeps its actual gain rather than
being normalized to its own peak. These outlines describe directional gain,
not contact distance or physical wire shape. Deeper nulls reach the −30 dBi
plot floor. Accepted-power gain already includes the modeled wire and ground
effects; realized gain applies the 50 Ω mismatch once as well.

A vertical slice covers the upper half of the sky: its baseline is the horizon
and its top is straight overhead. The two sides use actual computed samples
at opposite azimuths. No below-ground pattern is inferred or drawn. Broadside
slices use the directions perpendicular to the wire span; end-on slices use
the directions along it. In the broadside slice, the right horizon is azimuth
90° and the left horizon is 270°; both have 0° elevation.

The horizontal-direction plots look around the antenna while holding elevation
at a useful angle, such as 20° or 60° above the horizon. A literal 0° horizon
cut would show an unhelpful null in this ground model. Azimuth 0°/180° lies
along the wire span, and 90°/270° is broadside; these are antenna-relative
directions, not compass bearings. The report retains angle-versus-gain charts
for reading small differences and offers both PNG and SVG downloads of every
static figure.

For further background, see the [ARRL antenna modeling tutorials](https://www.arrl.org/antenna-modeling-for-beginners).

## Short field-measurement plan

1. **Measure the assembled antenna first.** Record each section from feed or
   link reference points, exposed copper and folded-back lengths, connector
   lengths, unplugged gaps and tail routing. Photograph each open and closed
   link next to a ruler. Record the mast material, coax type/length and choke.
2. **Make the impedance reference plane repeatable.** Calibrate the analyzer
   at the feedpoint where practical, or characterize and de-embed the exact
   feedline. Keep its routing repeatable and record the reference plane.
   Save complex impedance sweeps, not only an SWR screenshot.
3. **Tune and document 33/10 ft, then freeze the wire.** Measure center, both
   outer ends, both link heights, span and sag. Tune in 20/30/40 m order and
   recheck all three. Repeat 5/10/15/20 ft end heights without adjusting wire;
   use the same site and orientation. Extend sweeps whenever the minimum
   leaves the band. Record both zero-reactance and minimum-SWR frequencies.
4. **Test the consequential uncertainties.** At fixed geometry on 20 m,
   compare B open versus closed while A remains open; then change open-tail
   spacing/routing. Check contacts repeatedly after reconnecting. A four-wire
   DC contact measurement can flag poor contacts but does not establish RF
   wire or contact loss. Repeat useful geometries after a soil-moisture change.
5. **Separate feedline effects from geometry.** Check common-mode current
   and repeat a sweep with a documented change in coax routing/choke placement.
   Changes expose an omitted system effect; do not compensate for it by
   silently changing the antenna's modeled conductivity.
6. **Compare radiation with repeated observations.** Alternate geometries
   rapidly at fixed power, frequency and orientation using stable remote
   receivers when available. Use several directions and repeated trials to
   reduce propagation bias. Contact counts, signal reports and SWR cannot
   independently determine absolute radiation efficiency.
