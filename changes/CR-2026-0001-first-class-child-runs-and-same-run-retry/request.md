# First-Class Child Runs and Same-Run Retry

## Summary

Model child executions as real runs with their own unique run_id, checkpoint, logs, status, and retry lifecycle. Parent runs link to child runs through metadata and context instead of embedding child execution under the parent log directory.

Retry remains simple: retry the selected failed run in place. It does not create a new run and does not require selecting a node.

## Key Changes

- Extend run metadata with linkage fields: `parent_run_id`, `parent_node_id`, `root_run_id`, and `child_invocation_index`.
- When `stack.manager_loop` starts a child flow, allocate a new child `run_id`, create a normal run record, and execute the child with its own run root, logs, checkpoint, events, and status.
- Record the active child run in parent context, e.g. `context.stack.child.run_id`, plus status/outcome fields already used by the manager.
- Emit parent events such as `ChildRunStarted` and `ChildRunCompleted` with the child `run_id` so the parent timeline links to the child timeline.
- Show child runs in the top-level run list, with parent/root linkage visible so they are traceable back to the parent run.

## Retry Behavior

- Add `POST /attractor/pipelines/{run_id}/retry`.
- Retry only accepts terminal failed runs with an available checkpoint and graph snapshot.
- Retry reuses the same `run_id`, run root, checkpoint, graph snapshot, working directory, model, and log/event stream.
- Retry changes the selected run status from failed to running, clears `last_error`, appends retry lifecycle events, and calls the executor with `resume=True`.
- Existing continue remains a fork/manual recovery operation and continues to create a new run.

## Parent/Child Semantics

- A normal new child invocation always creates a new child run and starts with `resume=False`.
- A retry of a failed child run resumes that same child run with `resume=True`.
- Parent manager nodes do not overwrite child logs because each child invocation has its own run root.
- If a parent run failed because a child failed, the linked child run can be retried directly. After the child succeeds, retrying the parent resumes the parent from its checkpoint and observes the updated linked child result rather than creating a replacement child.

## Test Plan

- Child launch creates a distinct run record with parent/root linkage and appears in the top-level run list.
- Multiple executions of the same manager node create separate child run IDs and preserve each child’s logs/checkpoints.
- Retrying a failed root run reuses the same root `run_id` and resumes from checkpoint.
- Retrying a failed child run reuses the same child `run_id` and resumes from the child checkpoint.
- Retrying a parent after its child has been retried successfully does not create a duplicate child run.
- Existing continue behavior remains unchanged and still creates a new linked continuation run.

## Assumptions

- Child runs are first-class run records and visible in the top-level run list.
- Retry is explicit user action only; no automatic transient retry policy is added.
- The parent run remains the orchestration run; child runs own their execution logs, checkpoints, and retry state.
