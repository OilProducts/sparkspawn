from __future__ import annotations

REQ_IDS = tuple(f"REQ-{index:03d}" for index in range(1, 19))
CD_IDS = tuple(f"CD-{index:03d}" for index in range(1, 16))


REQUIREMENT_COVERAGE: dict[str, tuple[str, ...]] = {
    "REQ-001": ("library surface", "low-level client boundary"),
    "REQ-002": ("session model", "turn records"),
    "REQ-003": ("async event stream", "host-visible lifecycle events"),
    "REQ-004": ("turn loop", "tool round execution"),
    "REQ-005": ("tool registry", "tool error conversion"),
    "REQ-006": ("file tools", "command tools", "search tools", "glob tools"),
    "REQ-007": ("execution environment", "local filesystem implementation"),
    "REQ-008": ("deterministic truncation", "warning events"),
    "REQ-009": ("provider profiles", "capability flags"),
    "REQ-010": ("openai edit surface", "apply_patch behavior"),
    "REQ-011": ("anthropic edit surface", "old_string new_string behavior"),
    "REQ-012": ("gemini edit surface", "gemini instruction behavior"),
    "REQ-013": ("prompt layering", "project documents"),
    "REQ-014": ("steering", "reasoning effort changes"),
    "REQ-015": ("loop detection", "warning injection"),
    "REQ-016": ("subagent spawn", "child wait and close"),
    "REQ-017": ("recoverable tool errors", "deterministic cleanup"),
    "REQ-018": ("deterministic parity matrix", "optional live smoke"),
}


DECISION_COVERAGE: dict[str, tuple[str, ...]] = {
    "CD-001": ("importable agent library",),
    "CD-002": ("async process_input entrypoint",),
    "CD-003": ("typed event stream",),
    "CD-004": ("SDK request and response types",),
    "CD-005": ("execution environment boundary",),
    "CD-006": ("provider-native tool surfaces",),
    "CD-007": ("observable validation over prompt text",),
    "CD-008": ("tool results carry errors",),
    "CD-009": ("full output on events", "truncated model-facing output"),
    "CD-010": ("AGENTS.md discovery", "provider instruction layering"),
    "CD-011": ("session orchestration behavior",),
    "CD-012": ("child sessions and depth limits",),
    "CD-013": ("SDK-layer retries and cleanup",),
    "CD-014": ("default uv pytest gate", "opt-in live smoke", "ruff gate"),
    "CD-015": ("subagent runtime before profile completion",),
}


def _assert_complete_manifest(
    manifest: dict[str, tuple[str, ...]],
    expected_ids: tuple[str, ...],
) -> None:
    assert tuple(manifest) == expected_ids
    assert all(manifest[identifier] for identifier in expected_ids)
    assert all(isinstance(label, str) and label for labels in manifest.values() for label in labels)


def test_m6_requirement_traceability_manifest_is_complete() -> None:
    _assert_complete_manifest(REQUIREMENT_COVERAGE, REQ_IDS)


def test_m6_contract_decision_traceability_manifest_is_complete() -> None:
    _assert_complete_manifest(DECISION_COVERAGE, CD_IDS)


def test_m6_closure_conditions_are_explicit_in_the_manifest() -> None:
    assert REQUIREMENT_COVERAGE["REQ-018"] == (
        "deterministic parity matrix",
        "optional live smoke",
    )
    assert DECISION_COVERAGE["CD-014"] == (
        "default uv pytest gate",
        "opt-in live smoke",
        "ruff gate",
    )
    assert "apply_patch behavior" in REQUIREMENT_COVERAGE["REQ-010"]
    assert "anthropic edit surface" in REQUIREMENT_COVERAGE["REQ-011"]
    assert "gemini edit surface" in REQUIREMENT_COVERAGE["REQ-012"]
    assert "full output on events" in DECISION_COVERAGE["CD-009"]
