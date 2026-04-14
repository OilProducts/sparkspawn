from __future__ import annotations

import importlib.util
from pathlib import Path


def test_package_discovery_uses_spark_namespaces_only() -> None:
    assert importlib.util.find_spec("spark.workspace.api") is not None
    assert importlib.util.find_spec("spark.chat.service") is not None
    assert importlib.util.find_spec("workspace") is None


def test_legacy_workspace_package_is_removed_from_source_tree() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "src" / "workspace").exists()
