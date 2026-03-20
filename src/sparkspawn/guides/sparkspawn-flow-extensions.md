# Spark Spawn Flow Extensions

This document defines Spark Spawn-owned flow-surface extensions layered onto [attractor-spec.md](/Users/chris/tinker/sparkspawn/specs/attractor-spec.md).

It consolidates and supersedes `sparkspawn-attractor-extensions.md` as the canonical contract for Spark Spawn-specific flow metadata and authoring extensions.

## 1. Purpose

Spark Spawn may attach product-specific metadata to the flow surface defined by Attractor.

These extensions:
- may be persisted in DOT
- may also exist as local client defaults outside DOT
- do not alter Attractor core semantics unless a host product explicitly interprets them

## 2. Relationship to `attractor-spec.md`

Attractor remains authoritative for:
- DOT syntax
- execution semantics
- handler behavior
- model stylesheet semantics
- validation rules that are not explicitly extended here

This document defines additions and interpretation rules for Spark Spawn only. It does not modify the Attractor grammar or introduce new core handler types.

## 3. Extension Classification Model

Spark Spawn flow-surface extensions fall into three classes:

1. `UI-only local state`
   - not stored in DOT
   - not part of flow interchange

2. `Persisted but non-semantic flow metadata`
   - stored in DOT
   - used by Spark Spawn authoring or presentation
   - ignored by Attractor execution semantics

3. `Runtime-interpreted product extensions`
   - stored in DOT
   - interpreted by Spark Spawn runtime behavior if explicitly implemented

Every Spark Spawn extension key should declare which class it belongs to.

## 4. UI-Only Local Defaults

Global editor defaults may exist outside DOT. Their purpose is to seed authoring choices, not create runtime semantics.

Example client-side key:
- `sparkspawn.ui_defaults`

Storage details for local defaults are implementation examples, not an interoperability contract.

## 5. Persisted Flow-Level Metadata

The following graph attributes are persisted Spark Spawn metadata:

| Key | Type | Class | Default | Meaning |
| --- | --- | --- | --- | --- |
| `sparkspawn.title` | String | `Persisted but non-semantic flow metadata` | `""` | Spark Spawn display title for flow discovery and authoring surfaces. Falls back to graph `label` when unset. |
| `sparkspawn.description` | String | `Persisted but non-semantic flow metadata` | `""` | Spark Spawn short description for flow discovery and authoring surfaces. Falls back to graph `goal` when unset. |
| `sparkspawn.launch_inputs` | JSON-encoded array string | `Runtime-interpreted product extension` | `""` | Spark Spawn launch-form schema. The product may render a launch form from it and map the submitted values into Attractor `launch_context` under `context.*`. |
| `ui_default_llm_model` | String | `Persisted but non-semantic flow metadata` | `""` | Flow-level default model id shown or seeded by Spark Spawn authoring tools. |
| `ui_default_llm_provider` | String | `Persisted but non-semantic flow metadata` | `""` | Flow-level default provider key shown or seeded by Spark Spawn authoring tools. |
| `ui_default_reasoning_effort` | String | `Persisted but non-semantic flow metadata` | `""` | Flow-level default reasoning-effort value shown or seeded by Spark Spawn authoring tools. |

These attributes live in the DOT `graph [ ... ]` block.

`sparkspawn.title`, `sparkspawn.description`, and `ui_default_*` are persisted but non-semantic metadata. By themselves they are not execution directives.

`sparkspawn.launch_inputs` is product-interpreted metadata. It does not change Attractor execution semantics by itself, but Spark Spawn may use it to gather launch-time values and construct `launch_context` for a run.

### 5.1 `sparkspawn.launch_inputs` Shape

`sparkspawn.launch_inputs` stores a JSON array of objects with this shape:

```json
[
  {
    "key": "context.request.summary",
    "label": "Request Summary",
    "type": "string",
    "description": "Short description shown in the launch form.",
    "required": true
  }
]
```

Rules:
- `key` must be a `context.*` key
- `label` is the user-facing launch form label
- `type` must be one of `string`, `string[]`, `boolean`, `number`, or `json`
- `description` is optional explanatory text shown in Spark Spawn launch surfaces
- `required` controls whether Spark Spawn blocks launch when the value is omitted

Spark Spawn is responsible for validating this schema before using it. Attractor consumers that ignore Spark Spawn extensions may ignore this field entirely.

## 6. Persisted Node-Level Authoring Metadata

Spark Spawn may persist the following node attributes as authoring metadata:

| Key | Type | Class | Default | Meaning |
| --- | --- | --- | --- | --- |
| `sparkspawn.reads_context` | JSON-encoded array string | `Persisted but non-semantic flow metadata` | `""` | Declares which `context.*` keys the node is expected to consume from launch state or earlier stages. |
| `sparkspawn.writes_context` | JSON-encoded array string | `Persisted but non-semantic flow metadata` | `""` | Declares which `context.*` keys the node is expected to produce for later stages. |

