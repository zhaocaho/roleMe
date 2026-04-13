from __future__ import annotations

import argparse
import json

from tools.role_ops import role_dir


parser = argparse.ArgumentParser()
parser.add_argument("role_name")
parser.add_argument("--target-schema", default="1.0")
args = parser.parse_args()

manifest_path = role_dir(args.role_name) / "role.json"
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
payload["schemaVersion"] = args.target_schema
manifest_path.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"upgraded {args.role_name} to schema {args.target_schema}")
