# UI Frontend Test Migration Plan

## Goal
Move the frontend test strategy from brittle source-snippet assertions to a maintainable test pyramid:

1. Unit/component behavior tests in `frontend` (Vitest + React Testing Library).
2. Browser smoke journeys in Playwright (`frontend/e2e/smoke/*`).
3. Narrow Python contract tests only for backend/frontend parser and release-gate contracts.

## Current Baseline
- Frontend browser smoke coverage is concentrated in one file:
  - `frontend/e2e/ui-smoke.spec.ts`
- UI-oriented Python integration tests are spread across 80 files:
  - `tests/integration/test_ui_*.py`

## Target Layout

```text
frontend/
  src/
    components/__tests__/
      AppShell.test.tsx
      ProjectsPanel.test.tsx
      ProjectSpecWorkflow.test.tsx
      ExecutionControls.test.tsx
      GraphSettings.test.tsx
      InspectorAndNodeAuthoring.test.tsx
      EditorSaveState.test.tsx
    store/__tests__/
      projectScope.test.ts
    lib/__tests__/
      graphAttrValidation.test.ts
  e2e/
    fixtures/
      app.fixture.ts
      flows.fixture.ts
      routes.fixture.ts
    smoke/
      editor-diagnostics.spec.ts
      editor-save.spec.ts
      execution-lifecycle.spec.ts
      runs-observability.spec.ts

tests/
  contracts/
    frontend/
      test_dot_roundtrip_contracts.py
      test_raw_dot_baseline_fixtures.py
      test_stylesheet_parser_contracts.py
    docs/
      test_ui_spec_artifacts.py
    release_gate/
      test_ui_required_feature_release_gate.py
```

## Move Map (File-by-File)

### Move to `frontend/src/components/__tests__/AppShell.test.tsx`
- `tests/integration/test_ui_explainability_views.py`
- `tests/integration/test_ui_global_regions_canvas_primary_zone.py`
- `tests/integration/test_ui_global_regions_top_navigation_context.py`
- `tests/integration/test_ui_information_architecture_areas.py`
- `tests/integration/test_ui_progressive_disclosure.py`
- `tests/integration/test_ui_projects_top_nav_active_project_indicator.py`

### Move to `frontend/src/components/__tests__/ProjectsPanel.test.tsx`
- `tests/integration/test_ui_project_registry_uniqueness.py`
- `tests/integration/test_ui_projects_workspace_duplicate_path_prevention.py`
- `tests/integration/test_ui_projects_workspace_entry_points.py`
- `tests/integration/test_ui_projects_workspace_glanceable_metadata.py`
- `tests/integration/test_ui_projects_workspace_recent_favorite_switching.py`
- `tests/integration/test_ui_projects_workspace_registration.py`

### Move to `frontend/src/components/__tests__/ProjectSpecWorkflow.test.tsx`
- `tests/integration/test_ui_project_scoped_ai_conversation_surface.py`
- `tests/integration/test_ui_project_scoped_conversation_history.py`
- `tests/integration/test_ui_project_scoped_proposal_conversation_isolation.py`
- `tests/integration/test_ui_project_scoped_spec_edit_apply_confirmation.py`
- `tests/integration/test_ui_project_scoped_spec_edit_proposal_preview.py`
- `tests/integration/test_ui_project_scoped_spec_edit_reject_non_mutating.py`

### Move to `frontend/src/components/__tests__/ExecutionControls.test.tsx`
- `tests/integration/test_ui_build_workflow_plan_gate.py`
- `tests/integration/test_ui_execution_run_initiation.py`
- `tests/integration/test_ui_execution_runtime_controls.py`
- `tests/integration/test_ui_global_regions_execution_footer_stream.py`
- `tests/integration/test_ui_operational_safety_status_transitions.py`
- `tests/integration/test_ui_plan_gate_controls.py`
- `tests/integration/test_ui_single_select_semantics.py`
- `tests/integration/test_ui_spec_plan_workflow_launch.py`

