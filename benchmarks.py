"""Benchmark circuits: the four organizer cases plus a generality suite."""

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import QFTGate
from qiskit.quantum_info import random_clifford


def organizer_cases():
    a = QuantumCircuit(5)
    a.h(0); a.cx(0, 4); a.cx(0, 4); a.h(0)
    a.cx(1, 3); a.cx(3, 4)

    b = QuantumCircuit(5)
    b.h(0)
    for i in range(1, 5):
        b.cx(0, i)

    c = QuantumCircuit(5)
    c.h(0); c.cx(0, 4); c.h(2); c.cx(2, 4); c.cz(1, 3)

    d = QuantumCircuit(5)
    for i in range(5):
        d.h(i)
    for i in [0, 1, 2, 3]:
        d.cx(i, i + 1)
    for i in [3, 2, 1, 0]:
        d.cx(i, i + 1)

    return {
        "redundant_and_remote": a,
        "ghz_star": b,
        "remote_entanglers": c,
        "cancel_chain": d,
    }


def generality_suite():
    cases = {}

    q = QuantumCircuit(5)
    q.append(QFTGate(5), range(5))
    cases["qft5"] = q

    e = QuantumCircuit(5)
    e.h(0); e.cx(0, 4); e.rz(0.7, 2); e.cx(0, 4); e.h(0)
    e.cx(1, 3); e.cx(3, 4)
    cases["commute_cancel"] = e

    rng = np.random.default_rng(11)
    for t in range(3):
        cases[f"clifford{t}"] = random_clifford(5, seed=int(rng.integers(1e6))).to_circuit()

    f = QuantumCircuit(5)
    for _ in range(30):
        p, q_ = rng.choice(5, 2, replace=False)
        f.cx(int(p), int(q_))
        f.rz(float(rng.uniform(0, 2 * np.pi)), int(rng.integers(5)))
    cases["random_remote"] = f

    g = QuantumCircuit(5)
    for i in range(4):
        g.cx(i, i + 1)
    g.cx(0, 4)
    for i in [3, 2, 1, 0]:
        g.cx(i, i + 1)
    cases["parity_ring"] = g

    return cases