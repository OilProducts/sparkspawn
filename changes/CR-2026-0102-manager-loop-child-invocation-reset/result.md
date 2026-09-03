# Manager-Loop Child Invocation Reset — Result

Implemented manually (the implement-change flow could not be used to fix the
defect that breaks the implement-change flow).

## Implemented

- **Acknowledgement discriminator** (`attractor-runtime/src/manager_loop.rs`,
  `linked_child_is_history`): on entry with a terminal linked child,
  `autostart_child_pipeline` now distinguishes crash recovery from re-entry.
  A child whose `ChildRunCompleted` was acknowledged at or before this run's
  checkpoint — i.e. a prior completion of this node already consumed it — or
  whose `parent_run_id` is another run (a continuation restored its context)
  is history: the child snapshot is cleared and a fresh invocation launches
  with an advanced `child_invocation_index` and the current context. A
  completed child never acknowledged is the one durable invocation a dead
  executor left behind and is adopted as before; running, waiting, and
  restart-marked children keep their resume semantics.

- **`ChildInvocationReset` event** (`events.rs`, `journals.rs`): emitted when
  re-entry discards a stale link, carrying the node, prior child run id, and
  reason, rendered in the run timeline as a lifecycle entry.

- **Node entry limit** (`executor.rs`, `attractor-core` `NodeRuntimeConfig`):
  routing that re-enters a node more than `runtime.max_entries` times
  (engine default 32; CR-0100's own run legitimately needed 11) fails the run
  with `node_entry_limit_exceeded: node … entered N times (limit L)` instead of
  spinning. The typed field is mirrored into handler attrs.

## Tests (`flow_definition_typed_runtime_contracts.rs`)

- Re-entry after the executor checkpointed past the node launches a fresh
  child with invocation index 2 and emits `ChildInvocationReset`.
- Re-entry with an unacknowledged completed child adopts it: no sibling, no
  reset event.
- A continuation run linking another run's completed child invokes afresh.
- A permanently failing evaluate → implement loop fails the run at the entry
  limit with the explicit reason (route trace shows the bounded entries).
- Existing CR-0100 recovery contracts (`run_recovery_contracts`) unchanged and
  green; full `just test` gate green.
