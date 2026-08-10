"""Typed ingestion for measured antenna impedance data."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REQUIRED_COLUMNS = (
    "antenna_config_id",
    "date",
    "band",
    "frequency_hz",
    "resistance_ohm",
    "reactance_ohm",
    "measurement_reference_plane",
    "deployment_notes",
    "tuner_state",
    "source_provenance",
)


@dataclass(frozen=True)
class ImpedanceMeasurement:
    """One complex-impedance observation at a documented reference plane."""

    antenna_config_id: str
    measured_on: date
    band: str
    frequency_hz: int
    resistance_ohm: float
    reactance_ohm: float
    measurement_reference_plane: str
    deployment_notes: str
    tuner_state: str
    source_provenance: str

    @property
    def impedance_ohm(self) -> complex:
        return complex(self.resistance_ohm, self.reactance_ohm)

    @property
    def frequency_mhz(self) -> float:
        return self.frequency_hz / 1_000_000.0


def load_impedance_measurements(path: Path) -> tuple[ImpedanceMeasurement, ...]:
    """Load and validate a canonical measured-impedance CSV."""

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing measurement columns: {sorted(missing)}")
        rows = tuple(_parse_row(row, index + 2) for index, row in enumerate(reader))

    if not rows:
        raise ValueError("Measurement file is empty")

    keys = [(row.antenna_config_id, row.band, row.frequency_hz) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate antenna/config, band, and frequency row")
    if len({row.antenna_config_id for row in rows}) != 1:
        raise ValueError("A measurement file must contain exactly one configuration")
    return rows


def _parse_row(row: dict[str, str], line_number: int) -> ImpedanceMeasurement:
    try:
        measurement = ImpedanceMeasurement(
            antenna_config_id=row["antenna_config_id"].strip(),
            measured_on=date.fromisoformat(row["date"].strip()),
            band=row["band"].strip(),
            frequency_hz=int(row["frequency_hz"]),
            resistance_ohm=float(row["resistance_ohm"]),
            reactance_ohm=float(row["reactance_ohm"]),
            measurement_reference_plane=row["measurement_reference_plane"].strip(),
            deployment_notes=row["deployment_notes"].strip(),
            tuner_state=row["tuner_state"].strip(),
            source_provenance=row["source_provenance"].strip(),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid measurement at CSV line {line_number}") from error

    if not measurement.antenna_config_id or not measurement.band:
        raise ValueError(f"Blank identifier at CSV line {line_number}")
    if measurement.frequency_hz <= 0:
        raise ValueError(f"Non-positive frequency at CSV line {line_number}")
    if measurement.resistance_ohm <= 0:
        raise ValueError(f"Non-passive measured resistance at CSV line {line_number}")
    if not measurement.measurement_reference_plane:
        raise ValueError(f"Missing reference plane at CSV line {line_number}")
    if not measurement.source_provenance:
        raise ValueError(f"Missing provenance at CSV line {line_number}")
    return measurement
