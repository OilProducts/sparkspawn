from __future__ import annotations

from pathlib import Path


GUIDES_DIR_NAME = "guides"
DOT_AUTHORING_GUIDE_NAME = "dot-authoring.md"
ATTRACTOR_SPEC_NAME = "attractor-spec.md"
FLOW_EXTENSIONS_SPEC_NAME = "sparkspawn-flow-extensions.md"


def dot_authoring_guide_path() -> Path:
    path = Path(__file__).resolve().parent / GUIDES_DIR_NAME / DOT_AUTHORING_GUIDE_NAME
    if not path.exists():
        raise RuntimeError(f"DOT authoring guide is unavailable: {path}")
    return path


def attractor_spec_path() -> Path:
    path = Path(__file__).resolve().parent / GUIDES_DIR_NAME / ATTRACTOR_SPEC_NAME
    if not path.exists():
        raise RuntimeError(f"Packaged Attractor spec is unavailable: {path}")
    return path


def flow_extensions_spec_path() -> Path:
    path = Path(__file__).resolve().parent / GUIDES_DIR_NAME / FLOW_EXTENSIONS_SPEC_NAME
    if not path.exists():
        raise RuntimeError(f"Packaged Spark Spawn flow extensions spec is unavailable: {path}")
    return path
