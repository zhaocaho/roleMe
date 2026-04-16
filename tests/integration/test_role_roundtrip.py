from scripts.build_skill import build_skill
from tools.context_router import (
    build_context_snapshot,
    discover_brain_paths,
    discover_context_paths,
)
from tools.memory import build_frozen_snapshot, summarize_and_write
from tools.role_ops import (
    RoleInterview,
    RoleInterviewProject,
    RoleInterviewTopic,
    archive_general_workflow,
    begin_role_interview,
    doctor_role,
    finalize_role_interview,
    initialize_role,
    initialize_role_from_interview,
    parse_workflow_archive_response,
    load_query_context_bundle,
    load_role_bundle,
    submit_interview_answer,
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
    assert (artifact / "skill.yaml").exists()
    assert (artifact / "SKILL.md").exists()
    assert (artifact / "assets" / "templates" / "persona" / "narrative.md").exists()


def test_role_roundtrip_discovers_brain_topics_progressively(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI Product\n\nFocus on AI product strategy.\n\n- Related: topics/pricing.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "pricing.md").write_text(
        "# Pricing\n\nDiscuss AI product pricing and packaging.\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "index.md").write_text(
        "# Knowledge Index\n\n- AI Product: topics/ai-product.md\n",
        encoding="utf-8",
    )

    discovered = discover_brain_paths(role_path, query="I want to discuss AI product pricing", max_depth=2)

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
        "# AI Product\n\nFocus on AI product strategy and execution.\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "index.md").write_text(
        "# Knowledge Index\n\n- AI Product: topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "projects" / "index.md").write_text(
        "# Project Index\n\n- roleMe refactor: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text(
        "# roleMe refactor\n\nThis refactor connects user role context with AI product knowledge.\n- Reference: brain/topics/ai-product.md\n",
        encoding="utf-8",
    )

    discovered = discover_context_paths(
        role_path,
        query="How should we design AI product strategy in the roleMe refactor?",
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
        "# Narrative\n\nI focus on AI product strategy.\n",
        encoding="utf-8",
    )
    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (role_path / "brain" / "topics" / "ai-product.md").write_text(
        "# AI Product\n\nFocus on AI product strategy and execution.\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "index.md").write_text(
        "# Knowledge Index\n\n- AI Product: topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "projects" / "index.md").write_text(
        "# Project Index\n\n- roleMe refactor: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text(
        "# roleMe refactor\n\nThis refactor connects user role context with AI product knowledge.\n- Reference: brain/topics/ai-product.md\n",
        encoding="utf-8",
    )

    snapshot = build_context_snapshot(
        role_path,
        query="How should we design AI product strategy in the roleMe refactor?",
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
        "# AI Product\n\nFocus on AI product strategy and execution.\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "index.md").write_text(
        "# Knowledge Index\n\n- AI Product: topics/ai-product.md\n",
        encoding="utf-8",
    )
    (role_path / "projects" / "index.md").write_text(
        "# Project Index\n\n- roleMe refactor: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text(
        "# roleMe refactor\n\nThis refactor connects user role context with AI product knowledge.\n- Reference: brain/topics/ai-product.md\n",
        encoding="utf-8",
    )

    bundle = load_query_context_bundle(
        "self",
        query="How should we design AI product strategy in the roleMe refactor?",
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


def test_role_roundtrip_initializes_from_interview_and_supports_query_context(tmp_role_home):
    interview = RoleInterview(
        narrative="I focus on AI product strategy and role engineering.",
        communication_style="Default to Chinese and lead with the conclusion.",
        decision_rules="Prioritize execution, then consistency, then maintainability.",
        disclosure_layers="Start from resident context and expand on demand.",
        user_memory=["Default language is Chinese", "Lead with the conclusion"],
        memory_summary=["Long-term focus on AI product strategy"],
        brain_topics=[
            RoleInterviewTopic(
                slug="ai-product",
                title="AI Product",
                summary="Focus on positioning and execution.",
                content="# AI Product\n\nFocus on positioning and execution.\n",
            )
        ],
        projects=[
            RoleInterviewProject(
                name="roleme",
                context="This project is refactoring roleMe into a Hermes-like user role context system.",
                overlay="Answer with both role engineering and AI product perspectives.",
                memory=["Current priority is interview orchestration and progressive retrieval."],
            )
        ],
    )

    initialize_role_from_interview("self", skill_version="0.1.0", interview=interview)
    bundle = load_query_context_bundle(
        "self",
        query="How should the roleMe project handle AI product strategy?",
        max_chars=900,
        max_brain_depth=1,
    )

    assert "persona/narrative.md" in bundle.resident_files
    assert "brain/topics/ai-product.md" in bundle.discovered_paths
    assert "projects/roleme/context.md" in bundle.discovered_paths
    assert "AI Product" in bundle.context_snapshot


def test_role_roundtrip_interview_session_materializes_and_supports_query_context(
    tmp_role_home,
):
    session = begin_role_interview("self")

    answers = {
        "narrative": "I am an AI product strategist who moved from delivery work into role engineering, and I now focus on long-term human-AI collaboration systems.",
        "language_preference": "默认中文，需要时也可以英文。",
        "communication_style": "Default to Chinese, lead with the conclusion, and keep collaboration direct and structured.",
        "decision_rules": "Prioritize execution, then consistency, then maintainability.",
        "disclosure_layers": "Start from resident context and expand only when needed.",
        "user_memory": "- Default language is Chinese\n- Lead with the conclusion",
        "memory_summary": "- Long-term focus on AI product strategy\n- Active roleMe refactor",
        "brain_topics": "\n".join(
            [
                "title: AI Product",
                "slug: ai-product",
                "summary: Focus on positioning and execution.",
                "content: # AI Product",
                "",
                "Focus on positioning and execution.",
            ]
        ),
        "projects": "\n".join(
            [
                "name: roleme",
                "context: This project is refactoring roleMe into a user role context system.",
                "overlay: Answer with both role engineering and AI product perspectives.",
                "memory: Current priority is interview orchestration | Progressive retrieval remains important.",
            ]
        ),
    }

    while session.current_stage != "review":
        session = submit_interview_answer(session, answers[session.current_stage])

    finalize_role_interview(session, skill_version="0.1.0")
    bundle = load_query_context_bundle(
        "self",
        query="How should the roleMe project handle AI product strategy?",
        max_chars=900,
        max_brain_depth=1,
    )

    assert session.current_stage == "review"
    assert "brain/topics/ai-product.md" in bundle.discovered_paths
    assert "projects/roleme/context.md" in bundle.discovered_paths
    assert "AI Product" in bundle.context_snapshot


def test_role_roundtrip_interview_correction_with_replace_mode_materializes_latest_value(
    tmp_role_home,
):
    session = begin_role_interview("self")
    session = submit_interview_answer(
        session,
        "I am an AI product strategist who moved from delivery work into role engineering, and I now focus on long-term human-AI collaboration systems.",
    )
    session = submit_interview_answer(session, "默认中文，需要时也可以英文。")
    session = submit_interview_answer(
        session,
        "Default to Chinese, lead with the conclusion, and keep collaboration direct and structured.",
    )
    session = submit_interview_answer(
        session,
        "Default to Chinese and keep responses concise and direct.",
        slot="communication_style",
        mode="replace",
    )

    answers = {
        "decision_rules": "Prioritize execution, then consistency, then maintainability.",
        "disclosure_layers": "Start from resident context and expand only when needed.",
        "user_memory": "- Default language is Chinese\n- Keep responses concise",
        "memory_summary": "- Long-term focus on AI product strategy\n- Active roleMe refactor",
        "brain_topics": "\n".join(
            [
                "title: AI Product",
                "slug: ai-product",
                "summary: Focus on positioning and execution.",
                "content: # AI Product",
                "",
                "Focus on positioning and execution.",
            ]
        ),
        "projects": "\n".join(
            [
                "name: roleme",
                "context: This project is refactoring roleMe into a user role context system.",
                "overlay: Answer with both role engineering and AI product perspectives.",
                "memory: Current priority is interview orchestration | Progressive retrieval remains important.",
            ]
        ),
    }

    while session.current_stage != "review":
        session = submit_interview_answer(session, answers[session.current_stage])

    role_path = finalize_role_interview(session, skill_version="0.1.0")

    assert "keep responses concise and direct" in (
        role_path / "persona" / "communication-style.md"
    ).read_text(encoding="utf-8")


def test_role_roundtrip_partial_interview_can_finalize_and_keep_growing_later(
    tmp_role_home,
):
    session = begin_role_interview("self")
    session = submit_interview_answer(
        session,
        "I am an AI product strategist who moved from delivery work into role engineering, and I now focus on long-term human-AI collaboration systems.",
    )
    session = submit_interview_answer(session, "")
    session = submit_interview_answer(
        session,
        "Lead with the conclusion and keep collaboration direct and structured.",
    )
    session = submit_interview_answer(
        session,
        "Prioritize execution first, consistency second, and long-term maintainability third.",
    )

    role_path = finalize_role_interview(session, skill_version="0.1.0")

    assert session.current_stage == "review"
    assert (role_path / "persona" / "narrative.md").exists()
    assert "Preferred language:" not in (
        role_path / "memory" / "USER.md"
    ).read_text(encoding="utf-8")
    assert "Lead with the conclusion" in (
        role_path / "persona" / "communication-style.md"
    ).read_text(encoding="utf-8")


def test_role_roundtrip_archives_general_workflow_and_reloads_snapshot_notice(
    tmp_role_home,
):
    initialize_role("self", skill_version="0.1.0")
    load_role_bundle("self")
    plan = parse_workflow_archive_response(
        {
            "kind": "general",
            "role_name": "self",
            "project_title": None,
            "project_slug": None,
            "workflow_slug": "general-collaboration",
            "workflow_title": "通用协作工作流",
            "workflow_summary": "适合需要先设计再执行的任务",
            "workflow_applies_to": "当用户需要先对齐工作方式、再进入执行时使用",
            "workflow_keywords": ["协作", "设计", "执行"],
            "workflow_doc_markdown": "# 通用协作工作流\n\n先澄清场景，再开始执行。\n",
            "context_summary_markdown": "## 全局上下文\n\n用于沉淀通用协作流程。\n",
            "user_rules": ["先澄清场景，再开始执行"],
            "memory_summary": ["可复用流程应沉淀为通用工作方式"],
            "project_memory": [],
        }
    )

    result = archive_general_workflow(plan)

    assert "brain/workflows/general-collaboration.md" in result.written_paths
    assert "memory/MEMORY.md" in result.written_paths
    assert result.requires_reload is True
