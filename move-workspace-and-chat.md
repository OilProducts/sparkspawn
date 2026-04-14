# Move Workspace Under `spark` and Split Chat Orchestration

## Summary

Refactor the current top-level `workspace` package into Spark-owned subpackages with a hard import cutover:

- move workspace state, routes, flow catalog, triggers, and conversation persistence under `spark.workspace`
- move agent/session/prompt orchestration under `spark.chat`
- keep the public `/workspace` HTTP surface, the runtime data layout under `SPARK_HOME/workspace`, and existing CLI/API behavior unchanged
- do not keep Python compatibility aliases for the old `workspace.*` import paths

This change is a namespace and layering cleanup, not a product rename.

## Key Changes

### Package and namespace split

Adopt this target layout:

- `src/spark/workspace/`
  - `api.py`
  - `storage.py`
  - `flow_catalog.py`
  - `triggers.py`
  - `attractor_client.py`
  - `conversations/`
    - `models.py`
    - `repository.py`
    - `artifacts.py`
    - `utils.py`
- `src/spark/chat/`
  - `service.py`
  - `session.py`
  - `prompt_templates.py`
  - `response_parsing.py` or equivalent chat-runtime helper module

Remove the top-level `src/workspace/` package after all imports are updated.

### Ownership and boundary rules

Move these responsibilities into `spark.workspace`:

- project registry and project filesystem layout
- workspace flow discovery and launch policy state
- trigger definitions/runtime
- conversation state models and persistence
- conversation-linked artifact persistence for flow run requests and direct launches
- the mounted `/workspace` router

Move these responsibilities into `spark.chat`:

- `ProjectChatService`
- Codex app session/process plumbing
- chat prompt template loading and fixed prompt frame
- chat response parsing and live event orchestration
- Spark packaged-guide lookups used by chat

Split the current `project_chat_common.py` by responsibility instead of moving it wholesale:
- generic conversation/state helpers go to `spark.workspace.conversations`
- Spark/Codex/chat-runtime helpers go to `spark.chat`

### Composition and imports

Update composition so `spark.app` owns the full assembly:

- import the workspace router from `spark.workspace.api`
- import `ProjectChatService` from `spark.chat.service`
- continue mounting the workspace API under `/workspace`
- continue injecting the chat service into the workspace router through dependencies rather than moving chat ownership back into Attractor

Update repo imports/tests/docs to the new `spark.*` paths in one cut:
- no `workspace.*` compatibility modules
- no re-export shims
- remove `workspace*` from setuptools package discovery and rely on `spark*` for the moved code

### Naming cleanup

Rename the stale `project_chat_*` modules while moving them so the new structure matches responsibility:

- state/data modules become `spark.workspace.conversations.*`
- orchestration/runtime modules become `spark.chat.*`

Keep the product term “workspace” for the public API/spec/docs surface:
- retain `/workspace/...`
- retain `spark-workspace.md`
- retain runtime directories like `SPARK_HOME/workspace/...`

## Public Interfaces and Contract Changes

- Python import surface changes:
  - old `workspace.*` imports are removed
  - new imports live under `spark.workspace.*` and `spark.chat.*`
- No HTTP route changes:
  - `/workspace/api/...` remains unchanged
- No CLI behavior changes:
  - `spark`, `spark-server`, and their current commands remain unchanged
- No runtime storage layout changes:
  - keep existing `SPARK_HOME/workspace/...` paths and file formats

## Test Plan

Run full verification with:

- `uv run pytest -q`

Update and/or add coverage for:

- product app composition still mounting `/workspace` and serving the same workspace endpoints
- project chat endpoints and conversation behavior still working through the unchanged `/workspace/api/...` surface
- CLI behavior still targeting the same `/workspace/api/...` URLs
- trigger, flow catalog, and project metadata tests using the new `spark.workspace.*` imports
- packaging/import sanity so the installed artifact no longer exposes a top-level `workspace` package but does expose the moved `spark.workspace` and `spark.chat` modules

## Assumptions and Defaults

- The package is still alpha, so a hard Python import cutover is acceptable.
- `workspace` is treated as a Spark subsystem, not an independent reusable top-level package.
- Chat orchestration is treated as a separate Spark subsystem from workspace state/persistence.
- `spark_common` is out of scope for this refactor and stays as-is.
- This change should update repo docs/spec path references where they mention `src/workspace/...`, but it should not rename the user-facing workspace concept.

