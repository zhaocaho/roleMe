from scripts.build_skill import build_skill


def test_build_skill_creates_artifact_without_scripts(tmp_path):
    artifact = build_skill(output_root=tmp_path)

    assert artifact.name == "roleMe"
    assert (artifact / "SKILL.md").exists()
    assert (artifact / "references" / "usage.md").exists()
    assert (artifact / "tools" / "role_ops.py").exists()
    assert (artifact / "tools" / "memory.py").exists()
    assert (artifact / "assets" / "templates" / "AGENT.md").exists()
    assert not (artifact / "scripts").exists()


def test_build_skill_preserves_skill_frontmatter(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")

    assert skill_md.startswith("---\n")
    assert "name: roleme" in skill_md
    assert "description:" in skill_md
