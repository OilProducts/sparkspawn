# Deterministic Turn Finalization

## Summary

Keep append-only provider activity as the authority and the transcript as its deterministic projection. Treat `turn_completed` as the authoritative model-turn boundary; do not add a background app-server listener.

At that boundary, finalize every transient segment before committing the turn so no running work survives and repeated recovery produces exactly the same transcript.

## Implementation Changes

- Introduce one shared turn projector/finalizer used by both live ingestion and recovery.
  - Preserve segment identity and order from first observation.
  - Retain all captured tool output.
  - Finalize before committing the assistant turn or publishing terminal UI state.
  - Replaying identical activity must produce no mutations.

- Finalize unmatched tool starts according to turn outcome.
  - Successful turn: set segment status to `complete`, tool status to new terminal state `yielded`, and completion reason to `turn_boundary_yield`.
  - Failed/canceled turn: set segment and tool status to `failed` with error code `tool_completion_missing`.
  - Keep each tool at its original stream position.
  - Never label routine yielded work as interrupted or omit it.

- Make provider identity and ordering durable.
  - Thread the appended provider-event sequence into projection.
  - Keep item-backed segment IDs based on app turn and item ID.
  - Give singleton lifecycle events such as `turn_completed` IDs based on app turn and event kind.
  - Give repeatable itemless events IDs based on their durable provider-event sequence.
  - Stop deriving any segment ID from the mutable order counter.

- Define presentation ordering precisely.
  - The final answer is the last user-visible content segment.
  - Tool rows remain at their original stream positions.
  - Lifecycle markers may follow the final answer but remain non-rendered metadata.
  - Remove frontend workarounds; rendering continues to sort canonical segments by `order`.

- Repair existing malformed projections without modifying raw activity.
  - On reopen, detect terminal turns containing running segments, unstable duplicate lifecycle events, or post-answer work caused by prior projection.
  - Deterministically replay that affected turn from provider activity through the shared projector.
  - Append corrective segment upserts and segment tombstones; do not rewrite event history.
  - Persist a projection-version marker so repaired turns are not repeatedly rebuilt.

## Interfaces

- Extend tool-call status with terminal non-error value `yielded`.
- Add optional tool completion reason, using `turn_boundary_yield` for this case.
- Add append-only transcript tombstone records for removing obsolete projected segments during compatibility repair.
- Keep provider activity, conversation turn status, and existing completed/failed tool payloads backward compatible.

## Test Plan

- Successful turn with a yielded command: output retained, tool is `yielded`, original order preserved, final answer remains last visible content.
- Failed and canceled turns with unmatched starts: tools become failed with `tool_completion_missing`.
- Normal completed and failed tools remain unchanged.
- Duplicate `turn_completed` replay produces one lifecycle segment with stable identity.
- Reopen and repeated recovery produce no additional records after the first reconciliation.
- Historical malformed fixtures converge through corrective upserts/tombstones while raw provider events remain byte-for-byte unchanged.
- Live SSE and reopened snapshots produce equivalent canonical timelines.
- Frontend API parsing and tool rows accept `yielded` and render it as neutral terminal work, without a spinner or error treatment.

## Assumptions

- The model-turn boundary is authoritative; Spark will not track process exit after `turn_completed`.
- The model-visible yield observation and captured output are the transcript truth even if the underlying process continues.
- `agent_event` segments remain lifecycle/debug metadata and are not user-visible timeline rows.
- Existing malformed conversations should repair automatically on reopen.
