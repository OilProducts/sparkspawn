# Unified Conversation and Node-Execution Storage

## Summary

Use one shared append-only activity-storage contract for:

- a project-chat conversation;
- one concrete execution attempt of an LLM node.

Each activity resource owns exactly:

- `events.jsonl`: detailed provider/debug events, including stream deltas;
- `transcript.jsonl`: complete logical transcript records, never deltas.

A run is an orchestration container, not a transcript. Its root event log contains workflow events only. The Runs UI composes run, child-run, and node-execution resources for presentation.

This is a hard cutover with no migration or legacy compatibility code.

## Resource Ownership and Layout

- Give every node execution a stable identity containing:
  - run ID;
  - node ID;
  - global stage index;
  - retry attempt, starting at zero.
- Extend `NodeExecutionRequest` and emitted events to carry that complete identity.
- Store each attempt independently:

```text
run-root/
  events.jsonl
  logs/
    <node-id>/
      executions/
        <stage-index>-<attempt>/
          events.jsonl
          transcript.jsonl
          prompt.md
          response.md
          status.json
          initial-context.txt
```

- Repeated visits to a node receive different stage indexes.
- Retries of one visit retain the stage index and receive different attempt numbers.
- Synthetic LLM executions such as result summarization use the same storage contract.
- Non-LLM node attempts may use the same execution directory for artifacts and detailed events but do not create an empty transcript.
- Stop overwriting the current static `logs/<node-id>/` artifact files.

## Identical Transcript Semantics

- Implement one shared activity repository, event schema, transcript schema, materializer, reader, and live-update contract for project conversations and LLM-node executions.
- Use the existing `TranscriptTurn` and `TranscriptSegment` types for both.
- A node-execution transcript begins with its resolved prompt/input as a user turn.
- Append complete logical records immediately:
  - user messages and input answers;
  - assistant messages;
  - reasoning/thinking blocks;
  - plan blocks;
  - completed or failed tool calls;
  - request-user-input prompts;
  - compaction and agent events intentionally represented in transcripts.
- Transcript entries are full `turn_upsert` or `segment_upsert` records with revision, commit time, and source-event sequence.
- Full-record upserts are allowed for genuine state transitions; hydration applies last-write-wins by stable ID.
- Never append content deltas to `transcript.jsonl`.
- Require every provider’s terminal event to contain the complete logical unit.

## Detailed Events and Recovery

- Write provider/debug activity only to the owning execution’s `events.jsonl`.
- Remove `CodergenAdapter`, content-delta, reasoning-delta, and model-tool-delta events from the run-root journal.
- Keep the run-root `events.jsonl` limited to orchestration:
  - run lifecycle and outcome;
  - node-attempt start/completion/failure;
  - retries and routing;
  - checkpoints and gates;
  - child-run lifecycle.
- Append the detailed event before its semantic transcript record.
- On recovery, use transcript entries’ source-event sequences to inspect only the uncommitted execution-event suffix and append missing completed units idempotently.
- Partial units remain transient. On reconnect, completed history comes from `transcript.jsonl` and any unfinished unit is rebuilt only from the small event suffix following the last transcript commit.
- Use append locks and tail-derived dense sequences; add no snapshots, databases, indexes, watermark files, or compaction.

## Run Presentation and APIs

- Replace the run-level projected transcript with an execution inventory plus execution-scoped activity endpoints.
- Expose execution identity and status in run detail.
- Serve an execution transcript directly from its `transcript.jsonl`.
- Serve execution debug events directly from its `events.jsonl`.
- Publish the same transcript-upsert live envelope for project chat and executions, differing only in resource identity.
- Let the Runs UI:
  - group attempts under node labels;
  - display repeated executions separately;
  - merge orchestration events and execution transcript units into its activity presentation;
  - traverse child runs without copying or globally resequencing their storage.
- Remove `/segments` and the run-level combined-transcript authority after the frontend moves to execution-scoped transcripts.
- Keep source-local sequences; do not manufacture a combined parent/run cursor.

## Code Removal

- Delete run transcript reconstruction from run-root journals.
- Delete combined parent/child transcript projection and incremental segment-projection caches.
- Delete conversation `transcript.json` rewrites and its separate semantic journal implementation.
- Replace the conversation-specific and run-specific materializers with the shared activity repository.
- Remove static-node transcript grouping based only on node ID and retry counters.
- Remove duplicate transcript response models and frontend parsing paths.
- Update result summarization to read execution transcripts and artifacts rather than replaying the run journal.

## Tests and Acceptance

- Verify equivalent chat and node-execution events produce identical transcript JSONL records.
- Verify 50,000 deltas plus one completion yield 50,001 detailed events and one completed transcript segment.
- Verify repeated visits to one node create separate execution directories and transcripts.
- Verify retries create separate attempt directories without overwriting the failed attempt.
- Verify prompts become user turns and completed provider units become correctly ordered segments.
- Verify run-root events contain no provider stream deltas.
- Verify crash recovery appends a missing completed unit once without replaying committed history.
- Verify parent and child run presentation composes independently owned execution resources.
- Verify tool-output bounding and full-output artifact access remain intact.
- Add a large-run regression test proving execution transcript hydration scales with logical-unit count and never reads the run-root journal.
- Add architecture tests preventing run-level transcript projection and separate chat/run transcript writers from returning.

## Assumptions

- One execution attempt is the transcript ownership boundary.
- A retry is a new execution attempt.
- A run itself has no transcript.
- Run orchestration events and node-execution activity are separate resources joined only by presentation.
- Existing pre-cutover activity storage is intentionally unsupported after the hard cutover.
