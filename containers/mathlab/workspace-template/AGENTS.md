# Agent guidance for MathLab

## Proof integrity

A machine-checkable claim earns that status only through its checked artifact.
Reviewed informal proofs, located results, and conjectures may be retained at
their explicitly weaker status. Verification gates are not negotiable and may
not be redefined:

- A Lean result counts only if `lake build` succeeds on the exact stated
  theorem with **zero `sorry`/`admit`**, and `#print axioms <theorem>`
  reports nothing beyond the standard Mathlib axioms (`propext`,
  `Classical.choice`, `Quot.sound`). Introducing a new `axiom` to make a
  proof compile is fabrication, not progress.
- A SAT-based result counts only with a DRAT certificate that `drat-trim`
  verifies. An exhaustive search counts only if the search program, its
  exact inputs, and its output digest are committed alongside the claim.
- Weakening a theorem statement to make it provable is legitimate
  mathematics ONLY when the weakening is stated plainly in the result —
  never silently.
- Distinguish clearly between: (a) a new proof, (b) a formalization of a
  known proof, and (c) a result located in existing literature. All three
  are valuable; mislabeling one as another is a violation.

## Knowledge discipline

`problem.md` is the exact problem and its resolution criteria. `state.md` is
the concise current claim state, not a diary. Read both before working, then
consult only the history records relevant to the selected uncertainty.

Every completed research action has one immutable record under `history/` and
its supporting material under the matching `evidence/` directory. Do not
rewrite old history. Do not repeat an unsuccessful approach without naming a
new ingredient that addresses its recorded obstruction.

Update `state.md` only from independently assessed claims. Keep conditional
results conditional, derived conjectures distinct from the main problem, and
computational evidence scoped to exactly what was checked.

## Working style

- Compute before conjecturing: use the installed engines (PARI/GP, nauty —
  binaries are prefixed on Ubuntu: nauty-geng, nauty-directg, etc. —,
  cadical/kissat, z3/cvc5, HiGHS/CSDP, the Python stack at
  /opt/mathlab/venv) to build evidence before attempting proof.
- Start Lean work by copying /opt/mathlab/template (Mathlib is prebuilt at
  /opt/mathlab/mathlib4; the pinned commit is /opt/mathlab/MATHLIB_COMMIT).
  Never modify the shared Mathlib checkout.
- Small, durable increments: each assessed research action preserves its
  claims, evidence, verification result, and history record. The workflow
  commits the complete action atomically.
