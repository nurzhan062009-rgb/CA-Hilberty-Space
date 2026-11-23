"""Layout-aware peephole optimizer for a 5-qubit linear device.

Method (three stages):
  1. Interaction-graph layout search: enumerate physical placements of the
     logical qubits and keep the ones that minimize weighted interaction
     distance on the line. Cheap for n=5 (120 permutations).
  2. Identity-block pruning: split the circuit into maximal blocks acting on
     at most two qubits, drop blocks whose unitary is the identity (up to a
     global phase). Iterate to a fixed point so cascades collapse.
  3. Peephole KAK resynthesis: after routing, re-synthesize every two-qubit
     block with the KAK decomposition (at most 3 CX per block) and merge
     single-qubit runs into rz-sx-rz. The same resynthesis is also applied
     before routing, so cheaper blocks enter the router.

Every candidate is verified against the original unitary (layout-aware)
before it can win, so an aggressive rewrite can never corrupt the result.
The portfolio spans preset levels 2-3 over a seed sweep, the lookahead
router, AQC two-qubit synthesis, and the best interaction-graph layouts.
"""

from itertools import permutations
from time import perf_counter

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import CXGate
from qiskit.quantum_info import Operator
from qiskit.synthesis import TwoQubitBasisDecomposer
from qiskit.transpiler import CouplingMap, PassManager
from qiskit.transpiler.passes import Optimize1qGatesDecomposition

N_QUBITS = 5
EDGES = [(i, i + 1) for i in range(N_QUBITS - 1)] + [(i + 1, i) for i in range(N_QUBITS - 1)]
COUPLING = CouplingMap(EDGES)
BASIS = ["rz", "sx", "x", "cx"]
SEEDS = (42, 7, 2026)
SWEEP_SEEDS = tuple(range(12))
TOP_LAYOUTS = 8

_kak = TwoQubitBasisDecomposer(CXGate(), basis_fidelity=1.0)
_1q_pm = PassManager([Optimize1qGatesDecomposition(target=None, basis=["rz", "sx", "x"])])


def _interaction_weights(qc):
    w = {}
    for inst in qc.data:
        qs = [qc.find_bit(q).index for q in inst.qubits]
        if len(qs) >= 2:
            for a in range(len(qs)):
                for b in range(a + 1, len(qs)):
                    key = (min(qs[a], qs[b]), max(qs[a], qs[b]))
                    w[key] = w.get(key, 0) + 1
    return w


def best_layouts(qc, k=TOP_LAYOUTS):
    """Rank physical placements by weighted interaction distance on the line."""
    n = qc.num_qubits
    w = _interaction_weights(qc)
    scored = []
    for perm in permutations(range(n)):
        cost = sum(cnt * abs(perm[a] - perm[b]) for (a, b), cnt in w.items())
        scored.append((cost, list(perm)))
    scored.sort(key=lambda t: t[0])
    return [layout for _, layout in scored[:k]]


def _blocks(qc):
    """Commutation-aware peephole windows.

    A block is a maximal subsequence of gates supported on one qubit pair S;
    interleaved gates whose support is disjoint from S commute with the whole
    block and are deferred past it. Yields (block_indices, deferred_indices,
    support) plus lone gates as single-index blocks.
    """
    data = qc.data
    n = len(data)
    supports = [set(qc.find_bit(q).index for q in inst.qubits) for inst in data]
    i = 0
    while i < n:
        op = data[i].operation
        s = supports[i]
        if op.name in ("barrier", "measure", "reset") or len(s) > 2:
            yield [i], [], sorted(s)
            i += 1
            continue
        block, deferred = [i], []
        j = i + 1
        while j < n:
            oj = data[j].operation
            if oj.name in ("barrier", "measure", "reset"):
                break
            sj = supports[j]
            if sj <= s:
                block.append(j)
            elif not (sj & s):
                deferred.append(j)
            else:
                break
            j += 1
        yield block, deferred, sorted(s)
        i = j if len(block) + len(deferred) > 1 else i + 1


def _block_unitary(qc, indices, support):
    sub = QuantumCircuit(len(support))
    pos = {q: i for i, q in enumerate(support)}
    for k in indices:
        inst = qc.data[k]
        sub.append(inst.operation, [pos[qc.find_bit(q).index] for q in inst.qubits])
    return sub, Operator(sub)


def _carry_layout(dst, src):
    # QuantumCircuit.layout is read-only in qiskit >= 2.6
    dst._layout = src.layout


def _rebuild(qc, kept):
    out = QuantumCircuit(qc.num_qubits, qc.num_clbits)
    for inst in kept:
        out.append(inst.operation, inst.qubits, inst.clbits)
    _carry_layout(out, qc)
    out.global_phase = qc.global_phase
    return out


def prune_identities(qc, max_rounds=8):
    """Drop <=2-qubit blocks equal to identity; repeat until nothing changes."""
    for _ in range(max_rounds):
        drop = set()
        for block, _, support in _blocks(qc):
            if len(block) < 2 or not support:
                continue
            _, op = _block_unitary(qc, block, support)
            if op.equiv(Operator(np.eye(2 ** len(support)))):
                drop.update(block)
        if not drop:
            break
        qc = _rebuild(qc, [inst for k, inst in enumerate(qc.data) if k not in drop])
    return qc


