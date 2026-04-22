from tools.graph_index import load_graph
from tools.memory import InboxEntry, LearningEntry, SessionSummary, write_session_summary
from tools.role_ops import doctor_role, initialize_role


def _summary(session_id: str) -> SessionSummary:
    inbox = InboxEntry(
        id="inbox-20260422-001",
        title="Short summaries",
        summary="User may prefer short summaries before design documents.",
        evidence="可能还是先给我一版短摘要吧。",
        source="user_statement",
        suggested_target="user",
        confidence="medium",
        promotion_notes="Promote after repeated confirmation.",
        created_at="2026-04-22T10:00:00+08:00",
        last_seen_at="2026-04-22T10:00:00+08:00",
    )
    learning = LearningEntry(
        id="learning-20260422-001",
        title="Design before implementation",
        rule_candidate="Do not implement before writing a design document.",
        how_to_apply="Draft design first when the user requests a feature.",
        evidence="先出设计文档。",
        promotion_target="memory/USER.md",
        learning_type="correction",
        applies_to="global",
        created_at="2026-04-22T10:00:00+08:00",
        last_seen_at="2026-04-22T10:00:00+08:00",
    )
    return SessionSummary(
        session_id=session_id,
        date="2026-04-22",
        started_at="2026-04-22T09:30:00+08:00",
        ended_at="2026-04-22T11:00:00+08:00",
        summary="讨论 roleMe 记忆生命周期。",
        keywords=["roleMe", "inbox", "session"],
        work_completed=["修订设计文档"],
        decisions=["session 文件使用日内序号"],
        artifacts=[
            "docs/superpowers/specs/"
            "2026-04-22-roleme-memory-lifecycle-internal-skills-design.md"
        ],
        inbox_candidates=[inbox],
        learning_candidates=[learning],
        suggested_promotions=["确认后提升到 USER"],
    )


def test_initialize_role_creates_sessions_index_and_schema(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    assert (role_path / "memory" / "sessions" / "index.md").exists()
    schema_text = (role_path / "brain" / "graph" / "schema.yaml").read_text(
        encoding="utf-8"
    )
    assert "  - Session" in schema_text


def test_write_session_summary_creates_file_index_and_graph(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    path = write_session_summary(role_path, _summary("2026-04-22-001"))

    assert path == role_path / "memory" / "sessions" / "2026-04-22-001.md"
    text = path.read_text(encoding="utf-8")
    assert "- session_id: 2026-04-22-001" in text
    assert "## Suggested Promotions" in text
    index_text = (role_path / "memory" / "sessions" / "index.md").read_text(
        encoding="utf-8"
    )
    assert "## 2026-04-22-001" in index_text
    assert "- file: 2026-04-22-001.md" in index_text
    graph = load_graph(role_path)
    assert any(
        node.type == "Session"
        and node.path == "memory/sessions/2026-04-22-001.md"
        for node in graph.nodes
    )


def test_write_session_summary_does_not_overwrite_same_day_session(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    first = write_session_summary(role_path, _summary("2026-04-22-001"))
    second = write_session_summary(role_path, _summary("2026-04-22-002"))

    assert first.exists()
    assert second.exists()
    assert first != second


def test_doctor_reports_missing_session_target(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "memory" / "sessions" / "index.md").write_text(
        "# Sessions\n\n"
        "## 2026-04-22-001\n"
        "- file: 2026-04-22-001.md\n"
        "- summary: missing\n"
        "- inbox_candidates: 1\n"
        "- learning_candidates: 0\n"
        "- promotions: 0\n",
        encoding="utf-8",
    )

    report = doctor_role("self")

    assert any(
        "memory/sessions/index.md points to missing file: "
        "memory/sessions/2026-04-22-001.md" in warning
        for warning in report.warnings
    )
