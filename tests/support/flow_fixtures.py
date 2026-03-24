from __future__ import annotations

from pathlib import Path, PurePosixPath


FLOW_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "flows"


def fixture_flow_path(name: str) -> Path:
    return FLOW_FIXTURES_DIR / Path(*PurePosixPath(name).parts)


def load_flow_fixture(name: str) -> str:
    path = fixture_flow_path(name)
    return path.read_text(encoding="utf-8")


def seed_flow_fixture(flows_dir: Path, fixture_name: str, *, as_name: str | None = None) -> Path:
    flows_root = flows_dir.expanduser().resolve(strict=False)
    flows_root.mkdir(parents=True, exist_ok=True)
    flow_name = as_name or fixture_name
    target_path = flows_root / Path(*PurePosixPath(flow_name).parts)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(load_flow_fixture(fixture_name), encoding="utf-8")
    return target_path
