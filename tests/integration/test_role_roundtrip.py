from scripts.build_skill import build_skill
from tools.memory import build_frozen_snapshot, summarize_and_write
from tools.role_ops import doctor_role, initialize_role, load_role_bundle


def test_role_roundtrip_init_load_write_memory_and_package(tmp_role_home, tmp_path):
    role_path = initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")
    summarize_and_write(role_path, target="memory", source_text="默认中文沟通。")
    snapshot = build_frozen_snapshot(role_path, max_chars=400)
    artifact = build_skill(output_root=tmp_path)
    report = doctor_role("self")

    assert bundle.role_name == "self"
    assert "默认中文沟通" in snapshot
    assert report.missing_files == []
    assert artifact.name == "roleMe"
    assert (artifact / "SKILL.md").exists()
