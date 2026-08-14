"""Small, reproducible NEC-2 deck generator/runner for portable wire studies."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import hashlib
from dataclasses import dataclass
from pathlib import Path

FT = 0.3048
FLOAT = r"[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?"
FREQUENCY_RE = re.compile(rf"FREQUENCY\s*:\s*({FLOAT})\s*MHz", re.I)
EFFICIENCY_RE = re.compile(rf"EFFICIENCY\s*=\s*({FLOAT})\s*Percent", re.I)
INPUT_RE = re.compile(
    rf"^\s*\d+\s+\d+\s+"
    rf"{FLOAT}\s+{FLOAT}\s+{FLOAT}\s+{FLOAT}\s+"
    rf"({FLOAT})\s+({FLOAT})\s+{FLOAT}\s+{FLOAT}\s+{FLOAT}\s*$",
    re.M,
)
PATTERN_RE = re.compile(
    rf"^\s*({FLOAT})\s+({FLOAT})\s+{FLOAT}\s+{FLOAT}\s+({FLOAT})\s+"
    rf"{FLOAT}\s+{FLOAT}\s+\S+\s+.*$",
    re.M,
)


@dataclass(frozen=True)
class NecResult:
    frequency_mhz: float
    impedance_ohm: complex
    efficiency: float | None
    pattern: tuple[tuple[float, float, float], ...] = ()  # elevation, azimuth, dBi


@dataclass(frozen=True)
class InvertedV:
    center_height_ft: float
    end_height_ft: float | None = None
    apex_angle_deg: float | None = None

    def endpoints(self, total_length_ft: float) -> tuple[float, float]:
        half = total_length_ft / 2.0
        if self.end_height_ft is not None:
            drop = self.center_height_ft - self.end_height_ft
            if drop < 0 or drop >= half:
                raise ValueError("Invalid fixed-height inverted-V geometry")
            horizontal = math.sqrt(half * half - drop * drop)
            return horizontal, self.end_height_ft
        if self.apex_angle_deg is None:
            raise ValueError("Geometry needs end height or apex angle")
        horizontal = half * math.sin(math.radians(self.apex_angle_deg / 2.0))
        end_height = self.center_height_ft - half * math.cos(
            math.radians(self.apex_angle_deg / 2.0)
        )
        if end_height <= 0:
            raise ValueError("Inverted-V end is at or below ground")
        return horizontal, end_height

    def included_angle_deg(self, total_length_ft: float) -> float:
        horizontal, _ = self.endpoints(total_length_ft)
        return math.degrees(2.0 * math.asin(horizontal / (total_length_ft / 2.0)))


@dataclass(frozen=True)
class Wire:
    """One straight NEC wire, with coordinates in meters."""

    tag: int
    segments: int
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    radius_m: float


@dataclass(frozen=True)
class SeriesLoad:
    """A lumped series impedance applied to one wire segment."""

    tag: int
    segment: int
    impedance_ohm: complex


def find_nec2c(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        path = Path(explicit)
        if path.is_file():
            return path
        found = shutil.which(str(explicit))
    else:
        found = shutil.which("nec2c")
    if not found:
        raise FileNotFoundError("nec2c not found; install the nec2c package")
    return Path(found)


def doublet_deck(
    *,
    title: str,
    total_length_ft: float,
    geometry: InvertedV,
    frequency_mhz: float,
    radius_m: float,
    conductivity_s_m: float,
    epsilon_r: float,
    ground_conductivity_s_m: float,
    pattern: bool = False,
) -> str:
    horizontal_ft, end_height_ft = geometry.endpoints(total_length_ft)
    x = horizontal_ft * FT
    z_end = end_height_ft * FT
    z_center = geometry.center_height_ft * FT
    gap = 0.02
    cards = _header(title)
    cards += [
        _gw(1, 61, -x, 0, z_end, -gap / 2, 0, z_center, radius_m),
        _gw(2, 1, -gap / 2, 0, z_center, gap / 2, 0, z_center, radius_m),
        _gw(3, 61, gap / 2, 0, z_center, x, 0, z_end, radius_m),
        "GE 0",
        "EK 0",
        f"LD 5 0 0 0 {conductivity_s_m:.9e} 0 0",
        f"GN 2 0 0 0 {epsilon_r:.6f} {ground_conductivity_s_m:.9f}",
        f"FR 0 1 0 0 {frequency_mhz:.9f} 0",
        "EX 0 2 1 0 1.0 0.0",
        "PT -1",
    ]
    cards += _execute(pattern)
    return "\n".join(cards) + "\n"


def direct_wire_deck(
    *,
    title: str,
    radiator_ft: float,
    counterpoise_ft: float,
    feed_height_ft: float,
    support_height_ft: float,
    counterpoise_height_ft: float,
    counterpoise_azimuth_deg: float,
    frequency_mhz: float,
    radius_m: float,
    conductivity_s_m: float,
    epsilon_r: float,
    ground_conductivity_s_m: float,
    pattern: bool = False,
) -> str:
    rise = support_height_ft - feed_height_ft
    if rise <= 0 or rise >= radiator_ft:
        raise ValueError("Direct radiator cannot reach requested support height")
    run = math.sqrt(radiator_ft * radiator_ft - rise * rise)
    gap = 0.02
    feed_z = feed_height_ft * FT
    counterpoise_rise = counterpoise_height_ft - feed_height_ft
    if abs(counterpoise_rise) >= counterpoise_ft:
        raise ValueError("Counterpoise cannot reach requested endpoint height")
    counterpoise_run = math.sqrt(
        counterpoise_ft * counterpoise_ft - counterpoise_rise * counterpoise_rise
    )
    counterpoise_angle = math.radians(counterpoise_azimuth_deg)
    counterpoise_x = -gap / 2 + counterpoise_run * FT * math.cos(
        counterpoise_angle
    )
    counterpoise_y = counterpoise_run * FT * math.sin(counterpoise_angle)
    cards = _header(title)
    cards += [
        _gw(
            1,
            41,
            counterpoise_x,
            counterpoise_y,
            counterpoise_height_ft * FT,
            -gap / 2,
            0,
            feed_z,
            radius_m,
        ),
        _gw(2, 1, -gap / 2, 0, feed_z, gap / 2, 0, feed_z, radius_m),
        _gw(
            3,
            61,
            gap / 2,
            0,
            feed_z,
            run * FT,
            0,
            support_height_ft * FT,
            radius_m,
        ),
        "GE 0",
        "EK 0",
        f"LD 5 0 0 0 {conductivity_s_m:.9e} 0 0",
        f"GN 2 0 0 0 {epsilon_r:.6f} {ground_conductivity_s_m:.9f}",
        f"FR 0 1 0 0 {frequency_mhz:.9f} 0",
        "EX 0 2 1 0 1.0 0.0",
        "PT -1",
    ]
    cards += _execute(pattern)
    return "\n".join(cards) + "\n"


def wire_network_deck(
    *,
    title: str,
    wires: tuple[Wire, ...],
    source_tag: int,
    source_segment: int,
    frequency_mhz: float,
    conductivity_s_m: float,
    epsilon_r: float,
    ground_conductivity_s_m: float,
    loads: tuple[SeriesLoad, ...] = (),
    pattern: bool = False,
) -> str:
    """Create a NEC deck for an arbitrary connected passive wire network."""

    if not wires:
        raise ValueError("At least one wire is required")
    if len({wire.tag for wire in wires}) != len(wires):
        raise ValueError("Wire tags must be unique")
    tags = {wire.tag: wire for wire in wires}
    if source_tag not in tags or not 1 <= source_segment <= tags[source_tag].segments:
        raise ValueError("Source must reference an existing wire segment")
    for load in loads:
        if load.tag not in tags or not 1 <= load.segment <= tags[load.tag].segments:
            raise ValueError("Load must reference an existing wire segment")
        if load.impedance_ohm.real < 0:
            raise ValueError("A passive series load cannot have negative resistance")

    cards = _header(title)
    cards += [
        _gw(
            wire.tag,
            wire.segments,
            *wire.start,
            *wire.end,
            wire.radius_m,
        )
        for wire in wires
    ]
    cards += [
        "GE 0",
        "EK 0",
        f"LD 5 0 0 0 {conductivity_s_m:.9e} 0 0",
    ]
    cards += [
        "LD 4 "
        f"{load.tag} {load.segment} {load.segment} "
        f"{load.impedance_ohm.real:.9e} {load.impedance_ohm.imag:.9e} 0"
        for load in loads
    ]
    cards += [
        f"GN 2 0 0 0 {epsilon_r:.6f} {ground_conductivity_s_m:.9f}",
        f"FR 0 1 0 0 {frequency_mhz:.9f} 0",
        f"EX 0 {source_tag} {source_segment} 0 1.0 0.0",
        "PT -1",
    ]
    cards += _execute(pattern)
    return "\n".join(cards) + "\n"


def asymmetric_inverted_v_deck(
    *,
    title: str,
    total_length_ft: float,
    feed_fraction: float,
    center_height_ft: float,
    apex_angle_deg: float,
    frequency_mhz: float,
    radius_m: float,
    conductivity_s_m: float,
    epsilon_r: float,
    ground_conductivity_s_m: float,
    pattern: bool = False,
) -> str:
    """Create an OCFD through near-end-fed inverted-V deck."""

    if total_length_ft <= 0 or not 0 < feed_fraction < 1:
        raise ValueError("Length must be positive and feed fraction inside the wire")
    left_ft = total_length_ft * feed_fraction
    right_ft = total_length_ft - left_ft
    half_angle = math.radians(apex_angle_deg / 2.0)
    gap = 0.02
    center_z = center_height_ft * FT

    def endpoint(length_ft: float, direction: float) -> tuple[float, float, float]:
        horizontal = length_ft * FT * math.sin(half_angle)
        z = center_z - length_ft * FT * math.cos(half_angle)
        if z <= 0:
            raise ValueError("Asymmetric dipole endpoint is at or below ground")
        return direction * (horizontal + gap / 2.0), 0.0, z

    wires = (
        Wire(
            1,
            _odd_segments(left_ft, total_length_ft),
            endpoint(left_ft, -1),
            (-gap / 2, 0, center_z),
            radius_m,
        ),
        Wire(
            2,
            1,
            (-gap / 2, 0, center_z),
            (gap / 2, 0, center_z),
            radius_m,
        ),
        Wire(
            3,
            _odd_segments(right_ft, total_length_ft),
            (gap / 2, 0, center_z),
            endpoint(right_ft, 1),
            radius_m,
        ),
    )
    return wire_network_deck(
        title=title,
        wires=wires,
        source_tag=2,
        source_segment=1,
        frequency_mhz=frequency_mhz,
        conductivity_s_m=conductivity_s_m,
        epsilon_r=epsilon_r,
        ground_conductivity_s_m=ground_conductivity_s_m,
        pattern=pattern,
    )


def fan_dipole_deck(
    *,
    title: str,
    total_lengths_ft: tuple[float, ...],
    azimuths_deg: tuple[float, ...],
    center_height_ft: float,
    apex_angle_deg: float,
    frequency_mhz: float,
    radius_m: float,
    conductivity_s_m: float,
    epsilon_r: float,
    ground_conductivity_s_m: float,
    pattern: bool = False,
) -> str:
    """Create a common-feed fan inverted-V deck."""

    if not total_lengths_ft or len(total_lengths_ft) != len(azimuths_deg):
        raise ValueError("Fan lengths and azimuths must be non-empty and aligned")
    gap = 0.02
    center_z = center_height_ft * FT
    half_angle = math.radians(apex_angle_deg / 2.0)
    wires: list[Wire] = [
        Wire(1, 1, (-gap / 2, 0, center_z), (gap / 2, 0, center_z), radius_m)
    ]
    tag = 2
    for length_ft, azimuth_deg in zip(
        total_lengths_ft, azimuths_deg, strict=True
    ):
        half_ft = length_ft / 2.0
        horizontal = half_ft * FT * math.sin(half_angle)
        z = center_z - half_ft * FT * math.cos(half_angle)
        if z <= 0:
            raise ValueError("Fan dipole endpoint is at or below ground")
        angle = math.radians(azimuth_deg)
        offset = (horizontal * math.cos(angle), horizontal * math.sin(angle))
        segments = _odd_segments(half_ft, max(total_lengths_ft) / 2.0)
        wires.extend(
            (
                Wire(
                    tag,
                    segments,
                    (-offset[0], -offset[1], z),
                    (-gap / 2, 0, center_z),
                    radius_m,
                ),
                Wire(
                    tag + 1,
                    segments,
                    (gap / 2, 0, center_z),
                    (offset[0], offset[1], z),
                    radius_m,
                ),
            )
        )
        tag += 2
    return wire_network_deck(
        title=title,
        wires=tuple(wires),
        source_tag=1,
        source_segment=1,
        frequency_mhz=frequency_mhz,
        conductivity_s_m=conductivity_s_m,
        epsilon_r=epsilon_r,
        ground_conductivity_s_m=ground_conductivity_s_m,
        pattern=pattern,
    )


def radial_vertical_deck(
    *,
    title: str,
    radiator_ft: float,
    radial_ft: float,
    radial_count: int,
    feed_height_ft: float,
    radial_end_height_ft: float,
    frequency_mhz: float,
    radius_m: float,
    conductivity_s_m: float,
    epsilon_r: float,
    ground_conductivity_s_m: float,
    pattern: bool = False,
) -> str:
    """Create a vertical/Rybakov-like radiator with explicit elevated radials."""

    if radiator_ft <= 0 or radial_ft <= 0 or radial_count < 1:
        raise ValueError("Vertical dimensions and radial count must be positive")
    gap = 0.02
    feed_z = feed_height_ft * FT
    radial_z = radial_end_height_ft * FT
    radial_drop = feed_z - radial_z
    if abs(radial_drop) >= radial_ft * FT:
        raise ValueError("Radial cannot reach the requested endpoint height")
    radial_run = math.sqrt((radial_ft * FT) ** 2 - radial_drop**2)
    wires: list[Wire] = [
        Wire(1, 1, (0, 0, feed_z), (0, 0, feed_z + gap), radius_m),
        Wire(
            2,
            61,
            (0, 0, feed_z + gap),
            (0, 0, feed_z + gap + radiator_ft * FT),
            radius_m,
        ),
    ]
    for index in range(radial_count):
        angle = 2.0 * math.pi * index / radial_count
        wires.append(
            Wire(
                3 + index,
                31,
                (0, 0, feed_z),
                (
                    radial_run * math.cos(angle),
                    radial_run * math.sin(angle),
                    radial_z,
                ),
                radius_m,
            )
        )
    return wire_network_deck(
        title=title,
        wires=tuple(wires),
        source_tag=1,
        source_segment=1,
        frequency_mhz=frequency_mhz,
        conductivity_s_m=conductivity_s_m,
        epsilon_r=epsilon_r,
        ground_conductivity_s_m=ground_conductivity_s_m,
        pattern=pattern,
    )


def loaded_inverted_v_deck(
    *,
    title: str,
    total_length_ft: float,
    loads_from_center_ft: tuple[tuple[float, complex], ...],
    geometry: InvertedV,
    frequency_mhz: float,
    radius_m: float,
    conductivity_s_m: float,
    epsilon_r: float,
    ground_conductivity_s_m: float,
    pattern: bool = False,
) -> str:
    """Create a symmetric dipole with paired series coils or traps."""

    half_ft = total_length_ft / 2.0
    horizontal_ft, end_height_ft = geometry.endpoints(total_length_ft)
    gap = 0.02
    center_z = geometry.center_height_ft * FT
    wires = (
        Wire(
            1,
            61,
            (-horizontal_ft * FT, 0, end_height_ft * FT),
            (-gap / 2, 0, center_z),
            radius_m,
        ),
        Wire(2, 1, (-gap / 2, 0, center_z), (gap / 2, 0, center_z), radius_m),
        Wire(
            3,
            61,
            (gap / 2, 0, center_z),
            (horizontal_ft * FT, 0, end_height_ft * FT),
            radius_m,
        ),
    )
    loads: list[SeriesLoad] = []
    for distance_ft, impedance in loads_from_center_ft:
        if not 0 < distance_ft < half_ft:
            raise ValueError("A paired load must lie inside each dipole arm")
        offset = max(1, min(60, round(61 * distance_ft / half_ft)))
        loads.extend(
            (
                SeriesLoad(1, 62 - offset, impedance),
                SeriesLoad(3, offset, impedance),
            )
        )
    return wire_network_deck(
        title=title,
        wires=wires,
        source_tag=2,
        source_segment=1,
        frequency_mhz=frequency_mhz,
        conductivity_s_m=conductivity_s_m,
        epsilon_r=epsilon_r,
        ground_conductivity_s_m=ground_conductivity_s_m,
        loads=tuple(loads),
        pattern=pattern,
    )


def _odd_segments(length: float, reference_length: float) -> int:
    segments = max(3, round(61 * length / reference_length))
    return segments if segments % 2 else segments + 1


def run(
    deck: str,
    work_dir: Path,
    stem: str,
    nec2c: str | Path | None = None,
) -> tuple[NecResult, Path, Path]:
    work_dir.mkdir(parents=True, exist_ok=True)
    deck_path = work_dir / f"{stem}.nec"
    deck_path.write_text(deck, encoding="utf-8")
    executable = find_nec2c(nec2c)
    completed = subprocess.run(
        [str(executable), "-i", str(deck_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output_path = deck_path.with_suffix(".out")
    if completed.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            "nec2c failed "
            f"({completed.returncode})\nstdout:\n{completed.stdout}"
            f"\nstderr:\n{completed.stderr}"
        )
    return (
        parse(output_path.read_text(encoding="utf-8", errors="replace")),
        deck_path,
        output_path,
    )


def run_cached(
    deck: str,
    cache_dir: Path,
    nec2c: str | Path | None = None,
) -> tuple[NecResult, Path, Path, bool]:
    """Run one normalized deck once per exact solver binary and deck content."""

    executable = find_nec2c(nec2c)
    solver_digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    normalized_deck = deck.replace("\r\n", "\n")
    key = hashlib.sha256((solver_digest + "\0" + normalized_deck).encode()).hexdigest()
    # nec2c 1.3 retains a short legacy filename buffer. A 64-character SHA
    # causes a hard failure, so use a collision-resistant 64-bit stem and keep
    # the exact deck content beside the output for verification.
    stem = key[:16]
    deck_path = cache_dir / f"{stem}.nec"
    output_path = cache_dir / f"{stem}.out"
    if (
        deck_path.is_file()
        and output_path.is_file()
        and deck_path.read_text(encoding="utf-8") == normalized_deck
    ):
        result = parse(output_path.read_text(encoding="utf-8", errors="replace"))
        return result, deck_path, output_path, True
    result, deck_path, output_path = run(
        normalized_deck, cache_dir, stem, executable
    )
    return result, deck_path, output_path, False


def parse(text: str) -> NecResult:
    frequency = FREQUENCY_RE.search(text)
    impedance = INPUT_RE.search(text)
    if not frequency or not impedance:
        raise ValueError("Could not parse NEC frequency/input impedance")
    efficiency_match = EFFICIENCY_RE.search(text)
    points = []
    pattern_text = (
        text.split("RADIATION PATTERNS", 1)[1] if "RADIATION PATTERNS" in text else ""
    )
    for match in PATTERN_RE.finditer(pattern_text):
        theta = float(match.group(1))
        phi = float(match.group(2))
        points.append((90.0 - theta, phi, float(match.group(3))))
    return NecResult(
        frequency_mhz=float(frequency.group(1)),
        impedance_ohm=complex(float(impedance.group(1)), float(impedance.group(2))),
        efficiency=None
        if not efficiency_match
        else float(efficiency_match.group(1)) / 100.0,
        pattern=tuple(points),
    )


def _header(title: str) -> list[str]:
    clean = " ".join(title.split())[:70]
    return [f"CM {clean}", "CE"]


def _gw(
    tag: int,
    segments: int,
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
    radius: float,
) -> str:
    return (
        f"GW {tag} {segments} {x1:.9f} {y1:.9f} {z1:.9f} "
        f"{x2:.9f} {y2:.9f} {z2:.9f} {radius:.9f}"
    )


def _execute(pattern: bool) -> list[str]:
    if not pattern:
        return ["XQ 0", "EN"]
    return ["RP 0 19 72 1001 0 0 5 5 1000 0", "EN"]
