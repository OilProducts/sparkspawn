from __future__ import annotations

from difflib import unified_diff
from pathlib import Path

from .models import DiagnosticSeverity
from .formatter import canonicalize_dot
from .parser import DotParseError, parse_dot
from .validator import validate_graph


def find_dot_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.dot") if path.is_file())


def find_non_canonical_dot_diffs(dot_paths: list[Path]) -> list[str]:
    non_canonical: list[str] = []

    for path in dot_paths:
        source = path.read_text(encoding="utf-8")
        canonical = canonicalize_dot(source)
        normalized_source = source if source.endswith("\n") else f"{source}\n"
        if normalized_source == canonical:
            continue

        diff = "".join(
            unified_diff(
                normalized_source.splitlines(keepends=True),
                canonical.splitlines(keepends=True),
                fromfile=f"{path} (current)",
                tofile=f"{path} (canonical)",
            )
        )
        non_canonical.append(diff)

    return non_canonical


def find_start_node_lint_errors(dot_paths: list[Path]) -> list[str]:
    errors: list[str] = []

    for path in dot_paths:
        source = path.read_text(encoding="utf-8")
        try:
            graph = parse_dot(source)
        except DotParseError as exc:
            errors.append(f"{path}: parse_error: {exc}")
            continue

        diagnostics = validate_graph(graph)
        for diagnostic in diagnostics:
            if diagnostic.severity != DiagnosticSeverity.ERROR:
                continue
            if diagnostic.rule_id != "start_node":
                continue
            errors.append(f"{path}:{diagnostic.line}: {diagnostic.rule_id}: {diagnostic.message}")

    return errors
