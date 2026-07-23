# Trigger-Relayed Session Chaining from Workspace Drafts

## Summary
Let a `flow_event` trigger launch the *next* session of a research program from the draft the completed session wrote, so programs run unattended until a session parks or fails. Today `TriggerAction { flow_name, project_path, static_context }` can only launch one fixed flow with static context, but each math-research session decides its successor dynamically: the flows now write `.mathlab/next-session.json` (`{"status": "continue"|"parked", "flow": ..., "inputs": {...}, "rationale": ...}`) at synthesis, adversarially reviewed in-run. Add one dynamic action mode that reads that draft server-side, where the full launch machinery (execution profiles, run records, locks) already lives.

## Why not the alternatives
- Flows cannot launch flows: containers have no control surface (correct, keep it that way).
- Subflow/manager-loop chaining cannot carry execution profiles: `launch_default_child_run` executes children in-process with the parent's raw `RuntimeHandlerRunner`; the container wrapper lives at the API layer and never applies to child runs. A dispatcher parent therefore cannot give session children the math-lab container, and a containerized parent cannot launch children at all (worker has no run paths).
- Auto-approving agent run-requests would hollow out the approval gate rather than replace it with an owner-configured policy. A trigger the owner creates *is* the standing authorization.

## Key Changes
1. **`TriggerAction` gains an action mode** (`mode: "workspace_draft"`, default `"static"` preserving current behavior). In draft mode:
   - On activation, read `<project_path>/.mathlab/next-session.json`.
   - Missing file, unparseable JSON, or `status != "continue"` → no-op activation (record the reason in trigger state `last_error`/message; do not fail the trigger).
   - Otherwise validate `flow` against an allowlist configured on the action (e.g. `["math-research/*"]`) and launch a top-level run with the draft's `inputs` as launch context, plus an action-configured `execution_profile_id`. Reject flows outside the allowlist.
   - Consume the draft on successful launch (rename to `.mathlab/next-session.launched.json`) so a crash-loop cannot relaunch the same draft twice; the flows also clear it in `prepare_workspace`.
2. **`flow_event` source config** already filters by `flow_name` and terminal `statuses`; chaining triggers use `statuses: ["completed"]` so a failed session stops its chain (dossier holds state; resumable by relaunching manually).
3. **CLI**: `spark trigger create` accepts the new action fields (mode, allowlist, execution profile). No new commands.
4. **No changes** to approval-gated agent run-requests, launch policies, or the worker protocol.

## Loop safety
- A parked or absent draft is a clean stop, not an error.
- Draft consumption plus `statuses: ["completed"]` bounds every activation to one launch per finished session; there is no path that fires without a fresh draft written by a fresh completed run.
- The in-run adversarial reviewer already gates the draft's honesty (inputs executable, status justified) before the run can complete.

## Test Plan
- Trigger contract tests: draft mode launches the draft's flow with draft inputs and configured profile on a `completed` event; no-ops on parked/missing/malformed drafts and on non-allowlisted flows; consumes the draft exactly once; static mode behavior unchanged.
- One end-to-end contract: flow completes → trigger fires → child-of-chain run record exists with correct flow_name, launch context, and execution profile; second activation without a new draft is a no-op.
- `cargo test -p spark-triggers -p spark-server -p spark-storage`.

## Assumptions
- The trigger is created per program (per project) by the owner; creating it is the owner's standing consent to unattended chaining and spend for that program.
- Chained sessions inherit the flow defaults for model/provider unless the draft or action overrides them.
