# Result

Large completed tool outputs are now externalized once before event persistence. Project-chat and node-execution events retain an 8 KiB UTF-8-safe preview plus the exact size and activity-local artifact reference; transcript materialization preserves that same representation without creating a second sidecar.

Activity tail reads now scan backward until they have a complete final JSONL record instead of assuming every record fits within 64 KiB. Existing large inline logs remain valid and require no migration.

## Validation

- Oversized event and transcript tail regressions pass.
- Shared event/transcript artifact regressions pass for storage, project chat, and node execution.
- Storage, attractor-runtime, and workspace conversation contract suites pass.
- Rust formatting passes.
