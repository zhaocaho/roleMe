from tools.graph_index import load_graph
from tools.memory import InboxEntry, LearningEntry, write_inbox_entry, write_learning_entry
import tools.memory as memory
from tools.role_ops import initialize_role


def test_write_inbox_entry_creates_body_index_and_graph(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    path = write_inbox_entry(
        role_path,
        InboxEntry(
            id="inbox-20260422-001",
            title="Short design summaries",
            summary="User may prefer short summaries before design documents.",
            evidence="以后写设计文档可能还是先给我一版短摘要吧。",
            source="user_statement",
            suggested_target="user",
            confidence="medium",
            promotion_notes="Promote after repeated confirmation.",
            created_at="2026-04-22T10:00:00+08:00",
            last_seen_at="2026-04-22T10:00:00+08:00",
        ),
    )

    assert path == role_path / "memory" / "inbox" / "inbox-20260422-001.md"
    text = path.read_text(encoding="utf-8")
    assert "- source: user_statement" in text
    assert "- confidence: medium" in text
    assert "## Promotion Notes" in text
    index_text = (role_path / "memory" / "inbox" / "index.md").read_text(
        encoding="utf-8"
    )
    assert (
        "inbox-20260422-001: Short design summaries -> "
        "memory/inbox/inbox-20260422-001.md"
    ) in index_text
    graph = load_graph(role_path)
    assert any(
        node.type == "MemoryCandidate"
        and node.path == "memory/inbox/inbox-20260422-001.md"
        for node in graph.nodes
    )


def test_write_inbox_entry_updates_matching_pending_entry(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    first = InboxEntry(
        id="inbox-20260422-001",
        title="Short design summaries",
        summary="User may prefer short summaries before design documents.",
        evidence="first",
        source="user_statement",
        suggested_target="user",
        confidence="medium",
        promotion_notes="Promote after repeated confirmation.",
        created_at="2026-04-22T10:00:00+08:00",
        last_seen_at="2026-04-22T10:00:00+08:00",
    )
    second = InboxEntry(
        id="inbox-20260422-002",
        title="Short design summaries duplicate",
        summary="User may prefer short summaries before design documents.",
        evidence="second",
        source="user_statement",
        suggested_target="user",
        confidence="medium",
        promotion_notes="Promote after repeated confirmation.",
        created_at="2026-04-22T11:00:00+08:00",
        last_seen_at="2026-04-22T11:00:00+08:00",
    )

    path = write_inbox_entry(role_path, first)
    duplicate_path = write_inbox_entry(role_path, second)

    assert duplicate_path == path
    text = path.read_text(encoding="utf-8")
    assert "- recurrence: 2" in text
    assert "- last_seen_at: 2026-04-22T11:00:00+08:00" in text
    assert "second" in text
    assert not (role_path / "memory" / "inbox" / "inbox-20260422-002.md").exists()


def test_write_learning_entry_creates_body_index_and_graph(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    path = write_learning_entry(
        role_path,
        LearningEntry(
            id="learning-20260422-001",
            title="Design before implementation",
            rule_candidate="Do not implement before writing a design document.",
            how_to_apply="When the user requests a feature, draft design first.",
            evidence="不要一上来写实现，先出设计文档。",
            promotion_target="memory/USER.md",
            learning_type="correction",
            applies_to="global",
            created_at="2026-04-22T10:00:00+08:00",
            last_seen_at="2026-04-22T10:00:00+08:00",
        ),
    )

    assert path == role_path / "memory" / "learnings" / "learning-20260422-001.md"
    text = path.read_text(encoding="utf-8")
    assert "## Rule Candidate" in text
    assert "## Promotion Target" in text
    index_text = (role_path / "memory" / "learnings" / "index.md").read_text(
        encoding="utf-8"
    )
    assert (
        "learning-20260422-001: Design before implementation -> "
        "memory/learnings/learning-20260422-001.md"
    ) in index_text
    graph = load_graph(role_path)
    assert any(
        node.type == "Learning"
        and node.path == "memory/learnings/learning-20260422-001.md"
        for node in graph.nodes
    )


def test_write_learning_entry_updates_matching_pending_entry(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    first = LearningEntry(
        id="learning-20260422-001",
        title="Design before implementation",
        rule_candidate="Do not implement before writing a design document.",
        how_to_apply="Draft design first.",
        evidence="first",
        promotion_target="memory/USER.md",
        learning_type="correction",
        applies_to="global",
        created_at="2026-04-22T10:00:00+08:00",
        last_seen_at="2026-04-22T10:00:00+08:00",
    )
    second = LearningEntry(
        id="learning-20260422-002",
        title="Design before implementation duplicate",
        rule_candidate="Do not implement before writing a design document.",
        how_to_apply="Draft design first.",
        evidence="second",
        promotion_target="memory/USER.md",
        learning_type="correction",
        applies_to="global",
        created_at="2026-04-22T11:00:00+08:00",
        last_seen_at="2026-04-22T11:00:00+08:00",
    )

    path = write_learning_entry(role_path, first)
    duplicate_path = write_learning_entry(role_path, second)

    assert duplicate_path == path
    text = path.read_text(encoding="utf-8")
    assert "- recurrence: 2" in text
    assert "- last_seen_at: 2026-04-22T11:00:00+08:00" in text
    assert "second" in text
    assert not (
        role_path / "memory" / "learnings" / "learning-20260422-002.md"
    ).exists()


def test_candidate_markdown_survives_graph_write_failure(tmp_role_home, monkeypatch):
    role_path = initialize_role("self", skill_version="0.1.0")
    monkeypatch.setattr(
        memory,
        "_persist_graph",
        lambda role_path, nodes, edges: (_ for _ in ()).throw(
            RuntimeError("graph boom")
        ),
    )

    path = write_inbox_entry(
        role_path,
        InboxEntry(
            id="inbox-20260422-001",
            title="Short design summaries",
            summary="User may prefer short summaries before design documents.",
            evidence="first",
            source="user_statement",
            suggested_target="user",
            confidence="medium",
            promotion_notes="Promote after repeated confirmation.",
            created_at="2026-04-22T10:00:00+08:00",
            last_seen_at="2026-04-22T10:00:00+08:00",
        ),
    )

    assert path.exists()
    assert "Short design summaries" in path.read_text(encoding="utf-8")


def test_candidate_markdown_survives_graph_load_failure(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "graph" / "nodes.jsonl").write_text(
        "{bad json\n",
        encoding="utf-8",
    )

    path = write_inbox_entry(
        role_path,
        InboxEntry(
            id="inbox-20260422-001",
            title="Short design summaries",
            summary="User may prefer short summaries before design documents.",
            evidence="first",
            source="user_statement",
            suggested_target="user",
            confidence="medium",
            promotion_notes="Promote after repeated confirmation.",
            created_at="2026-04-22T10:00:00+08:00",
            last_seen_at="2026-04-22T10:00:00+08:00",
        ),
    )

    assert path.exists()
    assert "Short design summaries" in path.read_text(encoding="utf-8")
