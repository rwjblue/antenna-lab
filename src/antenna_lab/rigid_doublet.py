"""Symmetric rigid whip doublets with an optional isolated conductive mast.

Positive arm elevation makes an upward V; negative elevation makes an inverted
V. Dimensions describe the full straight whips, excluding the short horizontal
NEC excitation bridge. The mast is a uniform isolated wire surrogate, not a
material model of a tapered, anisotropic carbon-fiber pole.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from antenna_lab.nec import FT, Wire, wire_network_deck


@dataclass(frozen=True)
class RigidDoublet:
    arm_length_ft: float = 17.0
    feed_height_ft: float = 30.0
    arm_elevation_deg: float = 45.0
    radius_m: float = 0.0015
    arm_segments: int = 181
    feed_gap_m: float = 0.06

    def __post_init__(self) -> None:
        for name in ("arm_length_ft", "feed_height_ft", "radius_m", "feed_gap_m"):
            _positive(name, getattr(self, name))
        if not math.isfinite(self.arm_elevation_deg) or not (
            -90.0 < self.arm_elevation_deg < 90.0
        ):
            raise ValueError("Arm elevation must be finite and between -90 and 90")
        _segments("Arm segments", self.arm_segments)
        if self.feed_gap_m / 3.0 <= 2.0 * self.radius_m:
            raise ValueError("Each feed bridge segment must exceed the wire diameter")
        if self.tip_height_ft <= 0.0:
            raise ValueError("Doublet tip is at or below ground")

    @property
    def tip_height_ft(self) -> float:
        return self.feed_height_ft + self.arm_length_ft * math.sin(
            math.radians(self.arm_elevation_deg)
        )

    @property
    def span_ft(self) -> float:
        """Tip-to-tip horizontal span, including the excitation bridge."""

        return self.feed_gap_m / FT + 2.0 * self.arm_length_ft * math.cos(
            math.radians(self.arm_elevation_deg)
        )


@dataclass(frozen=True)
class FloatingMast:
    """Vertical isolated wire; height is length, offset is perpendicular to V.

    The bottom must be above ground. An offset of zero is allowed if the mast
    stops short of the radiator; intersecting or touching wires are rejected.
    Conductivity is an explicit sensitivity assumption for the surrogate.
    A nonzero x_offset_m breaks left/right symmetry for coupling sensitivity;
    a perfectly centered vertical mast lies on a symmetry plane of the feed.
    """

    height_ft: float = 29.0
    bottom_height_ft: float = 0.5
    offset_m: float = 0.10
    radius_m: float = 0.015
    segments: int = 91
    conductivity_s_m: float = 5e4
    x_offset_m: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "height_ft",
            "bottom_height_ft",
            "radius_m",
            "conductivity_s_m",
        ):
            _positive(name, getattr(self, name))
        if not all(math.isfinite(value) for value in (self.offset_m, self.x_offset_m)):
            raise ValueError("Mast offsets must be finite")
        _segments("Mast segments", self.segments)

    @property
    def top_height_ft(self) -> float:
        return self.bottom_height_ft + self.height_ft


def rigid_doublet_wires(
    geometry: RigidDoublet, mast: FloatingMast | None = None
) -> tuple[Wire, ...]:
    """Return left arm, source bridge, right arm, and optional floating mast.

    Arms have tags 1 and 3, the three-segment source bridge tag 2, and the mast
    tag 4. Exciting the middle bridge segment keeps its neighbors collinear;
    the source itself does not lie directly at the whip bends. Geometry lies
    in the x/z plane, with the mast displaced along y by default.
    """

    half_gap = geometry.feed_gap_m / 2.0
    center_z = geometry.feed_height_ft * FT
    tip_z = geometry.tip_height_ft * FT
    tip_x = geometry.span_ft * FT / 2.0
    wires = (
        Wire(
            1,
            geometry.arm_segments,
            (-tip_x, 0.0, tip_z),
            (-half_gap, 0.0, center_z),
            geometry.radius_m,
        ),
        Wire(
            2,
            3,
            (-half_gap, 0.0, center_z),
            (half_gap, 0.0, center_z),
            geometry.radius_m,
        ),
        Wire(
            3,
            geometry.arm_segments,
            (half_gap, 0.0, center_z),
            (tip_x, 0.0, tip_z),
            geometry.radius_m,
        ),
    )
    if mast is None:
        return wires
    mast_wire = Wire(
        4,
        mast.segments,
        (mast.x_offset_m, mast.offset_m, mast.bottom_height_ft * FT),
        (mast.x_offset_m, mast.offset_m, mast.top_height_ft * FT),
        mast.radius_m,
    )
    for wire in wires:
        if _distance_to_mast(wire, mast_wire) <= wire.radius_m + mast.radius_m:
            raise ValueError("Floating mast must not touch or intersect the doublet")
    return (*wires, mast_wire)


def rigid_doublet_deck(
    *,
    title: str,
    geometry: RigidDoublet,
    frequency_mhz: float,
    conductivity_s_m: float,
    epsilon_r: float,
    ground_conductivity_s_m: float,
    mast: FloatingMast | None = None,
    pattern: bool = False,
) -> str:
    """Build a balanced feedpoint NEC deck, without a transmission line."""

    _positive("Frequency", frequency_mhz)
    _positive("Radiator conductivity", conductivity_s_m)
    return wire_network_deck(
        title=title,
        wires=rigid_doublet_wires(geometry, mast),
        source_tag=2,
        source_segment=2,
        frequency_mhz=frequency_mhz,
        conductivity_s_m=conductivity_s_m,
        epsilon_r=epsilon_r,
        ground_conductivity_s_m=ground_conductivity_s_m,
        wire_conductivity_s_m=None if mast is None else {4: mast.conductivity_s_m},
        pattern=pattern,
    )


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")


def _segments(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _distance_to_mast(wire: Wire, mast: Wire) -> float:
    """Minimum centerline separation from a segment to a vertical mast.

    Splitting at mast endpoint heights gives intervals with quadratic squared
    distance, avoiding a sampled clearance check that could miss a collision.
    """

    start = wire.start
    delta = tuple(end - begin for begin, end in zip(start, wire.end, strict=True))
    bottom, top = mast.start[2], mast.end[2]
    cuts = [0.0, 1.0]
    if delta[2] != 0.0:
        cuts += [
            fraction
            for height in (bottom, top)
            if 0.0 < (fraction := (height - start[2]) / delta[2]) < 1.0
        ]
    cuts.sort()
    distances = []
    for lower, upper in zip(cuts, cuts[1:], strict=False):
        middle_z = start[2] + (lower + upper) / 2.0 * delta[2]
        boundary = bottom if middle_z < bottom else top if middle_z > top else None
        displacement = (
            start[0] - mast.start[0],
            start[1] - mast.start[1],
            0.0 if boundary is None else start[2] - boundary,
        )
        direction = (delta[0], delta[1], 0.0 if boundary is None else delta[2])
        square = sum(value * value for value in direction)
        fraction = (
            lower
            if square == 0.0
            else -sum(
                value * step
                for value, step in zip(displacement, direction, strict=True)
            )
            / square
        )
        fraction = min(upper, max(lower, fraction))
        distances.append(
            math.sqrt(
                sum(
                    (value + fraction * step) ** 2
                    for value, step in zip(displacement, direction, strict=True)
                )
            )
        )
    return min(distances)
