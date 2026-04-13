from __future__ import annotations

from pathlib import Path
import shutil


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_skill(output_root: Path) -> Path:
    root = repo_root()
    destination = output_root / "roleme"
    if destination.exists():
        shutil.rmtree(destination)

    shutil.copytree(root / "skill", destination)
    shutil.copytree(root / "tools", destination / "tools")
    shutil.copytree(root / "templates", destination / "assets" / "templates")
    return destination


def publish_skill() -> Path:
    return build_skill(repo_root() / "skills")
