"""Bandwidth extraction must use full crossings, not a band-clipped width."""

from types import SimpleNamespace

import numpy as np
import pytest

from antenna_lab.fan_bandwidth import coverage, full_window
from antenna_lab.transmission_line import swr


def test_coverage_clips_to_requested_interval():
    assert coverage([6.98, 7.23], [7, 7.3]) == pytest.approx(0.23 / 0.3)
    assert coverage([6, 8], [7, 7.3]) == 1
    assert coverage([6, 6.9], [7, 7.3]) == 0
    assert coverage(None, [7, 7.3]) == 0


class AnalyticStudy:
    def solve(self, lengths, spacing, frequency):
        return (SimpleNamespace(impedance_ohm=50 + 1000j * (frequency - 10)),)


def test_full_window_retains_both_out_of_band_crossings():
    study = AnalyticStudy()
    sweep = []
    for f in np.linspace(9.9, 10.1, 31):
        z = study.solve(None, None, f)[0].impedance_ohm
        sweep.append([f, z.real, z.imag, float(swr(z))])
    window = full_window(study, None, None, "30m", {"sweep": sweep})
    assert window == pytest.approx(
        [10 - 50 / (2**0.5 * 1000), 10 + 50 / (2**0.5 * 1000)], abs=1e-6
    )


def test_unbracketed_window_is_not_reported_as_bandwidth():
    with pytest.raises(ValueError, match="Unbracketed"):
        full_window(AnalyticStudy(), None, None, "30m", {"sweep": [[10, 50, 0, 1]]})
    assert (
        full_window(AnalyticStudy(), None, None, "30m", {"sweep": [[10, 200, 0, 4]]})
        is None
    )


def test_local_crossings_agree_with_analytic_matched_window():
    from antenna_lab.fan_bandwidth import local_windows

    study = AnalyticStudy()
    study.config = {"bands_mhz": {"40m": 10, "30m": 10, "20m": 10}}
    rows = local_windows(study, 0.5, {"lengths_ft": [33, 23, 16]})
    assert len(rows) == 3
    for row in rows:
        assert row["width_khz"] == pytest.approx(100 / (2**0.5), abs=0.002)
        assert row["full_swr2_window_mhz"] == pytest.approx(
            [9.96464466, 10.03535534], abs=1e-6
        )
