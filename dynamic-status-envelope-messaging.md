# Shared Dynamic `status_envelope` Contract Messaging

## Summary
Replace the duplicated hard-coded `status_envelope` wording with one shared formatter that generates the node-specific `context_updates` rules from the resolved `spark.writes_context` contract.

The shared formatter should be used in both places that currently drift:
- the initial Codergen prompt appendix
- the same-thread repair prompt after a contract violation

The formatter should be strict when no writes are allowed:
- keep the generic status-envelope schema
- add node-specific guidance saying this node must not emit `context_updates`
- when writes are allowed, list the exact normalized keys and state that no others are permitted

## Key Changes
### Shared contract formatter
- Introduce one internal shared helper for `status_envelope` messaging that accepts the resolved write contract and returns the node-specific contract text.
- Keep the shared formatter responsible for:
  - whether `context_updates` are allowed for this node
  - the exact allowed keys, in deterministic normalized order
  - the flat dotted-key rule for `context_updates`
- Do not try to unify the entire repair prompt and initial prompt into one string builder; the repair prompt still needs its own framing (`validation error`, `re-emit only`, `do not do new work`, previous invalid answer). Share the contract-rules section, not the whole message.

### Initial prompt behavior
- Update the Codergen `status_envelope` appendix to include:
  - the generic schema lines
  - the shared node-specific `context_updates` rules from the formatter
- Empty/missing `spark.writes_context`:
  - explicitly say this node must not emit `context_updates`
  - remove the current generic encouragement to put machine-readable details there
- Non-empty `spark.writes_context`:
  - explicitly list the exact allowed keys
  - keep the flat dotted-key examples

### Repair prompt behavior
- Update the backend repair prompt to embed the same shared node-specific contract text.
- Empty allowlist violations:
  - explicitly instruct the model to re-emit the same decision with no `context_updates`
- Non-empty allowlist violations:
  - explicitly instruct the model to re-emit using only the listed keys
- Preserve the existing repair constraints:
  - no new repo work
  - same substantive decision
  - same routing unless contract correction requires otherwise

### Scope boundaries
- Do not change runtime enforcement, merge semantics, or `Outcome` parsing.
- Do not add a new diagnostics channel in this change.
- Do not change `spark.reads_context`; it already has deterministic prompt projection.
- No external/public API changes; this is an internal prompt-construction refactor plus docs/tests.

### Docs
- Update the Attractor spec and Spark authoring docs to describe the dynamic prompt behavior:
  - `status_envelope` includes node-specific write guidance derived from `spark.writes_context`
  - nodes without declared writes are prompted not to emit `context_updates`
  - runtime enforcement remains the source of truth if the model still violates the contract

## Test Plan
- Handler tests:
  - node with declared writes gets an initial prompt that lists the exact allowed keys
  - node with no declared writes gets an initial prompt that says it must not emit `context_updates`
  - flat dotted-key examples appear only in the write-allowed case
- Backend repair tests:
  - empty-allowlist violation produces a repair prompt that says to re-emit with no `context_updates`
  - non-empty allowlist violation produces a repair prompt that lists the exact allowed keys
  - repair prompt still includes the previous invalid answer and “do not do new repository work” framing
- Consistency tests:
  - assert the initial prompt and repair prompt both use the same shared contract-text generator
  - pin one no-write case and one write-allowed case so future wording drift is caught
- Validation:
  - `uv run pytest -q tests/handlers/test_codergen_handler.py tests/api/test_backend_invariance.py`
  - `uv run pytest -q`

## Assumptions And Defaults
- Use the resolved normalized `spark.writes_context` contract as the sole source of truth for node-specific prompt wording.
- Keep the generic top-level schema unchanged; node-specific rules narrow how `context_updates` may be used.
- Empty or missing `spark.writes_context` means the prompt should tell the model not to emit `context_updates`, even though the parser still tolerates an empty object structurally.
- The shared helper should live in a neutral internal module reachable by both the Codergen handler and the backend repair path, rather than duplicating strings across those files.

