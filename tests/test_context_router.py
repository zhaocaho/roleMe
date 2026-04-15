from tools.context_router import (
    build_context_snapshot,
    discover_brain_paths,
    discover_context_paths,
    discover_project_paths,
    route_context_lookup,
)
from tools.role_ops import initialize_role


def test_route_context_prefers_brain_for_domain_queries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    result = route_context_lookup(role_path, query="帮我分析这个 AI 产品策略")

    assert result.primary_path == "brain/index.md"
    assert "memory/episodes/*" in result.fallback_paths


def test_route_context_prefers_projects_for_project_queries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    result = route_context_lookup(role_path, query="这个仓库里的 roleMe 重构怎么推进")

    assert result.primary_path == "projects/index.md"
    assert "brain/index.md" in result.fallback_paths


def test_discover_brain_paths_selects_relevant_topic_from_index(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "topics").mkdir(parents=True, exist_ok=True)
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n"
        "- AI 产品: topics/ai-product.md\n"
        "- 角色工程: topics/role-design.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI 产品\n\n关注 AI 产品策略、定位和落地。\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "role-design.md").write_text(
        "# 角色工程\n\n关注角色包设计与上下文结构。\n",
        encoding="utf-8",
    )

    result = discover_brain_paths(role_path, query="帮我分析这个 AI 产品策略")

    assert result == ["brain/index.md", "brain/topics/ai-product.md"]


def test_discover_brain_paths_follows_topic_links_progressively(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "topics").mkdir(parents=True, exist_ok=True)
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n"
        "- AI 产品: topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI 产品\n\n"
        "聚焦 AI 产品策略。\n\n"
        "- 延伸阅读: topics/pricing.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "pricing.md").write_text(
        "# 定价\n\n讨论 AI 产品定价与包装。\n",
        encoding="utf-8",
    )

    result = discover_brain_paths(role_path, query="我想讨论 AI 产品定价", max_depth=2)

    assert result == [
        "brain/index.md",
        "brain/topics/ai-product.md",
        "brain/topics/pricing.md",
    ]


def test_discover_context_paths_combines_project_and_brain_context(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (role_path / "brain" / "topics").mkdir(parents=True, exist_ok=True)

    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n"
        "- roleMe 重构: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text(
        "# roleMe 重构\n\n"
        "当前在做 roleMe 重构，重点是把用户角色上下文与 AI 产品知识结合。\n\n"
        "- 参考知识: brain/topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n"
        "- AI 产品: topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI 产品\n\n关注 AI 产品策略、定位和落地。\n",
        encoding="utf-8",
    )

    result = discover_context_paths(
        role_path,
        query="这个 roleMe 重构里的 AI 产品策略怎么设计",
        max_brain_depth=1,
    )

    assert result == [
        "projects/index.md",
        "projects/roleme/context.md",
        "brain/index.md",
        "brain/topics/ai-product.md",
    ]


def test_discover_project_paths_follows_context_workflow_link_one_hop(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- roleMe: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text(
        "# roleMe\n\n- Workflow: workflow.md\n",
        encoding="utf-8",
    )
    (project_dir / "workflow.md").write_text(
        "# roleMe Workflow\n\n先对齐目标，再分解任务。\n",
        encoding="utf-8",
    )

    result = discover_project_paths(role_path, query="这个项目怎么协作")

    assert result == [
        "projects/index.md",
        "projects/roleme/context.md",
        "projects/roleme/workflow.md",
    ]


def test_build_context_snapshot_combines_resident_and_discovered_context(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "persona" / "narrative.md").write_text(
        "# 人物自述\n\n我是一个重视产品策略和角色设计的人。\n",
        encoding="utf-8",
    )
    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (role_path / "brain" / "topics").mkdir(parents=True, exist_ok=True)
    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- roleMe 重构: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text(
        "# roleMe 重构\n\n当前重构关注用户角色上下文与 AI 产品知识融合。\n\n- 参考知识: brain/topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n- AI 产品: topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI 产品\n\n关注 AI 产品策略、定位和落地。\n",
        encoding="utf-8",
    )

    snapshot = build_context_snapshot(
        role_path,
        query="这个 roleMe 重构里的 AI 产品策略怎么设计",
        max_chars=800,
        max_brain_depth=1,
    )

    assert "## resident" in snapshot
    assert "persona/narrative.md" in snapshot
    assert "## discovered" in snapshot
    assert "projects/roleme/context.md" in snapshot
    assert "brain/topics/ai-product.md" in snapshot


def test_build_context_snapshot_respects_character_budget(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "topics").mkdir(parents=True, exist_ok=True)
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n- AI 产品: topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI 产品\n\n" + ("策略 " * 200),
        encoding="utf-8",
    )

    snapshot = build_context_snapshot(
        role_path,
        query="AI 产品策略",
        max_chars=220,
        max_brain_depth=1,
    )

    assert len(snapshot) <= 220
