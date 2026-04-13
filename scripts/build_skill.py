from __future__ import annotations

from pathlib import Path
import shutil


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_skill(output_root: Path, version: str) -> Path:
    root = repo_root()
    destination = output_root / f"roleme-v{version}"
    if destination.exists():
        shutil.rmtree(destination)

    shutil.copytree(root / "skill", destination)
    shutil.copytree(root / "tools", destination / "tools")
    shutil.copytree(root / "templates", destination / "assets" / "templates")
    return destination
