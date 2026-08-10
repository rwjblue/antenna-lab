from pathlib import Path

import pytest

from antenna_lab.measurements import load_impedance_measurements

MEASUREMENTS = Path("data/measured/58ft_doublet_2026-08-08.csv")


def test_baseline_measurement_ingestion() -> None:
    rows = load_impedance_measurements(MEASUREMENTS)

    assert [row.band for row in rows] == [
        "40m",
        "30m",
        "20m",
        "17m",
        "15m",
        "12m",
        "10m",
    ]
    assert [row.frequency_hz for row in rows] == [
        7_050_000,
        10_120_000,
        14_050_000,
        18_080_000,
        21_050_000,
        24_910_000,
        28_050_000,
    ]
    assert [row.impedance_ohm for row in rows] == [
        35.5 - 211j,
        31.0 - 25.5j,
        5.8 - 71.8j,
        2.3 - 35.1j,
        49.1 + 2.3j,
        4.3 - 16j,
        4.1 - 21.4j,
    ]
    assert {row.measurement_reference_plane for row in rows} == {
        "radio end of deployed 28 ft balanced line"
    }


def test_ingestion_rejects_non_passive_measurement(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    header = MEASUREMENTS.read_text(encoding="utf-8").splitlines()[0]
    path.write_text(
        header
        + "\nconfig,2026-08-08,20m,14050000,-1,0,radio end,notes,unknown,fixture\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Non-passive"):
        load_impedance_measurements(path)
