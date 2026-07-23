# Safe Math-Flow Chaining: Items 1–5

## Summary

Repair the existing chaining implementation with the smallest changes that provide serialized, post-success, exactly-once continuation. Do not reconcile either math workspace or restart research runs in this change.

## Implementation Changes

1. **Remove recurring ignition**

   - Delete the two current `*-ignite` interval triggers before any restart.
   - Disable the two `*-chain` triggers during deployment and testing.
   - Do not add replacement timers. Initial ignition will be a manual launch or a one-time trigger only.

2. **Serialize math runs**

   - Add the same project-scoped execution lock to all three math-research flow catalog entries:
     - scope: `project`
     - key: `math-research`
     - conflict policy: `queue`
   - Reuse the existing catalog and runtime lock machinery; add no new lock implementation.
   - The shared key ensures different math flows cannot overlap within the same project while allowing Tuza and BSD to run independently.

3. **Publish continuation only after successful review**

   - Change synthesis to write `.mathlab/next-session.draft.json`.
   - Change reviewers to inspect that draft filename.
   - At the end of each existing commit tool, after the repository commit succeeds, atomically rename the reviewed draft to `.mathlab/next-session.json`.
   - Preparation clears stale draft, active, and launching files.
   - A failure before commit therefore leaves no launchable continuation.

4. **Make event chaining reliable and single-consumer**

   - Pass the existing run-event observer into trigger-launched flows. The current schedule activation path constructs its workspace service without that observer, so successor completion never reaches `flow_event`.
   - Reuse the existing terminal-event publisher; do not add polling or a second event system.
   - On activation, atomically claim `next-session.json` by renaming it to `next-session.launching.json` before launching:
     - claim failure means another activation won and becomes a recorded no-op;
     - launch failure renames it back for deliberate retry;
     - launch success renames it to `next-session.launched.json`.
   - Keep `flow_event` restricted to `statuses: ["completed"]`.
   - Re-enable one `*-chain` trigger per project only after the integration test passes.

5. **Validate draft inputs against the selected flow**

   - Reuse the existing YAML `FlowDefinition.inputs` parser in the workspace trigger path.
   - Before claiming or launching a draft:
     - reject unknown input keys;
     - require every declared required input that lacks a default;
     - validate supplied JSON values against each declared input type;
     - continue allowing omitted optional inputs.
   - Record validation failures as trigger no-ops with a precise message; do not consume the draft or create a run.
   - Add no new schema format or dependency.

## Interfaces and Compatibility

- Keep the existing `.mathlab/next-session.json` launch contract unchanged.
- Add only the internal `.mathlab/next-session.draft.json` and `.mathlab/next-session.launching.json` lifecycle states.
- Static triggers, approval-gated run requests, flow definitions, and existing trigger configuration remain backward compatible.
- No new CLI command or public API is required.

## Test Plan

- Flow validation: all three math flows synthesize/review the draft file and promote it only after a successful commit; review or commit failure leaves no active draft.
- Lock contract: two math-flow launches for one project serialize; launches for different projects can execute concurrently.
- Event integration: a trigger-launched run completes, emits its terminal event, consumes one valid draft, and launches exactly one successor.
- Race test: two activations against one draft produce one launch and one no-op.
- Failure tests: failed source run, failed successor launch, parked/missing/malformed draft, and duplicate terminal event do not lose or duplicate work.
- Input tests: valid required/optional inputs launch; missing required, unknown, wrong-type, and cross-flow keys no-op without consuming the draft.
- Regression: existing static-trigger, schedule-trigger, catalog-lock, and workspace-draft contract suites remain green.

## Assumptions

- Workspace reconciliation and selection of the next mathematical continuation are explicitly deferred.
- Queueing is preferred over rejection because it preserves an authorized launch while still preventing overlap.
- The recurring ignition triggers are disposable operational scaffolding, not part of the product design.
- No chaining trigger is re-enabled until the event integration and race tests pass.
