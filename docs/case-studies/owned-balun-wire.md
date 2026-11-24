# Owned wire for the open 1:1 balun

**Later reassessment, same date:** use the [pragmatic build decision](balun-decision.md)
for the current ranking and instructions. The 22 AWG purchase below is no
longer treated as settled. Controlled spacing matters for both magnet-wire
gauges, and the FEP comparison remains a real candidate. The new report also
confirms that P22 terminals support both solid and stranded copper in range.

Inventory checked 17 September 2026. Seven variants and purchase quantities
were matched to Amazon order confirmations; the eighth, 28 AWG silicone,
was identified by the owner. All eight are reported on hand. Original pack
sizes below are not remaining-stock measurements. No private order records
are copied into this repository.

| Wire | Exact Amazon ASIN | Original package | Balun assessment |
| --- | --- | --- | --- |
| 18 AWG magnet, natural | [B07H7DP7RN](https://www.amazon.com/dp/B07H7DP7RN) | 4 oz, about 51 ft | Alternative owned-wire trial; lower copper loss, thicker/stiffer wire, needs suitable terminations |
| 28 AWG magnet, natural | [B07HRKT1WQ](https://www.amazon.com/dp/B07HRKT1WQ) | 4 oz | Small coils / low power; not first choice for 100 W |
| 22 AWG FEP, orange | [B0D21RSJHX](https://www.amazon.com/dp/B0D21RSJHX) | 100 ft | Viable winding trial or short leads; verify completed RF performance |
| 22 AWG FEP, yellow | [B0D21LHTVL](https://www.amazon.com/dp/B0D21LHTVL) | 100 ft | Same construction; identifiable second conductor |
| 20 AWG parallel silicone, red/black | [B077X9MVWG](https://www.amazon.com/dp/B077X9MVWG) | 25 ft cable | Bonded two-conductor cable, convenient but bulky; not specified as 50 ohms |
| 22 AWG silicone, orange | [B071L3DBG1](https://www.amazon.com/dp/B071L3DBG1) | 250 ft | Flexible jumpers; 1.7 +/-0.1 mm insulated OD |
| 18 AWG silicone, yellow | [B071HH246Z](https://www.amazon.com/dp/B071HH246Z) | 250 ft | Heavier leads; 2.3 +/-0.1 mm insulated OD |
| 28 AWG silicone, red and black | [B07HGT77R5](https://www.amazon.com/dp/B07HGT77R5) | 50 ft each, 100 ft total | Separate wires, 1.2 +/-0.1 mm insulated OD; signal wiring |

## Recommendation

Plan **12 bifilar turns of 22 AWG enamelled copper on one 2631801202**,
following the owner's choice to acquire that gauge. It is not yet confirmed
stock. Record the selected enamel build and finished diameter. Use a
crossover to route input below and output above the core; count the
crossover passage in the 12 total turns. The numerical screen does not
resolve crossover geometry, so the completed winding must be measured.

The owned 22 AWG FEP is a reasonable comparison winding, not restricted to
pigtails. The owned 18 AWG magnet wire remains another alternative.

The owned 18 AWG listing specifies polyurethane enamel and 155 C, but does
not reliably establish enamel build or finished OD. Its advertised 1.00 mm
diameter is close to nominal bare 18 AWG (1.024 mm), so do not use it as a
guaranteed insulated envelope. Measure the wound core against the 34 x 18 mm
allowance. Do not assume the temperature class supplies an RF voltage rating.

The P22-6R-M terminal accepts 26–22 AWG, so **do not force 18 AWG into it**.
Use short 22 AWG FEP pigtails with soldered, individually insulated splices,
or an eyelet explicitly compatible with both 18 AWG and the M3 stud. Support
the winding mechanically so the pigtails and solder joints see no tension.

Thin enamel on larger copper can make a touching pair's impedance too low,
just as thick hookup insulation can make it too high. Check a short sample
of the pair and the completed winding with a 50 ohm termination before
adopting the spacing. Controlled spacing changes require a new RF sweep.
Neither 18 AWG nor 22 AWG alone establishes the pair's characteristic impedance.

## Why the 22 AWG FEP is not an automatic substitute

[BNTECHGO's specification](https://bntechgo.com/bntechgo-22awg-fep-teflon-coated-tin-plated-copper-wire-in-orange-100-ft-has-a-temperature-rating-of-65-to-200-c-fep-teflon-wire-is-suitable-for-applications-requiring-high-temperature-resistance/)
gives 19 x 0.15 mm tinned-copper strands, 1.42 +/-0.1 mm insulated OD,
300 V and -65 to 200 C. FEP is the listed insulation, rather than PTFE;
the product is marketed using “Teflon.”

At jacket contact, conductor centers are about 1.42 mm apart, compared with
roughly 0.65 mm copper-equivalent diameter (the actual strand bundle is wider).
That much spacing suggests a higher-impedance line than the desired 50 ohms.
This is an engineering inference from geometry, not a measured Z0 or a
calibrated dielectric/field model. Tighter twisting does not remove the
insulation spacing. It also changes line length and coupling. FEP remains
a reasonable experiment if its finished differential match passes, and an
excellent practical candidate for short identifiable pigtails.

Silicone insulation is thicker for the available 18/22 AWG products. The
already-bonded 20 AWG pair is also not a rated RF transmission line. These
are useful stock without being the preferred compact 1:1 winding.

## Extended numerical comparison

`mise run bifilar-choke` now includes 18/20/22/28 AWG in the copper screen
and Z0=25/30/40/50/60/70/100/120/150 ohm line scenarios. Those Z0 values are
**not assigned to specific products**. They expose both low- and high-Z0
mismatch risks while actual insulation dimensions and effective permittivity
remain unknown. Refer to the study's [method](bifilar-choke.md).

For 0.60 m per conductor at matched 100 W, the nominal solid-round copper
skin model estimates total pair loss as follows:

| Nominal copper gauge | 40 m, upper edge | 20 m, upper edge |
| --- | ---: | ---: |
| 18 AWG | 0.53 W | 0.74 W |
| 22 AWG baseline | 0.84 W | 1.17 W |
| 28 AWG | 1.68 W | 2.35 W |

These estimates exclude pigtails, joints, proximity, tin plating, strand
contact effects, mismatch and ferrite loss. They are not measured insertion
loss or a power qualification. Uninsulated tinned strands are not Litz wire.
The [original RF and staged thermal checks](bifilar-choke.md#bench-acceptance-and-the-100-w-goal)
still apply to the owned-wire prototype.
