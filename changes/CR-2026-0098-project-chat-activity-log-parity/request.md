# Project-Chat Activity Log Parity

## Summary

Connect project chat’s existing provider-event stream to its existing `ActivityRepository`. Persist normalized provider events—including deltas—to the conversation’s append-only `events.jsonl`; continue writing only complete logical records to `transcript.jsonl`.

This is a narrow correction to CR-0097, not another storage redesign.

## Implementation Changes

- In the existing project-chat event sink, append every incoming normalized `TurnStreamEvent` before transcript projection or live publication.
- Add one focused conversation-repository method that wraps the event with its owning turn ID and calls the existing `ActivityRepository::append_event`.
- Keep derived `stream_delta` envelopes transient. Do not persist them because their underlying provider events will already be durable.
- Do not change node-execution storage, APIs, frontend behavior, transcript schemas, activity layout, or run presentation.
- For recovery, inspect only the existing uncommitted event suffix when reopening an interrupted conversation. Materialize a missing terminal logical unit once using its stable turn/segment identity; ignore partial deltas and already-committed units.
- Update the CR result wording to distinguish durable normalized provider events from transient UI envelopes.

The persisted event payload is the minimum needed for ownership and recovery:

```json
{
  "type": "provider_event",
  "turn_id": "turn-id",
  "event": { "...normalized TurnStreamEvent..." }
}
```

No new event hierarchy, generic framework, materializer rewrite, index, snapshot, migration, or background worker is introduced.

## Test Plan

- Drive the real project-chat producer with 50,000 content deltas and one completion; assert 50,001 provider events and one completed transcript unit.
- Assert no content delta is ever written to `transcript.jsonl`.
- Interrupt after persisting a terminal event but before its transcript append; reopen twice and assert recovery appends the logical unit exactly once.
- Assert partial events do not create transcript records.
- Assert existing live stream deltas, reconnect behavior, user messages, input requests, and completed tool calls remain unchanged.
- Run the focused storage and workspace conversation contracts, live-SSE contracts, Rust formatting check, and frontend conversation tests.

## Assumptions

- Existing post-cutover conversations are not backfilled.
- Normalized `TurnStreamEvent` data is sufficient for the detailed/debug log; raw provider transport frames are out of scope.
- Existing node-execution behavior is correct and remains untouched.
- No public API or frontend changes are expected.
