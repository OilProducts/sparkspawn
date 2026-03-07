# Advanced Feature Access Guardrails

Checklist item: [1.3-03]

This note defines how the UI keeps advanced feature access enabled in alignment with `ui-spec.md`.

## Spec Anchor

- `ui-spec.md` section `1.3 Non-Goals` includes: "Hiding advanced features in favor of a simplified-only mode."
- `ui-spec.md` section `2. Design Principles` allows progressive disclosure but requires full access.

## Guardrail Rules

1. Required controls must remain accessible in the UI for all spec-required behaviors.
2. Progressive disclosure is allowed (for example collapsible advanced panels), but collapsed state must not remove required spec controls.
3. Any "basic" presentation mode may simplify defaults, but it must not remove required spec controls from reachable UI paths.
4. Raw DOT remains available as an advanced editing modality and must not be the only path for controls already exposed in structured UI.

## Verification approach

- Keep this guardrail document and checklist linkage under test.
- Preserve integration coverage that fails if checklist item `[1.3-03]` is not marked complete.
- When adding new advanced controls, ensure they are reachable without hidden feature flags that disable required access.
