# Run-Scoped Container Environments

## Summary

Make `local_container` executions use one container for the duration of an uninterrupted pipeline execution. All nodes and retries will share installed packages and other container-local state. Do not expose lifecycle configuration in flow definitions or execution profiles yet.

## Implementation Changes

- Construct the production `ContainerizedNodeExecutor` with its existing `keep_container_open()` behavior.
- Reuse that container for every node, retry, and final result-summary step in the pipeline.
- Retain existing bind mounts for durable workspace and run artifacts.
- Remove the container when the executor is dropped at completion, failure, cancellation, or pause.
- A resumed or continued execution starts a fresh container; dependencies needed across restarts must still be baked into the image.
- Make no flow-schema, public API, or execution-profile changes. If per-node isolation becomes necessary later, add it as execution-profile policy rather than flow YAML.

## Test Plan

- Execute a multi-node container flow and assert one `docker run`, multiple `docker exec` calls, and final cleanup.
- Verify container-local state created by one node is observable by the next.
- Verify retries reuse the same container.
- Verify normal completion and node failure both remove the container.
- Verify separate runs receive separate containers.
- Preserve existing placement, mount, event-streaming, and run-record contract tests.

## Assumptions

- “Shared environment” means one uninterrupted execution attempt; pause/resume and explicit continuation create a new environment.
- Run containers remain isolated from other runs.
- Network and privilege policy remain properties of the selected execution profile/image, not the flow.
- No current flow intentionally depends on resetting system state between nodes.
