# Raw DOT Required Configuration Report

Checklist item: [1.1-01]

Date: 2026-02-28

## Scope

This report lists configuration that is required by [`ui-spec.md`](/Users/chris/tinker/sparkspawn/ui-spec.md) but is not currently authorable through first-class UI controls, forcing users to leave the UI and edit raw DOT.

## Current Required Raw-DOT Surfaces

| Spec anchor | Required configuration | Why raw DOT is currently required | Evidence in current UI code |
| --- | --- | --- | --- |
| `ui-spec.md` §6.1, Appendix A (`A1-08`, `A1-09`) | `stack.child_dotfile`, `stack.child_workdir` | Graph settings do not expose either field, so users cannot set child-pipeline manager context in structured UI. | [`frontend/src/components/GraphSettings.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/GraphSettings.tsx), [`frontend/src/lib/dotUtils.ts`](/Users/chris/tinker/sparkspawn/frontend/src/lib/dotUtils.ts) |
| `ui-spec.md` §6.6, Appendix A (`A1-10`, `A1-11`) | `tool_hooks.pre`, `tool_hooks.post` | No graph-level tool hook form inputs exist, so hook commands must be added/edited in DOT text. | [`frontend/src/components/GraphSettings.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/GraphSettings.tsx), [`frontend/src/lib/dotUtils.ts`](/Users/chris/tinker/sparkspawn/frontend/src/lib/dotUtils.ts) |
| `ui-spec.md` §6.7, Appendix A (`A2-22`..`A2-25`) | `manager.poll_interval`, `manager.max_cycles`, `manager.stop_condition`, `manager.actions` | The node editor has no manager-loop field group, so manager-loop behavior configuration requires DOT edits. | [`frontend/src/components/TaskNode.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/TaskNode.tsx), [`frontend/src/lib/dotUtils.ts`](/Users/chris/tinker/sparkspawn/frontend/src/lib/dotUtils.ts) |
| `ui-spec.md` §6.2, Appendix A (`A2-26`) | `human.default_choice` | Wait-human controls expose answer selection during runs, but no authoring input exists for default-choice timeout behavior. | [`frontend/src/components/TaskNode.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/TaskNode.tsx), [`frontend/src/lib/dotUtils.ts`](/Users/chris/tinker/sparkspawn/frontend/src/lib/dotUtils.ts) |
| `ui-spec.md` §6.4, Appendix B (`B-03`, `B-04`, `B-05`) | `subgraph`, `node[...]` defaults, `edge[...]` defaults | Canvas/inspector controls currently target node/edge instances only and do not provide subgraph or defaults-block authoring. | [`frontend/src/components/Editor.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/Editor.tsx), [`frontend/src/components/TaskNode.tsx`](/Users/chris/tinker/sparkspawn/frontend/src/components/TaskNode.tsx), [`frontend/src/lib/dotUtils.ts`](/Users/chris/tinker/sparkspawn/frontend/src/lib/dotUtils.ts) |

## Notes

- This report documents where users currently leave structured UI to raw DOT for required configuration.
- It does not yet score behavior-loss severity; that is tracked by checklist item `[1.1-02]`.
- Raw DOT is currently required for subgraph, node[...] defaults, and edge[...] defaults authoring.
- Manager-loop selection is partially available through `type` override inputs, but manager-specific attrs still require raw DOT.
