import math

import pytest

from antenna_lab.efrw_study import (
    efrw_wires,
    load_efrw_config,
    radiator_points_ft,
)


def _path_length(points):
    return sum(
        math.dist(start, end)
        for start, end in zip(points[:-1], points[1:], strict=True)
    )


def test_each_deployment_preserves_53_ft_radiator_length() -> None:
    config = load_efrw_config("configs/53ft-efrw-v1.json")
    for deployment in config["deployments"].values():
        points = radiator_points_ft(deployment, 53.0)
        assert _path_length(points) == pytest.approx(53.0)
        assert all(point[2] > 0 for point in points)


def test_both_return_cases_have_source_and_explicit_return() -> None:
    config = load_efrw_config("configs/53ft-efrw-v1.json")
    for return_id in config["returns"]:
        wires = efrw_wires(config, "sloper_30", return_id)
        source = wires[-2]
        return_wire = wires[-1]
        assert source.segments == 1
        assert math.dist(source.start, source.end) == pytest.approx(0.02)
        assert math.dist(return_wire.start, return_wire.end) == pytest.approx(
            17.0 * 0.3048
        )


def test_coax_return_uses_coax_outside_radius() -> None:
    config = load_efrw_config("configs/53ft-efrw-v1.json")
    dedicated = efrw_wires(config, "sloper_20", "dedicated_counterpoise")[-1]
    coax = efrw_wires(config, "sloper_20", "coax_common_mode")[-1]
    assert coax.radius_m > dedicated.radius_m
