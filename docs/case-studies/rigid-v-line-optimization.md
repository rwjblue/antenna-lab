# Second round: line length and 25 ft whips

**About 30 ft of balanced line remains the best compact starting point for both
17 ft and 25 ft arms at a 30 ft feedpoint.** The more important electrical change
is using longer arms: they ease the 40 m load substantially, while shifting the
upper-band impedance peaks and radiation lobes. They are not a uniform upgrade
across 40–10 m.

See the [generated comparison](../../results/rigid-v-line-optimization-v2/README.md)
and [configuration](../../configs/rigid-v-line-optimization-v2.json). This round
adds generic tuner dissipation to the first study's line-loss and ideal L/C
screens. Its recommendations supersede the earlier line-ranking interpretation;
the original observations and numerical outputs remain preserved.

## What actually improves

These values are **available transmitter power delivered to the antenna port**,
using nominal line parameters and a generic lossy continuous tuner. They include
input mismatch and tuner/line loss; they exclude balun, coax, common-mode and
radiator loss. They are not measurements or total radiation efficiency.

| Arms | 40 m with 32.81 ft line, 1:1 | 40 m with 30 ft line, 1:1 | 40 m with 30 ft line, ideal 4:1 |
|---|---:|---:|---:|
| 17 ft each | 57.2% | 62.1% | 67.9% |
| 25 ft each | 78.8% | 80.8% | 87.3% |

Shortening the original line to 30 ft improves nominal 40 m delivery by about
**0.35 dB with 17 ft arms** and **0.11 dB with 25 ft arms**, retaining a 1:1
interface. These are modest improvements. At the same 30 ft line length and
1:1 ratio, changing to 25 ft arms improves 40 m delivery by about **1.14 dB**.

The ideal 4:1 transformation is worth testing, but its extra advantage over
1:1 at 30 ft is only about **0.38 dB for 17 ft arms** and **0.34 dB for 25 ft**
on nominal 40 m. An actual 4:1 balun that adds that much loss would erase the
advantage on this comparison. It also has to provide suitable balance in the
installed arrangement. The computation does not establish the best real balun.

The exact best compact grid coordinate is 29.75 ft, just above the assumed
29.66 ft minimum physical route. This is primarily a shortest-practical-line
result, not a special resonance at 29.75 ft. Exactly 30 ft is also included in
the expanded validation. Coarse near-best intervals for ideal 4:1 are roughly
30–32 ft for 17 ft arms and 30–39 ft for 25 ft arms; only shortlisted points
within these intervals receive the full uncertainty check.

Longer runs were searched through 100 ft. The 25 ft model has an interesting
region around 83–85 ft; its 1:1 finalist can outperform the compact 1:1 finalist
on the conservative delivery metric. However, neither arm length's best long
run beats its best compact ideal-4:1 result. For a hitch setup, the additional
suspended line and routing are difficult to justify from this model alone.
Excess balanced line cannot simply be assumed harmless when coiled or laid
against the truck; that geometry is outside the transmission-line model.

## Why 25 ft is a tradeoff

At the nominal geometry, 40 m feedpoint impedance changes from approximately
12.3−j838 Ω to 30.1−j380 Ω. With the 10 m line, modeled line loss falls from
1.31 dB to about 0.25 dB. The longer radiator reduces the difficult short-antenna
matching burden, but its near-full-wave high-impedance region moves toward
17 m: the 18.1 MHz load is about 4510−j460 Ω.

The [pattern comparison](../../results/rigid-v-line-optimization-v2/pattern_comparison.png)
shows another important change. At 28.5 MHz, 20° elevation and the same broadside
azimuth, the 25 ft radiator has about **7 dB less antenna-port gain** than the
17 ft radiator. The lobes have moved; comparable peak gain elsewhere does not
make the same direction equally strong. Matching efficiency alone misses this.

