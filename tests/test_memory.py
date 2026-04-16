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


def test_build_frozen_snapshot_includes_current_project_and_global_workflow_summaries(
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
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "context.md").write_text("# roleMe\n\n项目摘要。\n", encoding="utf-8")
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

    global_dir = role_path / "brain" / "workflows"
    global_dir.mkdir(parents=True, exist_ok=True)
    (global_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## analysis\n"
        "- title: 问题分析 workflow\n"
        "- file: analysis.md\n"
        "- applies_to: 当用户想分析问题、排查原因时使用\n"
        "- keywords: 分析, 排查\n"
        "- summary: 用于定位问题和形成分析结论\n",
        encoding="utf-8",
    )

    snapshot = build_frozen_snapshot(role_path, max_chars=1200)

    assert "## Current Project Workflow Summaries" in snapshot
    assert "project: roleme" in snapshot
    assert "slug: requirements" in snapshot
    assert "## Global Workflow Summaries" in snapshot
    assert "slug: analysis" in snapshot


def test_build_frozen_snapshot_skips_workflow_summaries_when_indexes_missing_or_invalid(
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
    invalid_dir = project_dir / "workflows"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    (invalid_dir / "index.md").write_text("# 工作流索引\n\n- bad shape\n", encoding="utf-8")

    snapshot = build_frozen_snapshot(role_path, max_chars=1200)

    assert "## Current Project Workflow Summaries" not in snapshot
    assert "## Global Workflow Summaries" not in snapshot


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
