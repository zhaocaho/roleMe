from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil


SCHEMA_VERSION = "1.0"
RESIDENT_PATHS = [
    "persona/narrative.md",
    "persona/communication-style.md",
    "persona/decision-rules.md",
    "memory/USER.md",
    "memory/MEMORY.md",
]
ON_DEMAND_PATHS = [
    "persona/disclosure-layers.md",
    "brain/index.md",
    "brain/topics",
    "projects/index.md",
    "projects",
    "memory/episodes",
]
REQUIRED_FILES = [
    "AGENT.md",
    "role.json",
    "brain/index.md",
    "memory/USER.md",
    "memory/MEMORY.md",
    "projects/index.md",
    "persona/narrative.md",
    "persona/communication-style.md",
    "persona/decision-rules.md",
    "persona/disclosure-layers.md",
]


@dataclass(frozen=True)
class RoleManifest:
    role_name: str
    schema_version: str
    role_version: str
    created_by_skill_version: str
    compatible_skill_range: str
    created_at: str
    updated_at: str
    default_load_profile: str = "standard"

    @classmethod
    def new(cls, role_name: str, skill_version: str) -> "RoleManifest":
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        return cls(
            role_name=role_name,
            schema_version=SCHEMA_VERSION,
            role_version="0.1.0",
            created_by_skill_version=skill_version,
            compatible_skill_range=">=0.1 <1.0",
            created_at=now,
            updated_at=now,
        )

    def write(self, path: Path) -> None:
        payload = {
            "roleName": self.role_name,
            "schemaVersion": self.schema_version,
            "roleVersion": self.role_version,
            "createdBySkillVersion": self.created_by_skill_version,
            "compatibleSkillRange": self.compatible_skill_range,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "defaultLoadProfile": self.default_load_profile,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


@dataclass(frozen=True)
class RoleBundle:
    role_name: str
    role_path: str
    resident_files: dict[str, str]
    on_demand_paths: list[str]


@dataclass(frozen=True)
class DoctorReport:
    missing_files: list[str]
    warnings: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def templates_dir() -> Path:
    return repo_root() / "templates"


def roleme_home() -> Path:
    override = os.environ.get("ROLEME_HOME")
    return Path(override).expanduser() if override else Path.home() / ".roleMe"


def role_dir(role_name: str) -> Path:
    return roleme_home() / role_name


def _render(source: Path, destination: Path, role_name: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text(encoding="utf-8").replace("<role-name>", role_name)
    destination.write_text(content, encoding="utf-8")


def initialize_role(role_name: str, skill_version: str) -> Path:
    destination = role_dir(role_name)
    if destination.exists():
        raise FileExistsError(f"Role already exists: {destination}")

    for relative_dir in ["brain/topics", "memory/episodes", "projects", "persona"]:
        (destination / relative_dir).mkdir(parents=True, exist_ok=True)

    for relative_file in [
        "AGENT.md",
        "brain/index.md",
        "memory/MEMORY.md",
        "memory/USER.md",
        "projects/index.md",
        "persona/communication-style.md",
        "persona/decision-rules.md",
        "persona/disclosure-layers.md",
        "persona/narrative.md",
    ]:
        _render(templates_dir() / relative_file, destination / relative_file, role_name)

    RoleManifest.new(role_name=role_name, skill_version=skill_version).write(
        destination / "role.json"
    )
    return destination


def load_role_bundle(role_name: str) -> RoleBundle:
    base_path = role_dir(role_name)
    resident_files = {
        relative: (base_path / relative).read_text(encoding="utf-8")
        for relative in RESIDENT_PATHS
    }
    return RoleBundle(
        role_name=role_name,
        role_path=str(base_path),
        resident_files=resident_files,
        on_demand_paths=ON_DEMAND_PATHS,
    )


def list_roles() -> list[str]:
    home = roleme_home()
    if not home.exists():
        return []
    return sorted(path.name for path in home.iterdir() if path.is_dir())


def export_role(role_name: str, output_dir: Path, as_zip: bool = True) -> Path:
    source = role_dir(role_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    if as_zip:
        archive_base = output_dir / source.name
        archive_path = shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=source.parent,
            base_dir=source.name,
        )
        return Path(archive_path)
    destination = output_dir / source.name
    shutil.copytree(source, destination, dirs_exist_ok=False)
    return destination


def doctor_role(role_name: str) -> DoctorReport:
    base_path = role_dir(role_name)
    missing = [relative for relative in REQUIRED_FILES if not (base_path / relative).exists()]
    warnings: list[str] = []
    manifest_path = base_path / "role.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            warnings.append(f"schema mismatch: {payload.get('schemaVersion')}")
    return DoctorReport(missing_files=missing, warnings=warnings)
