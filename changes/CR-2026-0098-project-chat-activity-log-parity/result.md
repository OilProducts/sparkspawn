---
id: CR-2026-0098-project-chat-activity-log-parity
title: Project-Chat Activity Log Parity
status: completed
type: fix
changelog: internal
---

## Summary

Project chat now durably appends every normalized provider event, including content deltas, before transcript projection or live publication. Delta-derived `stream_delta` UI envelopes remain transient, while `transcript.jsonl` continues to contain only complete logical records.

Interrupted conversations recover terminal durable provider events from only the uncommitted activity suffix, using stable turn and segment identities so a missing logical unit remains visible on every reopen while partial deltas and unrelated in-flight transcript batches remain hidden. Derived UI envelopes remain transient.

Provider-event persistence failures now fail the live turn before final transcript publication. Recovered transcript records retain the actual terminal provider-event sequence and are published through the existing conversation commit boundary.

## Validation

- Focused storage and workspace conversation contracts pass.
- Live-SSE and frontend conversation contracts pass.
- Recovery provenance and live write-failure regression contracts pass.
- `just test` reaches two unrelated source-checkout guard failures in the
  `spark-cli` process contracts; the same guard returns the expected error when
  invoked directly.
- Rust formatting passes.
