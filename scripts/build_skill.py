from __future__ import annotations

from pathlib import Path
import shutil


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def skill_source_dir() -> str:
    return "bundle"


def _ignore_runtime_artifacts(_directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name == "__pycache__" or name.endswith(".pyc"):
            ignored.add(name)
    return ignored


def build_skill(output_root: Path) -> Path:
    root = repo_root()
    destination = output_root / "roleme"
    if destination.exists():
        shutil.rmtree(destination)

    shutil.copytree(root / skill_source_dir(), destination)
    shutil.copytree(
        root / "tools",
        destination / "tools",
        ignore=_ignore_runtime_artifacts,
    )
    shutil.copytree(
        root / "templates",
        destination / "assets" / "templates",
        ignore=_ignore_runtime_artifacts,
    )
    return destination


def publish_skill() -> Path:
    return build_skill(repo_root() / "skills")


if __name__ == "__main__":
    print(publish_skill())