At 30° arm elevation, the 25 ft pair spans about 43.3 ft horizontally, plus the
hub, and the tips rise 12.5 ft above it. The 17 ft pair spans about 29.4 ft and
rises 8.5 ft. Whip taper, section mass, telescoping joints, wind and ice loading
are not mechanically modeled. As an example of the scale involved, the
[REZ 25 ft manufacturer listing](https://www.rezantenna.com/product-page/z-25ss-25-telescopic-whip-antenna)
specifies 675 g per whip—1.35 kg for two before the hub and feedline. That is
not an endorsement of any mast's ability to carry them in an elevated V.

For winter use, the 17 ft pair remains the simpler all-band prototype. The 25 ft
pair is particularly interesting if 40/30 m capability justifies the additional
structure and different upper-band pattern. A 25 ft telescoping product can also
be tested at shorter extension, but this run compares fixed 17 ft and fixed
25 ft arms; it does not optimize every intermediate extension.

## What was computed

- Coarse search: 20–100 ft in quarter-foot steps, with explicit comparison
  lengths. After enforcing the 30 ft installation route, 568 fixed line/ratio
  combinations per arm length were evaluated at 37 frequencies.
- Expanded check: 113 shortlisted combinations across both arm lengths,
  65 frequencies, nine geometry/ground/radius cases, 27 independent dry-line
  combinations and three tuner-Q profiles: **5,354,505 network cases**.
- Geometry cases retain the same hub height and angle for the controlled arm
  comparison, then individually test 20/25 ft hub heights, 15°/45° arm angles,
  effective radii of 0.75/3 mm, and poor/good ground.
- Dry line cases cross air-geometry impedance 480/495/510 Ω, VF 0.93/0.97/0.99,
  and matched loss 0.03/0.07/0.11 dB per 100 ft at 10 MHz. Effective Z₀ equals
  air-geometry impedance × VF. The wet stress case remains separate.
- Generic tuner profiles use inductor Q 35/70/120, capacitor Q 800/2000/5000 and
  contact resistance 0.25/0.10/0.05 Ω. Exact finite-Q solutions seed bounded
  local L/C searches, selecting highest delivery among states reaching 2.5:1.
  These values and the continuous search are not LDG measurements or firmware.
- The objective prioritizes all-frequency matching within each coherent
  scenario, then worst-band tenth-percentile antenna-port delivery. Every band
  receives equal weight; one candidate retains the same line and balun ratio
  across all bands. Scenario percentages are not real-world probabilities.

[LDG's published aggregate limits](https://irp.cdn-website.com/4d6cc687/files/uploaded/Z-100A_Manual_Rev_B_10.pdf)
are 20 µH / 1300 pF and an advertised 10:1 SWR range. Several modeled terminal
loads exceed that advertised range. A successful match in the generic circuit
does not extend the manufacturer's specification or establish actual Z-100A
coverage, discrete-bank resolution, component heating, voltage or current limits.

This is the best validated shortlist under stated assumptions, not a proven
global optimum. A length that looked weaker in the nominal coarse search could
perform better in an untested joint uncertainty case. Numerical checks address
solver consistency; analyzer measurements must establish the installed system.

## Reproduce

```bash
NEC2C_PATH=/path/to/nec2c mise run rigid-doublet-optimize

# Compact checked-in result; requires the plots extra:
PYTHONPATH=src uv run antenna-lab optimize-rigid-doublet \
  --config configs/rigid-v-line-optimization-v2.json \
  --output results/rigid-v-line-optimization-v2 \
  --nec2c /path/to/nec2c --compact
PYTHONPATH=src uv run antenna-lab verify-results results/rigid-v-line-optimization-v2
```

The full build retains compressed dry-scenario arrays. The compact package keeps
rankings, band summaries, nominal decompositions, NEC loads, plots, numerical
checks and hashes. The isolated first-pass 25 ft config is also available at
[`configs/rigid-v-25ft-v1.json`](../../configs/rigid-v-25ft-v1.json).
