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

## Validation

- Focused storage and workspace conversation contracts pass.
- Live-SSE and frontend conversation contracts pass.
- `just test` passed all reached workspace and live-SSE suites, then stopped on two pre-existing `spark-server` worker-process contract failures; both reproduce in isolation outside this change's storage/chat paths.
- Rust formatting passes.
