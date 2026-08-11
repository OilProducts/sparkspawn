---
id: CR-2026-0097-unified-conversation-and-node-execution-storage
title: Unified Conversation and Node-Execution Storage
status: completed
type: refactor
changelog: internal
---

## Summary

Completed the hard cutover to a shared append-only activity repository for project conversations and individual LLM node-execution attempts. Runs now retain orchestration events while execution-owned resources retain detailed provider events and full-record transcript upserts.

## Validation

- `cargo fmt --all -- --check` passed.
- Storage, runtime, API, workspace, and HTTP package tests passed, including the 50,001-event activity contract and repeated-visit/retry execution-storage coverage.
- The frontend build and 383 frontend unit tests passed.

## Shipped Changes

- Added the shared `ActivityRepository` and transcript/event schemas used by conversations and node executions.
- Stored each node visit and retry under `logs/<node-id>/executions/<stage-index>-<attempt>/`, with execution-scoped artifacts, status, events, and LLM transcripts.
- Added execution inventory, transcript, debug-event, and live transcript-upsert surfaces; updated the Runs UI and clients to compose execution activity with run orchestration.
- Moved result and usage reads to execution-owned records while retaining bounded tool previews and full-output artifacts.
- Removed run-level transcript reconstruction, segment projection/cache paths, legacy conversation transcript migration/rewrites, and the run `/segments` authority.
- Updated storage, runtime, API, workspace, HTTP, frontend, and architecture/spec contract coverage for the new ownership model.
