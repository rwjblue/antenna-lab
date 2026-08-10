# Source-bundle provenance and migration

Both original ZIPs were CRC-tested, extracted separately, and checked against
their internal SHA-256 manifests before architecture decisions were made. The
source ZIP hashes are recorded in `archive/source-bundles/SHA256SUMS`.

## v0.1 classification

Preserved unchanged in its source ZIP:

- manually transcribed RigExpert readings and KXAT2 observations;
- construction/baseline context;
- planned optimizer contract;
- analytical thin-wire pattern source, summary, overview, and PDF;
- original provenance and manifests.

Promoted to the active tree:

- analytical pattern report, overview, and summary as a clearly labeled
  historical/reference model under `reports/radiation-pattern-v0.1/`.

Historical only:

- the planned YAML optimizer architecture;
- provisional pre-optimization conclusions;
- any earlier absolute 17 m efficiency estimate (including roughly 47%).

## v1.0 classification

Preserved unchanged in its source ZIP:

- source/config/input data;
- full candidate grid and compact 390-member ensemble arrays;
- selected/paired/Pareto results;
- all figures, reports, hashes, and run metadata;
- the carried-forward analytical pattern model.

Promoted to the active tree:

- canonical measured rows with an explicit schema and reference plane;
- the exact rawest-available RigExpert CSV transcription;
- selected optimization tables, summary, and run metadata;
- optimization report and figures;
- explicit uncertainty ranges and model labels in active config.

Refactored rather than copied verbatim:

- the monolithic optimizer became typed measurement, transmission-line,
  radiator-surrogate, optimization, plotting, and CLI modules;
- output now has a small deterministic regression fixture and a portable
  SHA-256 manifest;
- hidden report generation was separated from numerical model functions;
- assumptions and confidence labels moved into checked-in config/docs.

Not duplicated outside the source ZIP:

- the 31 MB compact ensemble NPZ;
- the complete generated full-grid v1.0 tree;
- duplicate copies of the identical pattern source and artifacts.

Nothing was silently merged. v1.0 supersedes v0.1 for current results; v0.1 is
used only for provenance and the pattern work that v1.0 explicitly carried
forward unchanged.
