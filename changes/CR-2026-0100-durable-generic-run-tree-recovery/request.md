# Durable Generic Run-Tree Recovery

## Summary

Make Spark automatically resume an interrupted run tree in place. Recovery preserves run IDs, parent–child lineage, checkpoints, execution placement, and accounting. It remains completely unaware of milestone, item, validation, or other workflow-domain concepts.

Execution semantics are at-least-once for a started but uncheckpointed node. Nodes may opt into pausing instead of automatic rerun.

## Runtime changes

- Persist complete execution metadata on every child record by inheriting the parent’s resolved profile, mode, image, capabilities, and applicable execution lock.
- Treat the child record’s generic lineage fields—parent run, parent node, root run, and invocation index—as the durable parent–child link.
- On startup, recover orphaned root trees instead of marking running runs failed:
  - Resume only roots directly; descendants remain parent-owned.
  - At a resumed subflow node, find its unacknowledged child invocation.
  - Resume an interrupted child recursively, or consume its existing terminal result.
  - Create a new child only when no prior unacknowledged invocation exists.
  - If multiple children ambiguously claim the same invocation, stop with a corruption diagnostic.
- Reconcile crash windows generically:
  - A contract-valid durable node response is finalized without calling the node again.
  - A started node with no durable accepted response reruns automatically.
  - A child that finished before the parent recorded `ChildRunCompleted` is acknowledged from its persisted result.
  - A parent checkpoint that lagged a durable stage completion advances from the recorded outcome.
- Add `runtime.recovery_policy` with values `rerun` and `pause`; default to `rerun`.
  - `pause` produces a durable `waiting` state and `RecoveryDecisionRequired` event.
  - Explicit retry approves rerunning that node.
- Keep `continue from node` as a branching operation that creates a new root. Do not use it for crash recovery.

## Compatibility and bookkeeping

- Repair legacy interrupted children whose execution profile is absent by inheriting the recorded parent profile, then persist the repaired child record before resuming.
- Recognize existing restart-marked runs with checkpoints and no real terminal outcome as recoverable legacy trees; this includes the original LOAM parent and child.
- Start continuation usage at zero; expose lineage totals separately rather than cloning source-run usage.
- Make launch failures terminal: set `ended_at`, emit terminal runtime events, assign a stable failure reason code, and write an honest result artifact.
- Present lifecycle and outcome separately: a finished blocked run is shown as `Blocked`, not as successful completion.
- Safely refresh packaged flows using a manifest of previously seeded hashes:
  - Update untouched built-in flows when packaged content changes.
  - Preserve locally modified flow files.
  - Record the effective flow hash in run metadata.

## Public interfaces

- Extend typed node runtime configuration with:

```yaml
runtime:
  recovery_policy: rerun # default; alternative: pause
```

- Extend run events with `RecoveryDecisionRequired`.
- Allow the existing retry operation to resume a recovery-paused run in place.
- Add stable recovery failure codes for missing/corrupt lineage, unrecoverable execution placement, and ambiguous child invocation.

## Test plan

- Use synthetic generic nested flows only—no LOAM or milestone concepts.
- Interrupt a root, child, and grandchild at every durable boundary and verify automatic recovery preserves all run IDs and reaches the same result as uninterrupted execution.
- Cover crashes:
  - before and after child-record creation;
  - before and after `ChildRunStarted`;
  - during child execution;
  - after child completion but before parent acknowledgement;
  - after a valid node response but before checkpoint advancement;
  - during a node with no accepted response.
- Verify an interrupted current node reruns once under default at-least-once semantics, while `recovery_policy: pause` waits for explicit retry.
- Verify completed checkpointed nodes never rerun and intentional loop re-entry creates a new invocation.
- Verify child execution placement is inherited and independently resumable.
- Verify legacy missing-profile children are repaired from their parent and the original tree resumes.
- Verify continuation creates a separate root with zero new-run usage.
- Verify packaged untouched flows update while locally modified flows remain unchanged.
- Add one process-level test that kills the Spark service during a nested subflow and confirms startup alone completes the original tree.

## Assumptions

- Automatic recovery is enabled by default.
- Spark guarantees at-least-once execution for uncheckpointed work, not exactly-once external side effects.
- Workflow-domain files and prompts remain outside the recovery mechanism.
- Existing malformed continuations remain historical records; recovery targets the original interrupted run tree.
