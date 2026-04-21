import json

import pytest

from tools.file_ops import atomic_rewrite_jsonl, atomic_write_json, atomic_write_text


def test_atomic_write_text_replaces_existing_content(tmp_path):
    path = tmp_path / "role" / "memory" / "USER.md"
    path.parent.mkdir(parents=True)
    path.write_text("old\n", encoding="utf-8")

    atomic_write_text(path, "new\n")

    assert path.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_json_writes_utf8_and_trailing_newline(tmp_path):
    path = tmp_path / "role" / "brain" / "graph" / "indexes" / "by-type.json"

    atomic_write_json(path, {"Preference": ["偏好-1"]})

    assert json.loads(path.read_text(encoding="utf-8")) == {"Preference": ["偏好-1"]}
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_atomic_rewrite_jsonl_rejects_non_object_records(tmp_path):
    path = tmp_path / "nodes.jsonl"
    path.write_text('{"id":"existing"}\n', encoding="utf-8")

    with pytest.raises(TypeError, match="JSONL records must be objects"):
        atomic_rewrite_jsonl(path, [{"id": "ok"}, ["bad"]])

    assert path.read_text(encoding="utf-8") == '{"id":"existing"}\n'


def test_atomic_rewrite_jsonl_keeps_old_file_when_serialization_fails(tmp_path):
    path = tmp_path / "edges.jsonl"
    path.write_text('{"id":"edge-old"}\n', encoding="utf-8")

    with pytest.raises(TypeError):
        atomic_rewrite_jsonl(path, [{"id": "edge-new", "bad": object()}])

    assert path.read_text(encoding="utf-8") == '{"id":"edge-old"}\n'
