---
id: CR-2026-0092-trigger-relayed-session-chaining
title: Trigger-Relayed Session Chaining from Workspace Drafts
status: completed
type: feature
changelog: internal
---

## Summary

Delivered workspace-draft trigger actions for relaying a completed `flow_event` into the next top-level workspace flow run from `.mathlab/next-session.json`. Static trigger actions remain the default behavior.

## Validation

Validated with:

```sh
cargo test -p spark-triggers -p spark-storage -p spark-workspace -p spark-cli --tests
```

The command passed.

## Shipped Changes

- Trigger action definitions now support `mode`, `flow_allowlist`, and `execution_profile_id`, with `static` as the serialized/default-compatible mode and protected-trigger update checks for the new action fields.
- Workspace trigger activation now handles `mode = "workspace_draft"` by reading `<project_path>/.mathlab/next-session.json`, no-oping with recorded state messages for missing, invalid, parked, malformed, or non-allowlisted drafts, launching the draft-selected flow with draft inputs and an optional execution profile, and renaming the draft to `next-session.launched.json` after a successful launch.
- Trigger runtime state can record successful no-op activations without a run id, preserving a message for why no run launched.
- Math research flows now clear stale draft files during workspace preparation and require synthesis/review steps to write and check `.mathlab/next-session.json`.
- Contract coverage was updated across trigger storage, trigger runtime, workspace activation, CLI route, and HTTP route surfaces; the workspace activation contract covers a completed flow event launching a draft once with the configured execution profile and then no-oping on the consumed draft.
