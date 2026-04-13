from tools.role_ops import (
    RoleInterview,
    RoleInterviewProject,
    RoleInterviewTopic,
    assess_interview_gaps,
    begin_role_interview,
    build_interview_planner_prompt,
    doctor_role,
    finalize_role_interview,
    initialize_role,
    initialize_role_from_interview,
    list_roles,
    load_query_context_bundle,
    load_role_bundle,
    submit_interview_answer,
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


def test_initialize_role_from_interview_materializes_persona_memory_brain_and_projects(
    tmp_role_home,
):
    interview = RoleInterview(
        narrative="I focus on AI product strategy and role engineering.",
        communication_style="Default to Chinese and lead with the conclusion.",
        decision_rules="Prioritize execution, then consistency, then long-term maintainability.",
        disclosure_layers="Start with resident conclusions and expand projects or topics only when needed.",
        user_memory=[
            "Default language is Chinese",
            "Lead with the conclusion, then add details",
        ],
        memory_summary=[
            "Long-term focus on AI product strategy",
            "Refactoring roleMe into a user role context system",
        ],
        brain_topics=[
            RoleInterviewTopic(
                slug="ai-product",
                title="AI Product",
                summary="Focus on positioning, packaging, and execution.",
                content="# AI Product\n\nFocus on positioning, packaging, and execution.\n",
            )
        ],
        projects=[
            RoleInterviewProject(
                name="roleme",
                context="This project is turning roleMe into a Hermes-like user role context system.",
                overlay="Answer project questions through both role engineering and AI product lenses.",
                memory=["Current priority is interview orchestration and progressive retrieval."],
            )
        ],
    )

    role_path = initialize_role_from_interview("self", skill_version="0.1.0", interview=interview)

    assert "I focus on AI product strategy and role engineering." in (
        role_path / "persona" / "narrative.md"
    ).read_text(encoding="utf-8")
    assert "- Default language is Chinese" in (
        role_path / "memory" / "USER.md"
    ).read_text(encoding="utf-8")
    assert "- Long-term focus on AI product strategy" in (
        role_path / "memory" / "MEMORY.md"
    ).read_text(encoding="utf-8")
    assert (role_path / "brain" / "topics" / "ai-product.md").exists()
    assert "AI Product" in (role_path / "brain" / "index.md").read_text(encoding="utf-8")
    assert (role_path / "projects" / "roleme" / "context.md").exists()
    assert "Current priority is interview orchestration and progressive retrieval." in (
        role_path / "projects" / "roleme" / "memory.md"
    ).read_text(encoding="utf-8")


def test_begin_role_interview_starts_with_narrative_prompt(tmp_role_home):
    session = begin_role_interview("self")

    assert session.role_name == "self"
    assert session.current_stage == "narrative"
    assert session.answers == {}
    assert session.preview == ""
    assert "first-person" in session.current_prompt.lower()


def test_submit_interview_answer_reasks_same_slot_when_answer_is_too_shallow(tmp_role_home):
    session = begin_role_interview("self")

    next_session = submit_interview_answer(session, "I am a PM.")

    assert next_session.current_stage == "narrative"
    assert "already know" in next_session.current_prompt.lower()
    assert "how you got here" in next_session.current_prompt.lower()


def test_submit_interview_answer_moves_to_next_gap_when_answer_is_rich_enough(tmp_role_home):
    session = begin_role_interview("self")

    next_session = submit_interview_answer(
        session,
        "I am an AI product strategist who moved from delivery work into role engineering, and I now focus on building long-term human-AI collaboration systems.",
    )

    assert next_session.current_stage == "communication_style"
    assert "communication" in next_session.current_prompt.lower()
    assert "answers" not in next_session.current_prompt.lower()


def test_submit_interview_answer_advances_to_review_with_preview(tmp_role_home):
    session = begin_role_interview("self")

    answers = {
        "narrative": "I am an AI product strategist who moved from delivery work into role engineering, and I now focus on long-term human-AI collaboration systems.",
        "communication_style": "Default to Chinese, lead with the conclusion, and keep collaboration direct and structured.",
        "decision_rules": "Prioritize execution first, consistency second, and long-term maintainability third.",
        "disclosure_layers": "Start from resident context, then expand project and topic context only when needed.",
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

    assert session.current_stage == "review"
    assert "confirm" in session.current_prompt.lower()
    assert "AI Product" in session.preview
    assert "roleme" in session.preview


def test_assess_interview_gaps_reports_missing_and_partial_slots():
    gaps = assess_interview_gaps(
        {
            "narrative": "I am an AI product strategist.",
            "user_memory": "- Default language is Chinese",
        }
    )

    by_slot = {gap.slot: gap for gap in gaps}
    assert by_slot["narrative"].status == "partial"
    assert by_slot["communication_style"].status == "missing"
    assert by_slot["user_memory"].status == "partial"


def test_build_interview_planner_prompt_includes_known_answers_and_gap_summary(tmp_role_home):
    session = begin_role_interview("self")
    session = submit_interview_answer(
        session,
        "I am an AI product strategist who moved from delivery work into role engineering, and I now focus on building long-term human-AI collaboration systems.",
    )

    prompt = build_interview_planner_prompt(session)

    assert "Known answers" in prompt
    assert "Gap assessment" in prompt
    assert "communication_style" in prompt
    assert "AI product strategist" in prompt


def test_finalize_role_interview_writes_role_bundle_from_session(tmp_role_home):
    session = begin_role_interview("self")

    answers = {
        "narrative": "I am an AI product strategist who moved from delivery work into role engineering, and I now focus on long-term human-AI collaboration systems.",
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

    role_path = finalize_role_interview(session, skill_version="0.1.0")

    assert (role_path / "persona" / "narrative.md").exists()
    assert "I am an AI product strategist who moved from delivery work into role engineering" in (
        role_path / "persona" / "narrative.md"
    ).read_text(encoding="utf-8")
    assert "AI Product" in (role_path / "brain" / "index.md").read_text(encoding="utf-8")
    assert "Current priority is interview orchestration" in (
        role_path / "projects" / "roleme" / "memory.md"
    ).read_text(encoding="utf-8")
