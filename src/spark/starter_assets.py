from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable


STARTER_ASSET_DIR_NAME = "flows"


@dataclass(frozen=True)
class StarterFlowAsset:
    name: str
    content: str


@dataclass(frozen=True)
class SeedStarterFlowsResult:
    flows_dir: Path
    created: tuple[str, ...]
    updated: tuple[str, ...]
    skipped: tuple[str, ...]


def load_starter_flow_assets(*, project_root: Path | None = None) -> tuple[StarterFlowAsset, ...]:
    del project_root
    packaged_dir = resources.files("spark").joinpath(STARTER_ASSET_DIR_NAME)
    packaged_assets = sorted(
        (
            asset
            for asset in _iter_packaged_assets(packaged_dir)
            if asset.name.endswith(".dot")
        ),
        key=lambda asset: asset.name,
    )
    if not packaged_assets:
        raise RuntimeError("Packaged flow assets are unavailable.")
    return tuple(
        StarterFlowAsset(name=asset.name, content=asset.content)
        for asset in packaged_assets
    )


def seed_starter_flows(
    flows_dir: Path,
    *,
    force: bool = False,
    project_root: Path | None = None,
) -> SeedStarterFlowsResult:
    assets = load_starter_flow_assets(project_root=project_root)
    target_dir = flows_dir.expanduser().resolve(strict=False)
    target_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    for asset in assets:
        target_path = target_dir / Path(asset.name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        existed = target_path.exists()
        if existed and not force:
            skipped.append(asset.name)
            continue
        target_path.write_text(asset.content, encoding="utf-8")
        if existed:
            updated.append(asset.name)
        else:
            created.append(asset.name)

    return SeedStarterFlowsResult(
        flows_dir=target_dir,
        created=tuple(created),
        updated=tuple(updated),
        skipped=tuple(skipped),
    )


def _iter_packaged_assets(root) -> Iterable[StarterFlowAsset]:
    stack = [(root, "")]
    while stack:
        current, prefix = stack.pop()
        for entry in current.iterdir():
            entry_name = f"{prefix}{entry.name}"
            if entry.is_dir():
                stack.append((entry, f"{entry_name}/"))
                continue
            yield StarterFlowAsset(name=entry_name, content=entry.read_text(encoding="utf-8"))
