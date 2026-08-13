import numpy as np

from antenna_lab.kh1_nec import (
    BANDS,
    EXTENDED_BANDS,
    KH1_REQUIRED_BANDS,
    TUNER_ENVELOPES,
    _linked_geometry,
    _anchor,
    _baseline_tuner_rows,
    _kh1_tuner_proxy,
)


def test_empirical_topology_envelopes_reproduce_observed_kh1_split() -> None:
    measured = np.asarray(
        [35.5 - 211j, 31.0 - 25.5j, 5.8 - 71.8j, 2.3 - 35.1j, 49.1 + 2.3j, 4.3 - 16j, 4.1 - 21.4j]
    )
    rows = _baseline_tuner_rows(measured)
    scored = {row["band"]: row for row in rows[:5]}
    for envelope in TUNER_ENVELOPES:
        assert scored["40m"][f"{envelope}_compatible"]
        assert scored["30m"][f"{envelope}_compatible"]
        assert scored["15m"][f"{envelope}_compatible"]
        assert not scored["20m"][f"{envelope}_compatible"]
        assert not scored["17m"][f"{envelope}_compatible"]


def test_high_impedance_direct_wire_can_be_easy_for_supported_topology() -> None:
    stress, l_uh, c_pf, topology = _kh1_tuner_proxy(
        1815 - 1524j,
        14_050_000,
        lmax_uH=12.0,
        cmax_pF=400.0,
    )
    assert stress < 1.0
    assert 0 < l_uh < 12.0
    assert 0 < c_pf < 400.0
    assert topology in {0, 1}


def test_both_anchor_rules_preserve_baseline() -> None:
    measured = np.asarray([40 - 20j, 15 + 30j])
    nec = np.asarray([70 + 10j, 100 - 50j])
    for method in ("impedance_delta", "smith_displacement"):
        assert np.allclose(_anchor(measured, nec, nec, 450.0, method), measured)


def test_band_order_is_stable() -> None:
    assert [band for band, _, _ in BANDS[:5]] == ["40m", "30m", "20m", "17m", "15m"]


def test_extended_band_scope_preserves_original_anchor_order() -> None:
    assert [band for band, _, _ in EXTENDED_BANDS] == [
        "80m",
        "60m",
        "40m",
        "30m",
        "20m",
        "17m",
        "15m",
        "12m",
        "10m",
        "6m",
    ]
    assert KH1_REQUIRED_BANDS == ("40m", "30m", "20m", "17m", "15m")
    assert [band for band, _, _ in BANDS] == [
        "40m",
        "30m",
        "20m",
        "17m",
        "15m",
        "12m",
        "10m",
    ]


def test_80m_linked_reference_geometry_keeps_wire_above_ground() -> None:
    geometry_id, geometry = _linked_geometry("80m")
    assert geometry_id == "reference_30_5"
    _, end_height = geometry.endpoints(132.0)
    assert end_height == 5.0
