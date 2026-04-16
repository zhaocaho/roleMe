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


def test_discover_context_paths_prefers_project_workflow_index_entry(
    tmp_role_home,
    tmp_path,
    monkeypatch,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    repo_root = tmp_path / "roleMe"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(repo_root)

    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- roleMe: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    project_root = role_path / "projects" / "roleme"
    project_dir = project_root / "workflows"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_root / "context.md").write_text(
        "# roleMe\n\n项目摘要。\n\n- 参考知识: brain/topics/ai-product.md\n",
        encoding="utf-8",
    )
    (project_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## requirements\n"
        "- title: 需求分析 workflow\n"
        "- file: requirements.md\n"
        "- applies_to: 当用户想梳理需求、澄清范围、整理用户故事时使用\n"
        "- keywords: 需求, requirement, scope\n"
        "- summary: 用于把模糊需求整理成可规划输入\n",
        encoding="utf-8",
    )
    (project_dir / "requirements.md").write_text(
        "# 需求分析 workflow\n\n先澄清边界，再整理故事。\n",
        encoding="utf-8",
    )

    result = discover_context_paths(role_path, query="开始梳理这个需求")

    assert result == [
        "projects/index.md",
        "projects/roleme/context.md",
        "projects/roleme/workflows/index.md",
        "projects/roleme/workflows/requirements.md",
    ]


def test_discover_context_paths_falls_back_to_global_workflow_index_when_project_missing(
    tmp_role_home,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n- 工作流索引: workflows/index.md\n",
        encoding="utf-8",
    )
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## analysis\n"
        "- title: 问题分析 workflow\n"
        "- file: analysis.md\n"
        "- applies_to: 当用户想分析问题、排查原因、理解异常时使用\n"
        "- keywords: 分析, 排查, 诊断, why\n"
        "- summary: 用于定位问题和形成分析结论\n",
        encoding="utf-8",
    )
    (workflows_dir / "analysis.md").write_text(
        "# 问题分析 workflow\n\n先复述问题，再定位原因。\n",
        encoding="utf-8",
    )

    result = discover_context_paths(role_path, query="帮我分析这个异常原因")

    assert result == [
        "brain/index.md",
        "brain/workflows/index.md",
        "brain/workflows/analysis.md",
    ]


def test_discover_context_paths_does_not_inject_workflow_for_low_confidence_requests(
    tmp_role_home,
    tmp_path,
    monkeypatch,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    repo_root = tmp_path / "roleMe"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(repo_root)

    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- roleMe: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text("# roleMe\n\n项目摘要。\n", encoding="utf-8")
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## requirements\n"
        "- title: 需求分析 workflow\n"
        "- file: requirements.md\n"
        "- applies_to: 当用户想梳理需求、澄清范围、整理用户故事时使用\n"
        "- keywords: 需求, requirement, scope\n"
        "- summary: 用于把模糊需求整理成可规划输入\n",
        encoding="utf-8",
    )
    (workflows_dir / "requirements.md").write_text(
        "# 需求分析 workflow\n\n先澄清边界，再整理故事。\n",
        encoding="utf-8",
    )

    result = discover_context_paths(role_path, query="读一下这个文件")

    assert "projects/roleme/workflows/index.md" not in result
    assert "projects/roleme/workflows/requirements.md" not in result


def test_discover_context_paths_does_not_inject_ambiguous_workflow_entries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## analysis\n"
        "- title: 分析 workflow\n"
        "- file: analysis.md\n"
        "- applies_to: 分析问题和定位原因\n"
        "- keywords: 分析, 原因\n"
        "- summary: 用于分析问题\n\n"
        "## diagnose\n"
        "- title: 诊断 workflow\n"
        "- file: diagnose.md\n"
        "- applies_to: 诊断问题和定位原因\n"
        "- keywords: 诊断, 原因\n"
        "- summary: 用于诊断问题\n",
        encoding="utf-8",
    )
    (workflows_dir / "analysis.md").write_text("# 分析\n\n内容。\n", encoding="utf-8")
    (workflows_dir / "diagnose.md").write_text("# 诊断\n\n内容。\n", encoding="utf-8")

    result = discover_context_paths(role_path, query="分析这个原因")

    assert "brain/workflows/index.md" not in result
    assert "brain/workflows/analysis.md" not in result
    assert "brain/workflows/diagnose.md" not in result


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


def test_build_context_snapshot_includes_resident_workflow_summary_sections(
    tmp_role_home,
    tmp_path,
    monkeypatch,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    repo_root = tmp_path / "roleMe"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(repo_root)

    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- roleMe: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "context.md").write_text("# roleMe\n\n项目摘要。\n", encoding="utf-8")
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## requirements\n"
        "- title: 需求分析 workflow\n"
        "- file: requirements.md\n"
        "- applies_to: 当用户想梳理需求、澄清范围、整理用户故事时使用\n"
        "- keywords: 需求, scope\n"
        "- summary: 用于把模糊需求整理成可规划输入\n",
        encoding="utf-8",
    )

    snapshot = build_context_snapshot(role_path, query="开始梳理需求", max_chars=1200)

    assert "## resident" in snapshot
    assert "## Current Project Workflow Summaries" in snapshot
    assert "## discovered" in snapshot


def test_discover_context_paths_matches_project_workflow_for_end_to_end_delivery_language(
    tmp_role_home,
    tmp_path,
    monkeypatch,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    repo_root = tmp_path / "coresys-devops"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(repo_root)

    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- coresys-devops: projects/coresys-devops/context.md\n",
        encoding="utf-8",
    )
    project_dir = role_path / "projects" / "coresys-devops"
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "context.md").write_text("# coresys-devops\n\n项目摘要。\n", encoding="utf-8")
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## end-to-end-delivery\n"
        "- title: 端到端交付 workflow\n"
        "- file: end-to-end-delivery.md\n"
        "- applies_to: 当用户要求按完整交付流程推进需求实现时使用\n"
        "- keywords: 端到端开发流程, 软件需求规格说明书, 前后端, 数据库, 完整实现\n"
        "- summary: 用于从需求澄清到上线发布的完整闭环\n",
        encoding="utf-8",
    )
    (workflows_dir / "end-to-end-delivery.md").write_text(
        "# End-to-End Delivery Workflow\n\n正文。\n",
        encoding="utf-8",
    )

    result = discover_context_paths(
        role_path,
        query="用端到端开发流程来实现以下需求，并按照软件需求规格说明书完成前后端和数据库代码",
    )

    assert result == [
        "projects/index.md",
        "projects/coresys-devops/context.md",
        "projects/coresys-devops/workflows/index.md",
        "projects/coresys-devops/workflows/end-to-end-delivery.md",
    ]


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
