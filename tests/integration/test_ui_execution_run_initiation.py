from __future__ import annotations

from pathlib import Path


def test_run_initiation_captures_project_flow_source_workdir_and_backend_model_item_8_1_01() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    navbar_text = (repo_root / "frontend" / "src" / "components" / "Navbar.tsx").read_text(encoding="utf-8")

    required_snippets = [
        "const runInitiationForm = {",
        "projectPath: activeProjectPath || '',",
        "flowSource: activeFlow || '',",
        "workingDirectory: workingDir,",
        "backend: 'codex',",
        "model: model.trim() || null,",
        "data-testid=\"run-initiation-form\"",
        "data-testid=\"run-initiation-project\"",
        "data-testid=\"run-initiation-flow-source\"",
        "data-testid=\"run-initiation-working-directory\"",
        "data-testid=\"run-initiation-backend-model\"",
        "const flowRes = await fetch(`/api/flows/${encodeURIComponent(runInitiationForm.flowSource)}`)",
        "flow_content: flow.content,",
        "working_directory: runInitiationForm.workingDirectory,",
        "backend: runInitiationForm.backend,",
        "model: runInitiationForm.model,",
        "flow_name: runInitiationForm.flowSource,",
    ]

    for snippet in required_snippets:
        assert snippet in navbar_text, f"missing run initiation capture snippet: {snippet}"


def test_checklist_marks_item_8_1_01_complete() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checklist_text = (repo_root / "ui-implementation-checklist.md").read_text(encoding="utf-8")

    assert "- [x] [8.1-01]" in checklist_text
