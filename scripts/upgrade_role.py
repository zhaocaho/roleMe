from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.file_ops import atomic_write_json, atomic_write_text
from tools.role_ops import role_dir, templates_dir


def bootstrap_graph(role_path: Path) -> None:
    graph_dir = role_path / "brain" / "graph"
    (graph_dir / "indexes").mkdir(parents=True, exist_ok=True)
    schema_path = graph_dir / "schema.yaml"
    if not schema_path.exists():
        atomic_write_text(
            schema_path,
            (templates_dir() / "brain" / "graph" / "schema.yaml").read_text(encoding="utf-8"),
        )


def upgrade_role(role_name: str, target_schema: str) -> None:
    role_path = role_dir(role_name)
    manifest_path = role_path / "role.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["schemaVersion"] = target_schema
    atomic_write_json(manifest_path, payload)
    bootstrap_graph(role_path)


parser = argparse.ArgumentParser()
parser.add_argument("role_name")
parser.add_argument("--target-schema", default="1.0")
args = parser.parse_args()

upgrade_role(args.role_name, args.target_schema)
print(f"upgraded {args.role_name} to schema {args.target_schema}")
