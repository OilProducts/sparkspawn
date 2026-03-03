from pathlib import Path


def test_spec_first_behavior_mapping_doc_exists_with_required_control_coverage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    doc_path = repo_root / "ui-spec-first-behavior-map.md"

    assert doc_path.exists(), "missing spec-first behavior mapping doc for checklist item 2-01"

    doc_text = doc_path.read_text(encoding="utf-8")
    required_snippets = [
        "Checklist item: [2-01]",
        "ui-spec.md",
        "attractor-spec.md",
        "Control-to-Spec Behavior Map",
        "Top navigation mode switch (Editor/Execution/Settings/Runs)",
        "Execute button",
        "Add Node button",
        "Flow create/delete/select controls",
        "Graph settings drawer",
        "Apply To Nodes button",
        "Reset From Global button",
        "Node inspector fields",
        "Node quick-edit controls",
        "Edge inspector fields",
        "Validation panel entries",
        "Canvas controls (pan/zoom/fit/minimap)",
        "Run history refresh/open/cancel actions",
        "Execution footer cancel control",
        "Terminal clear action",
        "Projects workspace controls",
        "Explainability panel controls",
        "Run stream panel controls",
        "Stylesheet editor controls",
        "Spec references",
    ]

    for snippet in required_snippets:
        assert snippet in doc_text, f"missing required spec-first mapping coverage: {snippet}"

    required_component_paths = [
        "frontend/src/components/Navbar.tsx",
        "frontend/src/components/Sidebar.tsx",
        "frontend/src/components/Editor.tsx",
        "frontend/src/components/GraphSettings.tsx",
        "frontend/src/components/TaskNode.tsx",
        "frontend/src/components/ValidationPanel.tsx",
        "frontend/src/components/RunsPanel.tsx",
        "frontend/src/components/ExecutionControls.tsx",
        "frontend/src/components/Terminal.tsx",
        "frontend/src/components/SettingsPanel.tsx",
        "frontend/src/components/ProjectsPanel.tsx",
        "frontend/src/components/ExplainabilityPanel.tsx",
        "frontend/src/components/RunStream.tsx",
        "frontend/src/components/StylesheetEditor.tsx",
    ]
    for component_path in required_component_paths:
        assert component_path in doc_text, f"missing mapped control coverage for component: {component_path}"

    # Require a broad mapping table so the checklist item does not pass with a minimal subset.
    map_lines = [line for line in doc_text.splitlines() if line.startswith("| ") and " | " in line]
    assert len(map_lines) >= 22, "control mapping is too narrow for item 2-01"


