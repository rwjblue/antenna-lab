"""Vectorized continuous low-pass L matching with explicit component losses.

This is an approximate generic continuous-network search, not an LDG tuner
simulation or a mathematical global optimum. Exact finite-Q matching supplies
cheap seeds; component limits and a local search permit imperfect matches.
Inductor loss is series X/Q plus the specified contact resistance. Capacitor
loss is parallel B/Q. Q values are scenario inputs, not measured device data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

TOPOLOGIES = {0: "bypass", 1: "source_shunt", 2: "load_shunt"}


@dataclass(frozen=True)
class _Inputs:
    load: NDArray
    omega: NDArray
    inverse_l_q: NDArray
    inverse_c_q: NDArray
    contact_r: NDArray
    source_r: float


def _inputs(
    loads_ohm: ArrayLike,
    frequencies_hz: ArrayLike,
    inductor_q: ArrayLike,
    capacitor_q: ArrayLike,
    series_contact_r_ohm: ArrayLike,
    source_r_ohm: float,
) -> _Inputs:
    load, frequency, ql, qc, contact = np.broadcast_arrays(
        np.asarray(loads_ohm, dtype=complex),
        np.asarray(frequencies_hz, dtype=float),
        np.asarray(inductor_q, dtype=float),
        np.asarray(capacitor_q, dtype=float),
        np.asarray(series_contact_r_ohm, dtype=float),
    )
    if not np.all(np.isfinite(load)) or not np.all(load.real > 0):
        raise ValueError("Loads must have finite impedance and positive resistance")
    if not np.all(np.isfinite(frequency)) or not np.all(frequency > 0):
        raise ValueError("Frequencies must be finite and positive")
    if any(np.any(np.isnan(q)) or np.any(q <= 0) for q in (ql, qc)):
        raise ValueError("Component Q must be positive; infinity means lossless")
    if not np.all(np.isfinite(contact)) or np.any(contact < 0):
        raise ValueError("Contact resistance must be finite and nonnegative")
    if not math.isfinite(source_r_ohm) or source_r_ohm <= 0:
        raise ValueError("Source resistance must be finite and positive")
    return _Inputs(load, 2 * np.pi * frequency, 1 / ql, 1 / qc, contact, source_r_ohm)


def _network(
    inputs: _Inputs, x_l: NDArray, b_c: NDArray, topology: int
) -> tuple[NDArray, NDArray, NDArray, NDArray]:
    """Return input Z, accepted-power efficiency, transducer efficiency, SWR."""
    series_r = inputs.contact_r + x_l * inputs.inverse_l_q
    capacitor_g = b_c * inputs.inverse_c_q
    capacitor_y = capacitor_g + 1j * b_c
    if topology in (0, 1):
        branch_z = inputs.load + series_r + 1j * x_l
        input_z = 1 / (1 / branch_z + capacitor_y)
        efficiency = inputs.load.real / (
            inputs.load.real + series_r + capacitor_g * np.abs(branch_z) ** 2
        )
    else:
        parallel_y = 1 / inputs.load + capacitor_y
        parallel_z = 1 / parallel_y
        input_z = parallel_z + series_r + 1j * x_l
        efficiency = (1 / inputs.load).real / (
            parallel_y.real + series_r * np.abs(parallel_y) ** 2
        )
    accepted_fraction = (
        4 * inputs.source_r * input_z.real / np.abs(input_z + inputs.source_r) ** 2
    )
    accepted_fraction = np.clip(accepted_fraction, 0, 1)
    efficiency = np.clip(efficiency, 0, 1)
    gamma = np.abs((input_z - inputs.source_r) / (input_z + inputs.source_r))
    swr = np.divide(
        1 + gamma,
        1 - gamma,
        out=np.full(np.shape(gamma), np.inf),
        where=gamma < 1,
    )
    return tuple(
        np.asarray(value)
        for value in (input_z, efficiency, efficiency * accepted_fraction, swr)
    )


def _component_losses(
    inputs: _Inputs, x_l: NDArray, b_c: NDArray, topology: ArrayLike
) -> dict[str, NDArray]:
    """Dissipated power in each component divided by accepted input power."""
    coil_r = x_l * inputs.inverse_l_q
    capacitor_g = b_c * inputs.inverse_c_q
    branch_z = inputs.load + inputs.contact_r + coil_r + 1j * x_l
    source_cap_term = capacitor_g * np.abs(branch_z) ** 2
    source_denominator = inputs.load.real + inputs.contact_r + coil_r + source_cap_term
    parallel_y = 1 / inputs.load + capacitor_g + 1j * b_c
    parallel_magnitude_squared = np.abs(parallel_y) ** 2
    load_denominator = (
        parallel_y.real + (inputs.contact_r + coil_r) * parallel_magnitude_squared
    )
    source_numerators = (coil_r, capacitor_g * np.abs(branch_z) ** 2, inputs.contact_r)
    load_numerators = (
        coil_r * parallel_magnitude_squared,
        capacitor_g,
        inputs.contact_r * parallel_magnitude_squared,
    )
    return {
        f"{component}_loss_fraction_of_accepted": np.where(
            np.asarray(topology) == 2,
            load / load_denominator,
            source / source_denominator,
        )
        for component, source, load in zip(
            ("inductor", "capacitor", "contact"),
            source_numerators,
            load_numerators,
            strict=True,
        )
    }


def evaluate_network(
    loads_ohm: ArrayLike,
    frequencies_hz: ArrayLike,
    inductance_uh: ArrayLike,
    capacitance_pf: ArrayLike,
    *,
    topology: str,
    inductor_q: ArrayLike = 70,
    capacitor_q: ArrayLike = 2000,
    series_contact_r_ohm: ArrayLike = 0.1,
    source_r_ohm: float = 50,
) -> dict[str, NDArray]:
    """Evaluate one network state with RMS power conservation.

    ``tuner_efficiency`` is load power / power accepted at the network input.
    ``transducer_efficiency`` is load power / source available power, including
    residual mismatch. Contact resistance stays in series even with L = 0.
    """
    if topology not in ("source_shunt", "load_shunt", "bypass"):
        raise ValueError("Unknown network topology")
    inductance, capacitance, load, frequency = np.broadcast_arrays(
        np.asarray(inductance_uh, dtype=float),
        np.asarray(capacitance_pf, dtype=float),
        np.asarray(loads_ohm, dtype=complex),
        np.asarray(frequencies_hz, dtype=float),
    )
    if any(
        not np.all(np.isfinite(value)) or np.any(value < 0)
        for value in (inductance, capacitance)
    ):
        raise ValueError("L and C must be finite and nonnegative")
    if topology == "bypass" and (np.any(inductance != 0) or np.any(capacitance != 0)):
        raise ValueError("Bypass requires zero inductance and capacitance")
    inputs = _inputs(
        load, frequency, inductor_q, capacitor_q, series_contact_r_ohm, source_r_ohm
    )
    code = next(code for code, name in TOPOLOGIES.items() if name == topology)
    impedance, efficiency, transducer, swr = _network(
        inputs,
        inputs.omega * inductance * 1e-6,
        inputs.omega * capacitance * 1e-12,
        code,
    )
    return {
        "input_impedance_ohm": impedance,
        "input_swr": swr,
        "tuner_efficiency": efficiency,
        "transducer_efficiency": transducer,
        **_component_losses(
            inputs,
            inputs.omega * inductance * 1e-6,
            inputs.omega * capacitance * 1e-12,
            code,
        ),
    }


def _roots(a: NDArray, b: NDArray, c: NDArray) -> tuple[NDArray, NDArray]:
    """Stable real quadratic roots; NaN denotes a nonexistent real solution."""
    a, b, c = np.broadcast_arrays(a, b, c)
    discriminant = b * b - 4 * a * c
    real = discriminant >= 0
    q = -0.5 * (b + np.copysign(np.sqrt(np.maximum(0, discriminant)), b))
    nan = np.full(a.shape, np.nan)
    first = np.divide(q, a, out=nan.copy(), where=real & (a != 0))
    second = np.divide(c, q, out=nan.copy(), where=real & (q != 0))
    repeated_zero = real & (a != 0) & (q == 0)
    first = np.where(repeated_zero, 0, first)
    second = np.where(repeated_zero, 0, second)
    linear = (a == 0) & (b != 0)
    linear_root = np.divide(-c, b, out=nan.copy(), where=linear)
    return np.where(linear, linear_root, first), np.where(linear, linear_root, second)


def _exact_seeds(inputs: _Inputs, topology: int) -> tuple[tuple[NDArray, NDArray], ...]:
    """Solve Zin = source R algebraically for the finite-Q component model."""
    kl, kc, r0 = inputs.inverse_l_q, inputs.inverse_c_q, inputs.source_r
    if topology == 1:
        # Branch Z = (R + kl XL) + j(X + XL); shunt BC = Im(Z)/|Z|².
        # Re(Yin) = [Re(Z) + kc Im(Z)]/|Z|² = 1/R0.
        resistance, reactance = inputs.load.real + inputs.contact_r, inputs.load.imag
        roots = _roots(
            1 + kl**2,
            2 * resistance * kl + 2 * reactance - r0 * (kl + kc),
            resistance**2 + reactance**2 - r0 * (resistance + kc * reactance),
        )
        return tuple(
            (
                root,
                (reactance + root)
                / ((resistance + kl * root) ** 2 + (reactance + root) ** 2),
            )
            for root in roots
        )
    # Parallel Y = (G + kc BC) + j(B + BC); series XL = Im(Y)/|Y|².
    # R0 - contact R = [Re(Y) + kl Im(Y)]/|Y|².
    admittance = 1 / inputs.load
    conductance, susceptance = admittance.real, admittance.imag
    resistance = r0 - inputs.contact_r
    roots = _roots(
        resistance * (1 + kc**2),
        2 * resistance * (conductance * kc + susceptance) - kc - kl,
        resistance * (conductance**2 + susceptance**2) - conductance - kl * susceptance,
    )
    return tuple(
        (
            (susceptance + root)
            / ((conductance + kc * root) ** 2 + (susceptance + root) ** 2),
            root,
        )
        for root in roots
    )


def _better(
    eta: NDArray, swr: NDArray, best_eta: NDArray, best_swr: NDArray, target: float
) -> NDArray:
    matched, best_matched = swr <= target, best_swr <= target
    return matched & (~best_matched | (eta > best_eta)) | (
        ~matched
        & ~best_matched
        & ((swr < best_swr) | ((swr == best_swr) & (eta > best_eta)))
    )


def screen_matching(
    loads_ohm: ArrayLike,
    frequencies_hz: ArrayLike,
    *,
    max_l_uh: float = 20,
    max_c_pf: float = 1300,
    inductor_q: ArrayLike = 70,
    capacitor_q: ArrayLike = 2000,
    series_contact_r_ohm: ArrayLike = 0.1,
    source_r_ohm: float = 50,
    target_swr: float = 2.5,
    refinement_steps: tuple[float, ...] = (0.20, 0.07, 0.025),
) -> dict[str, NDArray]:
    """Select useful continuous states, broadcasting loads, frequency and Q.

    Select highest transducer efficiency among candidates at or below target
    SWR. If none qualify, select the lowest SWR (break ties by efficiency).
    Seeds include both exact finite-Q roots of both low-pass topologies, clipped
    to the component limits, plus each topology's four corners. Each topology
    receives a local eight-neighbor refinement; step sizes are fractions of
    its current L/C with 0.05 uH / 5 pF floors so zero values can move.

    ``refinement_steps=()`` exposes the seed-only result. The reported seed
    efficiency/SWR and improvement allow checking search sensitivity. A matched
    state is feasible in this continuous component model; it does not establish
    a real tuner's bank resolution, power handling, or firmware behavior.
    Q = infinity removes that component's dissipative loss. A lossless run must
    also explicitly set contact resistance to zero.
    """
    if any(not math.isfinite(value) or value <= 0 for value in (max_l_uh, max_c_pf)):
        raise ValueError("Component limits must be finite and positive")
    if not math.isfinite(target_swr) or target_swr < 1:
        raise ValueError("Target SWR must be finite and at least one")
    if any(not math.isfinite(step) or step <= 0 for step in refinement_steps):
        raise ValueError("Refinement steps must be finite and positive")
    inputs = _inputs(
        loads_ohm,
        frequencies_hz,
        inductor_q,
        capacitor_q,
        series_contact_r_ohm,
        source_r_ohm,
    )
    shape = inputs.load.shape
    zero = np.zeros(shape)
    max_x, max_b = inputs.omega * max_l_uh * 1e-6, inputs.omega * max_c_pf * 1e-12
    _, _, bypass_eta, bypass_swr = _network(inputs, zero, zero, 0)

    def starting_state() -> dict[str, NDArray]:
        return {
            "x": zero.copy(),
            "b": zero.copy(),
            "eta": bypass_eta.copy(),
            "swr": bypass_swr.copy(),
        }

    def consider(
        state: dict[str, NDArray], x: NDArray, b: NDArray, topology: int
    ) -> None:
        x = np.clip(np.nan_to_num(x, nan=0, posinf=np.inf, neginf=-np.inf), 0, max_x)
        b = np.clip(np.nan_to_num(b, nan=0, posinf=np.inf, neginf=-np.inf), 0, max_b)
        _, _, eta, candidate_swr = _network(inputs, x, b, topology)
        better = _better(eta, candidate_swr, state["eta"], state["swr"], target_swr)
        for key, value in (("x", x), ("b", b), ("eta", eta), ("swr", candidate_swr)):
            np.copyto(state[key], value, where=better)

    best = starting_state()
    best_topology = np.zeros(shape, dtype=np.int8)
    seed_best = starting_state()
    for topology in (1, 2):
        state = starting_state()
        for x, b in _exact_seeds(inputs, topology):
            consider(state, x, b, topology)
        for x, b in ((zero, max_b), (max_x, zero), (max_x, max_b)):
            consider(state, x, b, topology)
        seed_better = _better(
            state["eta"], state["swr"], seed_best["eta"], seed_best["swr"], target_swr
        )
        for key in seed_best:
            np.copyto(seed_best[key], state[key], where=seed_better)
        for fraction in refinement_steps:
            origin_x, origin_b = state["x"].copy(), state["b"].copy()
            dx = fraction * np.maximum(origin_x, inputs.omega * 0.05e-6)
            db = fraction * np.maximum(origin_b, inputs.omega * 5e-12)
            for sx, sb in (
                (-1, -1),
                (-1, 0),
                (-1, 1),
                (0, -1),
                (0, 1),
                (1, -1),
                (1, 0),
                (1, 1),
            ):
                consider(state, origin_x + sx * dx, origin_b + sb * db, topology)
        better = _better(
            state["eta"], state["swr"], best["eta"], best["swr"], target_swr
        )
        for key in best:
            np.copyto(best[key], state[key], where=better)
        np.copyto(best_topology, topology, where=better)
    source_metrics = _network(inputs, best["x"], best["b"], 1)
    load_metrics = _network(inputs, best["x"], best["b"], 2)
    impedance, efficiency, transducer, input_swr = (
        np.where(best_topology == 2, load, source)
        for source, load in zip(source_metrics, load_metrics, strict=True)
    )
    topology_names = np.array([TOPOLOGIES[code] for code in range(3)])
    return {
        "input_swr": input_swr,
        "transducer_efficiency": transducer,
        "tuner_efficiency": efficiency,
        "matched": input_swr <= target_swr,
        "inductance_uh": best["x"] / inputs.omega * 1e6,
        "capacitance_pf": best["b"] / inputs.omega * 1e12,
        "topology": topology_names[best_topology],
        "input_impedance_ohm": impedance,
        "mismatch_efficiency": transducer / efficiency,
        "seed_input_swr": seed_best["swr"],
        "seed_transducer_efficiency": seed_best["eta"],
        "transducer_efficiency_change_from_seed": transducer - seed_best["eta"],
        **_component_losses(inputs, best["x"], best["b"], best_topology),
    }