### Move to `frontend/src/components/__tests__/GraphSettings.test.tsx`
- `tests/integration/test_ui_graph_attr_inline_help_precedence.py`
- `tests/integration/test_ui_graph_level_attribute_completeness.py`
- `tests/integration/test_ui_raw_dot_mode_handoff.py`
- `tests/integration/test_ui_stylesheet_editor_syntax_highlighting.py`
- `tests/integration/test_ui_stylesheet_selector_effective_preview.py`

### Move to `frontend/src/components/__tests__/InspectorAndNodeAuthoring.test.tsx`
- `tests/integration/test_ui_direct_manipulation_persistence_hooks.py`
- `tests/integration/test_ui_inspector_context_driven_selection.py`
- `tests/integration/test_ui_inspector_interaction_patterns.py`
- `tests/integration/test_ui_node_shape_type_override.py`
- `tests/integration/test_ui_structured_form_editing.py`

### Move to `frontend/src/components/__tests__/EditorSaveState.test.tsx`
- `tests/integration/test_ui_live_state_updates.py`
- `tests/integration/test_ui_no_silent_loss_save_states.py`
- `tests/integration/test_ui_save_failure_remediation.py`
- `tests/integration/test_ui_save_state_indicator.py`
- `tests/integration/test_ui_unsaved_edits_reflect_immediately.py`

### Move to `frontend/src/store/__tests__/projectScope.test.ts`
- `tests/integration/test_ui_active_project_enforcement.py`
- `tests/integration/test_ui_cross_project_isolation.py`
- `tests/integration/test_ui_cross_project_isolation_behavior.py`
- `tests/integration/test_ui_project_scope_boundaries.py`
- `tests/integration/test_ui_project_switch_context_reset.py`
- `tests/integration/test_ui_projects_workspace_active_project_deep_link_restore.py`
- `tests/integration/test_ui_route_restoration.py`

### Move to `frontend/src/lib/__tests__/graphAttrValidation.test.ts`
- `tests/integration/test_ui_graph_attr_validation_normalization.py`

### Move to Playwright smoke suites

#### `frontend/e2e/smoke/editor-diagnostics.spec.ts`
- `tests/integration/test_ui_diagnostic_blocking_rules.py`
- `tests/integration/test_ui_diagnostic_navigability_select_focus.py`
- `tests/integration/test_ui_inline_diagnostic_badges.py`
- `tests/integration/test_ui_inspector_field_level_diagnostic_mapping.py`
- `tests/integration/test_ui_validation_panel_filter_sort.py`

#### `frontend/e2e/smoke/editor-save.spec.ts`
- `tests/integration/test_ui_save_semantic_equivalence.py`

#### `frontend/e2e/smoke/execution-lifecycle.spec.ts`
- `tests/integration/test_ui_plan_build_live_surfaces.py`
- `tests/integration/test_ui_workflow_failure_rerun.py`

#### `frontend/e2e/smoke/runs-observability.spec.ts`
- `tests/integration/test_ui_human_gate_prompt_discoverability.py`
- `tests/integration/test_ui_run_artifact_panel.py`
- `tests/integration/test_ui_run_checkpoint_panel.py`
- `tests/integration/test_ui_run_context_panel.py`
- `tests/integration/test_ui_run_event_timeline_panel.py`
- `tests/integration/test_ui_run_history_traceability.py`
- `tests/integration/test_ui_run_summary_panel.py`

### Consolidate Python contract tests

#### `tests/contracts/frontend/test_dot_roundtrip_contracts.py`
- `tests/integration/test_ui_edge_attributes_editor.py`
- `tests/integration/test_ui_graph_attr_round_trip.py`
- `tests/integration/test_ui_node_advanced_attrs_editor.py`
- `tests/integration/test_ui_node_handler_round_trip.py`
- `tests/integration/test_ui_node_manager_loop_authoring.py`
- `tests/integration/test_ui_tool_hook_authoring.py`

#### `tests/contracts/frontend/test_raw_dot_baseline_fixtures.py`
- `tests/integration/test_ui_raw_dot_baseline_fixtures.py`

#### `tests/contracts/frontend/test_stylesheet_parser_contracts.py`
- `tests/integration/test_ui_stylesheet_parse_lint_feedback.py`

