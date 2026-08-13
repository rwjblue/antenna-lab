"""Loss-aware antenna-tuner circuit models.

The switched-L implementation is exact for the documented network topology and
component-bank values supplied by a profile. Component Q and relay resistance
remain explicit sensitivity inputs unless measured values are available.
"""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import numpy as np
from scipy.optimize import minimize

from antenna_lab.kh1_nec import (
    DIRECT_CANDIDATES,
    DIRECT_DEPLOYMENTS,
    EXTENDED_BANDS,
    GROUNDS,
    _direct_case,
    _manifest,
    _quantile,
    _sha256,
    _version,
    _write_csv,
    _write_json,
)
from antenna_lab.nec import find_nec2c

Topology = Literal["load_shunt", "source_shunt", "bypass"]
Objective = Literal["best_swr", "lowest_loss_under_target"]

ATU_DIRECT_CONDUCTIVITIES = (
    ("ccs_mid", 15_000_000.0),
    ("copper", 58_000_000.0),
)


@dataclass(frozen=True)
class LossEnvelope:
    id: str
    inductor_q: float
    capacitor_q: float
    relay_contact_ohm: float
    fixed_series_ohm: float = 0.02


LOSS_ENVELOPES = (
    LossEnvelope("conservative", 35.0, 800.0, 0.050, 0.040),
    LossEnvelope("nominal", 70.0, 2_000.0, 0.025, 0.020),
    LossEnvelope("optimistic", 120.0, 5_000.0, 0.012, 0.010),
)


@dataclass(frozen=True)
class SwitchedLNetworkProfile:
    id: str
    label: str
    inductors_uH: tuple[float, ...]
    capacitors_pF: tuple[float, ...]
    supported_min_mhz: float
    supported_max_mhz: float
    provenance: str
    component_status: Literal["published", "inferred", "range-fit"]
    allow_source_shunt: bool = True
    allow_load_shunt: bool = True
    allow_bypass: bool = True
    bypass_swr: float = 2.5
    topology_relay_count: int = 1

    @property
    def series_relay_count(self) -> int:
        # Each binary inductor cell contributes one RF-path contact whether the
        # cell is inserted or bypassed. The topology relay is additional.
        return len(self.inductors_uH) + self.topology_relay_count

    def supports(self, frequency_hz: float) -> bool:
        frequency_mhz = frequency_hz / 1e6
        return self.supported_min_mhz <= frequency_mhz <= self.supported_max_mhz


PROFILES: dict[str, SwitchedLNetworkProfile] = {
    "kxat2": SwitchedLNetworkProfile(
        id="kxat2",
        label="Elecraft KXAT2 (KX2)",
        inductors_uH=(0.063, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0),
        capacitors_pF=(10.0, 18.0, 39.0, 82.0, 164.0, 330.0, 680.0),
        supported_min_mhz=1.8,
        supported_max_mhz=30.0,
        provenance="Elecraft KX2 schematic E740324 Rev A, KXAT2 page",
        component_status="published",
    ),
    "kxat3": SwitchedLNetworkProfile(
        id="kxat3",
        label="Elecraft KXAT3 (KX3)",
        inductors_uH=(0.06, 0.12, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0),
        capacitors_pF=(10.0, 18.0, 39.0, 82.0, 164.0, 330.0, 680.0, 1360.0),
        supported_min_mhz=1.8,
        supported_max_mhz=54.0,
        provenance="Elecraft KX3 schematic, KXAT3 page",
        component_status="published",
    ),
    "khatu1": SwitchedLNetworkProfile(
        id="khatu1",
        label="Elecraft KHATU1 (KH1; range-calibrated inference)",
        inductors_uH=(0.75, 1.5, 3.0, 6.0),
        capacitors_pF=(47.0, 100.0, 220.0),
        supported_min_mhz=7.0,
        supported_max_mhz=21.45,
        provenance=(
            "KH1 manual documents series-L/shunt-C operation, L/C/Z display, "
            "and eight ATU relays; public bank values were not found"
        ),
        component_status="inferred",
    ),
    "z11pro2": SwitchedLNetworkProfile(
        id="z11pro2",
        label="LDG Z-11Pro II (specification range-fit)",
        inductors_uH=(0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24),
        capacitors_pF=(15.0, 30.0, 60.0, 120.0, 240.0, 480.0, 960.0, 1920.0),
        supported_min_mhz=1.8,
        supported_max_mhz=54.0,
        provenance=(
            "Z-11Pro II manual publishes switched-L/high-low-Z architecture and "
            "matching range, but not current-production bank values"
        ),
        component_status="range-fit",
    ),
}


@dataclass(frozen=True)
class AtuSolution:
    profile: str
    loss_envelope: str
    objective: str
    frequency_hz: float
    load_resistance_ohm: float
    load_reactance_ohm: float
    supported: bool
    topology: str
    l_mask: int
    c_mask: int
    inductance_uH: float
    capacitance_pF: float
    input_resistance_ohm: float
    input_reactance_ohm: float
    input_swr: float
    accepted_power_w: float
    load_power_w: float
    tuner_dissipation_w: float
    tuner_efficiency: float
    transducer_efficiency: float
    tuner_loss_db: float
    total_loss_db: float
    inductor_loss_w: float
    capacitor_loss_w: float
    relay_and_fixed_loss_w: float


