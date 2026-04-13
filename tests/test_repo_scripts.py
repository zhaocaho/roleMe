from scripts.build_skill import build_skill, publish_skill


def test_build_skill_creates_artifact_without_scripts(tmp_path):
    artifact = build_skill(output_root=tmp_path)

    assert artifact.name == "roleme"
    assert (artifact / "SKILL.md").exists()
    assert (artifact / "references" / "usage.md").exists()
    assert (artifact / "tools" / "role_ops.py").exists()
    assert (artifact / "tools" / "memory.py").exists()
    assert (artifact / "tools" / "context_router.py").exists()
    assert (artifact / "assets" / "templates" / "AGENT.md").exists()
    assert (artifact / "assets" / "templates" / "persona" / "narrative.md").exists()
    assert not (artifact / "assets" / "templates" / "self-model").exists()
    assert not (artifact / "scripts").exists()


def test_build_skill_preserves_skill_frontmatter(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")

    assert skill_md.startswith("---\n")
    assert "name: roleme" in skill_md
    assert "description:" in skill_md


def test_publish_skill_writes_repo_publish_directory(tmp_path, monkeypatch):
    (tmp_path / "skill" / "agents").mkdir(parents=True)
    (tmp_path / "skill" / "references").mkdir(parents=True)
    (tmp_path / "tools").mkdir()
    (tmp_path / "templates" / "persona").mkdir(parents=True)

    (tmp_path / "skill" / "SKILL.md").write_text("---\nname: roleme\n---\n", encoding="utf-8")
    (tmp_path / "skill" / "agents" / "openai.yaml").write_text("name: roleMe\n", encoding="utf-8")
    (tmp_path / "skill" / "references" / "usage.md").write_text("usage\n", encoding="utf-8")
    (tmp_path / "tools" / "role_ops.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "memory.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "context_router.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "templates" / "AGENT.md").write_text("agent\n", encoding="utf-8")
    (tmp_path / "templates" / "persona" / "narrative.md").write_text("persona\n", encoding="utf-8")

    monkeypatch.setitem(publish_skill.__globals__, "repo_root", lambda: tmp_path)

    artifact = publish_skill()

    assert artifact == tmp_path / "skills" / "roleme"
    assert (artifact / "SKILL.md").exists()
    assert (artifact / "agents" / "openai.yaml").exists()
    assert (artifact / "references" / "usage.md").exists()
    assert (artifact / "tools" / "role_ops.py").exists()
    assert (artifact / "tools" / "context_router.py").exists()
    assert (artifact / "assets" / "templates" / "AGENT.md").exists()
    assert (artifact / "assets" / "templates" / "persona" / "narrative.md").exists()
