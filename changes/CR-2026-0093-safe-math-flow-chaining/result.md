# CR-2026-0093 result

Implemented safe math-flow chaining with the existing trigger, terminal-event,
flow-catalog lock, and launch paths.

- All three math-research flows now share the project-scoped `math-research`
  queue lock.
- Math synthesis writes a reviewed next-session draft; commit nodes promote it
  only after a successful repository commit, and preparation removes stale
  handoff state.
- Flow-event chain triggers validate the selected YAML flow inputs before
  atomically claiming the next session, and successor selection is restricted
  to the three approved math-research catalog flows. Claim loss, unauthorized
  selections, and invalid drafts are
  recorded as no-ops, launch failures restore the active file, and successful
  launches retain the atomically recorded launched file.
- Validation accepts exactly the FlowDefinition input types `string`,
  `string[]`, `boolean`, `number`, and `json`; unsupported declared types are
  reported without consuming the continuation.
- Trigger-launched runs now receive the existing run-event observer, including
  terminal-event successors.
- Integration coverage runs a real preparation tool that removes stale draft,
  active, and launching files, waits for the successor run to reach a terminal
  state, and verifies preparation ran and the successful launched marker
  survives. A deterministic observer check verifies the durable run-preparation
  boundary still has only the launching claim; that claim is promoted before
  detached execution can begin, so real flow preparation cannot race promotion.
  Boundary and earlier launch failures restore the active file.
- Math chaining is selected only for `*-chain` flow-event triggers targeting
  the three math-research flows; ordinary math flow-event triggers retain
  their configured static launch behavior. Each chain also compares normalized
  configured and event project paths before reading or claiming a handoff, so
  cross-project terminal events are non-consuming no-ops.
- Added an applied deployment transition over the existing file-backed trigger
  repository. It disables both chains, removes the Tuza and BSD recurring
  ignite triggers, runs the supplied integration gate, then enables and checks
  exactly one completed-only chain per project.

Validation: `just test` and `git diff --check`.
