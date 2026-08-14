# ATU loss model

This study separates three different quantities that are often collapsed into
one statement about an antenna being “efficient”:

1. **Antenna radiation efficiency**: power accepted at the antenna feedpoint
   that NEC predicts will be radiated rather than dissipated in the modeled wire
   and ground.
2. **Tuner efficiency**: power accepted by the tuner input that reaches the
   antenna load rather than being dissipated in inductors, capacitor ESR,
   relays, and fixed series resistance.
3. **Transducer efficiency**: source available power that reaches the load. This
   includes both tuner dissipation and residual input mismatch.

For the direct-fed 41 ft radiator / 17 ft counterpoise there is effectively no
feedline between tuner and antenna. The tuner is therefore the principal
intentional matching-loss element that is absent from the NEC antenna-efficiency
number.

## Switched-L network calculation

The automatic-tuner model enumerates every discrete inductor and capacitor
state for both supported L-network orientations:

- series inductance followed by a load-side shunt capacitor;
- source-side shunt capacitor followed by series inductance.

For each state the model uses complex impedances with finite component Q and
relay/contact resistance. It calculates input impedance, input SWR, accepted
power, load power, component dissipation, tuner efficiency, and transducer
efficiency. Two search objectives are retained:

- `best_swr`: closest match, similar to a tuner firmware search that minimizes
  measured reflected power;
- `lowest_loss_under_target`: highest transducer efficiency (load power divided
  by source available power) among states at or below the requested SWR
  threshold. The study retains separate 1.5:1 and 2.5:1 selections.

Comparing these objectives shows when the very best SWR is not the lowest-loss
usable state.

The 2.5:1 result is also the rollback boundary used in result summaries. A
higher residual SWR is flagged as likely to make the KH1 reduce RF output; the
flag is a conservative modeling rule, not a published Elecraft trip point.

## Loss sensitivity envelopes

Exact in-circuit Q and contact resistance are not published for these tuners and
will vary with frequency, current, component tolerance, construction, and age.
The study therefore reports explicit conservative, nominal, and optimistic
loss envelopes rather than one falsely precise insertion-loss value.

| envelope | inductor Q | capacitor Q | relay contact | fixed series |
|---|---:|---:|---:|---:|
| conservative | 35 | 800 | 0.050 ohm | 0.040 ohm |
| nominal | 70 | 2000 | 0.025 ohm | 0.020 ohm |
| optimistic | 120 | 5000 | 0.012 ohm | 0.010 ohm |

These are sensitivity assumptions, not manufacturer specifications. Actual
state measurements and insertion-loss measurements should narrow them.

## Tuner profiles and provenance

### Elecraft KXAT2 / KX2

The KXAT2 profile uses the seven inductor and seven capacitor banks shown in the
official KX2 schematic. The effective capacitor values account for the paired
82 pF bank used for the nominal 160 pF step.

- inductors: 0.063, 0.125, 0.25, 0.5, 1, 2, 4 uH;
- capacitors: 10, 18, 39, 82, 164, 330, 680 pF;
- modeled range: 1.8–30 MHz.