def resynthesize_peepholes(qc, max_rounds=4):
    """KAK-resynthesize 2q blocks when it saves CX; consolidate 1q runs."""
    for _ in range(max_rounds):
        pieces = []
        improved = False
        for block, deferred, support in _blocks(qc):
            if len(support) == 2 and len(block) >= 2:
                sub, op = _block_unitary(qc, block, support)
                old_cx = sub.count_ops().get("cx", 0)
                if old_cx >= 1:
                    new_sub = _kak(op)
                    new_cx = new_sub.count_ops().get("cx", 0)
                    better = new_cx < old_cx or (
                        new_cx == old_cx
                        and (new_sub.size(), new_sub.depth()) < (sub.size(), sub.depth())
                    )
                    if better:
                        pieces.append((new_sub, support))
                        pieces.append(([qc.data[k] for k in deferred], None))
                        improved = True
                        continue
            pieces.append(([qc.data[k] for k in block], None))
            pieces.append(([qc.data[k] for k in deferred], None))
        if not improved:
            break
        out = QuantumCircuit(qc.num_qubits, qc.num_clbits)
        for piece, support in pieces:
            if isinstance(piece, QuantumCircuit):
                out.compose(piece, qubits=support, inplace=True)
            else:
                for inst in piece:
                    out.append(inst.operation, inst.qubits, inst.clbits)
        _carry_layout(out, qc)
        qc = out
    merged = _1q_pm.run(qc)
    _carry_layout(merged, qc)
    return prune_identities(merged)


def _score(qc):
    ops = qc.count_ops()
    return (ops.get("cx", 0), qc.depth(), qc.size())


def optimize_for_device(circuit, top_layouts=TOP_LAYOUTS, seeds=SEEDS, return_report=False):
    """Portfolio: layout search x routing seeds x peephole resynthesis.

    Only candidates that are unitary-equivalent to the input (accounting for
    the transpiler layout) may be returned. Among valid candidates we minimize
    a weighted normalized cost mirroring the judging rubric (CX 25, depth 20,
    size 5), relative to the plain optimization_level=3 baseline.
    """
    reference = Operator.from_circuit(circuit)
    candidates = []
    t0 = perf_counter()

    plain = transpile(circuit, basis_gates=BASIS, coupling_map=COUPLING,
                      optimization_level=3, seed_transpiler=SEEDS[0])
    candidates.append(("O3 seed 42", plain))
    base_cx, base_depth, base_size = _score(plain)

    for seed in SWEEP_SEEDS:
        for level in (2, 3):
            r = transpile(circuit, basis_gates=BASIS, coupling_map=COUPLING,
                          optimization_level=level, seed_transpiler=seed)
            candidates.append((f"O{level} seed {seed}", r))

    for seed in (42, 7, 0):
        try:
            r = transpile(circuit, basis_gates=BASIS, coupling_map=COUPLING,
                          optimization_level=3, seed_transpiler=seed,
                          routing_method="lookahead")
            candidates.append((f"lookahead seed {seed}", r))
        except Exception:
            pass
    for seed in (42, 0):
        try:
            r = transpile(circuit, basis_gates=BASIS, coupling_map=COUPLING,
                          optimization_level=3, seed_transpiler=seed,
                          unitary_synthesis_method="aqc")
            candidates.append((f"aqc seed {seed}", r))
        except Exception:
            pass

    pruned = prune_identities(circuit)
    pre_kak = resynthesize_peepholes(pruned)
    layouts = best_layouts(circuit, k=top_layouts)
    for layout in layouts:
        for seed in seeds:
            routed = transpile(pruned, basis_gates=BASIS, coupling_map=COUPLING,
                               initial_layout=layout, optimization_level=3,
                               seed_transpiler=seed)
            candidates.append((f"layout {layout} seed {seed}", routed))
            candidates.append((f"layout {layout} seed {seed} +KAK",
                               resynthesize_peepholes(routed)))
    for layout in layouts[:4]:
        for seed in (42, 7):
            try:
                routed = transpile(pre_kak, basis_gates=BASIS, coupling_map=COUPLING,
                                   initial_layout=layout, optimization_level=3,
                                   seed_transpiler=seed)
                candidates.append((f"preKAK layout {layout} seed {seed}", routed))
            except Exception:
                pass
            try:
                routed = transpile(pruned, basis_gates=BASIS, coupling_map=COUPLING,
                                   initial_layout=layout, optimization_level=3,
                                   seed_transpiler=seed, routing_method="lookahead")
                candidates.append((f"lookahead layout {layout} seed {seed}", routed))
            except Exception:
                pass

    def cost(qc):
        cx, depth, size = _score(qc)
        return (25 * cx / max(base_cx, 1)
                + 20 * depth / max(base_depth, 1)
                + 5 * size / max(base_size, 1))

    best, best_key, best_label = None, None, None
    n_valid = 0
    for label, cand in candidates:
        try:
            if not Operator.from_circuit(cand).equiv(reference):
                continue
        except Exception:
            continue
        n_valid += 1
        key = (round(cost(cand), 6), _score(cand))
        if best_key is None or key < best_key:
            best, best_key, best_label = cand, key, label

    if best is None:
        best = plain
    report = {
        "candidates": len(candidates),
        "valid": n_valid,
        "winner": best_label,
        "seconds": round(perf_counter() - t0, 3),
    }
    return (best, report) if return_report else best