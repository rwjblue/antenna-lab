"""Small, reproducible NEC-2 deck generator/runner for portable wire studies."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
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
    counterpoise_angle = math.radians(counterpoise_azimuth_deg)
    counterpoise_x = -gap / 2 + counterpoise_ft * FT * math.cos(
        counterpoise_angle
    )
    counterpoise_y = counterpoise_ft * FT * math.sin(counterpoise_angle)
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