Source: [Elecraft KX2 schematic files, rev. A](https://ftp.elecraft.com/KX2/Manuals%20Downloads/E740324%20KX2%20Schematic%20Files%20RevA.pdf).

### Elecraft KXAT3 / KX3

The KXAT3 profile uses the eight inductor and eight capacitor banks shown in the
official KX3 schematic.

- inductors: 0.06, 0.12, 0.25, 0.5, 1, 2, 4, 8 uH;
- capacitors: 10, 18, 39, 82, 164, 330, 680, 1360 pF;
- modeled range: 1.8–54 MHz.

Source: [Elecraft KX3 schematic diagram](https://ftp.elecraft.com/KX3/Manuals%20Downloads/KX3SchematicDiagramDec2012.pdf).

### Elecraft KHATU1 / KH1

The KH1 owner’s manual documents a medium-range series-L/shunt-C tuner, a
switchable high/low impedance orientation, eight latching relays including the
orientation relay, and an `ATU PARAM` diagnostic that displays the selected L,
C, and Z state. Public documentation does not expose the individual L/C bank
values. The current profile is therefore an explicitly labeled 4-L/3-C inferred
bank that is constrained by the observed 58/28 tune/fail behavior. It must not
be treated as the KHATU1 bill of materials.

Source: [Elecraft KH1 owner’s manual, rev. B7](https://ftp.elecraft.com/KH1/Manuals%20Downloads/KH1%20Owner%27s%20Manual,%20rev%20B7.pdf).

Populate `data/measured/atu_states_template.csv` with `ATU PARAM` observations
to replace the inferred aggregate state with measurements.

### LDG Z-11Pro II

The Z-11Pro II manual documents a switched-L network, a high/low-Z relay, 1.8–54
MHz coverage, and a specified 6–1000 ohm matching range without the optional
4:1 transformer. Current public documentation does not provide the individual
L/C bank values or a service schematic. The repository profile is therefore a
range-fit 8-L/8-C binary bank used to explore plausible loss, not a claim about
the production board.

Source: [LDG Z-11Pro II product documentation](https://ldgelectronics.com/index.php/products/zero-power/z-11proii/).

### EMTECH ZM-2 — BNC prebuilt

The modeled unit is the EMTECH `ZM-2 - BNC Connectors - Prebuilt`. It is rated by EMTECH for 80 through 10 meters and 15 W maximum. The ZM-2 is not an L network. It is represented as a coupled-resonator Z-match
using the documented 27-turn primary with 16/11-turn tap choices, 7-turn link,
dual 266 pF capacitors, and switched 500 pF input capacitance. The model solves
capacitor settings and tap choice while including finite coil and capacitor Q.
The documented SWR-indicator bridge is modeled as bypassed during normal operation, as instructed after tuning. Core AL, frequency-dependent core loss, coupling coefficient, winding parasitics, and variable-capacitor law are not yet calibrated, so the topology is specific to the owned unit but its loss result remains a sensitivity estimate.

Sources: [EMTECH ZM-2 BNC prebuilt product page](https://emtech-qrp.com/product/zm-2-bnc-connectors-prebuilt/) and [EMTECH ZM-2 construction and operation guide](https://manuals.plus/m/77d9a99e14f1a25e02aa2c2a9489da5db5e04c52c27d9c256ca3dbc769cac1fa).

## Reproducing the study

One-shot local execution:

```bash
sudo apt-get install nec2c
uv sync --frozen --no-editable --group dev
uv run antenna-lab run-atu-loss-study --output build/atu-loss
uv run antenna-lab verify-results build/atu-loss
```

The GitHub Actions pipeline runs the same work in stages:

```bash
antenna-lab run-atu-direct-nec --output build/atu-input
antenna-lab run-atu-profile-study \
  --direct-nec-csv build/atu-input/atu-direct-nec.csv \
  --profile kxat2 \
  --output build/atu-kxat2
antenna-lab assemble-atu-loss-study \
  --input build/atu-artifacts \
  --output build/atu-loss
```

The CI matrix evaluates KXAT2, KXAT3, KHATU1, Z-11Pro II, and ZM-2 independently,
then assembles a manifest-verified canonical artifact.

## Measurement plan

For each radio/tuner and band:

1. Measure raw antenna `R+jX` at the tuner output reference plane.
2. Tune normally and record final SWR.
3. For KH1, record `ATU PARAM` L, C, and Z values. Record equivalent state data
   from KX2/KX3 diagnostics when available.
4. Repeat the tune from a cleared or deliberately different state to determine
   whether firmware lands on multiple equivalent matches.
5. Measure tuner insertion loss with a VNA or two-power-meter fixture at a safe
   level and compare against the predicted state.
6. Repeat at representative power to detect current-dependent inductor or relay
   loss, while staying within tuner ratings.

A useful field result is not merely “the tuner found 1.0:1.” The relevant output
is end-to-end power delivered to the modeled antenna, including tuner loss and
residual mismatch.