@dataclass(frozen=True)
class _StateTable:
    mask: np.ndarray
    value: np.ndarray
    resistance: np.ndarray
    selected_count: np.ndarray


def _binary_states(values: tuple[float, ...], resistance: np.ndarray) -> _StateTable:
    masks = np.arange(1 << len(values), dtype=np.int64)
    bits = ((masks[:, None] >> np.arange(len(values))) & 1).astype(float)
    return _StateTable(
        mask=masks,
        value=bits @ np.asarray(values, dtype=float),
        resistance=bits @ resistance,
        selected_count=np.sum(bits, axis=1),
    )


def _capacitor_states(
    capacitors_pF: tuple[float, ...],
    omega: float,
    loss: LossEnvelope,
) -> tuple[_StateTable, np.ndarray]:
    values_f = np.asarray(capacitors_pF, dtype=float) * 1e-12
    esr = 1.0 / (omega * values_f * loss.capacitor_q)
    branch_r = esr + loss.relay_contact_ohm
    branch_z = branch_r - 1j / (omega * values_f)
    branch_y = 1.0 / branch_z
    masks = np.arange(1 << len(capacitors_pF), dtype=np.int64)
    bits = ((masks[:, None] >> np.arange(len(capacitors_pF))) & 1).astype(float)
    admittance = bits @ branch_y
    table = _StateTable(
        mask=masks,
        value=bits @ np.asarray(capacitors_pF, dtype=float),
        resistance=bits @ branch_r,
        selected_count=np.sum(bits, axis=1),
    )
    return table, admittance


def _swr(z: np.ndarray | complex, reference_ohm: float = 50.0) -> np.ndarray:
    z_array = np.asarray(z, dtype=complex)
    gamma = (z_array - reference_ohm) / (z_array + reference_ohm)
    magnitude = np.minimum(np.abs(gamma), 1.0 - 1e-12)
    return (1.0 + magnitude) / (1.0 - magnitude)


def _db_loss(efficiency: float) -> float:
    if not math.isfinite(efficiency) or efficiency <= 0:
        return math.inf
    return -10.0 * math.log10(min(efficiency, 1.0))


def _solution_for_state(
    profile: SwitchedLNetworkProfile,
    load: complex,
    frequency_hz: float,
    loss: LossEnvelope,
    topology: Topology,
    l_mask: int,
    c_mask: int,
    *,
    available_power_w: float = 1.0,
    objective: str,
) -> AtuSolution:
    if topology == "bypass":
        zin = load
        accepted = available_power_w * max(
            0.0, 1.0 - abs((zin - 50.0) / (zin + 50.0)) ** 2
        )
        return AtuSolution(
            profile.id,
            loss.id,
            objective,
            frequency_hz,
            load.real,
            load.imag,
            profile.supports(frequency_hz),
            topology,
            0,
            0,
            0.0,
            0.0,
            zin.real,
            zin.imag,
            float(_swr(zin)),
            accepted,
            accepted,
            0.0,
            1.0,
            accepted / available_power_w,
            0.0,
            _db_loss(accepted / available_power_w),
            0.0,
            0.0,
            0.0,
        )

    omega = 2.0 * math.pi * frequency_hz
    l_values = np.asarray(profile.inductors_uH) * 1e-6
    l_bits = ((l_mask >> np.arange(len(l_values))) & 1).astype(float)
    total_l = float(l_bits @ l_values)
    inductor_r = float(l_bits @ (omega * l_values / loss.inductor_q))
    series_contact_r = (
        profile.series_relay_count * loss.relay_contact_ohm
        + loss.fixed_series_ohm
    )
    z_series = complex(inductor_r + series_contact_r, omega * total_l)

    c_values = np.asarray(profile.capacitors_pF) * 1e-12
    c_bits = ((c_mask >> np.arange(len(c_values))) & 1).astype(float)
    selected_c = c_values[c_bits.astype(bool)]
    if len(selected_c):
        c_branch_r = (
            1.0 / (omega * selected_c * loss.capacitor_q)
            + loss.relay_contact_ohm
        )
        c_branch_z = c_branch_r - 1j / (omega * selected_c)
        y_c = np.sum(1.0 / c_branch_z)
    else:
        c_branch_r = np.asarray([], dtype=float)
        c_branch_z = np.asarray([], dtype=complex)
        y_c = 0j

    if topology == "load_shunt":
        z_parallel = 1.0 / (1.0 / load + y_c)
        zin = z_series + z_parallel
    else:
        z_branch = z_series + load
        zin = 1.0 / (1.0 / z_branch + y_c)

    source_r = 50.0
    source_v = 2.0 * math.sqrt(available_power_w * source_r)
    input_current = source_v / (source_r + zin)
    input_voltage = input_current * zin
    accepted = max(0.0, float((input_voltage * input_current.conjugate()).real))

    if topology == "load_shunt":
        series_current = input_current
        cap_voltage = input_voltage - series_current * z_series
        load_voltage = cap_voltage
    else:
        cap_voltage = input_voltage
        series_current = input_voltage / (z_series + load)
        load_voltage = series_current * load

    load_current = load_voltage / load
    load_power = max(0.0, float((load_voltage * load_current.conjugate()).real))
    inductor_loss = abs(series_current) ** 2 * inductor_r
    relay_fixed_loss = abs(series_current) ** 2 * series_contact_r
    capacitor_loss = 0.0
    if len(selected_c):
        branch_currents = cap_voltage / c_branch_z
        capacitor_loss = float(np.sum(np.abs(branch_currents) ** 2 * c_branch_r))
    tuner_dissipation = max(0.0, accepted - load_power)
    modeled_breakdown = inductor_loss + relay_fixed_loss + capacitor_loss
    # Keep the power-balance value authoritative; breakdown can differ by tiny
    # numerical roundoff.
    if modeled_breakdown > 0 and tuner_dissipation > 0:
        scale = tuner_dissipation / modeled_breakdown
        inductor_loss *= scale
        relay_fixed_loss *= scale
        capacitor_loss *= scale

    tuner_efficiency = load_power / accepted if accepted > 0 else 0.0
    transducer_efficiency = load_power / available_power_w
    return AtuSolution(
        profile.id,
        loss.id,
        objective,
        frequency_hz,
        load.real,
        load.imag,
        profile.supports(frequency_hz),
        topology,
        int(l_mask),
        int(c_mask),
        total_l * 1e6,
        float(np.sum(selected_c) * 1e12),
        zin.real,
        zin.imag,
        float(_swr(zin)),
        accepted,
        load_power,
        tuner_dissipation,
        tuner_efficiency,
        transducer_efficiency,
        _db_loss(tuner_efficiency),
        _db_loss(transducer_efficiency),
        inductor_loss,
        capacitor_loss,
        relay_fixed_loss,
    )