### Consolidate docs and release-gate tests

#### `tests/contracts/docs/test_ui_spec_artifacts.py`
- `tests/integration/test_ui_advanced_feature_access.py`
- `tests/integration/test_ui_parity_complete_user_journey_script.py`
- `tests/integration/test_ui_parity_risk_report.py`
- `tests/integration/test_ui_raw_dot_required_config_report.py`
- `tests/integration/test_ui_role_persona_scenarios.py`
- `tests/integration/test_ui_runtime_parser_boundaries.py`
- `tests/integration/test_ui_spec_first_behavior_mapping.py`

#### `tests/contracts/release_gate/test_ui_required_feature_release_gate.py`
- `tests/integration/test_ui_required_feature_release_gate.py`

## Execution Phases

### Phase 1 (start now)
- Add Vitest + RTL test harness.
- Add shared test setup utilities.
- Migrate first slice (`ProjectsPanel` + project path validation behavior) from Python snippet checks.

#### Phase 1 Progress (2026-03-03)
- Added Vitest + RTL dependencies and config in `frontend`:
  - `frontend/vitest.config.ts`
  - `frontend/src/test/setup.ts`
  - `frontend/package.json` scripts: `test:unit`, `test:unit:watch`
- Added first behavior-driven frontend unit tests:
  - `frontend/src/components/__tests__/ProjectsPanel.test.tsx`
  - `frontend/src/store/__tests__/projectScope.test.ts`
- Added convenience runner:
  - `just frontend-unit`
- Legacy Python snippet tests are still present during transition and will be removed once equivalent Vitest coverage is migrated in batches.

### Phase 2
- Split Playwright smoke file into `smoke/*` suites and shared fixtures.
- Remove Python tests that only check whether smoke test names/screenshots exist.

#### Phase 2 Progress (2026-03-03)
- Split monolithic smoke spec into:
  - `frontend/e2e/smoke/editor-diagnostics.spec.ts`
  - `frontend/e2e/smoke/editor-save.spec.ts`
  - `frontend/e2e/smoke/execution-lifecycle.spec.ts`
  - `frontend/e2e/smoke/runs-observability.spec.ts`
- Added shared smoke helpers:
  - `frontend/e2e/fixtures/smoke-helpers.ts`
- Removed legacy `frontend/e2e/ui-smoke.spec.ts`.
- Removed legacy Python smoke-reference tests that only validated smoke naming/screenshot-string presence.

### Phase 3
- Consolidate parser/round-trip Python tests into `tests/contracts/frontend/*` with shared helper fixtures.
- Remove duplicate compile/probe code from individual files.

#### Phase 3 Progress (2026-03-03)
- Added consolidated frontend contract test suite under:
  - `tests/contracts/frontend/test_dot_roundtrip_contracts.py`
  - `tests/contracts/frontend/test_raw_dot_baseline_fixtures.py`
  - `tests/contracts/frontend/test_stylesheet_parser_contracts.py`
- Added `tests/contracts/conftest.py` to keep repo-root imports stable for targeted contract runs.
- Removed superseded legacy integration contract files from `tests/integration/test_ui_*.py`.

### Phase 4
- Merge docs and release-gate tests into `tests/contracts/docs/*` and `tests/contracts/release_gate/*`.
- Delete superseded legacy `tests/integration/test_ui_*.py` files.

#### Phase 4 Progress (2026-03-03)
- Added:
  - `tests/contracts/docs/test_ui_spec_artifacts.py`
  - `tests/contracts/release_gate/test_ui_required_feature_release_gate.py`
- Removed all remaining legacy `tests/integration/test_ui_*.py` files.
- Validation complete across:
  - `npm --prefix frontend run test:unit`
  - `npm --prefix frontend run ui:smoke -- --list`
  - `uv run pytest -q`

## Acceptance Criteria
- Frontend UI behavior coverage primarily lives in Vitest + Playwright.
- Python UI tests remain only for cross-runtime contracts and governance checks.
- No test asserts checklist checkbox state for feature correctness.
- Playwright smoke suites do not mutate tracked flow fixtures.
