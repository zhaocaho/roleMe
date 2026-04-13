from tools.role_ops import (
    doctor_role,
    initialize_role,
    list_roles,
    load_query_context_bundle,
    load_role_bundle,
)


def test_initialize_role_creates_required_files(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    assert (role_path / "AGENT.md").exists()
    assert (role_path / "role.json").exists()
    assert (role_path / "brain" / "topics").is_dir()
    assert (role_path / "memory" / "episodes").is_dir()
    assert (role_path / "persona" / "narrative.md").exists()
    assert not (role_path / "self-model").exists()


def test_load_role_bundle_returns_persona_resident_and_on_demand_paths(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")

    assert bundle.role_name == "self"
    assert "persona/narrative.md" in bundle.resident_files
    assert "memory/MEMORY.md" in bundle.resident_files
    assert "persona/disclosure-layers.md" in bundle.on_demand_paths
    assert "brain/index.md" in bundle.on_demand_paths


def test_list_roles_returns_sorted_names(tmp_role_home):
    initialize_role("beta", skill_version="0.1.0")
    initialize_role("alpha", skill_version="0.1.0")

    assert list_roles() == ["alpha", "beta"]


def test_doctor_role_reports_missing_file(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "AGENT.md").unlink()

    report = doctor_role("self")
    assert "AGENT.md" in report.missing_files


def test_load_query_context_bundle_returns_query_specific_snapshot(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI 产品\n\n聚焦 AI 产品策略与落地。\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n- AI 产品: topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- roleMe 重构: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text(
        "# roleMe 重构\n\n当前重构关注用户角色上下文与 AI 产品知识融合。\n\n- 参考知识: brain/topics/ai-product.md\n",
        encoding="utf-8",
    )

    bundle = load_query_context_bundle(
        "self",
        query="这个 roleMe 重构里的 AI 产品策略怎么设计",
        max_chars=900,
        max_brain_depth=1,
    )

    assert bundle.role_name == "self"
    assert "persona/narrative.md" in bundle.resident_files
    assert bundle.discovered_paths == [
        "projects/index.md",
        "projects/roleme/context.md",
        "brain/index.md",
        "brain/topics/ai-product.md",
    ]
    assert "## resident" in bundle.context_snapshot
    assert "## discovered" in bundle.context_snapshot
