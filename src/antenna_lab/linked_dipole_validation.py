"""Reconcile NEC power gain with radiation into the upper hemisphere.

NEC's printed "radiated power" subtracts wire and network dissipation only.
The space-wave gain integral is needed to account for imperfect ground. See
``docs/linked-dipole-power-audit.md`` for definitions and limitations.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

from antenna_lab.nec import FLOAT, Wire
from antenna_lab.rigid_doublet_validation import average_gain


def upper_hemisphere_efficiency(
    pattern: Iterable[tuple[float, float, float]],
) -> float:
    """Return integral(G dΩ)/(4π) for absolute, accepted-power gain in dBi.

    Requires a rectangular upper-hemisphere grid, including elevation 0 and
    90 degrees, without a duplicate azimuth 360-degree column. Reuses the
    established full-sphere quadrature by mirroring, then dividing by two;
    the mirror is purely an integration device, not radiation below ground.
    The result is not clamped: a nonphysical answer must remain detectable.
    """
    points = list(pattern)
    if not points or any(
        len(point) != 3
        or not all(math.isfinite(value) for value in point)
        or not 0 <= point[0] <= 90
        for point in points
    ):
        raise ValueError("Efficiency requires finite upper-hemisphere pattern points")
    elevations = {point[0] for point in points}
    if 0 not in elevations or 90 not in elevations or len(elevations) < 3:
        raise ValueError("Efficiency requires a complete upper-hemisphere grid")
    mirrored = points + [
        (-elevation, azimuth, gain)
        for elevation, azimuth, gain in points
        if elevation > 0
    ]
    return average_gain(mirrored) / 2.0


def power_budget(output_text: str) -> dict[str, float]:
    """Parse one NEC power budget without calling printed efficiency radiation.

    Values retain solver output rounding. Multiple-frequency output is rejected
    rather than silently mixing a budget with another frequency's pattern.
    """
    fields = {
        "input_power_w": ("INPUT POWER", "Watts"),
        "nec_printed_radiated_power_w": ("RADIATED POWER", "Watts"),
        "structure_loss_w": ("STRUCTURE LOSS", "Watts"),
        "network_loss_w": ("NETWORK LOSS", "Watts"),
        "nec_printed_efficiency_fraction": ("EFFICIENCY", "Percent"),
    }
    result: dict[str, float] = {}
    for key, (label, unit) in fields.items():
        matches = re.findall(rf"{label}\s*=\s*({FLOAT})\s*{unit}", output_text, re.I)
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one NEC {label} value")
        result[key] = float(matches[0])
    if result["input_power_w"] <= 0:
        raise ValueError("Accepted input power must be positive")
    result["nec_printed_efficiency_fraction"] /= 100.0
    result["printed_balance_residual_w"] = (
        result["input_power_w"]
        - result["nec_printed_radiated_power_w"]
        - result["structure_loss_w"]
        - result["network_loss_w"]
    )
    return result


def reconciled_power_budget(
    output_text: str, pattern: Iterable[tuple[float, float, float]]
) -> dict[str, float]:
    """Add space-wave power and the remaining ground/numerical residual.

    The residual is energy not present in far-field upper-hemisphere space
    waves or explicit structure/network dissipation. It is not a separate
    integration of local soil heating. No efficiency factor is applied to the
    gain again; the existing gain already includes the modeled loss effects.
    """
    if "POWER GAINS" not in output_text or "DIRECTIVE GAINS" in output_text:
        raise ValueError("Reconciliation requires NEC absolute power-gain output")
    result = power_budget(output_text)
    efficiency = upper_hemisphere_efficiency(pattern)
    input_power = result["input_power_w"]
    radiation = efficiency * input_power
    residual = (
        input_power - radiation - result["structure_loss_w"] - result["network_loss_w"]
    )
    result.update(
        upper_hemisphere_efficiency=efficiency,
        upper_hemisphere_radiated_power_w=radiation,
        structure_loss_fraction=result["structure_loss_w"] / input_power,
        network_loss_fraction=result["network_loss_w"] / input_power,
        ground_and_numerical_residual_w=residual,
        ground_and_numerical_residual_fraction=residual / input_power,
    )
    return result


def upper_hemisphere_efficiency_from_fields(output_text: str) -> float:
    """Independently normalize NEC's printed space-wave electric fields.

    For peak-amplitude fields, U = r²(|Eθ|² + |Eφ|²)/(2η₀). NEC uses
    η₀ = 376.73 ohms. This checks gain-versus-field normalization but not the
    accuracy of the shared underlying electromagnetic solution. Requires one
    explicit RP range and one upper-hemisphere pattern with no duplicate seam.
    """
    budget = power_budget(output_text)
    ranges = re.findall(rf"RANGE:\s*({FLOAT})\s*METERS", output_text, re.I)
    if len(ranges) != 1 or float(ranges[0]) <= 0:
        raise ValueError("Field integration requires one positive explicit RP range")
    if output_text.count("RADIATION PATTERNS") != 1:
        raise ValueError("Field integration requires exactly one radiation pattern")
    factor = 2 * math.pi * float(ranges[0]) ** 2 / (376.73 * budget["input_power_w"])
    pattern = []
    for line in output_text.split("RADIATION PATTERNS", 1)[1].splitlines():
        columns = line.split()
        # A null can have a blank polarization-sense column (11, not 12).
        if len(columns) not in (11, 12):
            continue
        try:
            theta, phi = float(columns[0]), float(columns[1])
            e_theta, e_phi = float(columns[-4]), float(columns[-2])
        except ValueError:
            continue
        gain = factor * (e_theta**2 + e_phi**2)
        pattern.append((90.0 - theta, phi, 10 * math.log10(max(1e-300, gain))))
    return upper_hemisphere_efficiency(pattern)


def free_space_reactive_deck(deck: str) -> str:
    """Remove conductor/contact dissipation while retaining reactive LD loads.

    The study uses LD5 conductivity, LD4 contact impedance, and LD2 distributed
    insulation reactance. Other loading types are rejected to keep the meaning
    of this validation explicit. An LD4 reactance, if present, is preserved.
    """
    cards = []
    ground_cards = pattern_cards = 0
    for line in deck.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "GN":
            line = "GN -1"
            ground_cards += 1
        elif fields[0] == "RP":
            line = "RP 0 37 72 1001 0 0 5 5 1000 0"
            pattern_cards += 1
        elif fields[0] == "LD":
            kind = int(fields[1])
            if kind == 5:
                continue
            if kind not in (2, 4):
                raise ValueError("Reactive validation supports only LD2, LD4 and LD5")
            fields[5] = "0"
            line = " ".join(fields)
        cards.append(line)
    if ground_cards != 1 or pattern_cards != 1:
        raise ValueError("Validation expects one ground card and one pattern card")
    return "\n".join(cards) + "\n"


def check_open_endpoints(
    output_text: str, wires: Iterable[Wire], band: str
) -> dict[str, Any]:
    """Check NEC's actual endpoint connections against the linked wire network.

    Uses the printed segmentation I-/I+ fields, including connection signs.
    All wire endpoints are checked: source, closed bridges, open gaps, and outer
    tips. The band check uses this study's stable tag convention and permits the
    explicit both-outer-links-closed 20 m sensitivity case.
    """
    wires = tuple(wires)
    if band not in ("20m", "30m", "40m"):
        raise ValueError("Connectivity check supports linked 20/30/40m bands")
    expected_tags = {1, 10, 11, 12, 20, 21, 22}
    tags = {wire.tag for wire in wires}
    # The first arm sections have graded near-source pieces; the main section
    # tags still identify the remainders ending at link A. Require matching,
    # consecutive piece tags on both sides instead of assuming seven wires.
    left_near = {tag - 1000 for tag in tags if 1000 <= tag < 1100}
    right_near = {tag - 2000 for tag in tags if 2000 <= tag < 2100}
    expected_tags.update(1000 + index for index in left_near)
    expected_tags.update(2000 + index for index in right_near)
    if band in ("30m", "40m"):
        expected_tags.update((13, 23))
    if band == "40m" or (band == "20m" and {14, 24} <= tags):
        expected_tags.update((14, 24))
    errors = []
    if (
        left_near != right_near
        or not left_near
        or left_near != set(range(len(left_near)))
    ):
        errors.append("Graded source mesh must have consecutive mirrored piece tags")
    if tags != expected_tags or len(tags) != len(wires):
        errors.append("Wire tags do not match the requested linked-band topology")
    if output_text.count("SEGMENTATION DATA") != 1:
        return {"passed": False, "errors": ["Expected one segmentation table"]}
    table = output_text.split("SEGMENTATION DATA", 1)[1].split("DATA CARD", 1)[0]
    segments = {}
    for line in table.splitlines():
        fields = line.split()
        if len(fields) != 12:
            continue
        try:
            index, before, repeated_index, after, tag = (
                int(fields[position]) for position in (0, 8, 9, 10, 11)
            )
            tuple(float(fields[position]) for position in range(1, 8))
        except ValueError:
            continue
        if index != repeated_index or index in segments:
            errors.append("Malformed or duplicate NEC segmentation row")
        segments[index] = (before, after, tag)
    if len(segments) != sum(wire.segments for wire in wires):
        errors.append("Printed segment count does not match the wire network")
    endpoints = []
    first_segment = 1
    for wire in wires:
        for index in range(first_segment, first_segment + wire.segments):
            if index not in segments or segments[index][2] != wire.tag:
                errors.append(f"Missing or incorrect segment tag at segment {index}")
        endpoints.extend(
            (
                (wire.tag, "start", first_segment, wire.start),
                (wire.tag, "end", first_segment + wire.segments - 1, wire.end),
            )
        )
        first_segment += wire.segments
    details = []
    for tag, end, index, coordinate in endpoints:
        neighbors = [
            (other_end, other_index)
            for other_tag, other_end, other_index, other_coordinate in endpoints
            if (tag, end) != (other_tag, other_end)
            and math.dist(coordinate, other_coordinate) < 1e-7
        ]
        if len(neighbors) > 1:
            errors.append(f"Unsupported multiple-wire junction at tag {tag} {end}")
        expected = 0
        if len(neighbors) == 1:
            other_end, other_index = neighbors[0]
            expected = -other_index if end == other_end else other_index
        actual = None
        if index in segments:
            actual = segments[index][0 if end == "start" else 1]
        details.append(
            {
                "tag": tag,
                "endpoint": end,
                "segment": index,
                "expected_connection": expected,
                "actual_connection": actual,
                "passed": len(neighbors) <= 1 and actual == expected,
            }
        )
    open_link_ends = sum(
        row["expected_connection"] == 0
        and (row["tag"], row["endpoint"]) not in ((12, "end"), (22, "end"))
        for row in details
    )
    expected_open_link_ends = 8 - 2 * len(tags & {13, 14, 23, 24})
    if open_link_ends != expected_open_link_ends:
        errors.append("Unexpected number of geometrically open link endpoints")
    return {
        "passed": not errors and all(row["passed"] for row in details),
        "errors": errors,
        "segment_count": len(segments),
        "open_link_endpoint_count": open_link_ends,
        "closed_link_count": len(tags & {13, 14, 23, 24}),
        "endpoint_checks": details,
    }
