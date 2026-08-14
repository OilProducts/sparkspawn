# Shipped result

Implemented in-place generic run-tree recovery. Startup now validates durable
lineage, repairs legacy child placement metadata, resumes orphaned roots and
recursively reuses unacknowledged children, and consumes durable node responses
when checkpoints lag. Recovery failures use stable reason codes.

Linked children already named in a parent checkpoint are now resumed from
their own durable checkpoint as well; terminal linked children are reconciled
and externally launched live children remain observation-only. The recursive
path preserves the existing child identity and does not create a sibling.

Added typed `runtime.recovery_policy` (`rerun` by default, `pause` for explicit
retry), the durable `RecoveryDecisionRequired` event, child placement
inheritance, zeroed continuation usage, effective flow hashes, honest launch
failure metadata, and hash-manifest-based packaged-flow refresh that preserves
local edits.

Lineage integrity failures are excluded from the resume pass even when a
duplicate child invocation implicates a parent held in the original recovery
snapshot. Repeated recovery keeps the parent terminal with the stable
`recovery_ambiguous_child_invocation` code. Run creation hashes the exact
captured flow source at the storage boundary, covering roots, nested children,
and continuations uniformly.

Recovery-paused nodes remain durably waiting across repeated startups and
resume only after the retry route records explicit authorization. Lineage
lineage checks also reject parent-node or invocation metadata without a parent run
using the stable `recovery_missing_lineage` code. Restart-twice contract tests
cover both behaviors.

Pause is evaluated only after probing the checkpointed node's durable accepted
response. This ordering applies to roots and recursively recovered children, so
checkpoint lag is reconciled without requesting a retry; explicit retry still
resumes the same paused root and child identities in place.

Durable response reconciliation now uses the live node's context-write contract
and requires both a fully typed status artifact and response artifact. Missing,
malformed, or contract-invalid artifacts are therefore unaccepted and retain
the configured at-least-once rerun/pause behavior instead of suppressing work.

The process contract now launches the real `spark-server`, executes a generic
three-level nested run through HTTP and durable storage, kills the service at a
grandchild human gate, restarts it, and verifies recursive in-place completion
with every run ID and parent link preserved. Packaged-flow contracts also prove
that a stale seeded file refreshes from its recorded hash while an independently
edited file remains untouched.

Checked with `just test`.

Explicit pause-retry authorization is now durably consumed immediately before
both root and recursively recovered child execution begins. A crash before the
rerun produces an accepted durable response therefore returns the same run ID
and lineage to `RecoveryDecisionRequired` on the next startup and requires a
new explicit retry. Ambiguous child-invocation reconciliation now also
terminalizes every implicated child with the stable
`recovery_ambiguous_child_invocation` code, leaving no running orphan.
