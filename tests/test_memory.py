from tools.memory import (
    build_frozen_snapshot,
    compact_memory,
    recall,
    replace_memory_entry,
    remove_memory_entry,
    summarize_and_write,
    write_memory,
)
from tools.role_ops import initialize_role


def test_build_frozen_snapshot_uses_resident_layers(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    snapshot = build_frozen_snapshot(role_path, max_chars=300)

    assert "persona/narrative.md" in snapshot
    assert "memory/USER.md" in snapshot
    assert len(snapshot) <= 300


def test_summarize_and_write_deduplicates_entries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    summarize_and_write(
        role_path,
        target="memory",
        source_text="default Chinese communication; default Chinese communication; lead with the conclusion",
    )

    result = recall(role_path, "default Chinese")
    assert result["summary_hits"].count("- default Chinese communication") == 1


def test_write_memory_supports_episode_and_promotion(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    episode_path = write_memory(
        role_path,
        target="episode",
        content="Important preference: explain code with the conclusion first and details after.",
    )
    summarize_and_write(
        role_path,
        target="memory",
        source_text="explain code with the conclusion first and details after",
    )

    result = recall(role_path, "conclusion first")
    assert episode_path.exists()
    assert result["summary_hits"] == [
        "- explain code with the conclusion first and details after"
    ]


def test_replace_memory_entry_updates_existing_value(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    write_memory(role_path, target="user", content="default Chinese communication")

    changed = replace_memory_entry(
        role_path,
        target="user",
        old_content="default Chinese communication",
        new_content="default bilingual communication",
    )

    result = recall(role_path, "bilingual")
    assert changed is True
    assert result["summary_hits"] == ["- default bilingual communication"]


def test_remove_memory_entry_deletes_existing_value(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    write_memory(role_path, target="memory", content="lead with the conclusion")

    changed = remove_memory_entry(
        role_path,
        target="memory",
        content="lead with the conclusion",
    )

    result = recall(role_path, "lead with the conclusion")
    assert changed is True
    assert result["summary_hits"] == []


def test_compact_memory_enforces_entry_budget(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    for index in range(10):
        write_memory(role_path, target="memory", content=f"item {index}")

    compact_memory(role_path, target="memory", max_entries=4)
    result = recall(role_path, "item")
    assert result["summary_hits"] == [
        "- item 6",
        "- item 7",
        "- item 8",
        "- item 9",
    ]