@lru_cache(maxsize=256)
def _switched_state_tables(
    profile: SwitchedLNetworkProfile,
    frequency_hz: float,
    loss: LossEnvelope,
) -> tuple[_StateTable, _StateTable, np.ndarray, float]:
    """Return frequency-dependent state tables shared by many load cases."""
    omega = 2.0 * math.pi * frequency_hz
    l_h = np.asarray(profile.inductors_uH, dtype=float) * 1e-6
    l_resistance = omega * l_h / loss.inductor_q
    l_states = _binary_states(tuple(l_h), l_resistance)
    c_states, c_admittance = _capacitor_states(
        profile.capacitors_pF, omega, loss
    )
    series_contact_r = (
        profile.series_relay_count * loss.relay_contact_ohm
        + loss.fixed_series_ohm
    )
    return l_states, c_states, c_admittance, series_contact_r


def solve_switched_l_network(
    profile: SwitchedLNetworkProfile,
    load: complex,
    frequency_hz: float,
    loss: LossEnvelope,
    *,
    objective: Objective = "best_swr",
    target_swr: float = 1.5,
) -> AtuSolution:
    """Enumerate every discrete L/C/topology state and return one solution."""
    if load.real <= 0:
        raise ValueError("Load resistance must be positive")
    if not profile.supports(frequency_hz):
        return AtuSolution(
            profile.id,
            loss.id,
            objective,
            frequency_hz,
            load.real,
            load.imag,
            False,
            "unsupported",
            0,
            0,
            0.0,
            0.0,
            math.nan,
            math.nan,
            math.inf,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            math.inf,
            math.inf,
            0.0,
            0.0,
            0.0,
        )

    omega = 2.0 * math.pi * frequency_hz
    l_states, c_states, c_admittance, series_contact_r = (
        _switched_state_tables(profile, float(frequency_hz), loss)
    )
    z_series = (
        l_states.resistance
        + series_contact_r
        + 1j * omega * l_states.value
    )[:, None]
    y_c = c_admittance[None, :]

    candidates: list[tuple[Topology, np.ndarray, np.ndarray]] = []
    if profile.allow_load_shunt:
        z_parallel = 1.0 / (1.0 / load + y_c)
        zin = z_series + z_parallel
        load_voltage_ratio = z_parallel / (50.0 + zin)
        candidates.append(("load_shunt", zin, load_voltage_ratio))
    if profile.allow_source_shunt:
        z_branch = z_series + load
        zin = 1.0 / (1.0 / z_branch + y_c)
        input_voltage_ratio = zin / (50.0 + zin)
        load_voltage_ratio = input_voltage_ratio * load / z_branch
        candidates.append(("source_shunt", zin, load_voltage_ratio))

    source_v = 2.0 * math.sqrt(50.0)
    load_conductance = (1.0 / load).real
    best: tuple[float, int, int, Topology] | None = None
    for topology, zin, load_voltage_ratio in candidates:
        swrs = _swr(zin)
        load_power = np.abs(source_v * load_voltage_ratio) ** 2 * load_conductance
        gamma = (zin - 50.0) / (zin + 50.0)
        accepted = np.maximum(0.0, 1.0 - np.abs(gamma) ** 2)
        tuner_eff = np.divide(
            load_power,
            accepted,
            out=np.zeros_like(load_power, dtype=float),
            where=accepted > 1e-15,
        )
        if objective == "lowest_loss_under_target":
            eligible = swrs <= target_swr
            score = np.where(eligible, -tuner_eff, np.inf)
            if not np.any(eligible):
                score = swrs
        else:
            score = swrs
        flat = int(np.nanargmin(score))
        l_index, c_index = np.unravel_index(flat, score.shape)
        candidate_score = float(score[l_index, c_index])
        if best is None or candidate_score < best[0]:
            best = (
                candidate_score,
                int(l_states.mask[l_index]),
                int(c_states.mask[c_index]),
                topology,
            )

    if profile.allow_bypass and float(_swr(load)) <= profile.bypass_swr:
        bypass = _solution_for_state(
            profile,
            load,
            frequency_hz,
            loss,
            "bypass",
            0,
            0,
            objective=objective,
        )
        if best is None or (
            objective == "best_swr" and bypass.input_swr < best[0]
        ):
            return bypass
        if objective == "lowest_loss_under_target" and bypass.input_swr <= target_swr:
            return bypass

    if best is None:
        raise RuntimeError("No tuner topology was enabled")
    _, l_mask, c_mask, topology = best
    return _solution_for_state(
        profile,
        load,
        frequency_hz,
        loss,
        topology,
        l_mask,
        c_mask,
        objective=objective,
    )


