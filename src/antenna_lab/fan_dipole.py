"""Constant-spacing, common-feed fan with aligned parallel-wire segmentation.

Lengths are each straight branch, per side, beyond its ideal source bridge.
The 40 m tip defines the slope; shorter wires share it and end higher up.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from antenna_lab.linked_dipole import insulation_inductance_h_m
from antenna_lab.nec import FT, Wire, wire_network_deck

INCH = 0.0254
BANDS = ("40m", "30m", "20m")


def fan_network(
    lengths_ft: Sequence[float], spacing_in: float, config: Mapping[str, Any]
) -> tuple[Wire, ...]:
    """Create three coupled dipoles with equal in-phase ideal source voltages.

    The optional physical_bus topology is a numerical diagnostic only.

    All parallel wires share interval boundaries, including shorter wire tips.
    Subdivision within each shared interval is identical on every branch.
    This avoids the offset matching points warned about in NEC-2 part III.
    """
    if len(lengths_ft) != 3 or not lengths_ft[0] > lengths_ft[1] > lengths_ft[2] > 0:
        raise ValueError("Expected descending positive 40/30/20 m half lengths")
    if config.get("feed_model", "equal_voltage") not in (
        "equal_voltage",
        "physical_bus",
    ):
        raise ValueError("Unknown feed model")
    radius = config["metal_radius_m"]
    spacing = spacing_in * INCH
    source = config["source_length_m"]
    mesh = config["max_segment_length_m"]
    if min(source / config.get("source_segments", 9), mesh, spacing) <= 8 * radius:
        raise ValueError("Source, bus and mesh must exceed eight conductor radii")
    if spacing <= 2 * config["insulation_outer_radius_m"]:
        raise ValueError("Wire jackets cannot touch or overlap")
    lengths = [value * FT for value in lengths_ft]
    center = config["center_height_ft"] * FT
    drop = (config["center_height_ft"] - config["end_height_ft"]) * FT
    if not 0 <= drop < lengths[0] or config["end_height_ft"] <= 0:
        raise ValueError("40 m wire cannot reach the requested end height")
    slope = drop / lengths[0]
    horizontal = math.sqrt(1 - slope**2)
    rotation = math.radians(config.get("ribbon_rotation_deg", 0))
    source_segments = config.get("source_segments", 9)
    if source_segments < 3 or source_segments % 2 != 1:
        raise ValueError("Source segment count must be odd and at least three")
    wires = [
        Wire(
            1,
            source_segments,
            (-source / 2, 0, center),
            (source / 2, 0, center),
            radius,
        )
    ]
    # Resolve the near fields at every branch tip on ALL parallel wires.
    # Uniform long segments can converge very slowly even when aligned.
    boundaries = [0.0]
    anchors = [0.0, *sorted(lengths)]
    near = min(spacing, source / source_segments, mesh / 3)
    for lo, hi in zip(anchors[:-1], anchors[1:], strict=True):
        left, right = [lo], [hi]
        step = near
        while step < mesh and right[-1] - left[-1] > 4 * step:
            left.append(left[-1] + step)
            right.append(right[-1] - step)
            step *= 1.4
        count = max(1, math.ceil((right[-1] - left[-1]) / mesh))
        middle = [
            left[-1] + (right[-1] - left[-1]) * i / count for i in range(1, count)
        ]
        boundaries.extend(left[1:] + middle + list(reversed(right)))
    tag = 10
    for sign in (-1, 1):
        # Rotation about each arm preserves true perpendicular spacing.
        normal = (
            -sign * slope * math.sin(rotation),
            math.cos(rotation),
            -horizontal * math.sin(rotation),
        )

        def point(s, branch, sign=sign, normal=normal):
            return (
                sign * (source / 2 + s * horizontal) + branch * spacing * normal[0],
                branch * spacing * normal[1],
                center - s * slope + branch * spacing * normal[2],
            )

        for branch in range(2):
            wires.append(
                Wire(
                    tag,
                    max(1, math.ceil(spacing / min(mesh, source / source_segments))),
                    point(0, branch),
                    point(0, branch + 1),
                    radius,
                )
            )
            tag += 1
        for branch, length in enumerate(lengths):
            for start, end in zip(boundaries[:-1], boundaries[1:], strict=True):
                if start >= length - 1e-9:
                    break
                wires.append(
                    Wire(
                        tag,
                        max(1, math.ceil((end - start) / mesh)),
                        point(start, branch),
                        point(end, branch),
                        radius,
                    )
                )
                tag += 1
    if config.get("feed_model", "equal_voltage") == "equal_voltage":
        if rotation:
            raise ValueError("Equal-voltage feeds currently require horizontal ribbon")
        bus_tags = {10, 11, (len(wires) - 1) // 2 + 10, (len(wires) - 1) // 2 + 11}
        wires = [wire for wire in wires if wire.tag not in bus_tags]
        for branch in (1, 2):
            wires.append(
                Wire(
                    10000 + branch,
                    source_segments,
                    (-source / 2, branch * spacing, center),
                    (source / 2, branch * spacing, center),
                    radius,
                )
            )
    return tuple(wires)


def fan_deck(lengths_ft, spacing_in, frequency_mhz, config, *, pattern=False):
    wires = fan_network(lengths_ft, spacing_in, config)
    soil = config["grounds"][config.get("ground", "average")]
    deck = wire_network_deck(
        title=f"Parallel fan 40/30/20m spacing {spacing_in:g}in",
        wires=wires,
        source_tag=1,
        source_segment=(config.get("source_segments", 9) + 1) // 2,
        frequency_mhz=frequency_mhz,
        conductivity_s_m=config["effective_conductivity_s_m"],
        epsilon_r=soil["epsilon_r"],
        ground_conductivity_s_m=soil["conductivity_s_m"],
        pattern=pattern,
    )
    # Each source bridge is bare. Three equal, in-phase ideal voltages impose
    # the common port; the FULL coupled solution supplies all three currents.
    # Total impedance is V / sum(I), not any individual NEC port impedance.
    if config.get("feed_model", "equal_voltage") == "equal_voltage":
        excluded = {1, 10001, 10002}
        segment = (config.get("source_segments", 9) + 1) // 2
        deck = deck.replace(
            "PT -1",
            "".join(f"EX 0 {tag} {segment} 0 1.0 0.0\n" for tag in (10001, 10002))
            + "PT -1",
        )
    else:
        excluded = {1, 10, 11, (len(wires) - 1) // 2 + 10, (len(wires) - 1) // 2 + 11}
    inductance = insulation_inductance_h_m(config)
    coating = "".join(
        f"LD 2 {wire.tag} 0 0 0 {inductance:.12e} 0\n"
        for wire in wires
        if wire.tag not in excluded
    )
    return deck.replace("GN 2", coating + "GN 2", 1)
