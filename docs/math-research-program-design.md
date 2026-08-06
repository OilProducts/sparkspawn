# Math research program: clean-room design

## Purpose

Maintain and improve the justified mathematical knowledge about one problem
until:

1. a proof is kernel-checked and its formal statement is judged faithful to
   the problem;
2. a counterexample is directly verified against the exact problem statement;
3. a human explicitly accepts an independently reviewed informal proof; or
4. a human cancels the program.

Computational evidence, literature reports, partial lemmas, and failed attacks
are progress but are not automatic resolution.

## Workspace contract

One workspace belongs to one research problem.

```text
problem.md
state.md
history/
evidence/
```

### `problem.md`

The stable source of truth for what is being investigated.

It contains:

- the current precise statement;
- definitions, quantifiers, domains, and conventions;
- numbered earlier statement versions and why they changed;
- the accepted resolution criteria;
- standing constraints supplied by the user.

A derived conjecture is a claim in `state.md`, not a silent replacement for
the problem. Changing the research problem requires an explicit new statement
version.

### `state.md`

A concise, replaceable description of current mathematical knowledge.
It is not a diary.

```markdown
# Current state

## Verdict

Open.

## Established claims

| ID | Status | Statement | Basis |
|----|--------|-----------|-------|
| C1 | certified proof | ... | evidence/A17 |
| C2 | computational evidence | ... | evidence/A18 |

## Dependencies

- Resolving the main problem requires C3 and C4.
- C4 depends on C5.

## Open frontier

1. C5: ...
2. C4: ...

## Approaches not to repeat unchanged

- A8: ... failed because ...
```

Claim statuses are:

- `open`
- `conjectured`
- `located result`
- `computational evidence`
- `reviewed proof`
- `certified proof`
- `verified counterexample`
- `conditional result`
- `refuted`

Every non-open status points to evidence or an exact source.

### `history/`

One immutable record per completed research action:

```text
history/A0001.md
history/A0002.md
```

Each record states:

- the targeted claim or uncertainty;
- why the action was selected;
- what was attempted;
- what was established, rejected, or left uncertain;
- what changed in `state.md`;
- what a future attempt must do differently.

A failed action receives a history record when its obstruction is understood.
Repeated workflow retries do not create research history.

### `evidence/`

Evidence is grouped by research action:

```text
evidence/A0002/
  report.md
  claim.json
  verify.sh
  ...
```

`claim.json` identifies:

- the exact claim and problem-statement version;
- the kind of claim;
- the artifacts offered in support;
- the command that checks the machine-checkable portion;
- tool and dependency versions relevant to reproduction.

`verify.sh` is required when a claim is machine-checkable. Its contents depend
on the claim:

- Lean build, integrity scan, and axiom report for formal proofs;
- direct property evaluation for a counterexample;
- certificate checking for SAT results;
- input regeneration, scope checks, and digest comparison for enumeration;
- explicit numerical error or interval checks for numerical claims.

The workflow supplies one interface—`verify.sh`—without pretending every kind
of mathematical evidence has the same verification method.

## One research action

Each iteration answers:

> Which feasible action is most likely to cause a meaningful change in the
> current claim state?

Before work starts, the selected action records:

- target claim;
- current uncertainty;
- proposed activity;
- possible outcomes and how each would change the state;
- resource bound;
- the new ingredient distinguishing it from prior failed attacks.

The activity may mix literature work, computation, proof development,
counterexample search, and formalization. These are methods, not workflow
phases.

## Assessment

Results receive two independent forms of assessment where applicable.

### Mechanical assessment

Run the evidence-specific verifier. A failed verifier means the proposed
machine-checkable claim is not established.

One focused repair is permitted. If it still fails, record the obstruction,
downgrade or withdraw the claim, update the state, and select a different
action.

### Mathematical assessment

An independent reader checks matters the machine cannot:

- statement fidelity;
- missing hypotheses or cases;
- whether a witness attacks the actual claim;
- whether a reported computational scope matches the program;
- whether a cited theorem has the required hypotheses;
- whether prose conclusions exceed the evidence.

Assessment may accept, downgrade, reject, or split a claim. It does not enter
an editorial rewrite loop.

## State transition

After assessment:

1. preserve accepted and rejected evidence;
2. write one history record;
3. replace `state.md` with the new concise state;
4. commit the action atomically;
5. check the resolution criterion;
6. if unresolved, select another action.

Local repair budgets end an action, not the research program.

## Resolution

Automatic resolution requires one of:

- a kernel-checked proof plus an accepted statement-fidelity assessment;
- a directly verified counterexample to the exact current problem statement.

An independently reviewed informal proof remains `reviewed proof` until a
human accepts it or it is certified.

The resolution check is always against `problem.md`. Proving or refuting a
derived claim does not accidentally resolve the parent problem.

## BSD walkthrough

Problem: prove full saturation of the rank-one subgroup for representative
156, or determine the exact obstruction.

The state can represent:

- exact verified relation `5 * [0,0] = [-3/4,1/8]`;
- verified saturation for primes below 100;
- certified conditional rank-one height/index lemmas;
- numerical height agreement as computational evidence;
- the open need for certified curve-specific height bounds that discharge the
  conditional lemma's hypotheses.

The conditional Lean theorem is preserved as a certified claim, but it does
not resolve the problem because its curve-specific hypotheses remain open.
The next action targets those hypotheses rather than formalizing the same
conditional implication again.

## Tuza walkthrough

Problem: prove or refute `tau(G) <= 2 * nu(G)` for every finite simple graph.

The state can represent:

- reproducible finite searches through an exact vertex bound;
- the observed extremal ratio and retained examples;
- certified local Lean lemmas;
- a derived K4 claim suggested by equality data;
- the smallest unexamined case and the missing global argument.

Proving or refuting the derived K4 claim changes the frontier but does not
resolve Tuza's conjecture. A finite search is computational evidence unless
its conclusion is itself the bounded finite claim under investigation.

Both examples fit the same state and evidence model without separate BSD,
graph-search, prove/refute, or formalization workflows.

## Minimal workflow shape

Only after the workspace contract is stable should it become a flow:

```text
prepare
  -> select and perform one research action
  -> assess evidence
  -> update state and commit
  -> resolution check
       -> resolved
       -> repeat
```

Parallel agents are an optional technique used by a selected action, not part
of the permanent graph.