@dataclass(frozen=True)
class ZMatchProfile:
    id: str = "zm2"
    label: str = "EMTECH ZM-2 BNC prebuilt coupled Z-match"
    primary_turn_options: tuple[int, ...] = (27, 16, 11)
    secondary_turns: int = 7
    al_nh_per_turn2: float = 11.0
    coupling: float = 0.90
    c1_max_pF: float = 1_032.0
    c2_max_pF: float = 532.0
    supported_min_mhz: float = 3.5
    supported_max_mhz: float = 30.0

    def supports(self, frequency_hz: float) -> bool:
        mhz = frequency_hz / 1e6
        return self.supported_min_mhz <= mhz <= self.supported_max_mhz


ZM2_PROFILE = ZMatchProfile()


def _evaluate_zmatch(
    load: complex,
    frequency_hz: float,
    loss: LossEnvelope,
    turns: int,
    c1_pF: float,
    c2_pF: float,
) -> tuple[complex, float, float]:
    omega = 2.0 * math.pi * frequency_hz
    lp = ZM2_PROFILE.al_nh_per_turn2 * turns**2 * 1e-9
    ls = ZM2_PROFILE.al_nh_per_turn2 * ZM2_PROFILE.secondary_turns**2 * 1e-9
    mutual = ZM2_PROFILE.coupling * math.sqrt(lp * ls)
    rp = omega * lp / loss.inductor_q
    rs = omega * ls / loss.inductor_q
    z_primary = complex(rp, omega * lp)
    z_secondary = complex(rs, omega * ls)
    reflected = (omega * mutual) ** 2 / (z_secondary + load)
    loaded_primary = z_primary + reflected

    c2 = max(c2_pF, 0.1) * 1e-12
    r_c2 = 1.0 / (omega * c2 * loss.capacitor_q)
    z_c2 = complex(r_c2, -1.0 / (omega * c2))
    z_tank = 1.0 / (1.0 / loaded_primary + 1.0 / z_c2)

    c1 = max(c1_pF, 0.1) * 1e-12
    r_c1 = 1.0 / (omega * c1 * loss.capacitor_q)
    z_c1 = complex(r_c1, -1.0 / (omega * c1))
    zin = z_c1 + z_tank + loss.fixed_series_ohm

    source_v = 2.0 * math.sqrt(50.0)
    input_current = source_v / (50.0 + zin)
    tank_voltage = input_current * z_tank
    primary_current = tank_voltage / loaded_primary
    secondary_current = (
        -1j * omega * mutual * primary_current / (z_secondary + load)
    )
    load_power = abs(secondary_current) ** 2 * load.real
    gamma = (zin - 50.0) / (zin + 50.0)
    accepted = max(0.0, 1.0 - abs(gamma) ** 2)
    tuner_efficiency = load_power / accepted if accepted > 1e-15 else 0.0
    return zin, tuner_efficiency, load_power


