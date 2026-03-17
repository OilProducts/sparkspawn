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

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `ui_default_llm_model` | String | `""` | Flow-level default model id shown or seeded by Spark Spawn authoring tools. |
| `ui_default_llm_provider` | String | `""` | Flow-level default provider key shown or seeded by Spark Spawn authoring tools. |
| `ui_default_reasoning_effort` | String | `""` | Flow-level default reasoning-effort value shown or seeded by Spark Spawn authoring tools. |

These attributes live in the DOT `graph [ ... ]` block.

They are persisted but non-semantic metadata. By themselves they are not execution directives.

## 6. Authoring Behavior

When a new node or flow is created in Spark Spawn authoring tools:

1. On flow creation, the editor may snapshot global defaults into `ui_default_*`.
2. If a flow lacks `ui_default_*`, the editor may seed them once from the current global defaults.
3. New nodes use the flow snapshot as their default.
4. Global defaults do not retroactively update existing flows.
5. The editor may persist explicit node attributes when the operator chooses values that should become semantic runtime inputs.

These are Spark Spawn authoring rules, not Attractor requirements.

## 7. Interaction With Core Runtime Attributes

If Spark Spawn writes explicit node attributes such as:
- `llm_model`
- `llm_provider`
- `reasoning_effort`

those values are core Attractor attributes and follow Attractor precedence and runtime semantics.

`ui_default_*` metadata never overrides execution semantics by itself.

This is the critical distinction:
- `ui_default_*` is metadata
- explicit node attrs are semantic runtime inputs

## 8. Validation and Ignore Rules

Attractor implementations that do not understand Spark Spawn extension attributes may ignore them unless a host product explicitly adopts them.

Spark Spawn tooling may:
- preserve them
- surface them in authoring UIs
- validate them as Spark Spawn-owned metadata

Unknown Spark Spawn extension attributes should have explicit handling rules in Spark Spawn tooling rather than accidental or inconsistent behavior.

## 9. Compatibility and Forward-Compatibility Constraints

Flows containing only `ui_default_*` metadata remain executable as standard Attractor flows because those attributes are non-semantic.

Future Spark Spawn extension keys should declare:
- their classification
- whether they are DOT-persisted
- whether they are semantic or non-semantic

New keys should avoid accidental collision with future Attractor core attributes.

## 10. Examples

Example:

```dot
digraph Example {
    graph [
        ui_default_llm_model="gpt-5.2",
        ui_default_llm_provider="openai",
        ui_default_reasoning_effort="high"
    ];

    start [shape=Mdiamond];
    task  [label="Draft plan"];
    exit  [shape=Msquare];

    start -> task -> exit;
}
```

In this example:
- the `ui_default_*` keys are persisted non-semantic metadata
- runtime semantics do not change unless Spark Spawn later materializes explicit node attrs
- an Attractor-only consumer may parse the flow and ignore the Spark Spawn metadata
