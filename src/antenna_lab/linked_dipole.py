"""Explicit three-section linked dipole; disconnected wires remain in the solve.

Distances are per leg, excluding half the separately specified source bridge.
Link centers keep their position when a bridge is removed to open a link.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from antenna_lab.nec import FT, SeriesLoad, Wire, wire_network_deck


def geometry_dimensions(
    lengths_ft: Sequence[float], end_height_ft: float, config: Mapping[str, Any]
) -> dict[str, float | None]:
    if len(lengths_ft) != 3 or any(value <= 0 for value in lengths_ft):
        raise ValueError("Three positive per-leg section lengths are required")
    length = sum(lengths_ft)
    center = float(config["center_height_ft"])
    drop = center - end_height_ft
    if end_height_ft <= 0 or not 0 <= drop < length:
        raise ValueError("Straight legs cannot reach the requested end height")
    run = math.sqrt(length**2 - drop**2)
    half_source_ft = float(config["source_length_m"]) / (2 * FT)
    return {
        "center_height_ft": center,
        "end_height_ft": end_height_ft,
        "half_length_ft": length,
        "link_a_height_ft": center - drop * lengths_ft[0] / length,
        "link_b_height_ft": center - drop * sum(lengths_ft[:2]) / length,
        "apex_angle_deg": 2 * math.degrees(math.acos(drop / length)),
        "span_ft": 2 * (half_source_ft + run),
        "stake_distance_ft": None
        if drop == 0
        else half_source_ft + run * center / drop,
        "cord_length_ft": None if drop == 0 else length * end_height_ft / drop,
    }


def linked_network(
    lengths_ft: Sequence[float],
    end_height_ft: float,
    band: str,
    config: Mapping[str, Any],
    *,
    outer_closed_on_20m: bool = False,
) -> tuple[tuple[Wire, ...], tuple[SeriesLoad, ...]]:
    """Use explicit finite electrical breaks and real bridge wires when closed."""
    if band not in ("20m", "30m", "40m"):
        raise ValueError("Only the linked 20/30/40m assembly is supported")
    geometry_dimensions(lengths_ft, end_height_ft, config)
    length = sum(lengths_ft) * FT
    drop = (config["center_height_ft"] - end_height_ft) * FT
    slope = drop / length
    horizontal = math.sqrt(1 - slope**2)
    center = config["center_height_ft"] * FT
    radius = config["metal_radius_m"]
    gap = config["open_gap_m"]
    source = config["source_length_m"]
    max_segment = config["max_segment_length_m"]
    if min(radius, gap, source, max_segment) <= 0 or gap < 4 * radius:
        raise ValueError("Positive dimensions and a resolved finite gap are required")
    if source / 3 <= 2 * radius:
        raise ValueError("Each source segment must exceed the metal conductor diameter")
    if gap >= min(lengths_ft) * FT:
        raise ValueError("Electrical gap must be shorter than every section")
    # Excite the center of three equal collinear segments. Matching the first
    # leg segment to a bridge segment, then grading outward, avoids source
    # power errors from abrupt changes in segment length near the feedpoint.
    wires = [Wire(1, 3, (-source / 2, 0, center), (source / 2, 0, center), radius)]
    loads = []
    link_a = lengths_ft[0] * FT
    link_b = sum(lengths_ft[:2]) * FT
    intervals = (
        (0, link_a - gap / 2),
        (link_a + gap / 2, link_b - gap / 2),
        (link_b + gap / 2, length),
    )
    closed = (
        band in ("30m", "40m"),
        band == "40m" or (band == "20m" and outer_closed_on_20m),
    )
    for side, sign in enumerate((-1, 1)):

        def point(s: float, direction: int = sign) -> tuple[float, float, float]:
            return direction * (source / 2 + s * horizontal), 0, center - s * slope

        for section, (start, end) in enumerate(intervals):
            tag = 10 + side * 10 + section
            if section == 0:
                near_length = source / 3
                near_index = 0
                while near_length < max_segment * 0.99 or near_index == 0:
                    if start + near_length >= end:
                        raise ValueError(
                            "First section is too short for the source mesh"
                        )
                    wires.append(
                        Wire(
                            tag * 100 + near_index,
                            1,
                            point(start),
                            point(start + near_length),
                            radius,
                        )
                    )
                    start += near_length
                    near_length *= 1.4
                    near_index += 1
            wires.append(
                Wire(
                    tag,
                    max(1, math.ceil((end - start) / max_segment)),
                    point(start),
                    point(end),
                    radius,
                )
            )
        for index, position in enumerate((link_a, link_b)):
            if closed[index]:
                tag = 13 + side * 10 + index
                wires.append(
                    Wire(
                        tag,
                        1,
                        point(position - gap / 2),
                        point(position + gap / 2),
                        radius,
                    )
                )
                loads.append(
                    SeriesLoad(tag, 1, complex(config["contact_resistance_ohm"]))
                )
    return tuple(wires), tuple(loads)


def insulation_inductance_h_m(config: Mapping[str, Any]) -> float:
    """Thin sheath NEC series-L approximation, excluding dielectric dissipation."""
    radius = config["metal_radius_m"]
    outer = config["insulation_outer_radius_m"]
    epsilon = config["insulation_relative_permittivity"]
    if outer < radius or epsilon < 1 or config["insulation_loading_scale"] < 0:
        raise ValueError("Insulation radius/permittivity/loading scale is invalid")
    # Cebik equation 1A: empirical thin-sheath correspondence to NEC-4 IS.
    return (
        2e-7
        * ((outer / radius) * epsilon) ** (1 / 12)
        * (1 - 1 / epsilon)
        * math.log(outer / radius)
        * config["insulation_loading_scale"]
    )


def linked_deck(
    lengths_ft: Sequence[float],
    end_height_ft: float,
    band: str,
    frequency_mhz: float,
    config: Mapping[str, Any],
    *,
    ground: str = "average",
    pattern_step_deg: float | None = None,
    outer_closed_on_20m: bool = False,
) -> str:
    wires, loads = linked_network(
        lengths_ft, end_height_ft, band, config, outer_closed_on_20m=outer_closed_on_20m
    )
    soil = config["grounds"][ground]
    deck = wire_network_deck(
        title=f"Linked physical dipole {band} ends {end_height_ft:g}ft",
        wires=wires,
        loads=loads,
        source_tag=1,
        source_segment=2,
        frequency_mhz=frequency_mhz,
        conductivity_s_m=config["effective_conductivity_s_m"],
        epsilon_r=soil["epsilon_r"],
        ground_conductivity_s_m=soil["conductivity_s_m"],
        pattern=pattern_step_deg is not None,
    )
    inductance = insulation_inductance_h_m(config)
    if inductance:
        # LD 2 values are distributed R (ohm/m), L (H/m), and C (F*m).
        # Apply only to jacketed long wires, excluding source and link bridges.
        coating = "".join(
            f"LD 2 {wire.tag} 0 0 0 {inductance:.12e} 0\n"
            for wire in wires
            if wire.tag not in (1, 13, 14, 23, 24)
        )
        deck = deck.replace("GN 2", coating + "GN 2", 1)
    if pattern_step_deg is not None:
        if (
            pattern_step_deg <= 0
            or 90 % pattern_step_deg != 0
            or 360 % pattern_step_deg != 0
        ):
            raise ValueError("Pattern step must divide 90 and 360 degrees")
        card = (
            f"RP 0 {int(90 / pattern_step_deg) + 1} "
            f"{int(360 / pattern_step_deg)} 1001 0 0 "
            f"{pattern_step_deg:g} {pattern_step_deg:g} 1000 0"
        )
        deck = (
            "\n".join(
                card if line.startswith("RP ") else line for line in deck.splitlines()
            )
            + "\n"
        )
    return deck
