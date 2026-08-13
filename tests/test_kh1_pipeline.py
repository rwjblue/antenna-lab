from pathlib import Path

import pytest

from antenna_lab.kh1_nec import (
    DIRECT_CANDIDATES,
    DIRECT_DEPLOYMENTS,
    EXTENDED_BANDS,
    GEOMETRIES,
    GROUNDS,
)
from antenna_lab.kh1_pipeline import (
    CONDUCTOR_CASES,
    STUDY_LENGTHS,
    _all_direct_cases,
    _all_doublet_cases,
    _coerce_csv_value,
    _feedlines,
    _shard_items,
)


def test_doublet_case_shards_cover_every_case_once() -> None:
    cases = _all_doublet_cases()
    shards = [_shard_items(cases, index, 4) for index in range(4)]
    flattened = [case for shard in shards for case in shard]
    assert len(flattened) == len(cases)
    assert len({(case[0], case[2], case[3]) for case in flattened}) == len(cases)


def test_direct_case_shards_cover_every_case_once() -> None:
    cases = _all_direct_cases()
    shards = [_shard_items(cases, index, 2) for index in range(2)]
    flattened = [case for shard in shards for case in shard]
    keys = {(case[0], case[3], case[5], case[7], case[9]) for case in flattened}
    assert len(flattened) == len(cases)
    assert len(keys) == len(cases)


def test_grid_length_shards_cover_every_candidate_once() -> None:
    lengths = [float(value) for value in STUDY_LENGTHS]
    shards = [_shard_items(lengths, index, 4) for index in range(4)]
    flattened = [length for shard in shards for length in shard]
    candidates = {
        (length, float(feedline))
        for length in flattened
        for feedline in _feedlines()
    }
    assert len(flattened) == len(lengths)
    assert len(set(flattened)) == len(lengths)
    assert len(candidates) == len(lengths) * len(_feedlines())


def test_invalid_shard_bounds_are_rejected() -> None:
    with pytest.raises(ValueError):
        _shard_items([1], 0, 0)
    with pytest.raises(ValueError):
        _shard_items([1], 2, 2)


def test_csv_coercion_preserves_identifiers_and_restores_scalars() -> None:
    assert _coerce_csv_value("40m") == "40m"
    assert _coerce_csv_value("True") is True
    assert _coerce_csv_value("False") is False
    assert _coerce_csv_value("7050000") == 7_050_000
    assert _coerce_csv_value("35.5") == 35.5
    assert _coerce_csv_value("") is None


def test_pipeline_module_is_committed_source() -> None:
    assert Path(__file__).with_name("test_kh1_pipeline.py").is_file()


def test_extended_nec_case_counts_are_explicit() -> None:
    assert len(_all_doublet_cases()) == (
        len(GEOMETRIES) * len(STUDY_LENGTHS) * len(EXTENDED_BANDS)
    )
    assert len(_all_direct_cases()) == (
        len(DIRECT_CANDIDATES)
        * len(DIRECT_DEPLOYMENTS)
        * len(GROUNDS)
        * len(CONDUCTOR_CASES)
        * len(EXTENDED_BANDS)
    )
