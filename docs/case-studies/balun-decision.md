# Pragmatic open dipole-center balun decision

17 September 2026. **Build one Fair-Rite 2631801202, 12 turns of the owned
18 AWG magnet-wire pair, with measured, controlled spacing and short 22 AWG
FEP termination pigtails.** First compare a 0.60 m sample against the owned
orange/yellow FEP pair. Choose the FEP instead if its completed assembly
passes the differential tests below: its flexibility, insulation and direct
crimps are real advantages. Do not buy another core or assume that touching
enamel gives a 50 Ω line.

The best small purchase is **Remington 22HNSP.125 heavy-build 22 AWG copper**,
with spacing selected by the same sample test. It saves about 5 g of copper
and allows direct Panduit crimps; it does not promise lower RF loss. Buy it
if the 18 AWG spacing is difficult to hold, the pigtails are awkward, or
those grams matter. There is no established electrical benefit that requires
buying it before testing the owned wire.

This is a prototype recommendation, **not a measured all-band choke or a
100 W rating**. The smallest useful decision experiment is two straight
pair samples, then one core wound with the winner. A second full winding
is needed only if the first fails or the sample results are close.

## Evidence and stock audit

This reassessment supersedes the provisional recommendations in
[bifilar-choke](bifilar-choke.md) and [owned-balun-wire](owned-balun-wire.md),
while retaining their manufacturer datasets and magnetic calculations.
No RF or thermal measurements of the user's assembly were available.

