from tools.memory import (
    build_frozen_snapshot,
    compact_memory,
    recall,
    summarize_and_write,
    write_memory,
)
from tools.role_ops import initialize_role


def test_build_frozen_snapshot_uses_resident_layers(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    snapshot = build_frozen_snapshot(role_path, max_chars=300)

    assert "memory/USER.md" in snapshot
    assert len(snapshot) <= 300


def test_summarize_and_write_deduplicates_entries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    summarize_and_write(
        role_path,
        target="memory",
        source_text="默认中文沟通；默认中文沟通；结论先行。",
    )

    result = recall(role_path, "默认中文")
    assert result["summary_hits"].count("- 默认中文沟通") == 1


def test_write_memory_supports_episode_and_promotion(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    episode_path = write_memory(
        role_path,
        target="episode",
        content="重要偏好：代码解释要先结论后细节。",
    )
    summarize_and_write(role_path, target="memory", source_text="代码解释要先结论后细节。")

    result = recall(role_path, "代码解释")
    assert episode_path.exists()
    assert result["summary_hits"] == ["- 代码解释要先结论后细节"]


def test_compact_memory_enforces_entry_budget(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    for index in range(10):
        write_memory(role_path, target="memory", content=f"item {index}")

    compact_memory(role_path, target="memory", max_entries=4)
    result = recall(role_path, "item")
    assert len(result["summary_hits"]) == 4
