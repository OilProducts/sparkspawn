# Run Lifecycle Visibility Polish

## Summary

Five small defects found while recovering the CR-2026-0101 implementation
run, all about runs whose lifecycle happened outside the chat UI. None is
urgent; together they make continued or CLI-driven runs effectively
invisible.

## Implementation Changes

- Runs panel resync: a run created or continued through the workspace API or
  CLI must trigger the same runs-overview resync event as a UI-launched run.
  Today an already-open Runs panel never learns about it until the app is
  restarted.
- Group continuations: the runs list nests children by `parent_run_id` only;
  a run with `continued_from_run_id` should render under the run it
  continues, the same way children do.
- Row labels: continuation runs use timestamp-format ids
  (`run-2026-08-27T11-13-33-…`), and the list labels rows with
  `run_id.slice(0, 8)`, so every continuation displays as "run-2026". Derive
  the label from the flow name and start time, not an id prefix — and
  consider giving continuations the same id generator as launches.
- `spark run retry <id>` / `continue <id>`: a positional run id fails with a
  bare "unrecognized arguments" usage error. Accept the positional form, or
  name `--run` in the error.
- Conversation ownership for CLI continue/retry: a `continue` issued without
  `--conversation` creates a run no conversation owns, so no run card appears
  anywhere in chat. Either require `--conversation` for lifecycle verbs, or
  inherit ownership from the source run's conversation by default.

## Test Plan

- API-created run appears in an open Runs panel without restart.
- Continuation rows nest under their source run and carry a readable label.
- CLI positional run id accepted for retry/continue.
- `continue` without `--conversation` inherits the source run's conversation
  and produces a run card there.
