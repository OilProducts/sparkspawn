# UI Parity-Complete User Journey Acceptance Script

Checklist item: [1.2-01]

Goal: verify a parity-complete journey across `project-select`, `author`, `execute`, and `inspect` without raw DOT fallback.

Reference loop from `ui-spec.md`:
`select project -> collaborate on spec -> generate/approve implementation plan -> run build workflows -> inspect outcomes`

## Preconditions

1. User has at least one registered local project directory in the Projects area.
2. Active project is a Git repository and has permissions needed for run operations.
3. UI has access to flow editing, conversation/spec, execution, and run-inspection surfaces.
4. Seed flow exists that is spec-valid and runnable.

## Acceptance Script

1. Open the UI and pick a project from Projects (`project-select`).
2. Open the project-scoped conversation surface and update/refine spec text.
3. Generate a plan proposal and explicitly approve it.
4. Open the target flow in the editor and adjust graph/node/edge settings (`author`).
5. Run validation and resolve any surfaced diagnostics from UI controls.
6. Save the flow and re-open it to confirm values remain intact.
7. Launch a run from the execution surface with explicit project context (`execute`).
8. Observe active status, timeline/events, and gate prompts while the run is active.
9. Open the completed run in the run inspector (`inspect`).
10. Review checkpoint/context/artifacts and graph render from the inspector.
11. Perform an iteration edit in the same project and start a re-run.
12. Confirm history and artifacts remain project-scoped across both runs.

## Expected Results

1. The complete journey is executable in UI-only surfaces with no required raw DOT edits.
2. Project-scoped context is preserved through conversation, plan approval, authoring, run start, and inspection.
3. Authoring changes persist and rehydrate without behavior loss.
4. Execution and inspection provide sufficient evidence to diagnose outcomes and iterate safely.
