# Challenge statement (as received from the organizers)

Source: `02_Transpilation_Battle_Starter.ipynb`, CAHS Quantum Fest Hackathon 2026.
Reproduced verbatim below; our solution is in the repository root.

---

# Open Challenge 2 — Transpilation Battle
**Mission:** optimize fixed quantum circuits for a **5-qubit linear** simulated device. **Estimated time:** 5–10 hours. **100 points.**

**Constraints:** physical edges 0–1–2–3–4; bidirectional `cx`; basis `rz`, `sx`, `x`, `cx`. No cloud, API key, or real hardware. You may use built-in Qiskit passes or custom circuit rewrites, but explain your method.

**Deliverables:** optimization code, metrics CSV/table, before/after circuits, correctness checks, README, five-minute demo. Organizers should use additional hidden circuits to test generality.

**Important:** compare *unitary* circuits before measurements. Account for logical-to-physical layouts when testing equivalence. A better gate count with incorrect behavior earns zero optimization points for that case.

---

## Phase 1 — Baselines
Transpile each case at optimization levels 0–3 with the same seed. Measure CX count, depth, and wall-clock compile time. Qiskit may optimize away entire subcircuits; that is expected.

## Phase 2 — Your optimizer
Implement `optimize_for_device(circuit)`. You may choose initial layout, routing, optimization passes, or circuit identities. The returned circuit must use the target basis and legal physical edges. For reproducibility, fix seeds.

**Suggested ideas:** cancel inverse gates, commute gates to expose cancellations, change initial layout, compare routing methods, synthesize Clifford blocks. Don't optimize against only the provided circuits.

## Phase 3 — Verify correctness and physical legality
A routed circuit can have a nontrivial initial/final layout. For the provided small benchmarks, use `Operator.from_circuit(..., ignore_set_layout=True)`? **No**: ignoring layouts can silently hide permutation issues. Instead, use `Operator.from_circuit(circuit)` with layout metadata where supported, and verify on test inputs as well. Qiskit version behavior differs; report how you handled layout. The supplied helper uses `Operator.from_circuit` for the original and `Operator.from_circuit` for the transpiled circuit, which incorporates layout metadata in supported versions.

Do not compare only `|00000⟩` measurements: that can miss phase and unitary errors.

## Phase 4 — Compare and report
Calculate improvements relative to optimization level 3. Avoid division by zero if CX count or depth is zero. Report both metrics, even if one worsens. Organizers can score improvement using normalized ratios, but **equivalence and connectivity are hard gates**.

**Advanced:** inject per-edge two-qubit error rates and compare predicted or simulated output quality; write a custom `TransformationPass` and benchmark it on unseen circuits.

---

## Judging (100)
| Criterion | Points |
|---|---:|
| Equivalence and hardware validity | 25 |
| Two-qubit gate reduction | 25 |
| Depth reduction | 20 |
| Quality and generality of method | 15 |
| Benchmarks and reproducibility | 10 |
| Explanation | 5 |

**Submission:** `optimize_for_device` function, report with all four benchmark cases, proof/check of equivalence, package versions, README. Hidden benchmarks may be used for final judging.

---

## Submission rules (organizer email)

- Deadline: **Friday 27 November 2026, 15:00 GMT+5 (Astana)**; reply to the
  organizer email from the team captain with the team name and full member names.
- Notebooks must be submitted with **all cells executed and outputs visible**.
- A **five-minute demo** of the solution is part of the deliverables.
- AI assistance is allowed provided the team understands and can explain the code.
- Closing ceremony: 28 November 2026, 10:00 GMT+5.

## Where each deliverable lives in this repository

| Deliverable | File |
|---|---|
| Optimization code (`optimize_for_device`) | `optimizer.py`, notebook Stage 1–3 cells |
| Metrics CSV/table | `metrics.csv`, notebook Phase 4 |
| Before/after circuits | notebook Phase 2 drawings |
| Correctness checks | notebook Phase 3, `run_checks.py` (11/11 PASS) |
| README / explanation | `README.md` |
| Package versions | `requirements.txt`, notebook setup cell |
| Generality on unseen-style circuits | notebook generality suite (7 extra circuits) |
| Five-minute demo | `Transpilation_Battle_Demo.mp4` (submitted by email, not stored in git) |