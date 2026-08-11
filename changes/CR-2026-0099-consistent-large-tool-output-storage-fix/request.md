# Consistent Large Tool-Output Storage Fix

## Summary

Keep full tool output once as an activity-local artifact, while both `events.jsonl` and `transcript.jsonl` store the same bounded preview and artifact reference. Independently remove the invalid 64 KiB JSONL-record assumption so all valid existing logs remain readable.

## Implementation Changes

- Consolidate the existing tool-output externalization logic in `spark-storage` into one shared helper using the existing 8 KiB inline limit, UTF-8-safe preview, safe artifact names, and atomic sidecar writes.
- Before appending a completed tool event, externalize oversized output and replace every duplicated inline representation of that output with:
  - bounded `output`;
  - exact `output_size`;
  - `output_truncated: true`;
  - one shared relative `output_artifact`.
- Apply that same producer-side behavior to project-chat provider events and node-execution adapter events. The later transcript append must preserve the supplied artifact reference and must not rewrite or duplicate the sidecar.
- Keep small outputs inline. Keep non-tool events, deltas, event ordering, transcript completion boundaries, APIs, and presentation behavior unchanged.
- Replace `tail_record`’s one-chunk assumption with backward chunk scanning that assembles the complete final JSONL record before parsing. Preserve cheap tail-only reads for normal records and existing partial-write recovery.

## Interfaces and Compatibility

- No public HTTP, JSONL record type, or frontend interface changes.
- `output_artifact`, `output_size`, and `output_truncated` retain their existing meanings.
- Existing inline event records remain valid and readable; no migration or log rewriting is required.
- New oversized tool events and their transcript records reference one full-output artifact beneath the owning conversation or node-execution activity directory.

## Test Plan

- Append a single event line larger than 64 KiB, then append a transcript record referencing it; assert both succeed and the source sequence is recognized.
- Repeat with a large final transcript line and verify revision discovery.
- Preserve the existing partial-tail test to prove interrupted JSONL writes are still truncated safely.
- Drive oversized completed tool output through both project chat and node execution; assert:
  - one full sidecar contains the exact output;
  - event and transcript contain bounded UTF-8-safe previews;
  - both contain identical artifact metadata;
  - no second sidecar is created during transcript publication.
- Verify small outputs remain inline and the existing 50,000-delta/transcript and recovery contracts remain green.
- Run focused storage/workspace/runtime contracts, formatting, and the normal repository test gate.

## Assumptions

- The existing 8 KiB transcript inline limit becomes the shared inline limit for tool output in both durable files.
- “Detailed event log” requires lossless access to full output, not necessarily inline duplication.
- The interrupted Understory logs need no repair. After rebuilding with this fix, continue the failed parent from its durable checkpoint.
