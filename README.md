# LPR — Layout-aware Peephole Portfolio

**Transpilation Battle submission · Quantum Fest Hackathon 2026**

A verified circuit optimizer for a 5-qubit linear device (`0–1–2–3–4`,
bidirectional `cx`, basis `rz, sx, x, cx`). It beats Qiskit
`optimization_level=3` on two-qubit count *and* depth on hard circuits,
matches it where level 3 is already optimal, and **can never return a wrong
circuit**: every candidate passes a layout-aware unitary-equivalence gate
before it is allowed to win.

```
                 ┌────────────────────────────────────────────┐
   circuit ──►   │ 1. interaction-graph layout search (120 perms) │
                 │ 2. commutation-aware peephole: prune + KAK     │
                 │ 3. portfolio: levels 2–3 × seeds, lookahead,   │
                 │    AQC synthesis, top layouts × seeds          │
                 └───────────────────┬────────────────────────┘
                                     ▼
                    verify: Operator.from_circuit equivalence
                    (initial layout + routing permutation)
                                     ▼
                    pick min weighted cost (CX 25 · depth 20 · size 5)
```

## Headline results

Baseline = Qiskit `optimization_level=3`, seed 42. **Bold** = strict improvement.

| circuit | CX (O3 → LPR) | depth (O3 → LPR) | size (O3 → LPR) |
|---|---|---|---|
| redundant_and_remote | 2 → 2 | 2 → 2 | 2 → 2 |
| ghz_star | 6 → 6 | **21 → 16** | **29 → 20** |
| remote_entanglers | 3 → 3 | 7 → 7 | 15 → 15 |
| cancel_chain | 0 → 0 | 3 → 3 | 15 → 15 |
| qft5 | 30 → 30 | 51 → 51 | 95 → 95 |
| commute_cancel | 2 → 2 | 2 → 2 | 3 → 3 |
| clifford0 | **28 → 26** | **48 → 46** | 72 → 74 |
| clifford1 | 23 → 23 | 41 → 41 | 76 → 76 |
| clifford2 | **23 → 21** | 38 → 38 | **66 → 64** |
| random_remote | **57 → 55** | **60 → 56** | **86 → 82** |
| parity_ring | 1 → 1 | 1 → 1 | 1 → 1 |

11/11 circuits pass equivalence, a random-input behavioral check, and
basis/connectivity legality. Full numbers: [`metrics.csv`](metrics.csv).

## The method, in three stages

### 1. Interaction-graph layout search
Count two-qubit interactions per logical pair → weighted graph. On five
qubits there are only 120 physical placements, so we enumerate all of them
and keep the eight minimizing

```
cost(placement) = Σ_ij  w_ij · |phys(i) − phys(j)|
```

on the line. Interacting qubits sit close together, so the router has less
work to do. (Think seating plan: people who talk a lot get adjacent chairs.)

### 2. Commutation-aware peephole passes
Scan the circuit into maximal blocks supported on a single qubit pair `S`.
Gates on qubits *disjoint* from `S` commute with the whole block and are
deferred past it — this exposes cancellations that adjacent-only passes miss
(e.g. `CX(0,4) · Rz(2) · CX(0,4)`).

- **Prune:** delete any block whose unitary is the identity up to global phase.
- **Resynthesize:** rebuild remaining two-qubit blocks with the KAK
  decomposition (`TwoQubitBasisDecomposer`, ≤ 3 CX per block) when it saves
  CX or gates; merge single-qubit runs into `rz–sx–rz`.

Iterate to a fixed point. Run **before routing** (cheaper blocks enter the
router) and **after routing** (clean up SWAP debris).

### 3. Verified portfolio
One compiler run is a lottery ticket; we buy ~100 of them:

- preset levels 2–3 × seeds 0–11 (default layout),
- lookahead router × seeds 42/7/0,
- AQC two-qubit synthesis × seeds 42/0,
- top-8 layouts × seeds 42/7/2026, with post-routing peepholes,
- top-4 layouts × pre-routing KAK and × lookahead.

