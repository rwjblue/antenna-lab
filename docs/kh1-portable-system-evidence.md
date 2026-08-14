# KH1 portable-system evidence basis

This file separates facts and observations from the assumptions used by the
complete-system screen. The computed rankings are derived outputs, not measured
radiation efficiency.

## Published manufacturer facts

- The [Elecraft KH1 Owner's Manual, rev. B7](https://ftp.elecraft.com/KH1/Manuals%20Downloads/KH1%20Owner%27s%20Manual%2C%20rev%20B7.pdf)
  calls the tuner an L-network, exposes separate L/C/Z diagnostics, documents
  eight latching relays, says firmware tests all network combinations and
  chooses lowest SWR, and describes protection-related power fallback. It does
  not publish relay-to-component assignments, bank values, Q, loss, or a single
  SWR rollback threshold.
- The [KH1 product page](https://elecraft.com/products/kh1-transceiver) says the
  tuner matches most antennas below 2.5:1. This is a product claim, not a
  guaranteed impedance polygon or rollback boundary.
- The [KH1 design presentation](https://ftp.elecraft.com/KH1/Manuals%20Downloads/KH1%20Design%20Presentation.pdf)
  classifies it as a medium-range ATU, rather than the KX2's wide-range tuner.
- [Belden 8216](https://catalog.belden.com/techdata/EN/8216_techdata.pdf) provides
  the RG-174 50 ohm, 66% velocity-factor, and matched-attenuation data used as a
  coax scale. Matched loss is not substituted for mismatched-line loss.
- [Fair-Rite mix 61](https://fair-rite.com/61-material-data-sheet/) and
  [mix 52](https://fair-rite.com/52-material-data-sheet/) data establish
  material-dependent permeability/loss behavior; they do not specify a complete
  transformer's insertion loss.
- [Coilcraft 1812LS](https://www.coilcraft.com/getmedia/1df56443-b7c7-4f17-abaf-470b9bb5eee8/1812ls.pdf)
  and [KEMET CBR RF capacitor](https://content.kemet.com/datasheets/KEM_C1082_CBR0505_SMD.pdf)
  data bound miniature inductor/capacitor Q scales. They are not claimed as KH1
  parts.

## Measured inputs

- `data/measured/58ft_doublet_2026-08-08.csv` is the only canonical measured
  antenna impedance dataset. It is a RigExpert observation at the documented
  station-end reference plane for one 58 ft radiator / 28 ft balanced-line
  deployment.
- KXAT2 tuning behavior in the historical case study is an observation, not a
  KH1 measurement and not an impedance-range specification.
- The NEC and legacy ATU source artifacts are computational outputs, not
  measurements. Their Actions manifests and recorded source hashes were checked
  before reuse: NEC [run 31750551947](https://github.com/rwjblue/antenna-lab/actions/runs/31750551947)
  and ATU [run 31750551951](https://github.com/rwjblue/antenna-lab/actions/runs/31750551951).

## Inferred model values

- Eight relays plus L/C/Z diagnostics strongly imply four binary inductors,
  three binary capacitors, and a topology-reversal relay: 256 states.
- A [secondary KH1 hardware profile](https://forum.qrz.ru/2146374-post24.html)
  reports 0.35-5.25 uH and 60-420 pF. The exact endpoints correspond to four-bit
  0.35 uH and three-bit 60 pF binary banks. The `khatu1` profile uses those
  increments; `khatu1_wide_sensitivity` retains the older wider range.
- Candidate impedances, currents, NEC radiation efficiencies, tuner states,
  final efficiencies, rankings, and Pareto membership are model-derived.

## Sensitivity assumptions

- KH1 component Q, capacitor ESR/Q, and relay/contact resistance use
  optimistic/nominal/conservative envelopes because in-circuit data are absent.
- Compact 4:1 transformer loss is 0.20/0.35/1.00 dB; 9:1 is
  0.25/0.60/1.20 dB; 49:1 is 0.30/0.50/2.00 dB. Choke loss is
  0.10/0.20/0.50 dB. These ranges are engineering envelopes, not proposed-part
  measurements.
- Portable 4:1 and choke nominal scales are informed by an original builder's
  [compact QRP measurements](https://hamradiooutsidethebox.ca/2025/12/05/what-really-determines-the-efficiency-of-an-antenna/).
  Measurement/de-embedding detail is limited, so the values are not hard bounds.
- The EFHW scale is informed by a thermally measured
  [49:1 design](https://squashpractice.com/2021/07/20/engineering-the-efhw-491-transformer-and-antenna/)
  and its [measurement discussion](https://squashpractice.com/2021/06/23/performance-of-491-ferrite-core-transformers/).
  The modeled compact implementation uses a wider conservative bound.
- Trap models use finite component Q and current-dependent dissipation. The
  sentinel is informed by [Cebik's measured-commercial-trap analysis](https://antenna2.github.io/cebik/content/model/trap.html)
  and checked against [W8JI trap measurements](https://new.w8ji.com/trap-antennas-coaxial-trap-coax-dipole-antenna-loss-resistance/).
- Ground, conductor, deployment, component, and tuner cases are equal-weight
  sensitivities. Their p10/p50/p90 values are not occurrence probabilities.
- SWR above 2.5 is flagged as likely rollback risk for comparative screening.
  Elecraft does not publish that threshold; bench validation must replace it.

## Measurement cautions

[AI6XG's transformer-efficiency study](https://www.ai6xg.com/post/evaluating-efficiency-transformer-and-mismatch-losses-in-toroid-transformers-some-observations)
is a useful reminder that raw S21 combines dissipation, mismatch, fixture, and
load effects. Back-to-back fixtures still require mismatch correction and loss
allocation. The proposed physical validation therefore preserves reference
planes and reports residual mismatch separately from component heating/loss.

## Reproducible result

The machine-readable config is `configs/kh1-portable-final-v1.json`. The durable
result is `results/kh1-portable-final-v1/`, including input hashes,
`SHA256SUMS`, seven rankings, family winners, Pareto candidates, representative
per-band power budgets, sensitivity tables, and the physical validation plan.
