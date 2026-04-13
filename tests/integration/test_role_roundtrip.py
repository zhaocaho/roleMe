from scripts.build_skill import build_skill
from tools.context_router import (
    build_context_snapshot,
    discover_brain_paths,
    discover_context_paths,
)
from tools.memory import build_frozen_snapshot, summarize_and_write
from tools.role_ops import (
    doctor_role,
    initialize_role,
    load_query_context_bundle,
    load_role_bundle,
)


def test_role_roundtrip_init_load_write_memory_and_package(tmp_role_home, tmp_path):
    role_path = initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")
    summarize_and_write(
        role_path,
        target="memory",
        source_text="default Chinese communication; lead with the conclusion",
    )
    snapshot = build_frozen_snapshot(role_path, max_chars=400)
    artifact = build_skill(output_root=tmp_path)
    report = doctor_role("self")

    assert bundle.role_name == "self"
    assert "persona/narrative.md" in bundle.resident_files
    assert "brain/index.md" in bundle.on_demand_paths
    assert "default Chinese communication" in snapshot
    assert report.missing_files == []
    assert artifact.name == "roleme"
    assert (artifact / "SKILL.md").exists()
    assert (artifact / "assets" / "templates" / "persona" / "narrative.md").exists()


def test_role_roundtrip_discovers_brain_topics_progressively(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI 产品\n\n聚焦 AI 产品策略。\n\n- 延伸阅读: topics/pricing.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "pricing.md").write_text(
        "# 定价\n\n讨论 AI 产品定价与包装。\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n- AI 产品: topics/ai-product.md\n",
        encoding="utf-8",
    )

    discovered = discover_brain_paths(role_path, query="我想讨论 AI 产品定价", max_depth=2)

    assert discovered == [
        "brain/index.md",
        "brain/topics/ai-product.md",
        "brain/topics/pricing.md",
    ]


def test_role_roundtrip_combines_project_and_brain_discovery(tmp_role_home):
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

    discovered = discover_context_paths(
        role_path,
        query="这个 roleMe 重构里的 AI 产品策略怎么设计",
        max_brain_depth=1,
    )

    assert discovered == [
        "projects/index.md",
        "projects/roleme/context.md",
        "brain/index.md",
        "brain/topics/ai-product.md",
    ]


def test_role_roundtrip_builds_query_specific_context_snapshot(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "persona" / "narrative.md").write_text(
        "# 人物自述\n\n我是一个重视 AI 产品策略的人。\n",
        encoding="utf-8",
    )
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

    snapshot = build_context_snapshot(
        role_path,
        query="这个 roleMe 重构里的 AI 产品策略怎么设计",
        max_chars=900,
        max_brain_depth=1,
    )

    assert "## resident" in snapshot
    assert "## discovered" in snapshot
    assert "projects/roleme/context.md" in snapshot
    assert "brain/topics/ai-product.md" in snapshot


def test_role_roundtrip_loads_query_context_bundle(tmp_role_home):
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
