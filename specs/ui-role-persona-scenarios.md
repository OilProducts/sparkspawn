# UI Role Persona Scenarios

Checklist item: [3.1-01]

Spec reference: `ui-spec.md` section `3.1 User Roles`.

This document captures concrete role-oriented scenarios and measurable UI success criteria for the four primary personas.

## Pipeline Author Scenario

### Scenario
- Given an active project is selected and a flow is open in Editor mode
- When the author adds/edits graph, node, and edge settings and runs validation
- Then the author can save a spec-valid flow without switching to raw DOT for required fields

### Concrete UI Success Criteria
- Structured inspector controls cover required graph/node/edge attributes for the edited flow.
- Validation messages identify blocking issues before save and clear when resolved.
- Save status is visible (`saved`, `saving`, or `error`) with no silent-loss behavior.

## Operator Scenario

### Scenario
- Given a spec-valid flow in an active project
- When the operator starts a run and monitors execution
- Then the operator can observe run lifecycle, runtime stream output, and cancel transitions from the UI

### Concrete UI Success Criteria
- Run start is available only in project scope and reflects start/disabled/loading states.
- Live run output and status updates are visible during execution.
- Destructive controls (cancel) require explicit confirmation and show terminal transition state.

## Reviewer/Auditor Scenario

### Scenario
- Given a completed or failed run in project history
- When the reviewer opens run details for inspection
- Then the reviewer can inspect artifacts, context, events, and graph-linked execution evidence

### Concrete UI Success Criteria
- Run history is discoverable and supports opening a specific run deterministically.
- Inspector surfaces expose checkpoint/context/event/artifact evidence without CLI-only dependency.
- Failure and routing decisions are explainable from visible UI data.

## Project Owner/Planner Scenario

### Scenario
- Given multiple registered projects and an active project context
- When the planner iterates on project-scoped spec/plan/build workflow steps
- Then the planner can manage project context, review progress, and continue within the same scoped loop

### Concrete UI Success Criteria
- Active project identity is persistent and visible in top navigation.
- Project-scoped conversation/spec/plan/run entry points are directly accessible from first-class UI areas.
- Context isolation prevents cross-project conversation or artifact leakage during navigation and re-run.
