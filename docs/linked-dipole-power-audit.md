# NEC power and efficiency audit for the linked dipole

**Use integrated absolute power gain to report accepted-power-to-upper-hemisphere
space-wave efficiency. NEC's printed efficiency is a different quantity.**
This resolves the bookkeeping limitation identified in
[model limitations](../MODEL_LIMITATIONS.md) while preserving the reference-plane
distinctions in [efficiency and SWR](efficiency-and-swr.md). It does not calibrate
the physical wire, soil, feedline, or deployment.

## What the solver reports

The local NEC2C source is
[`KJ7LNW/nec2c`, commit `55be1e0`](https://github.com/KJ7LNW/nec2c/tree/55be1e0e3fe5ee9dad4ce6050711450d19c562fd).
The inspected `main.c` and `radiation.c` match that commit. The study records the
executable and deck hashes because an input file alone does not identify the run.

| Output | Definition and interpretation |
| --- | --- |
| Input power | Total real power accepted from the voltage sources; for the 1 V peak source, `Pin = 0.5 Re(1/Z)` |
| Structure loss | Ohmic power in explicit wire loads, including wire resistance and resistive contact loads |
| Network loss | Dissipation in NEC network/transmission-line ports; zero when none are present |
| Printed radiated power | `Pin − Pstructure − Pnetwork` |
| Printed efficiency | Printed radiated power divided by `Pin` |

The last two rows have no independently computed ground-loss term. A perfectly
conducting wire over lossy ground can therefore print 100% efficiency. These
definitions are explicit in the
[NEC output manual](https://www.nec2.org/part_3/output.html) and in
[`main.c`, lines 1587–1603](https://github.com/KJ7LNW/nec2c/blob/55be1e0e3fe5ee9dad4ce6050711450d19c562fd/main.c#L1587-L1603).

The study's `RP 0 … 1001 …` requests space waves with absolute power gain:
the four digits mean vertical/horizontal components, no normalized table,
power gain, and average-gain output. In particular the third digit is zero.
`RP 0` is the asymptotic space-wave calculation even when a display range of
1000 m is supplied. `RP 1` adds surface-wave fields and uses different output
coordinates; it is not used here. See the
[RP card specification](https://www.nec2.org/part_3/cards/rp.html).

The power-gain denominator is accepted input power. The alternate directive
setting divides by the printed radiated-power estimate, which still excludes
explicit ground accounting. The study does not use that alternate setting.
[`radiation.c`, lines 671–675](https://github.com/KJ7LNW/nec2c/blob/55be1e0e3fe5ee9dad4ce6050711450d19c562fd/radiation.c#L671-L675)
implements this normalization.

## Reconciled method

With elevation `e`, azimuth `φ`, and the solver's absolute total gain `G`:

```text
ηupper = (1 / 4π) ∫φ=0..2π ∫e=0..π/2 10^(GdBi(e,φ)/10) cos(e) de dφ
Pupper = Pin × ηupper
Presidual = Pin − Pupper − Pstructure − Pnetwork
```

`ηupper` is the fraction of accepted power escaping as upper-hemisphere far-field
space waves. The divisor is **4π**, although only the upper hemisphere is
integrated. Using a hemispheric mean would double the answer. This convention
also makes gain relative to an isotropic radiator explicit. The
[NEC theory manual, radiation-pattern section](https://www.nec2.org/other/nec2prt1.pdf)
defines accepted-power gain in this way.

For passive finite-conductivity homogeneous ground, `Presidual` represents power
not escaping in those space waves, after explicit wire/network dissipation.
It includes the soil/environment remainder and numerical error. It is **not an
independent volume integral of local soil heating**, and does not separate
near-field ground absorption from surface-wave energy ultimately attenuated in
the infinite ground. The report labels it a ground/numerical residual. Closing
this residual by subtraction is an accounting identity; the validation below
provides the independent numerical checks.

The implementation reuses the repository's `average_gain` solid-angle quadrature:
it mirrors the upper grid for integration and halves the result. That artificial
mirror never enters a physical pattern or a claimed below-ground radiation
result. Azimuth is periodic; 0 and 360 degrees are the same direction. The stored
grid excludes the duplicate 360-degree column, and integration closes the seam.
NEC's own printed average covers the requested sector only, so a 0–358-degree
request must not be mistaken for the complete 360-degree hemisphere.

## Validation and interpretation limits

The reusable tests cover isotropic gain (upper integral 0.5), a known
elevation-weighted pattern, rejected incomplete/duplicate grids, and unclamped
nonphysical results. Solver tests independently check:

- A lossless free-space straight dipole has average gain within 0.02 dB of unity.
- A lossless wire over perfect ground has `ηupper` within 0.003 of unity.
- Accepted source power agrees with `0.5 Re(1/Z)` to 0.02%, allowing print rounding.
- Reconstructing `G = 2πr²(|Eθ|²+|Eφ|²)/(376.73 Pin)` from printed field
  magnitudes produces `ηupper` within 0.001 of the gain integral. This tests
  normalization, not an independent field solution.
- Over real ground, integrated efficiency is below the printed efficiency.

These are checks on the accounting helper. The linked-assembly study separately
checks mesh, source-bridge dimensions, finite open gaps, and angular refinement
on its own geometry. The helper tests also run the three link states plus
20 m with B closed at a 10 mm gap: NEC's printed signed I−/I+ connection indices
must match every source, bridge, open link, and outer endpoint. They also check
lossless free-space gain with the insulation inductance retained. The existing
`free_space_lossless_deck` removes every load card and tests bare-wire geometry;
`free_space_reactive_deck` removes dissipation while retaining LD2/LD4 reactance.
Solver convergence does not validate an unmeasured material or connector model.

The source bridge has three equal horizontal segments and excites the middle
segment. Each leg begins with a segment of the same length, then segment
lengths grow by 1.4 toward the selected outer mesh spacing. This avoids an
abrupt segment-length change at the feedpoint. The fine local mesh follows the
same physical wire path and receives the same material/insulation loads as the
rest of the section. Simply subdividing the horizontal bridge without grading
the adjoining arms left an average-gain error and source-size dependence in
early diagnostics; the graded geometry is the maintained model.

The study should flag, rather than clip, efficiency outside the passive interval
or a materially negative ground residual. Small residual discrepancies at the
quadrature and print-rounding scale are not physical negative loss. Compare
2-degree and 1-degree integration, using 0.002 absolute efficiency difference as
a practical study acceptance threshold. Mesh/source gain errors should remain
within 0.1 dB, consistent with the existing numerical-validation infrastructure;
these tolerances are study quality criteria, not universal NEC accuracy claims.

## Combining insulation and wire loss

NEC2C adds overlapping loads. Its LD2 distributed series inductance contributes
imaginary impedance; LD5 contributes the finite-conductivity wire impedance.
The combination is explicit in
[`calculations.c`, lines 365–390](https://github.com/KJ7LNW/nec2c/blob/55be1e0e3fe5ee9dad4ce6050711450d19c562fd/calculations.c#L365-L390).
The additional LD2 loading does not itself dissipate power, although altered
currents change the wire loss.

A diagnostic using the **untuned initial dimensions** 16.5/6.8/9.8 ft per leg,
5 ft outer ends, 14.135 MHz, and 10 MS/m conductivity gave printed efficiencies
76.66% with the inductive sheath approximation and 76.57% without it. Removing
LD5 gave 100% printed efficiency in both cases; the loaded free-space average
gain was 1.00065. These are diagnostic inputs, not tuned results or material
measurements. The unexpectedly appreciable loss is plausible for a very thin
wire: the skin-effect estimate for the specified effective conductivity and
0.2413 mm metal radius is about 1.56 Ω/m, and the steep V lowers radiation
resistance. This calculation checks scale; the uncertain copper-clad-steel
construction still requires bounded material sensitivities.

## Mismatch is applied once

```text
Γ50 = (Z − 50) / (Z + 50)
ηmatch = 1 − |Γ50|²
mismatch loss (dB) = −10 log10(ηmatch)
realized gain (dBi) = NEC power gain (dBi) + 10 log10(ηmatch)
available-power-to-space-wave fraction = ηmatch × ηupper
```

Do not multiply NEC gain by `ηupper` again: modeled wire and ground effects are
already present in the gain. Comparing `G/ηupper` between geometries isolates
directional redistribution relative to escaped space-wave power; comparing
`ηupper` isolates the accepted-power radiation fraction. This is an algebraic
decomposition of the model. Actual coax, choke, tuner, mast, and common-mode
effects remain outside the ideal balanced feedpoint baseline.

## Reproduce the helper checks

```sh
PYTHONPATH=src uv run pytest tests/test_linked_dipole_validation.py -q
```

The live solver check uses `build/tools/nec2c` and skips if that executable is
absent. `linked_dipole_validation.py` exposes `power_budget`,
`upper_hemisphere_efficiency`, `reconciled_power_budget`, and
`upper_hemisphere_efficiency_from_fields` for the full study and its result
verification. Full model inputs, outputs, and study validation rows belong under
`build/`; this maintained audit describes the method.