def solve_zm2(
    load: complex,
    frequency_hz: float,
    loss: LossEnvelope,
    *,
    target_swr: float = 1.5,
) -> dict[str, Any]:
    if not ZM2_PROFILE.supports(frequency_hz):
        return {
            "profile": "zm2",
            "loss_envelope": loss.id,
            "supported": False,
            "frequency_hz": frequency_hz,
        }
    best: dict[str, Any] | None = None
    for turns in ZM2_PROFILE.primary_turn_options:
        c1_grid = np.geomspace(2.0, ZM2_PROFILE.c1_max_pF, 48)
        c2_grid = np.geomspace(2.0, ZM2_PROFILE.c2_max_pF, 48)
        for c1 in c1_grid:
            for c2 in c2_grid:
                zin, efficiency, load_power = _evaluate_zmatch(
                    load, frequency_hz, loss, turns, float(c1), float(c2)
                )
                input_swr = float(_swr(zin))
                score = (
                    0 if input_swr <= target_swr else 1,
                    -efficiency if input_swr <= target_swr else input_swr,
                    input_swr,
                )
                if best is None or score < best["score"]:
                    best = {
                        "score": score,
                        "turns": turns,
                        "c1_pF": float(c1),
                        "c2_pF": float(c2),
                        "zin": zin,
                        "efficiency": efficiency,
                        "load_power": load_power,
                    }
        assert best is not None
        x0 = np.log([best["c1_pF"], best["c2_pF"]])

        def objective(x: np.ndarray) -> float:
            c1, c2 = np.exp(x)
            if c1 > ZM2_PROFILE.c1_max_pF or c2 > ZM2_PROFILE.c2_max_pF:
                return 1e3
            zin, efficiency, _ = _evaluate_zmatch(
                load, frequency_hz, loss, turns, float(c1), float(c2)
            )
            input_swr = float(_swr(zin))
            penalty = max(0.0, input_swr - target_swr) ** 2 * 10.0
            return -efficiency + penalty

        optimized = minimize(objective, x0, method="Nelder-Mead")
        c1, c2 = np.exp(optimized.x)
        if c1 <= ZM2_PROFILE.c1_max_pF and c2 <= ZM2_PROFILE.c2_max_pF:
            zin, efficiency, load_power = _evaluate_zmatch(
                load, frequency_hz, loss, turns, float(c1), float(c2)
            )
            input_swr = float(_swr(zin))
            score = (
                0 if input_swr <= target_swr else 1,
                -efficiency if input_swr <= target_swr else input_swr,
                input_swr,
            )
            if best is None or score < best["score"]:
                best = {
                    "score": score,
                    "turns": turns,
                    "c1_pF": float(c1),
                    "c2_pF": float(c2),
                    "zin": zin,
                    "efficiency": efficiency,
                    "load_power": load_power,
                }
    assert best is not None
    zin = best["zin"]
    return {
        "profile": "zm2",
        "loss_envelope": loss.id,
        "supported": True,
        "frequency_hz": frequency_hz,
        "load_resistance_ohm": load.real,
        "load_reactance_ohm": load.imag,
        "primary_turns": best["turns"],
        "c1_pF": best["c1_pF"],
        "c2_pF": best["c2_pF"],
        "input_resistance_ohm": zin.real,
        "input_reactance_ohm": zin.imag,
        "input_swr": float(_swr(zin)),
        "tuner_efficiency": best["efficiency"],
        "transducer_efficiency": best["load_power"],
        "tuner_loss_db": _db_loss(best["efficiency"]),
        "total_loss_db": _db_loss(best["load_power"]),
        "model_status": (
            "documented EMTECH ZM-2 topology; core loss, coupling, "
            "parasitics, and capacitor law remain sensitivity inputs"
        ),
    }


def _direct_41_17_rows(nec2c: Path, jobs: int) -> list[dict[str, Any]]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    candidate_id = "41r-17c"
    radiator, counterpoise = DIRECT_CANDIDATES[candidate_id]
    cases = [
        (
            candidate_id,
            radiator,
            counterpoise,
            deployment_id,
            deployment,
            ground_id,
            ground,
            conductivity_id,
            conductivity,
            band,
            frequency,
        )
        for deployment_id, deployment in DIRECT_DEPLOYMENTS.items()
        for ground_id, ground in GROUNDS.items()
        for conductivity_id, conductivity in ATU_DIRECT_CONDUCTIVITIES
        for band, frequency, _ in EXTENDED_BANDS
    ]
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="atu-direct-nec-") as temporary:
        work = Path(temporary)
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(_direct_case, *case, nec2c, work): case for case in cases
            }
            for future in as_completed(futures):
                rows.append(future.result())
    return sorted(
        rows,
        key=lambda row: (
            row["deployment"],
            row["ground"],
            row["conductivity"],
            row["frequency_hz"],
        ),
    )


