---
id: CR-2026-0001-first-class-child-runs-and-same-run-retry
title: First-Class Child Runs and Same-Run Retry
status: completed
type: feature
changelog: public
---

## Summary

Implemented first-class child pipeline runs and explicit in-place retry for failed runs. Child executions now get their own run IDs, run roots, checkpoints, logs, events, status records, and top-level run list entries with parent/root linkage. Failed root or child runs can be retried through `POST /attractor/pipelines/{run_id}/retry`, reusing the same run ID and persisted runtime state with `resume=True`.

## Validation

- `uv run pytest -q`
- Result: 943 passed in 12.12s.

## Shipped Changes

- Backend run metadata now includes `parent_run_id`, `parent_node_id`, `root_run_id`, and `child_invocation_index`, and run listing/status hydration preserves those fields.
- `stack.manager_loop` launches child flows as independent run records and records linked child status in parent context under `context.stack.child.*`.
- Parent timelines emit `ChildRunStarted` and `ChildRunCompleted`; child timelines own their stage events, checkpoints, logs, and terminal runtime events.
- Added same-run retry lifecycle handling, including retry eligibility checks, retry checkpoint preparation, `PipelineRetryStarted`/`PipelineRetryCompleted` events, and active run/list updates.
- Retry-aware parent/child behavior reuses a successfully retried linked child when the parent run itself is retried, avoiding duplicate child invocations.
- Existing continue behavior remains a separate continuation/fork path.
- The runs UI and API client now parse and display parent/root linkage and expose a retry action for failed runs.
- API tests cover child run creation, repeated manager child invocations, same-run retry, child retry followed by parent retry, cancel behavior for child runs, persisted child events, and run record serialization.
