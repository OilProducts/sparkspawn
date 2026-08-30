# Manager-Loop Child Invocation Reset

## Summary

A manager-loop node re-entered after a downstream failure must launch a fresh
child invocation; today it unconditionally adopts its previously completed
child and reports vacuous success, so retry edges (evaluate → implement) loop
forever without doing work.

The regression was introduced by CR-2026-0100's recovery hardening
(`14c75dd`): to stop a restarted executor from manufacturing sibling children,
`autostart_child_pipeline` was changed to adopt any resolvable linked child and
return. Before that change a completed linked child was cleared and a new child
launched on re-entry — the behavior the retry loop depends on (CR-0100's own
implement-change run did eleven real attempts through it). Both requirements
are legitimate; the fix must distinguish them instead of choosing one.

## Implementation Changes

- Discriminate crash recovery from retry re-entry by acknowledgement, using
  machinery CR-0100 already introduced.
  - A completed linked child whose `ChildRunCompleted` event was acknowledged
    at or before the parent's checkpoint has already been consumed by a prior
    completion of this node: it is history. Clear the child snapshot, advance
    the child invocation index, and launch a fresh child with the current
    context (including downstream feedback such as
    `context.review.required_changes`).
  - A completed linked child with no acknowledged `ChildRunCompleted` is the
    one durable, unacknowledged invocation from a dead executor: adopt it, as
    today. Running, waiting, and restart-marked children keep their current
    resume semantics.
  - Never manufacture a sibling for an unacknowledged child; never adopt an
    acknowledged one.

- Cap failure-edge re-entries.
  - Bound the number of times a node may be re-entered along failure routing
    within one run (flow-configurable, with a conservative engine default).
  - On exhaustion, fail the run with an explicit reason naming the node and
    attempt count — never spin. The original incident looped 3,400+ cycles;
    with auth broken the cycles were ~1s each.

- Emit an event when a re-entry launches a fresh invocation (node id,
  invocation index, prior child run id) so the run timeline shows retry
  attempts as first-class work rather than indistinguishable stage repeats.

## Interfaces

- Flow-level knob for the failure-edge attempt cap; absent means the engine
  default. No changes to child run records beyond the existing
  `child_invocation_index`.
- Existing recovery behavior for running/waiting/restart-marked children is
  unchanged; `run_recovery_contracts` must keep passing as written.

## Test Plan

- Re-entry after downstream rejection launches a fresh child that sees the
  updated context, and the new child's invocation index advances (regression
  for the CR-2026-0101 implement loop).
- Executor restart with a completed-but-unacknowledged child adopts it without
  manufacturing a sibling (existing CR-0100 contracts stay green).
- Executor restart with an acknowledged completed child plus a pending failure
  re-entry launches fresh work instead of adopting.
- A permanently failing evaluate exhausts the attempt cap and fails the run
  with the explicit reason; event log shows each attempt.
- Ambiguous multi-child recovery still fails with
  `recovery_ambiguous_child_invocation`.

## Assumptions

- `ChildRunCompleted`-before-checkpoint acknowledgement is the authoritative
  signal that a child's result was consumed; no new persistence is required.
- Until this change lands, the implement-change flow cannot converge on any
  run whose evaluate fails at least once. Implement this change manually or in
  a single evaluate-clean attempt; do not rely on the retry loop it is fixing.