Every candidate is checked with `Operator.from_circuit(original).equiv(
Operator.from_circuit(candidate))` — this composes the initial layout and the
routing permutation, so permutations are never silently ignored. Candidates
that fail (or routers that crash) are discarded. Among survivors we minimize
a weighted normalized cost against the level-3 baseline, mirroring the
judging rubric: **CX 25 · depth 20 · size 5**.

**Safety argument:** the returned circuit is either a verified-equivalent
candidate or the plain level-3 baseline. There is no path that returns an
unequivalent circuit. A better gate count with wrong behavior is impossible
by construction.

## Which component wins where

| win | source |
|---|---|
| ghz_star depth 21 → 16 | seed/level sweep (same 6 CX, better parallelism) |
| clifford0 CX 28 → 26, depth 48 → 46 | lookahead router |
| clifford2 CX 23 → 21 | lookahead router |
| random_remote CX 57 → 55, depth 60 → 56 | pre-routing KAK + layout search |

Where level 3 is already optimal (`cancel_chain` → 0 CX, `parity_ring` → 1 CX)
we match it exactly. Honest note: `clifford0` size grows 72 → 74 while CX and
depth both improve; both numbers are reported, as the brief requires.

## Reproducibility

- Seeds fixed everywhere: 42 for baselines; 0–11 and 42/7/2026 for the portfolio.
- All correctness checks are unitary-level (no sampling noise).
- Compile time ≤ ~5 s per circuit on a laptop; the whole notebook runs in ~1 min.
- Tested with Python 3.11.9, qiskit 2.6.2, qiskit-aer 0.18.4, numpy 2.4.6,
  matplotlib 3.11.2, scipy 1.17.1.

## Files

| file | purpose |
|---|---|
| `Transpilation_Battle_SOLVED.ipynb` | full executed run: baselines, method, checks, plots, before/after circuits, generality suite |
| `optimizer.py` | the method as an importable module (`optimize_for_device`) |
| `benchmarks.py` | organizer cases + generality suite |
| `run_checks.py` | standalone test runner; writes `metrics.csv`, non-zero exit on any failure |
| `metrics.csv` | metrics for all 11 circuits |
| `build_notebook.py` | regenerates and re-executes the Battle notebook from `optimizer.py` |
| `requirements.txt` | pinned versions used for the submitted run |
| `Certificate_of_Participation_SOLVED.ipynb` | mandatory notebook, executed, 100/100 |
| `Certificate_of_Excellence_SOLVED.ipynb` | mandatory notebook, executed, 220/220 |
| `RUN_CHECKS.bat` | one-click correctness check on Windows |
| `START_JUPYTER.bat` | one-click JupyterLab in the browser (no VS Code needed) |

## Quickstart

```bash
pip install -r requirements.txt
python run_checks.py          # 11/11 PASS, writes metrics.csv
jupyter lab Transpilation_Battle_SOLVED.ipynb
```

No IBM account, token, or hardware — everything runs offline on local Aer.

## Five-minute demo

1. **0:00–0:45** — device and task: 5-qubit line, neighbor-only CX, four organizer circuits.
2. **0:45–1:30** — Phase 1 baselines: what levels 0–3 already achieve.
3. **1:30–3:00** — the method on `ghz_star`: layout scores → peephole pruning → portfolio; winning routing has 6 CX at depth 16 instead of 21.
4. **3:00–4:00** — live Phase 3: equivalence + random-state behavior + legality; comparison plots.
5. **4:00–5:00** — generality suite (clifford0 28→26 CX, clifford2 23→21, random_remote 57→55), `metrics.csv`, and the safety argument: verification is a hard gate.

The recorded demo (`Transpilation_Battle_Demo.mp4`, ~4.5 min) is submitted
separately together with the notebooks.