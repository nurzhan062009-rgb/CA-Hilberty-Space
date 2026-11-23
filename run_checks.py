"""Correctness + legality checks and metrics table for the optimizer.

Run:  python run_checks.py
Writes metrics.csv and prints a pass/fail report. Every circuit must be
unitary-equivalent to the original (layout-aware) and legal on the device;
a better gate count with wrong behavior counts as failure.
"""

import csv
import sys

import numpy as np
from qiskit import transpile
from qiskit.quantum_info import Operator, Statevector

from benchmarks import organizer_cases, generality_suite
from optimizer import optimize_for_device, COUPLING, BASIS, EDGES


def metrics(qc):
    ops = qc.count_ops()
    return {"cx": ops.get("cx", 0), "depth": qc.depth(), "size": qc.size()}


def legal_physical(c):
    edges = set(EDGES)
    for inst in c.data:
        if inst.operation.name not in BASIS and inst.operation.name != "barrier":
            return False, f"unsupported op {inst.operation.name}"
        if inst.operation.name == "cx":
            pair = tuple(c.find_bit(q).index for q in inst.qubits)
            if pair not in edges:
                return False, f"illegal edge {pair}"
    return True, "OK"


def behavior_check(original, candidate, n_states=3, seed=99):
    """Independent check: evolve random input states through both unitaries."""
    u = Operator.from_circuit(original)
    v = Operator.from_circuit(candidate)
    rng = np.random.default_rng(seed)
    for _ in range(n_states):
        psi = rng.normal(size=32) + 1j * rng.normal(size=32)
        psi /= np.linalg.norm(psi)
        a = Statevector(psi).evolve(u)
        b = Statevector(psi).evolve(v)
        if not a.equiv(b):
            return False
    return True


def main():
    rows = []
    failures = 0
    all_cases = {**organizer_cases(), **generality_suite()}
    for name, circ in all_cases.items():
        base = transpile(circ, basis_gates=BASIS, coupling_map=COUPLING,
                         optimization_level=3, seed_transpiler=42)
        opt, report = optimize_for_device(circ, return_report=True)
        eq = Operator.from_circuit(circ).equiv(Operator.from_circuit(opt))
        legal, msg = legal_physical(opt)
        beh = behavior_check(circ, opt)
        ok = eq and legal and beh
        failures += 0 if ok else 1
        bm, om = metrics(base), metrics(opt)
        rows.append({
            "case": name,
            "o3_cx": bm["cx"], "team_cx": om["cx"],
            "o3_depth": bm["depth"], "team_depth": om["depth"],
            "o3_size": bm["size"], "team_size": om["size"],
            "equivalent": eq, "legal": legal, "behavior_check": beh,
            "winner": report["winner"], "compile_seconds": report["seconds"],
        })
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: CX {bm['cx']}->{om['cx']}, "
              f"depth {bm['depth']}->{om['depth']}, size {bm['size']}->{om['size']} "
              f"({report['seconds']}s, {report['winner']})")

    with open("metrics.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows) - failures}/{len(rows)} checks passed; metrics.csv written")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())