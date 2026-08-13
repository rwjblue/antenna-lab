import numpy as np

from antenna_lab.kh1_nec import _anchor, _minimum_q, _q_separator


def test_q_separator_reproduces_observed_kh1_split() -> None:
    measured = np.asarray(
        [35.5 - 211j, 31.0 - 25.5j, 5.8 - 71.8j, 2.3 - 35.1j, 49.1 + 2.3j]
    )
    threshold, hardest_success, easiest_failure = _q_separator(measured)
    assert hardest_success < threshold < easiest_failure
    assert np.all(_minimum_q(measured[[0, 1, 4]]) <= threshold)
    assert np.all(_minimum_q(measured[[2, 3]]) > threshold)


def test_both_anchor_rules_preserve_baseline() -> None:
    measured = np.asarray([40 - 20j, 15 + 30j])
    nec = np.asarray([70 + 10j, 100 - 50j])
    for method in ("impedance_delta", "smith_displacement"):
        assert np.allclose(_anchor(measured, nec, nec, 450.0, method), measured)
