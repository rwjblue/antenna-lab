# Measured impedance schema

Canonical CSV files contain one analyzer reading per row:

| Field | Meaning |
| --- | --- |
| `antenna_config_id` | Stable identifier for the physical configuration. |
| `date` | Measurement date in ISO 8601 format. |
| `band` | Amateur band label. |
| `frequency_hz` | Analyzer frequency as an integer number of hertz. |
| `resistance_ohm` | Real component of measured impedance. |
| `reactance_ohm` | Signed imaginary component; negative is capacitive. |
| `measurement_reference_plane` | Exact electrical point where R+jX applies. |
| `deployment_notes` | Geometry/environment notes known for this run. |
| `tuner_state` | Whether/how an ATU participated in the reading. |
| `source_provenance` | Immutable upstream source and transcription note. |

`raw/58ft_doublet_rigexpert_transcription_v1.0.csv` is an exact copy of the
v1.0 source transcription. It is retained without normalization. The source
bundle did not contain a native RigExpert export; the preserved CSV is the
rawest available machine-readable record.

New measurements must be added as new dated files. Do not overwrite the
2026-08-08 baseline.
