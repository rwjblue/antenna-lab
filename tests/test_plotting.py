import numpy as np

from antenna_lab.plotting import analytical_pattern


def test_analytical_pattern_is_normalized_and_finite() -> None:
    elevations, azimuths, relative_db = analytical_pattern(18_080_000.0, 30.0)

    assert relative_db.shape == (len(elevations), len(azimuths))
    assert np.isfinite(relative_db).all()
    assert float(np.max(relative_db)) == 0.0
    assert float(np.min(relative_db)) >= -120.0

    peak = np.unravel_index(np.argmax(relative_db), relative_db.shape)
    assert elevations[peak[0]] == 34.0
    assert azimuths[peak[1]] in {0.0, 180.0}
