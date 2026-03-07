# Raw DOT Required Configuration Report

Checklist item: [1.1-01]

Date: 2026-03-03

## Scope

This report lists configuration required by [`ui-spec.md`](/Users/chris/tinker/sparkspawn/specs/ui-spec.md) that is still not authorable through first-class UI controls, forcing users to leave the UI and edit raw DOT.

## Current Required Raw-DOT Surfaces

| Spec anchor | Required configuration | Why raw DOT is currently required | Evidence in current UI code |
| --- | --- | --- | --- |
| `ui-spec.md` §6.4, Appendix B (`B-03`, `B-04`, `B-05`) | `subgraph`, `node[...]` defaults, `edge[...]` defaults | Canvas and inspectors currently operate on graph, node, and edge instances only, with no structured CRUD for subgraphs or scoped default blocks. | [`frontend/src/components/Editor.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/Editor.tsx), [`frontend/src/components/Sidebar.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/Sidebar.tsx), [`frontend/src/lib/dotUtils.ts`](/Users/chris/tinker/sparkspawn/frontend/src/lib/dotUtils.ts) |
| `ui-spec.md` §11.4 (`11.4-01`, `11.4-02`, `11.4-03`) | unknown-valid extension attributes | The structured model only supports a fixed attribute set and serializer output is hard-coded to known keys, so users must use raw DOT to author/preserve required project-specific extension attrs until the generic advanced key/value editor exists. | [`frontend/src/store.ts`](/Users/chris/tinker/sparkspawn/frontend/src/store.ts), [`frontend/src/components/GraphSettings.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/GraphSettings.tsx), [`frontend/src/components/Sidebar.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/Sidebar.tsx), [`frontend/src/lib/dotUtils.ts`](/Users/chris/tinker/sparkspawn/frontend/src/lib/dotUtils.ts) |

## Notes

- This report documents where users currently leave structured UI to raw DOT for required configuration.
- It does not score behavior-loss severity; that is tracked by checklist item `[1.1-02]`.
- Required raw-DOT constructs currently include subgraph, node[...] defaults, edge[...] defaults, and unknown-valid extension attributes.
- Remaining raw-DOT-required authoring is currently subgraph/default-block constructs and unknown-valid extension attributes pending the generic advanced key/value editor.