These attributes live on individual DOT nodes.

Rules:
- each declaration encodes a JSON array of strings
- each declared string must use the `context.*` namespace
- they document and guide Spark Spawn authoring surfaces
- they do not create runtime behavior automatically

Spark Spawn may use these declarations for:
- node inspector affordances
- documentation and authoring hints
- launch and review UX
- future validation of flow authoring contracts

Attractor execution semantics do not change merely because these declarations are present.

## 7. Authoring Behavior

When a new node or flow is created in Spark Spawn authoring tools:

1. On flow creation, the editor may snapshot global defaults into `ui_default_*`.
2. If a flow lacks `ui_default_*`, the editor may seed them once from the current global defaults.
3. New nodes use the flow snapshot as their default.
4. Graph-level launch input definitions may be persisted into `sparkspawn.launch_inputs`.
5. Node-level context read/write declarations may be persisted into `sparkspawn.reads_context` and `sparkspawn.writes_context`.
6. Global defaults do not retroactively update existing flows.
7. The editor may persist explicit node attributes when the operator chooses values that should become semantic runtime inputs.

These are Spark Spawn authoring rules, not Attractor requirements.

## 8. Interaction With Core Runtime Attributes

If Spark Spawn writes explicit node attributes such as:
- `llm_model`
- `llm_provider`
- `reasoning_effort`

those values are core Attractor attributes and follow Attractor precedence and runtime semantics.

`ui_default_*` metadata never overrides execution semantics by itself.

This is the critical distinction:
- `ui_default_*` is metadata
- explicit node attrs are semantic runtime inputs

This section also applies to the new Spark Spawn authoring-contract keys:
- `sparkspawn.launch_inputs` may cause Spark Spawn to construct Attractor `launch_context`, but it is not itself an Attractor runtime key
- `sparkspawn.reads_context` and `sparkspawn.writes_context` document intended context contracts, but they do not inject or mutate context on their own

## 9. Workspace Launch Policy

Whether an agent may independently initiate a flow is not stored in DOT.

Launch policy is a workspace-global Spark Spawn setting, currently modeled outside the flow file in the workspace flow catalog. This keeps the flow file self-describing while preserving host-product control over exposure policy.

Current launch-policy values are:
- `agent_requestable`
- `trigger_only`
- `disabled`

This is intentionally separate from persisted DOT metadata:
- `sparkspawn.title` and `sparkspawn.description` describe the flow itself
- launch policy describes how the workspace exposes that flow in a given installation

## 10. Validation and Ignore Rules

Attractor implementations that do not understand Spark Spawn extension attributes may ignore them unless a host product explicitly adopts them.

Spark Spawn tooling may:
- preserve them
- surface them in authoring UIs
- validate them as Spark Spawn-owned metadata
- reject malformed `sparkspawn.launch_inputs`
- reject malformed `sparkspawn.reads_context` / `sparkspawn.writes_context`

Unknown Spark Spawn extension attributes should have explicit handling rules in Spark Spawn tooling rather than accidental or inconsistent behavior.

## 11. Compatibility and Forward-Compatibility Constraints

Flows containing only Spark Spawn metadata remain executable as standard Attractor flows because these keys are host-product extensions rather than Attractor core attrs.

Future Spark Spawn extension keys should declare:
- their classification
- whether they are DOT-persisted
- whether they are semantic or non-semantic

New keys should avoid accidental collision with future Attractor core attributes.

## 12. Examples

Example:

```dot
digraph Example {
    graph [
        sparkspawn.title="Plan Generation",
        sparkspawn.description="Generate an execution plan from approved workspace context.",
        sparkspawn.launch_inputs="[{\"key\":\"context.request.summary\",\"label\":\"Request Summary\",\"type\":\"string\",\"description\":\"Short launch summary.\",\"required\":true}]",
        ui_default_llm_model="gpt-5.2",
        ui_default_llm_provider="openai",
        ui_default_reasoning_effort="high"
    ];

    start [shape=Mdiamond];
    task  [
        label="Draft plan",
        sparkspawn.reads_context="[\"context.request.summary\"]",
        sparkspawn.writes_context="[\"context.plan.summary\"]"
    ];
    exit  [shape=Msquare];

    start -> task -> exit;
}
```

In this example:
- the `sparkspawn.title` and `sparkspawn.description` keys are persisted non-semantic discovery metadata
- the `sparkspawn.launch_inputs` key is Spark Spawn launch-form metadata that may be converted into Attractor `launch_context`
- the `sparkspawn.reads_context` and `sparkspawn.writes_context` keys are persisted node-level authoring metadata
- the `ui_default_*` keys are persisted non-semantic metadata
- runtime semantics do not change unless Spark Spawn later materializes explicit node attrs
- an Attractor-only consumer may parse the flow and ignore the Spark Spawn metadata