def evaluate_profile_rows(
    profile: SwitchedLNetworkProfile,
    direct_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for antenna in direct_rows:
        load = complex(antenna["resistance_ohm"], antenna["reactance_ohm"])
        for loss in LOSS_ENVELOPES:
            for objective in ("best_swr", "lowest_loss_under_target"):
                solution = solve_switched_l_network(
                    profile,
                    load,
                    antenna["frequency_hz"],
                    loss,
                    objective=objective,
                )
                row = asdict(solution)
                row.update(
                    {
                        "band": antenna["band"],
                        "deployment": antenna["deployment"],
                        "ground": antenna["ground"],
                        "conductivity": antenna["conductivity"],
                        "antenna_nec_efficiency": antenna["nec_efficiency"],
                        "system_transducer_efficiency": (
                            antenna["nec_efficiency"]
                            * solution.transducer_efficiency
                            if antenna["nec_efficiency"] is not None
                            else math.nan
                        ),
                    }
                )
                rows.append(row)
    return rows


def evaluate_zm2_rows(direct_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for antenna in direct_rows:
        load = complex(antenna["resistance_ohm"], antenna["reactance_ohm"])
        for loss in LOSS_ENVELOPES:
            solution = solve_zm2(load, antenna["frequency_hz"], loss)
            solution.update(
                {
                    "band": antenna["band"],
                    "deployment": antenna["deployment"],
                    "ground": antenna["ground"],
                    "conductivity": antenna["conductivity"],
                    "antenna_nec_efficiency": antenna["nec_efficiency"],
                    "system_transducer_efficiency": (
                        antenna["nec_efficiency"]
                        * solution.get("transducer_efficiency", 0.0)
                        if antenna["nec_efficiency"] is not None
                        else math.nan
                    ),
                }
            )
            rows.append(solution)
    return rows


def summarize_atu_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    keys = sorted({(row["profile"], row["band"], row.get("objective", "manual")) for row in rows})
    for profile, band, objective in keys:
        subset = [
            row
            for row in rows
            if row["profile"] == profile
            and row["band"] == band
            and row.get("objective", "manual") == objective
            and row.get("supported", False)
        ]
        if not subset:
            summaries.append(
                {
                    "profile": profile,
                    "band": band,
                    "objective": objective,
                    "supported": False,
                }
            )
            continue
        matched = [row["input_swr"] <= 1.5 for row in subset]
        summaries.append(
            {
                "profile": profile,
                "band": band,
                "objective": objective,
                "supported": True,
                "sample_count": len(subset),
                "match_fraction_swr_1p5": float(np.mean(matched)),
                "input_swr_p50": _quantile([row["input_swr"] for row in subset], 0.5),
                "input_swr_p90": _quantile([row["input_swr"] for row in subset], 0.9),
                "tuner_efficiency_p10": _quantile([row["tuner_efficiency"] for row in subset], 0.1),
                "tuner_efficiency_p50": _quantile([row["tuner_efficiency"] for row in subset], 0.5),
                "tuner_loss_db_p90": _quantile([row["tuner_loss_db"] for row in subset], 0.9),
                "transducer_efficiency_p10": _quantile([row["transducer_efficiency"] for row in subset], 0.1),
                "system_efficiency_p10": _quantile([row["system_transducer_efficiency"] for row in subset], 0.1),
                "system_efficiency_p50": _quantile([row["system_transducer_efficiency"] for row in subset], 0.5),
            }
        )
    return summaries


def _load_direct_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            converted: dict[str, Any] = {}
            for key, value in row.items():
                if value in (None, ""):
                    converted[key] = None
                elif value in {"True", "False"}:
                    converted[key] = value == "True"
                else:
                    try:
                        converted[key] = float(value)
                    except ValueError:
                        converted[key] = value
            rows.append(converted)
    return rows


def _expected_direct_41_17_keys() -> dict[tuple[str, str, str, str], float]:
    return {
        (deployment_id, ground_id, conductivity_id, band): float(frequency)
        for deployment_id in DIRECT_DEPLOYMENTS
        for ground_id in GROUNDS
        for conductivity_id, _ in ATU_DIRECT_CONDUCTIVITIES
        for band, frequency, _ in EXTENDED_BANDS
    }


def _format_key_sample(
    keys: list[tuple[str, str, str, str]], limit: int = 8
) -> str:
    rendered = ["/".join(key) for key in keys[:limit]]
    if len(keys) > limit:
        rendered.append(f"...+{len(keys) - limit}")
    return "[" + ", ".join(rendered) + "]"


def _validate_direct_41_17_ensemble(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Require one exact 41/17 NEC row for every modeled scenario and band."""
    selected = [row for row in rows if row.get("candidate") == "41r-17c"]
    expected = _expected_direct_41_17_keys()
    counts: Counter[tuple[str, str, str, str]] = Counter()
    frequency_mismatches: list[tuple[str, str, str, str]] = []
    dimension_mismatches: list[tuple[str, str, str, str]] = []

    for row in selected:
        try:
            key = (
                str(row["deployment"]),
                str(row["ground"]),
                str(row["conductivity"]),
                str(row["band"]),
            )
            frequency_hz = float(row["frequency_hz"])
            radiator_ft = float(row["radiator_ft"])
            counterpoise_ft = float(row["counterpoise_ft"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                "Malformed 41r-17c direct NEC row; required identity, frequency, "
                "and dimension fields are missing or invalid"
            ) from error
        counts[key] += 1
        if key in expected and not math.isclose(
            frequency_hz, expected[key], rel_tol=0.0, abs_tol=0.5
        ):
            frequency_mismatches.append(key)
        if not (
            math.isclose(radiator_ft, 41.0, rel_tol=0.0, abs_tol=1e-6)
            and math.isclose(
                counterpoise_ft, 17.0, rel_tol=0.0, abs_tol=1e-6
            )
        ):
            dimension_mismatches.append(key)

    actual = set(counts)
    missing = sorted(set(expected) - actual)
    unexpected = sorted(actual - set(expected))
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    frequency_mismatches = sorted(set(frequency_mismatches))
    dimension_mismatches = sorted(set(dimension_mismatches))
    if (
        missing
        or unexpected
        or duplicates
        or frequency_mismatches
        or dimension_mismatches
    ):
        raise ValueError(
            "Incomplete or inconsistent 41r-17c direct NEC ensemble: "
            f"expected {len(expected)} unique rows; found {len(selected)} rows / "
            f"{len(actual)} unique keys; "
            f"missing={_format_key_sample(missing)}; "
            f"unexpected={_format_key_sample(unexpected)}; "
            f"duplicates={_format_key_sample(duplicates)}; "
            "frequency_mismatches="
            f"{_format_key_sample(frequency_mismatches)}; "
            "dimension_mismatches="
            f"{_format_key_sample(dimension_mismatches)}"
        )
    return sorted(
        selected,
        key=lambda row: (
            str(row["deployment"]),
            str(row["ground"]),
            str(row["conductivity"]),
            str(row["band"]),
        ),
    )


ATU_PROFILE_IDS = tuple(PROFILES) + ("zm2",)


def _reset_output_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def run_atu_direct_nec_stage(
    output_dir: Path,
    *,
    nec2c: str | Path | None = None,
    jobs: int = 6,
) -> dict[str, Any]:
    """Generate the shared 41/17 NEC load ensemble once."""
    _reset_output_directory(output_dir)
    executable = find_nec2c(nec2c)
    rows = _direct_41_17_rows(executable, jobs)
    filename = "atu-direct-nec.csv"
    _write_csv(output_dir / filename, rows)
    metadata = {
        "stage": "atu-direct-nec",
        "row_count": len(rows),
        "modeled_bands": [band for band, _, _ in EXTENDED_BANDS],
        "solver": _version(executable),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "output_file": filename,
    }
    _write_json(output_dir / "stage_metadata.json", metadata)
    _manifest(output_dir)
    return metadata


def run_atu_profile_stage(
    output_dir: Path,
    *,
    direct_nec_csv: Path,
    profile_id: str,
) -> dict[str, Any]:
    """Evaluate one tuner profile against the shared NEC load ensemble."""
    if profile_id not in ATU_PROFILE_IDS:
        raise ValueError(
            f"Unknown ATU profile {profile_id!r}; choose from {ATU_PROFILE_IDS}"
        )
    _reset_output_directory(output_dir)
    direct_rows = _validate_direct_41_17_ensemble(
        _load_direct_csv(direct_nec_csv)
    )
    if profile_id == "zm2":
        rows = evaluate_zm2_rows(direct_rows)
    else:
        rows = evaluate_profile_rows(PROFILES[profile_id], direct_rows)
    filename = f"atu-solutions-{profile_id}.csv"
    _write_csv(output_dir / filename, rows)
    metadata = {
        "stage": "atu-profile",
        "profile": profile_id,
        "direct_nec_row_count": len(direct_rows),
        "solution_row_count": len(rows),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "output_file": filename,
    }
    _write_json(output_dir / f"stage_metadata-{profile_id}.json", metadata)
    _manifest(output_dir)
    return metadata


def _find_unique_file(input_dir: Path, pattern: str) -> Path:
    matches = sorted(input_dir.rglob(pattern))
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {pattern!r} below {input_dir}; found {len(matches)}"
        )
    return matches[0]


def _load_solution_files(input_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    found_profiles: set[str] = set()
    for path in sorted(input_dir.rglob("atu-solutions-*.csv")):
        profile_id = path.stem.removeprefix("atu-solutions-")
        if profile_id in found_profiles:
            raise ValueError(f"Duplicate ATU profile artifact: {profile_id}")
        found_profiles.add(profile_id)
        rows.extend(_load_direct_csv(path))
    missing = set(ATU_PROFILE_IDS) - found_profiles
    extra = found_profiles - set(ATU_PROFILE_IDS)
    if missing or extra:
        raise ValueError(
            f"ATU profile artifacts incomplete: missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    return rows


def assemble_atu_loss_study(
    output_dir: Path,
    *,
    input_dir: Path,
) -> dict[str, Any]:
    """Assemble independently computed tuner-profile artifacts."""
    direct_path = _find_unique_file(input_dir, "atu-direct-nec.csv")
    direct_rows = _validate_direct_41_17_ensemble(
        _load_direct_csv(direct_path)
    )
    all_rows = _load_solution_files(input_dir)
    _reset_output_directory(output_dir)
    data_dir = output_dir / "data"
    provenance_dir = output_dir / "provenance"
    data_dir.mkdir()
    provenance_dir.mkdir()

    _write_csv(data_dir / "direct_41r_17c_nec.csv", direct_rows)
    _write_csv(data_dir / "atu_solutions.csv", all_rows)
    summaries = summarize_atu_rows(all_rows)
    _write_csv(data_dir / "atu_summary_by_band.csv", summaries)
    _write_json(
        data_dir / "profiles.json",
        {
            "switched_l": {key: asdict(value) for key, value in PROFILES.items()},
            "zm2": asdict(ZM2_PROFILE),
            "loss_envelopes": [asdict(value) for value in LOSS_ENVELOPES],
        },
    )
    for metadata_path in sorted(input_dir.rglob("stage_metadata*.json")):
        shutil.copy2(metadata_path, provenance_dir / metadata_path.name)

    summary = {
        "antenna": "41 ft radiator / 17 ft explicit counterpoise",
        "modeled_bands": [band for band, _, _ in EXTENDED_BANDS],
        "direct_nec_row_count": len(direct_rows),
        "solution_row_count": len(all_rows),
        "profiles": list(ATU_PROFILE_IDS),
        "summary_by_band": summaries,
        "limitations": [
            "KXAT2/KXAT3 bank values are schematic-derived; component Q and relay resistance are sensitivity inputs.",
            "KHATU1 bank values are inferred until ATU PARAM observations are supplied.",
            "Z-11Pro II bank values are specification-range-fit because current public schematics were not found.",
            "ZM-2 is an equivalent coupled-resonator model; tap parasitics, coupling, and physical capacitor law are not calibrated.",
        ],
    }
    _write_json(output_dir / "summary.json", summary)
    (output_dir / "REPORT.md").write_text(_atu_report(summary), encoding="utf-8")
    _write_json(
        output_dir / "run_metadata.json",
        {
            "pipeline": "profile-sharded",
            "github_sha": os.environ.get("GITHUB_SHA"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "source_sha256": _sha256(Path(__file__)),
            "input_file_count": sum(path.is_file() for path in input_dir.rglob("*")),
        },
    )
    _manifest(output_dir)
    return summary


def run_atu_loss_study(
    output_dir: Path,
    *,
    direct_nec_csv: Path | None = None,
    nec2c: str | Path | None = None,
    jobs: int = 6,
) -> dict[str, Any]:
    """Run the complete study locally using the same staged implementation."""
    with tempfile.TemporaryDirectory(prefix="atu-loss-study-") as temporary:
        staging = Path(temporary)
        if direct_nec_csv is None:
            direct_stage = staging / "direct"
            run_atu_direct_nec_stage(direct_stage, nec2c=nec2c, jobs=jobs)
            direct_path = direct_stage / "atu-direct-nec.csv"
        else:
            direct_stage = staging / "direct"
            direct_stage.mkdir()
            direct_path = direct_stage / "atu-direct-nec.csv"
            shutil.copy2(direct_nec_csv, direct_path)
            _write_json(
                direct_stage / "stage_metadata.json",
                {
                    "stage": "atu-direct-nec",
                    "source": str(direct_nec_csv),
                    "output_file": direct_path.name,
                },
            )
        for profile_id in ATU_PROFILE_IDS:
            run_atu_profile_stage(
                staging / profile_id,
                direct_nec_csv=direct_path,
                profile_id=profile_id,
            )
        return assemble_atu_loss_study(output_dir, input_dir=staging)

def _atu_report(summary: dict[str, Any]) -> str:
    lines = [
        "# ATU loss study: direct-fed 41/17 antenna",
        "",
        "This report separates antenna radiation efficiency from tuner dissipation and input mismatch. Every switched-L state is enumerated for the published KXAT2/KXAT3 banks and the explicitly labeled inferred/range-fit profiles.",
        "",
        "## Loss sensitivity",
        "",
        "| envelope | inductor Q | capacitor Q | relay contact | fixed series |",
        "|---|---:|---:|---:|---:|",
    ]
    for envelope in LOSS_ENVELOPES:
        lines.append(
            f"| {envelope.id} | {envelope.inductor_q:.0f} | {envelope.capacitor_q:.0f} | {envelope.relay_contact_ohm:.3f} ohm | {envelope.fixed_series_ohm:.3f} ohm |"
        )
    lines += [
        "",
        "## Results by tuner and band",
        "",
        "The table uses the low-loss state among matches at or below 1.5:1. `system p10` is NEC antenna efficiency multiplied by tuner transducer efficiency; it includes mismatch and tuner dissipation, but not unmodeled operator/common-mode effects.",
        "",
        "| tuner | band | match fraction | SWR p90 | tuner eff p10 | tuner loss p90 | system p10 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary["summary_by_band"]:
        if row["objective"] not in {"lowest_loss_under_target", "manual"}:
            continue
        if not row["supported"]:
            lines.append(f"| {row['profile']} | {row['band']} | unsupported | | | | |")
            continue
        lines.append(
            f"| {row['profile']} | {row['band']} | {row['match_fraction_swr_1p5'] * 100:.1f}% | {row['input_swr_p90']:.2f} | {row['tuner_efficiency_p10'] * 100:.1f}% | {row['tuner_loss_db_p90']:.2f} dB | {row['system_efficiency_p10'] * 100:.1f}% |"
        )
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def export_profiles(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "switched_l": {key: asdict(value) for key, value in PROFILES.items()},
                "zm2": asdict(ZM2_PROFILE),
                "loss_envelopes": [asdict(value) for value in LOSS_ENVELOPES],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
