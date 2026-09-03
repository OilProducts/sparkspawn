# Deterministic Turn Finalization — Result

Manual completion of implement-change run `run-18ce7764adc5e638` (the run's
child produced the transient-segment finalizer and frontend `yielded` typing;
its evaluate node failed the patch as incomplete, and the flow could not
relaunch the child due to the manager-loop child-reuse defect). The four
outstanding gaps from that evaluation are implemented here.

## Implemented

- **Stable segment identity** (`spark-common/src/segments.rs`,
  `spark-storage/src/conversation/identity.rs`): agent-event ids derive only
  from durable provider facts — app turn + item id when item-backed, app turn +
  event kind for singleton lifecycle events (`turn_completed` et al.), and the
  appended provider-event sequence for repeatable itemless events. No segment
  id derives from the mutable order counter; replayed events converge on their
  existing segments (order preserved from first observation).

- **One deterministic projector with replay-stable inputs**
  (`spark-workspace/src/conversations.rs`): live ingestion threads the
  provider append provenance (`committed_at` + sequence) into materialization
  and turn-boundary finalization; the wall-clock `iso_now()` finalization
  timestamp is gone. Live projection is now a fixed point for recovery replay
  (contract-tested: reopen after a live turn produces zero mutations).

- **Append-only tombstones + projection-version marker**
  (`spark-storage/src/conversation/{mutations,journal,commit}.rs`,
  `activity.rs`, `records.rs`): `SegmentTombstoned` mutations journal as
  `segment_tombstone` lines, append as `TranscriptRecord::SegmentTombstone`,
  and apply during hydration. `TranscriptTurn.projection_version` records the
  projector schema a turn was last projected/repaired under.

- **Historical repair on reopen**
  (`spark-storage/src/workspace_conversations.rs`): terminal turns below the
  current projection version showing stuck tool segments or order-derived
  lifecycle ids are rebuilt by replaying their raw provider activity through
  the shared projector; the diff lands as corrective upserts plus tombstones
  through the normal commit path, the turn is stamped, and a second reopen is
  byte-identical. Raw provider events are never modified (append-only prefix
  asserted in tests). Safety rails: a turn with no recorded provider activity
  is never touched (there is no authority to rebuild from), and removal is
  reserved for `segment-agent-event-` lifecycle markers — content and tool
  segments are only ever corrected in place through their stable ids, since
  delta-only content and model-tool items can be richer than a terminal-event
  replay reproduces.

- **Frontend**: `segment_tombstone` stream events parse and apply (segment
  removal + timeline rebuild); tool-call parsing accepts `yielded` and carries
  `completion_reason` (previously coerced to `completed`); the timeline
  trusts canonical order for final-answer placement instead of scanning
  backwards past visible work rows; `yielded` renders as neutral terminal
  work.

## Tests

- `spark-common`: stable singleton lifecycle identity under replay,
  sequence-scoped repeatable itemless ids, successful-turn yield (output
  retained, idempotent), failed-turn `tool_completion_missing`, normal
  terminal tools untouched.
- `spark-storage/tests/contracts/transcript_repair_contracts.rs`: the
  navy-hazel malformation (two stale running tool starts tail-appended after
  the final answer + duplicate order-derived `turn_completed` markers)
  converges to canonical stream positions with yielded statuses, one stable
  lifecycle marker, tombstones for the legacy ids, untouched provider
  activity, and an idempotent second reopen; failed-turn variant keeps the
  unmatched start visible as `failed`/`tool_completion_missing` at stream
  position.
- `spark-workspace` process contracts: live projection is a canonical fixed
  point for recovery replay.
- Frontend: tombstone event parse + reducer application, yielded parse with
  completion reason, timeline final-answer ordering and neutral yielded
  rendering.

## Notes

- The manager-loop child-reuse defect that stranded the original run
  (completed child adopted unconditionally on node re-entry, introduced by
  CR-0100's recovery hardening in `14c75dd`) is out of scope here and needs
  its own change request, together with a failure-edge attempt cap.
