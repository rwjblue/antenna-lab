# Rigid V doublet for winter operation from the hitch

The [second-round line/whip comparison](rigid-v-line-optimization.md) adds
generic tuner dissipation, a wider uncertainty grid and 25 ft arms. Use it for
the current feed-line recommendation; this page preserves the video reference
and initial prototype plan.

This is a promising **parked-vehicle prototype**: two rigid whips give a balanced
radiator with one elevated support, and open-wire feed lets us change bands from
inside the truck. The first study models nominal 17 ft arms and explores the
feed system. It does not establish a mast rating or guarantee LDG tuning.

## What the video actually specifies

Tim / K5OHY's [follow-up video](https://www.youtube.com/watch?v=0ZBsUXsak9Y)
and its English automatic transcript were checked on 2026-09-14:

| Detail | Evidence |
|---|---|
| **10 m / 32.81 ft of open-wire line** | [12:36](https://www.youtube.com/watch?v=0ZBsUXsak9Y&t=756s); the reference to 20 m describes the band |
| 30 ft carbon-fiber mast, previously 20 ft painter's pole | [1:59](https://www.youtube.com/watch?v=0ZBsUXsak9Y&t=119s) |
| Claimed contacts/tuning on 40–10 m; LDG Z100A | [9:57](https://www.youtube.com/watch?v=0ZBsUXsak9Y&t=597s), [11:14](https://www.youtube.com/watch?v=0ZBsUXsak9Y&t=674s) |
| Usually 1:1 balun; sometimes 4:1 | [14:32](https://www.youtube.com/watch?v=0ZBsUXsak9Y&t=872s); exact deployment hardware unstated |
| Two 18-AWG conductors, nylon clothesline and zip ties | Description and [15:15](https://www.youtube.com/watch?v=0ZBsUXsak9Y&t=915s) |
| Drive-on base with printed mast collar | [15:36](https://www.youtube.com/watch?v=0ZBsUXsak9Y&t=936s); not a tripod |
| Line slopes away from mast; fence post separates it from truck | [16:09](https://www.youtube.com/watch?v=0ZBsUXsak9Y&t=969s) |

The [original build](https://www.youtube.com/watch?v=PJ4i3W5rRGI) specifies two
17 ft telescoping whips. Exact extension, V angle, conductor spacing, velocity
factor, mast construction and balun details remain unknown. The follow-up
discusses whip breakage and a top-heavy assembly; those matter for winter use.

## What line length does

For a lossless balanced line,

\[
Z_{in}=Z_0\frac{Z_L+jZ_0\tan(\beta l)}{Z_0+jZ_L\tan(\beta l)},
\qquad \beta=\frac{2\pi f}{c\,VF}.
\]

At an **electrical** half-wave, impedance repeats. At an odd quarter-wave,
\(Z_{in}=Z_0^2/Z_L\). This inverts the **complex impedance**; it does not remove
reactance or guarantee a convenient resistance. The script uses the existing
lossy ABCD line model, including mismatch-enhanced loss.

For example, our nominal VF 0.97 makes a 10 m physical line about 88.5° at
7.15 MHz, 175.5° at 14.175 MHz and 262.8° at 21.225 MHz. Small changes in VF,
length or frequency move these transformations. Nylon, wetness and routing can
change the installed line; a half-wave description is approximate.

The radiator is roughly half a wavelength on 20 m, but only a quarter wavelength
**total** on 40 m. The line can make its terminal load more manageable without
making the physical radiator longer. Cebik's [half-length dipole study](https://antenna2.github.io/cebik/content/wire/40hb.pdf)
compares radiator gain before matching losses and explicitly discusses the
loss/matching difficulty of the low-resistance, highly reactive half-size load.
Its copper straight-wire results are not substituted for the stainless V.

## First model and its boundaries

The [first generated results](../../results/rigid-v-doublet-v1/README.md) support
testing **roughly 30–33 ft of line**, starting with the video's 10 m length.
This is a candidate measurement window for the reference geometry and assumed
line parameters, not an established optimum. At nominal settings, all seven
samples have an ideal continuous match within the published L/C limits. On
40 m, the 10 m line transforms roughly 12.3−j838 Ω to 5.3+j259 Ω, with about
1.31 dB modeled line loss. The resulting raw SWR remains far outside 10:1.
That combination explains why component capability, loss and actual tuning
must be checked separately. Longer line is not automatically more helpful.

[The config](../../configs/rigid-v-doublet-v1.json) uses a nominal 120° included
upward V: **each arm is 30° above horizontal**. It compares feed heights of
20/25/30 ft, upward angles of 15/30/45°, and a horizontal reference. At the
nominal angle, the projected arm span is about 29.4 ft and tips sit 8.5 ft above
the hub. The single support saves ground anchors; it still needs overhead room.

Other cases compare effective radii of 0.75/1.5/3 mm, stainless conductivity
1.4 MS/m against a copper reference, poor/average/good ground, and floating
conductive mast proxies. Whip taper, alloy/permeability, telescoping contacts,
bending and ice loading remain unmeasured. The mast is offset in both horizontal
directions to avoid perfect left/right symmetry hiding induced current. It
does not represent the truck, mast joints, or line-to-mast coupling.

The NEC source uses a 6 cm, three-segment bridge between the arms, excited at its
middle segment so its immediate neighbors are collinear. Each arm retains its
full 17 ft length outside that bridge. The nominal mesh uses 181 segments per
arm; 91/181/259-segment checks and lossless free-space average gain are recorded
in the result package. Refining 181 to 259 changes reference impedances by about
0.08–0.11% across the seven bands. This verifies numerical consistency, not the
unknown physical dimensions or material properties.

The dry line scenarios reuse assumptions from
[our existing doublet config](../../configs/58ft-doublet-v1.0.json).
They are not measurements of either line, and the video's 18-AWG construction
differs from our nominal 25–26 AWG wire. A fourth, deliberately adverse wet-line
scenario explores lower VF and greater loss; it is not a measured weather model.
No impedance observations from the 58 ft radiator are used to calibrate this one.

The sweep covers 20–75 ft in half-foot steps and explicitly includes 28 ft,
10 m, 40 ft and 20 m. A simple route requires a sloping run from the hub to a
3 ft high tuner, with 6 ft horizontal offset and 2 ft slack. That requires
29.66 ft at the 30 ft height: **our 28 ft line is too short for this assumed
route**, although a higher tuner, reduced slack or lower mast can change that.

[LDG's Rev B manual](https://irp.cdn-website.com/4d6cc687/files/uploaded/Z-100A_Manual_Rev_B_10.pdf)
publishes 10:1 SWR and 20 µH / 1300 pF. The study reports that SWR screen and
separately solves a lossless continuous low-pass L network with shunt capacitance
on either side. These are **screening calculations, not a Z-100A circuit or
firmware model**. Continuous solutions can exceed the advertised SWR envelope;
passing does not promise a tune, and failing exact matching does not rule out an
acceptable residual SWR. Component steps, Q and balun loss could change outcomes.

The 4:1 cases divide complex line-end impedance by four using an ideal transformer.
They do not model common-mode suppression. LDG's [1:1](https://www.ldgelectronics.com/rba-1-1-current-balun)
and [4:1](https://www.ldgelectronics.com/rba-4-1-voltage-balun) products are
different balun types, not interchangeable lossless implementations.

## Hitch and winter ideas

- **Start at 20–25 ft, then compare 30 ft.** A receiver-mounted mast socket with
  antirotation and a way to assemble/lower the collapsed mast within reach would
  simplify gloved setup. Check tailgate/hatch clearance with the actual truck.
  A sturdy receiver does not establish the pole's top-load or wind capacity.
- **Account for the entire head load.** Two whips, hub, adapters and hanging line
  load the mast. A pole that supports a light wire doublet may be unsuitable.
  Make the hub replaceable, provide feed-line strain relief, and plan rotation
  control separately from structural guying.
- **Keep the balanced-line route repeatable.** Try a removable insulated outrigger
  and a support near the vehicle. Put the balanced/unbalanced transition at a
  dry, accessible point and investigate a short coax cabin entry. Any coax between
  line and tuner must be included in the next electrical model; it is absent here.
- **Make winter teardown part of the design.** Drain and dry telescoping sections,
  avoid trapping water in sockets, and choose hardware that can be operated with
  gloves. Max-Gain's [mast instructions](https://mgs4u.com/wp-content/uploads/2017/12/ASSEMBLY-INSTRUCTIONS-MK-and-PP.pdf)
  discuss hitch mounting, feedline weight, guying and freeze damage from trapped water.
- **Treat carbon fiber as a test variable.** SOTABEAMS' [mast measurements](https://www.sotabeams.co.uk/blog/ultralight-carbonfibre-masts-advantages-and-disadvantages/)
  show that behavior depends on construction. A small effect in our floating-mast
  proxy would not validate running balanced line against an arbitrary carbon pole.

## Prototype measurements

1. Record fully extended arm lengths, section diameters, hub spacing, actual angle
   and feedpoint height. Identify the mast and weigh the complete head and line.
2. Characterize line VF/Z₀ with the analyzer and measure its physical length.
   Compare removable sections around the video length with our 28 ft reference;
   avoid cutting the existing doublet to test this new geometry.
3. Record R+jX at a stated reference plane for all seven bands, first with the
   antenna isolated from the truck where practical, then in the actual hitch
   installation. Keep line height/route and all jumper lengths documented.
4. Try 1:1 and 4:1 interfaces at low power, logging full-tune results, residual
   SWR and operating power. Check common-mode current and hardware heating before
   interpreting a match as low loss.
5. Repeat the promising configuration at 20/25/30 ft and in dry/damp conditions.
   Compare 40 m and 30 m against the existing doublet with repeatable observations.

## Reproduce

```bash
NEC2C_PATH=/path/to/nec2c mise run rigid-doublet
# or:
PYTHONPATH=src uv run antenna-lab run-rigid-doublet-study \
  --config configs/rigid-v-doublet-v1.json \
  --output build/rigid-v-doublet-v1 --nec2c /path/to/nec2c --jobs 6 --plot --validate
PYTHONPATH=src uv run antenna-lab verify-results build/rigid-v-doublet-v1
```

The generated report separates NEC feedpoint quantities, line loss, tuner-port
impedance and ideal matching requirements. Raw solver decks/outputs are cached
under `build/rigid-v-nec-cache`; output and deck hashes are in `nec_loads.csv`.
Seven sample frequencies do not establish performance across entire bands.

Use `--compact --plot --validate --output results/rigid-v-doublet-v1` to
regenerate the checked-in subset; omit `--compact` to retain every line-sweep row.
Plotting requires the `plots` extra installed by the README's quick start.