The requested n1rwj.com URL did not load in the research tool. I checked the
[published parts-bin page](https://rwjblue.com/radio/equipment/parts-bin/)
and the complete local `../rwjblue.com/src/data/radio-parts.ts`. The source
contains all eight specified wire products plus nine ferrite types,
connectors, terminals, heat shrink, capacitors and test resistors. The wires
are reported on hand; original spool lengths are not remaining stock.
Ferrites and most hardware still say **onHand: 0, incoming: …, 2026-08-13**.
Treat these as the user's purchased inventory, with physical receipt/count
still to verify. Thin PTFE tape, pads, tie grades and crimp tooling are not
itemized there. An entirely stock-only assembly presumes the protection and
mounting consumables already contemplated by the mechanical project are
available; otherwise add those consumables to the purchase list.

Evidence labels used here:

- **Manufacturer:** published dimensions, construction, ratings and raw
  ferrite curves; typical curves do not certify a wound assembly.
- **Published measurement:** KN5L and VE5REV's particular constructions.
- **Calculation:** the equations/CSV results in this repository.
- **Assumption/proposal:** spacing, effective dielectric constant, winding
  capacitance, acceptance limits and thermal duty cycle. None was fitted to
  this prototype.

The source lists the 29 mm core as 25 g; the current
[Fair-Rite page](https://fair-rite.com/product/toroidal-suppression-core-2631801202/)
specifies **24 g**, OD 29 ±0.75, ID 19 ±0.50, height 13.85 ±0.40 mm.
Use those tolerances for fit, and weigh the received part. Its one-turn
100 MHz impedance is not a usable HF multi-turn choke specification.

## Ranked shortlist

| Rank / purpose | Build | Why it earns a place | Main cost or condition |
| --- | --- | --- | --- |
| 1 — best owned-parts starting build | One 2631801202, 12 turns, spaced BNTECHGO 18 AWG enamel; 22 AWG FEP pigtails | Low copper resistance, existing stock, spacious aperture, controllable pair geometry | Stiff wire; about 8.9 g copper at 0.60 m per wire; spacing and splices take care |
| 2 — best modest purchase | Same core/turns, Remington 22HNSP.125, measured spacing | About 3.5 g copper, easier winding, known enamel build, direct P22 crimps | More conductor loss at comparable spacing ratio; still needs RF/thermal tests |
| 3 — easiest owned assembly, conditional challenger | Same core/turns, touching orange/yellow 22 AWG FEP | Durable insulation, flexible stranded wire, color identification, direct crimps | Likely high pair impedance; slightly larger package. Promote to first choice if measured match/loss pass |
| 4 — insulated purchase challenger | Same core, 12 turns, TE Spec 55 55A0111-22-6 or -9, flat touching pair | Smaller insulation envelope than owned FEP; stranded direct termination | Likely intermediate line impedance; upper-band match may be marginal; small-lot supply varies |
| 5 — later weight experiment | Two 2631801802 mix 31 cores, 12 turns of the selected pair | 14 g ferrite and similar magnetic geometry to the selected 24 g core | Tighter aperture, less thermal mass, altered pads and new RF/thermal qualification |

The weights are copper/core calculations, not weighed assemblies. First
spend effort controlling the line; the 29 mm core is not the main unresolved
choice. A low, resonant dipole may present 50–75 Ω or a reactive impedance;
the 50 Ω test is a reproducible test of the balun, not an assertion that the
antenna itself must be 50 Ω on every link setting.

## Core and turn comparison

The complete inventory was considered, rather than just the two cores in
the prior recommendation. This table uses the existing **material model,
12 turns and an arbitrarily common 2 pF bypass**. Values are band minima
of |Z| / R in kΩ; a common capacitance isolates magnetic geometry and is
not a prediction that different cores/wires have equal parasitics.

| Core | Bare OD × ID × height, mm; ferrite mass | 40 m | 20 m | Practical judgment |
| --- | --- | ---: | ---: | --- |
| 2631801202, mix 31 | 29 × 19 × 13.85; 24 g | 5.01 / 4.82 | 5.99 / 5.29 | Best first balance of aperture, evidence and size |
| 2631801802, mix 31 | 22.1 × 13.7 × 6.35; 7 g | 2.41 / 2.15 | 3.47 / 3.46 | Credible QRP/lightweight candidate, not disqualified electrically; less room and thermal capacity for 100 W goal |
| Two 2631801802 | 22.1 × 13.7 × 12.7; 14 g | 5.22 / 5.04 | 6.09 / 5.28 | Strongest later weight experiment |
| 5943001001, FT114-43 | 29 × 19 × 7.5; 13 g | 2.60 / 2.10 | 3.74 / 3.72 | Valid lighter alternate; shorter winding helps differential behavior, but less 40 m CM margin |
| 5943002701, FT140-43 | 35.55 × 23 × 12.7; 33 g | 4.97 / 4.42 | 6.09 / 5.60 | Larger aperture can ease coax/spacing; not a compelling magnetic improvement per gram |
| Two 2631801202 | 29 × 19 × 27.7; 48 g | 10.27 / 10.03 | 6.72 / 3.33 | Better lower-band magnetic impedance; too tall and not automatically better above resonance |
| 2631803802, mix 31 | 61 × 35.55 × 12.7; 118 g | 5.97 / 5.85 | 6.38 / 5.13 | Keep for external choking/test fixtures, not this compact center |
| 5943000601, FT82-43 | 21 × 13.2 × 6.35; 6.4 g | 2.39 / 1.92 | 3.46 / 3.42 | Small/light candidate, similar compromises to single 22 mm mix 31 |
| 2631800302 / 5943000301 | ~12.7 × 7.15 × 4.8–4.9; ~2 g | 2.16 / 1.91; 2.27 / 1.81 | 3.12 / 3.09; 3.29 / 3.23 | Numerical 12-turn rows are not physical feasibility: the aperture is too crowded for the preferred pairs, with very little thermal mass |

The ninth inventory ferrite, **2631250202** (6.35 × 2.95 × 25.4 mm sleeve,
2.9 g), belongs on a straight coax section. A string of sleeves adds
one-pass impedances approximately in series; do not apply multi-turn N²
scaling to the number of beads. Twenty-five sleeves alone are 635 mm long
and 72.5 g before coax: an external option, not a compact-center substitute.
The expanded CSV includes the sleeve's one-pass material screen.

Mix 43 is a valid current-choke material. The prior inventory labels
associating 43 with transformers and 31 with suppression are use suggestions,
not an electrical restriction. Mix 31 remains a sensible 40 m preference
here. Buying another material is not justified before measuring this stock.

For the chosen core, compare **10–14 turns**, starting at 12. The expanded
screen also contains 8 and 16 turns for trend context, not as preferred
builds. Thirteen increases the magnetic term by (13/12)² = 1.174 and adds
about 40–45 mm of wire per conductor. It can *reduce* R once capacitance
dominates. Ten or eleven can be better above resonance; try them if measured
40 m already has ample margin and 20–15 m is bypass-limited. Do not shorten
the winding just to conceal a high-impedance FEP line at the expense of 40 m
choking. Select the wire geometry first.

## Common-mode performance by band

The calculation remains `Zm = N²·Z_one_turn` or the separately retained
material/geometry model, followed by `Zcm = 1/(1/Zm + jωCp)`.
The [source manifest](../../data/reference/ferrite/README.md) identifies the
manufacturer CSVs. The table below uses **only the exact-part N=1 model,
12 turns**. Each entry is minimum R / range of X / minimum |Z| in kΩ over
the band; the extrema need not occur at the same frequency.

| Band swept | Assumed 2 pF: R / X / magnitude | Assumed 8 pF: R / X / magnitude | Implication |
| --- | --- | --- | --- |
| 40 m, 7–7.3 MHz | 5.43 / +1.13…+1.27 / 5.58 | 1.97 / −2.78…−2.74 / 3.38 | Strongest prospective coverage; first thermal priority |
| 30 m, 10.1–10.15 | 6.33 / −0.57…−0.54 / 6.35 | 0.86 / −2.19…−2.18 / 2.34 | R can already fall below the proposed floor |
| 20 m, 14–14.35 | 5.41 / −3.24…−3.08 / 6.30 | 0.34 / −1.57…−1.53 / 1.57 | Critical selection band: measure rather than infer from 40 m |
| 17 m, 18.068–18.168 | 3.53 / −4.01…−4.01 / 5.34 | 0.18 / −1.19…−1.18 / 1.20 | External CM assistance may be needed |
| 15 m, 21–21.45 | 2.35 / −3.88…−3.84 / 4.50 | 0.12 / −1.01…−0.99 / 1.00 | Most vulnerable to capacitive bypass and line mismatch |

These capacitances are **illustrative inputs, not estimated bounds**. A
real winding could lie outside all the cases. Neither this table nor its
capacitive reactance proves a crossover works. Negative X is not itself
a failure; substantial resistance reduces the chance of a sharp installed
resonance. A mostly reactive magnitude is less reassuring than the same
magnitude with substantial R.

[KN5L](https://www.kn5l.net/Balun-CM/BalunMeasure/) measured a ten-turn
assembly of this exact part with self-resonance around 17.3 MHz, and warns
against extracting intrinsic permeability from the multi-turn measurement
above its useful range. [VE5REV's original test](https://mjarc.ca/docs/T31-2631801202-TestData.pdf)
uses twelve turns of RG-316 with a crossover. These are useful construction
precedents, not this bifilar pair's R+jX, differential loss or power rating.

## Wire products and differential behavior

| Wire | Verified specification or explicit uncertainty | Decision |
| --- | --- | --- |
| Owned BNTECHGO 18 enamel, B07H7DP7RN | Polyurethane, 155°C; advertised 1.00 mm is inconsistent with treating nominal 1.024 mm bare 18 AWG plus enamel as a finished diameter | Measure bare/finished diameters. Use controlled spacing; not an automatic touching-pair winding |
| Owned BNTECHGO 28 enamel, B07HRKT1WQ | 155°C, unspecified enamel build; nominal bare 0.321 mm | More fragile; about twice the 22 AWG skin loss before proximity. Keep for low-power/measurement work rather than the first 100 W prototype |
| Owned FEP orange/yellow, B0D21RSJHX / B0D21LHTVL | 19 × 0.15 mm tinned copper, 1.42 ±0.10 mm OD, 300 V, −65 to 200°C | Valid full winding challenger and preferred pigtails; do not reject FEP as a material |
| Owned bonded 20 silicone, B077X9MVWG | Bonded red/black stranded pair; finished width/pitch not established here | Convenient but bulkier, not 50 Ω specified, and outside P22 gauge range. No clear advantage over the first two owned candidates |
| Owned 22 silicone, B071L3DBG1 | 1.7 ±0.1 mm OD | More aperture/face crowding than FEP without an established RF advantage |
| Owned 18 silicone, B071HH246Z | 2.3 ±0.1 mm OD | A flat single-layer 12-turn pair exceeds the available inner circumference in the fit screen; needs larger package/layering |
| Owned 28 silicone, B07HGT77R5 | Separate red/black, 1.2 ±0.1 mm OD | Small conductor with thick relative insulation: poor first compromise for loss, line impedance and 100 W durability |
| Purchase Remington **22HNSP.125** | 2 oz/62 ft; heavy min–nom build, nominal finished 0.0276 in = 0.701 mm; MW80-C polyurethane/polyamide, 155°C | Best inexpensive weight/termination improvement. Catalog family starts at $13.73, excluding shipping; confirm selected variant price |
| Purchase TE **55A0111-22-6** blue / **-9** white | Spec 55 crosslinked ETFE, 19/34 tinned copper, ~0.79 mm bundle, 1.09 mm OD, 0.13 mm nominal wall, 600 V, −65 to 150°C | Sensible thin-wall insulated alternative; test a short cut length before buying a spool |
| Purchase Alpha **5855** PTFE | 19/34 silver-plated copper, 1.295 ±0.127 mm OD, 600 V, −60 to 200°C; published bend radius 10× diameter | Little size advantage over owned FEP, and tight core bends need addressing. Not worth a large spool for this job |
| Purchase Alpha **2622** ThermoThin | ~1.12 mm OD, **10% nickel-plated** copper | Thin insulation alone is not enough: RF loss of the plated conductor is unqualified here. Prefer Spec 55 for the insulated sample |

Manufacturer sources: [BNTECHGO 18 enamel](https://bntechgo.com/bntechgo-18-awg-magnet-wire-enameled-copper-wire-enameled-magnet-winding-wire-4-oz-0-0393-diameter-1-spool-coil-natural-temperature-rating-155-widely-used-for-transformers-inductors/),
[BNTECHGO FEP](https://bntechgo.com/bntechgo-22awg-fep-teflon-coated-tin-plated-copper-wire-in-orange-100-ft-has-a-temperature-rating-of-65-to-200-c-fep-teflon-wire-is-suitable-for-applications-requiring-high-temperature-resistance/),
[Remington](https://www.remingtonindustries.com/magnet-wire/magnet-wire-22-awg-heavy-build-enameled-copper-8-spool-sizes/),
[TE Spec 55](https://www.te.com/en/product-216001-005.html),
[Alpha 5855](https://www.alphawire.com/products/wire/hook-up-wire/premium/5855),
[Alpha 2622](https://www.alphawire.com/products/wire/hook-up-wire/thermothin/2622).
The remaining owned-wire specifications are owner/inventory supplied, not
newly measured or all independently reverified. The Remington diameter is
a useful nominal selection, not a promise about every spool's enamel.

For small-lot Spec 55 sourcing, the checked
[DigiKey 55A0111-22-6 listing](https://www.digikey.com/en/products/detail/te-connectivity-raychem-cable-protection/55A0111-22-6/2399792)
offers feet, with displayed direct pricing $1.38/ft or $6.17 for 5 ft, but
zero direct stock. It reports Powell marketplace stock separately; verify
that seller's minimum quantity, price and delivery. Do not mistake the
displayed direct price for a marketplace quote. Budget roughly $10–25 plus
shipping for a small wire comparison as an allowance, not a verified order
total. Owned wire has zero new spool cost, but spacing/splicing labor counts.

The screening equations for a straight pair are
`Z0 ≈ 120 acosh(s/d)/sqrt(epsilon_eff)` and `VF ≈ 1/sqrt(epsilon_eff)`.
Here `s` is copper center spacing and `d` is cylinder diameter. This is a
homogeneous TEM approximation, not a field solution for enamel/air/ferrite.
For FEP, 19×0.15 mm gives 0.336 mm² copper area and a 0.654 mm equivalent
solid diameter, but a roughly 0.75 mm *bundle envelope* in ideal packing.
Using the equivalent diameter as the bundle's physical outside diameter
overstates spacing relative to copper. Neither represents the exact strand
surface; the new screen uses a stated 0.75 mm cylinder scenario.

With s=1.42 and d=0.75 mm, the air-to-homogeneous-FEP ε=2.1 reference cases
give approximately **150 to 104 Ω**. Those are free-pair reference values,
not bounds on the finished toroid. With d=1.024 and an *assumed* 1.06 mm
finished enamel diameter, touching 18 AWG gives 32 Ω in air and 16 Ω at
ε=4. A touching Remington 22 AWG pair is about 50 Ω in air, and lower when
dielectric loading is included. This is why neither FEP nor enamel decides
the match by itself. Twisting cannot remove jacket thickness.

Illustrative 0.60 m line results below include straight-cylinder skin and
pair proximity losses, a 50 Ω load and no dielectric/core/joint losses.
Enamel uses assumed εeff=2; FEP uses 1.5; Spec 55 uses 1.8. **Do not use
these values as product performance specifications.** RL is positive return
loss; IL includes reflection, while heat excludes reflected power.

| Scenario | Calculated Z0 | 40 m SWR / RL / IL | 20 m SWR / RL / IL | 15 m SWR / RL / IL | Heat at 100 W incident, 20 m |
| --- | ---: | --- | --- | --- | ---: |
| 18 enamel, touching at 1.06 mm | 22 Ω | 1.26 / 18.9 dB / 0.146 dB | 1.55 / 13.3 / 0.341 | 1.90 / 10.2 / 0.613 | 2.87 W |
| 18 enamel, s=1.25 mm | 55 Ω | 1.03 / 37.1 / 0.040 | 1.05 / 31.5 / 0.058 | 1.08 / 28.3 / 0.074 | 1.26 W |
| 22 heavy enamel, touching | 35 Ω | 1.10 / 26.7 / 0.101 | 1.19 / 21.1 / 0.164 | 1.29 / 17.8 / 0.234 | 2.92 W |
| 22 heavy enamel, s=0.82 mm | 61 Ω | 1.06 / 31.2 / 0.061 | 1.11 / 25.6 / 0.093 | 1.17 / 22.3 / 0.123 | 1.84 W |
| Owned FEP, touching | 123 Ω | 1.26 / 18.9 / 0.093 | 1.56 / 13.2 / 0.262 | 1.91 / 10.1 / 0.509 | 1.10 W |
| Spec 55, touching | 76 Ω | 1.11 / 25.6 / 0.055 | 1.23 / 19.9 / 0.104 | 1.35 / 16.6 / 0.168 | 1.34 W |

All five bands and 0.50/0.60/0.70 m lengths are in
[pair-scenarios.csv](../../results/balun-decision-v1/pair-scenarios.csv).
The thick FEP's relatively low calculated dissipation illustrates why bad
SWR and heating must be measured separately. An external choke cannot fix
that mismatch. The Spec 55 case is close enough to merit a sample, not an
automatic purchase recommendation. A moderate departure from 50 Ω can be
perfectly usable in a short line; hitting exactly 50 Ω is not the objective.

## Package, length and crossover

For flat, side-by-side pairs around the selected core, a simple nominal
envelope is ODcore+2D by hcore+2D. One pair crossing over another on one face
can add another D in height. These are geometry calculations, **not actual
package measurements**, and exclude tape, bend relief and tolerances.

| 12-turn pair | Nominal OD × height | Height with one extra face layer | Inner-rim occupancy | Approximate wire around core, each |
| --- | ---: | ---: | ---: | ---: |
| 18 enamel, D assumed 1.06, s=1.25 mm | 31.12 × 15.97 mm | 17.03 mm | 49% | 0.492 m |
| 22 heavy enamel, D=0.701, s=0.82 mm | 30.40 × 15.25 | 15.95 | 32% | 0.479 m |
| Owned 22 FEP, D=1.42 mm | 31.84 × 16.69 | 18.11 | 62% | 0.506 m |
| Spec 55, D=1.09 mm | 31.18 × 16.03 | 17.12 | 46% | 0.493 m |

Inner-rim occupancy uses `N(s+D)/[π(ID−D)]`; the FEP's aperture *area* fill
is only about 13%. Area fill alone therefore misses crowding along the rim.
These occupancies exclude end gaps, tape and the crossover's blocked area.
Thirteen FEP turns raise rim occupancy to 67%; 18 AWG to 53%. On two stacked
22.1 mm cores, the spaced 18 AWG pair uses about 70% of the smaller rim,
before those allowances; 22 AWG is easier there.

The length estimate is `N[2h+(OD−ID)+πD]`, a tight rectangular path. Add
roughly 80–120 mm per conductor for both lead ends and an initial 10–30 mm
crossover-detour allowance. **Cut 0.75 m of each conductor**, wind/dry-fit,
then measure the final path, expected roughly 0.58–0.66 m at 12 turns.
Measure rather than force that range. Bends, twist and protection can make
it longer. Pigtails count in the electrical length, not as free zero-length
connections.

The CAD's **34 × 18 mm** is plausible for enamel but is not a guaranteed FEP
envelope. At maximum specified core height and FEP diameter, one extra face
layer already reaches `14.25+3×1.52=18.81 mm`, before tape. For FEP, allow
**34 × 20 mm provisionally**, or route the crossover through unused aperture
space without laying it atop turns. Measure maximum OD/height, including
local bulges and wraps. A second layer at the outside rim can also exceed
34 mm. Avoid squeezing the winding with ties to make it fit.

Two core-protection layers on a corner and any spacer wraps can add more
than the simple D model. The flat pair must stay flat; rolling it on edge
increases thickness. Keep a visible separation between high- and low-end
turns, and avoid long parallel runs of input beside output. Keep each A/B
pair close together until its necessary fanout. Increasing separation
between adjacent *turns* can reduce coupling between distant winding
potentials; increasing separation *within the pair* changes differential
impedance. Those are different adjustments.

The crossover is required for routing, not advertised as a reduction in
capacitance. It can add local capacitance and disturb the pair. Keep its
geometry unchanged between 12/13-turn trials and photograph both faces.
An end-to-end lumped Cp sweep cannot resolve these effects, distributed
resonances, core-surface capacitance, mounting metal, pads, ties or rain.

Small coax does give a specified differential impedance. For example,
[Pasternack RG178B/U-BULK](https://www.pasternack.com/images/ProductPDF/RG178B-U-BULK.pdf)
is 50 Ω, 1.83 mm OD, VF 0.70, with a ~0.30 mm stranded plated steel/copper
center conductor. Its specified 100 MHz loss is 0.453 dB/m; a square-root
frequency extrapolation to HF gives about 0.10 dB for 0.60 m at 14 MHz,
but that is an unvalidated extrapolation, not a manufacturer HF or power
rating. The small center, shield fanout and termination work matter.

[HUBER+SUHNER RG_316_/U](https://www.hubersuhner.com/Asset/eyJpZGVudGlmaWVyIjoxMTY0NjMsInR5cGUiOiJhc3NldCJ9/KZOV2UhPqfMt4ZH8/H%2BS_RG_316_U_EN.PDF)
is 2.5 ±0.1 mm OD, about 16 g/m and specifies a **15 mm static bend radius**.
Do not confuse bend radius with the toroid's outside radius: the cable
bends around the core's small cross-section corners. Pasternack specifies
10.16 mm for *repeated* RG178 bends, without establishing a smaller safe
one-time winding bend in that sheet. The tight 34 × 18 mm geometry does not
establish compliance for either cable. Larger rounded loops/formers increase
length and package size. Obtain a cable-specific static-bend specification
before promoting coax; bulk-cable plus shipping and shield breakout work
are not justified merely to avoid a short pair test. A 50 Ω coax's internal
~97 pF/m capacitance is differential capacitance, not the choke's lumped
common-mode bypass Cp.

## Exact first-build routing and terminations

1. Use **one 2631801202**, inspect for cracks, and apply the thinnest smooth
   insulating abrasion protection available. No metal band around the core.
   The nylon ties hold it gently against the separate compliant pads; the
   core and winding carry no antenna tension. Use outdoor/UV-suitable ties
   if the assembly will remain exposed.
2. Cut two **750 mm BNTECHGO 18 AWG enamel** conductors. Label A and B at
   both ends. Measure finished diameter at several locations without
   crushing enamel, and a stripped coupon for copper diameter. Do not use
   the seller's 1.00 mm figure to infer enamel thickness.
3. Start the coupon with **1.20–1.30 mm center spacing**, aiming near 1.25 mm.
   This is a proposed starting setting, not a validated winding prescription.
   Use a thin continuous PTFE strip between wires or controlled tape build
   on one wire, retained by sparse narrow wraps. Determine the spacing from
   measured diameters and the assembled pair; a fixed number of stretched
   plumbing-tape wraps is not a thickness specification. Select the setting
   that passes the coupon test, then preserve it on the core. If it cannot
   survive gentle flexing, change construction/wire rather than trusting an
   unsupported air gap.
4. Wind the flat pair with **5 ordinary aperture passages, 1 crossover
   passage, then 6 ordinary passages: total 12 for each conductor**.
   Put the banks on opposite halves with input tails below and output tails
   above. Mark a front face and make every counted passage through the hole
   in the same front-to-back direction, routing the returns outside the core.
   The progression around the second bank may look reversed; magnetic
   linkage must remain aiding. Carry A/B together across the aperture, with
   no conductor swap or electrical join. For 13 use 6+1+6. Number the passages
   in photos; do not count 12 ordinary turns plus an extra crossover.
5. Connect **BNC center → A → one antenna post; BNC shell → B → the other
   post**. Neither wire joins the other. There is no center tap or separate
   direct shell-to-post bypass. Each winding wire remains continuous through
   the core; end pigtail joints are outside the winding. Keep the output pair
   together until the short split to the posts and the input pair together
   up to the BNC contact/tag.
6. Prefer **20–30 mm finished 22 AWG FEP pigtails at the two output ends**.
   Completely remove enamel over the splice, inspect clean copper, solder
   a mechanically stable overlap, and insulate each splice separately with
   appropriately sized owned heat shrink. Keep solder/heat shrink outside
   the aperture. Do not let shrink recovery move the pair spacing. Strip
   no more enamel than needed and cover any exposed copper.
7. At the BNC, solder clean stripped 18 AWG directly if the actual cup/tag
   accepts it without force. Otherwise use two similarly short FEP pigtails
   there too. A short 22 AWG section contributes little additional loss;
   the extra joints and flex transitions are the larger practical penalty.
   Give the rigid wire relaxed bends and restrain the insulated section so
   neither solder joint is a hinge or tension point.
8. Crimp the output FEP in **Panduit P22-6R-M** rings, using the specified
   tool/die or a verified equivalent. No pre-tinning the crimp barrel area,
   no doubling oversized wire, no solder as a repair for a bad crimp. Test
   spare samples for pullout and flex reliability. Assemble antenna-side
   strain relief through the printed wire holes before tightening the rings.

The CAD was read directly in
`../scad-lab/models/ham_radio/balun_dipole_center/balun_dipole_center.scad`.
It sets `terminal_hole_d=3.4` and asserts that this layout is for **M3**.
The README specifies two **M3 × 16 mm** screws, four nuts, eight ~7 mm OD
washers, and terminal centers X±10/Y70 mm. There is no M2 version in these
files. This verifies the design/BOM, not the diameter of screws in a drawer.
Dry-fit actual screws; retain M3 unless deliberately changing the mount.

[Panduit drawing N41227BB](https://www.panduit.com/content/dam/panduit/en/products/media/2/32/832/4832/98604832.pdf)
explicitly recommends **26–22 AWG solid or stranded copper**. P22-6R's
nominal #6 hole is **3.86 mm** (±0.254 mm), appropriate clearance for M3;
the drawing specifies 4.8 +0.8/−0 mm strip length and CT-100A pocket B or
CT-200 tooling. The family catalog excludes this small gauge range from
its general UL/CSA listing claims; do not invent a certified crimp rating.

Thus the **purchased 22 AWG enamel can crimp directly** after complete enamel
removal; FEP pigtails are optional for flex isolation, not required because
it is solid. For 18 AWG, P22 is the wrong conductor size. The inventoried
TE 31428 has a stated 3.02 mm hole, not assured M3 clearance. The Molex
0190700007 accepts larger wire but is for #3–#4/M2.6 hardware; verify its
actual hole and bulk before substitution. The 26 AWG ferrules are not a
22 AWG termination solution. Do not file rings or switch to M2 just to avoid
two short pigtails.

For the **Remington alternative**, use the same instructions with 750 mm
22HNSP.125 conductors, begin the coupon near **0.78–0.84 mm center spacing**,
then choose spacing by test. Crimp the stripped output ends directly to P22
with flex relief, or retain short FEP pigtails where handling warrants them.
For the **FEP alternative**, use the orange/yellow wires touching, laid flat
with sparse retention; don't shave insulation or crush it to change spacing.
Strip and solder/crimp directly. Keep turn count/routing/lead lengths matched
to the enamel comparison and reserve the extra measured package thickness.

## Loss and thermal uncertainty

The original isolated-wire skin estimate at 100 W/50 Ω, 0.60 m each, gives
about 0.53/0.74 W for 18 AWG and 0.84/1.17 W for 22 AWG on 40/20 m.
Those values omit proximity. For two straight cylinders carrying opposite
currents in the high-frequency limit, surface-current crowding gives the
factor `s/sqrt(s²−d²) = coth(acosh(s/d))` relative to isolated round-wire
skin resistance. This follows by integrating squared surface current in
bipolar coordinates; the factor tends to one at large separation and grows
as copper surfaces approach. It is not a calibrated factor for bent,
stranded wire on lossy ferrite.

In the illustrative geometry, touching 18 AWG has a factor about 3.9,
whereas the 1.25 mm-spaced pair is about 1.74. Gauge-only loss comparisons
can therefore give the wrong ranking. The RLGC calculation integrates line
current/mismatch and reports `1−|S11|²−|S21|²` as dissipation for a matched
receiving port. It does not count reflected power as heat. At fixed geometry
and impedance its heat scales by 0.50 or 0.12 for 50 or 12 W incident.
Temperature changes, proximity to other turns, tin/nickel plating, strand
contacts, imperfect balance, dielectric loss and joints add uncertainty.
Tinned strands are not Litz wire. No useful tight numerical upper bound on
real assembly loss has been established.

At 100 W into 50 Ω, differential current is 1.414 A RMS and differential
voltage is 70.7 V RMS / 100 V peak. These are reference operating values,
not the common-mode core excitation or a worst-case mismatch voltage.
Wire temperature class and a 300/600 V jacket label do not establish RF
power handling, abrasion tolerance or common-mode insulation stress.

Ferrite heating is set by common-mode excitation. With **net** RMS terminal
current `Icm=IA+IB` (both currents referenced in the same physical direction),
real terminal power is `|Icm|² Re(Zcm)`. In the ideal shunted model it equals
the magnetic branch dissipation; the individual branch current can differ
from terminal current. Do not substitute the 1.414 A differential current.
For a 5 kΩ resistive choke, 10/20/50 mA yields **0.5/2/12.5 W**. The antenna,
coax route, station grounding and environment determine the excitation.
A smaller core may be satisfactory; a larger one may still overheat.
The exposed arrangement aids convection but no thermal resistance or
temperature-dependent ferrite model has been measured here.

## Smallest useful comparison and acceptance gates

**First, two samples without ferrite.** Prepare a 0.60 m owned FEP pair and
a 0.60 m owned 18 AWG pair. Keep them well away from metal, with the same
short terminal fixture. On the magnet sample try contact, then the controlled
spacing proposed above. A calibrated one-port VNA with a short-leaded
49.9 Ω output load shows whether either construction is already unsuitable.
That resistor is analyzer-only, **0.25 W**, never a transmitter load.

For more information from the same sample, measure complex input impedance
with its far end open and shorted. For a uniform line,
`Z0 = sqrt(Zopen·Zshort)` (choose the passive, continuous branch). Infer
electrical length from `Zshort/Z0 = tanh(γl)` if useful. This requires
de-embedding end inductance/capacitance and a meaningful phase measurement;
don't overinterpret a low-frequency short dominated by fixture inductance.
The 50 Ω loaded sweep is the simpler go/no-go test. Repeat after gently
flexing/repositioning the sample to expose unstable spacing.

**Then one winding.** Wind the best sample construction on the 29 mm core,
12 counted passages. Check DC continuity and isolation before and after
mounting. Measure all five full bands, not just CW spot frequencies.
Suggested engineering acceptance targets, not universal standards:

| Quantity | Working target | What changes the recommendation |
| --- | --- | --- |
| Differential match into known 50 Ω | SWR ≤1.3, equivalently RL ≥17.7 dB, on all five bands | If FEP meets it and loss/thermal checks match enamel, promote FEP for easier assembly. If enamel misses, adjust spacing before changing core/turns |
| Differential dissipation | Prefer ≤0.10 dB of **accepted** power on 40/20 m (~2.3%); ≤0.15 dB (~3.4%) elsewhere | A candidate exceeding these merits rework; a reproducible ≥0.05 dB difference is meaningful only if larger than fixture uncertainty |
| Total differential insertion loss | Aim ≤0.15 dB on 40/20 m; ≤0.20 dB elsewhere, with S11 reported | Low IL alone doesn't establish balance; good S11 alone doesn't establish low loss |
| Standalone CM impedance | Magnitude ≥2 kΩ and R ≥1 kΩ on every band claimed; prefer R ≥2 kΩ on 40/20 m | If 40 m misses, try 13 and recheck. If 20 m fails while 40 m is strong, compare 10/11 turns or less end coupling before adding turns |
| Mechanical stability | Repeatable RF after mounting, flexing and remounting; no damaged insulation or loose crimps | If controlled 18 AWG spacing/splices are troublesome, buy the 22 AWG comparison |

For two-port differential loss, **do not connect both ends of the B winding
to ordinary VNA port shields and assume it is valid**: their common ground
can bypass that winding. Use a characterized isolated balanced receive
fixture, or a proper four-port mixed-mode setup with the differential
reference normalized to 50 Ω. De-embed fixture loss and report both S11 and
S21; repeat with reversed DUT orientation and changed cable placement.
Report noise/repeatability before claiming hundredths of a dB.

A practical screening fallback is two identical baluns connected output to
output with their joined antenna terminals floating, BNCs at the VNA. Compare
against a through fixture. This avoids directly grounding the intermediate
balanced junction, but **do not simply halve total dB loss or accept its
SWR as the single-DUT answer**: mismatch can cancel and the pair's modes
interact. Use it to flag excess loss, retaining the single-DUT loaded test
and thermal measurements. A trustworthy single-assembly insertion loss
requires the isolated/mixed-mode fixture or adequate de-embedding.

For common mode, disconnect normal feed connections and temporarily join
A+B at each end. Float both junctions (including any attached BNC shell)
from fixture ground. Insert them between the two center pins of a short,
calibrated 50 Ω series fixture; join the two fixture shields directly.
With complex linear S21, `Zcm=100(1/S21−1) Ω`. Validate with known resistors
around 1–5 kΩ and record fixture open/through response; lead capacitance and
the open fixture's bypass can dominate the highest impedances. The owned
2.49 kΩ resistor is useful as a check, including its own lead parasitics.
Export Touchstone, inspect R, X and |Z|, and repeat with modest cable
repositioning. Negative measured R or wild fixture dependence invalidates
the extraction. Remove all temporary joins before powering normally.

Do not wind a matrix of every wire/core combination. If both initial samples
pass, build 18 AWG first, then FEP only if needed to resolve an actual
assembly tradeoff. If both fail, test Remington 22 AWG spacing next; Spec 55
is the alternative when flexible jacketed wire is preferred. Try a second
core size only after a clear magnetic/thermal/weight limitation is observed.

External choking is acceptable on 17/15 m (and 30 m if required), after this
balun passes **differential** match/loss on those bands. Test the combined
installed system: impedances of separated chokes and intervening coax do
not generally just add. A build failing the core 40/20 m targets should be
improved at the center rather than using external choking to obscure the
first design's weakness.

## Staged CW thermal qualification

1. Attach a transmitter-rated 50 Ω load across the antenna posts, with the
   same mount, pads, ties, BNC and lead dress intended in service. Track
   ambient, core surface, wire/splices and printed support temperatures.
   Use a sensor method that does not introduce a conductive RF path; IR
   measurements need attention to enamel/metal emissivity and viewing area.
2. Start at **12 W, then 50 W, then 100 W**, testing 40 and 20 m first and
   then 30/17/15 m. At each level use a logged **50% RF duty cycle**, e.g.
   1 s on/1 s off, for at least 10 minutes and until the hottest reading
   changes by less than 1°C over five minutes. Continue up to 30 minutes if
   needed; no plateau means no pass. This is a proposed demanding CW cycle,
   not an assertion that all CW has 50% duty. Qualify a higher intended duty
   separately. Cool between band/power comparisons.
3. Add the longest intended tune/key-down interval; use **30 seconds** as
   an initial declared qualification limit, and test longer if actually
   required. Passing intermittent CW does not authorize unlimited key-down.
4. Pending actual print/pad material data, use conservative prototype stops:
   **50°C absolute or 20°C rise above ambient**, whichever comes first, or
   any lower component-specific limit with margin. These are chosen bench
   limits, not PETG or ferrite ratings. Stop immediately for accelerating
   rise, odor, softened mounting, intermittent contact or changing SWR.
   Record forward/reflected power and RF duty; don't label transmitter dial
   settings as delivered load power.
5. Repeat with the intended linked/resonant dipole and coax routing, including
   the plausible less-symmetric field deployment, starting again at 12 W.
   Keep the antenna reasonably matched, log its feedpoint behavior, and
   compare with/without any planned external choke. A clamp around the
   entire coax, if calibrated, measures net common-mode current and helps
   explain ferrite heating. A balanced dummy load alone does not apply the
   real deployment's common-mode stress.
6. After cooling, repeat VNA sweeps, continuity/isolation and a gentle flex
   inspection. Record the maximum temperature, ambient, duty, tune duration,
   band, antenna/coax geometry and final dimensions. Exposed-wire weather
   and UV life remain separate uncertainties; repeat low-power RF checks
   after realistic damp exposure and drying before extending outdoor claims.

Only claim **100 W CW for the tested duty, key-down duration, ambient range
and deployment envelope** after those tests pass. If 100 W fails but 50 W
passes, retain a documented 50 W operating limit and identify whether the
wire/joints or common-mode ferrite heating caused the failure. Do not infer
that one more turn, thicker wire or a higher-temperature jacket fixes it.

## Reproduction and repository changes

Run `mise run balun-decision`. The new module extends the original magnetic
screen with complex band extrema for all inventoried ferrites, uniform RLGC
line S parameters, geometry/length sensitivities and straight-pair proximity.
It retains independent material and exact-part models, and does not infer
physical capacitance from either. Geometry and dielectric scenarios are
explicit in the CSVs. The original study outputs remain unchanged.

- [Calculated results](../../results/balun-decision-v1/README.md)
- [Implementation](../../src/antenna_lab/balun_decision.py)
- [Model tests](../../tests/test_balun_decision.py)

Tests verify lossless power conservation/agreement with the original line
screen, an analytically known lossy transmission line, and dielectric/
proximity limiting behavior. They validate equations and implementation,
not ferrite/winding predictions. Source hashes accompany the generated data.
No CAD geometry or parts inventory was changed by this reassessment.

At the time of the study, all **277 tests** passed with `mise run test`.
The new Python files pass Ruff formatting and lint checks. The repository-wide
`mise run check` stops at pre-existing formatting differences in nine files.
