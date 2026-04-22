from tools.graph_index import load_graph
from tools.memory import InternalSkill, write_internal_skill
from tools.role_ops import doctor_role, initialize_role


VALID_BODY = """# 代码评审能力

## Purpose

Find behavioral risks in code changes.

## When To Use

Use when the user asks for code review.

## Inputs

Changed files or a diff.

## Procedure

Review correctness, tests, and regressions.

## Outputs

Findings first, then residual risks.

## Boundaries

Do not rewrite unrelated code.
"""


def test_initialize_role_creates_skills_index_and_schema(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    assert (role_path / "skills" / "index.md").exists()
    schema_text = (role_path / "brain" / "graph" / "schema.yaml").read_text(
        encoding="utf-8"
    )
    assert "  - Skill" in schema_text


def test_write_internal_skill_creates_body_index_and_graph(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    path = write_internal_skill(
        role_path,
        InternalSkill(
            slug="code-review",
            title="代码评审能力",
            applies_to="当用户要求 review、审查代码、找风险时使用",
            keywords=["review", "代码评审", "风险"],
            summary="按风险优先级输出代码审查意见",
            body_markdown=VALID_BODY,
        ),
    )

    assert path == role_path / "skills" / "code-review.md"
    index_text = (role_path / "skills" / "index.md").read_text(encoding="utf-8")
    assert "## code-review" in index_text
    assert "- file: code-review.md" in index_text
    graph = load_graph(role_path)
    assert any(
        node.type == "Skill" and node.path == "skills/code-review.md"
        for node in graph.nodes
    )


def test_doctor_reports_internal_skill_missing_required_section(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "skills" / "index.md").write_text(
        "# Internal Skills\n\n"
        "## code-review\n"
        "- title: 代码评审能力\n"
        "- file: code-review.md\n"
        "- applies_to: 当用户要求 review 时使用\n"
        "- keywords: review\n"
        "- summary: 审查代码\n",
        encoding="utf-8",
    )
    (role_path / "skills" / "code-review.md").write_text(
        "# 代码评审能力\n\n## Purpose\n\nFind risks.\n",
        encoding="utf-8",
    )

    report = doctor_role("self")

    assert any(
        "skills/code-review.md missing required section: When To Use" in warning
        for warning in report.warnings
    )
