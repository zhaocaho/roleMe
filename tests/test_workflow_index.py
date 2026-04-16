from pathlib import Path

from tools.workflow_index import (
    WorkflowIndexEntry,
    normalize_workflow_slug,
    parse_workflow_index,
    render_workflow_index,
    upsert_workflow_index_entry,
)


def test_normalize_workflow_slug_keeps_stable_unicode_tokens():
    assert normalize_workflow_slug("需求分析 workflow") == "需求分析-workflow"
    assert normalize_workflow_slug(" RoleMe / Requirements  ") == "roleme-requirements"


def test_parse_workflow_index_round_trips_structured_entries():
    text = (
        "# 工作流索引\n\n"
        "## requirements\n"
        "- title: 需求分析 workflow\n"
        "- file: requirements.md\n"
        "- applies_to: 当用户想梳理需求、澄清范围、确认目标时使用\n"
        "- keywords: 需求, requirement, scope\n"
        "- summary: 用于把模糊需求整理成可进入规划的输入\n"
    )

    entries = parse_workflow_index(text)

    assert entries == [
        WorkflowIndexEntry(
            slug="requirements",
            title="需求分析 workflow",
            file="requirements.md",
            applies_to="当用户想梳理需求、澄清范围、确认目标时使用",
            keywords=("需求", "requirement", "scope"),
            summary="用于把模糊需求整理成可进入规划的输入",
        )
    ]
    assert render_workflow_index(entries) == text


def test_upsert_workflow_index_entry_replaces_existing_slug_without_duplication(
    tmp_path: Path,
):
    index_path = tmp_path / "index.md"
    index_path.write_text(
        "# 工作流索引\n\n"
        "## requirements\n"
        "- title: 旧标题\n"
        "- file: requirements.md\n"
        "- applies_to: 旧适用场景\n"
        "- keywords: 需求\n"
        "- summary: 旧摘要\n",
        encoding="utf-8",
    )

    upsert_workflow_index_entry(
        index_path,
        WorkflowIndexEntry(
            slug="requirements",
            title="需求分析 workflow",
            file="requirements.md",
            applies_to="当用户想梳理需求、澄清范围、确认目标时使用",
            keywords=("需求", "requirement", "scope"),
            summary="新版摘要",
        ),
    )

    rendered = index_path.read_text(encoding="utf-8")
    assert rendered.count("## requirements") == 1
    assert "新版摘要" in rendered
    assert "旧摘要" not in rendered
