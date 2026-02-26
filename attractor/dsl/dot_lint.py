from __future__ import annotations

from difflib import unified_diff
from pathlib import Path

from .formatter import canonicalize_dot


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
