from scripts.build_skill import build_skill, publish_skill
from pathlib import Path
import runpy
import subprocess
import sys


def test_critical_role_tools_do_not_write_role_files_directly():
    checked_files = [
        Path("tools/workflow_index.py"),
        Path("tools/memory.py"),
        Path("tools/role_ops.py"),
    ]
    offenders: list[str] = []
    for path in checked_files:
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if ".write_text(" in line:
                offenders.append(f"{path}:{lineno}:{line.strip()}")

    assert offenders == []


def test_build_skill_creates_artifact_without_scripts(tmp_path):
    artifact = build_skill(output_root=tmp_path)

    assert artifact.name == "roleme"
    assert (artifact / "skill.yaml").exists()
    assert (artifact / "SKILL.md").exists()
    assert (artifact / "references" / "usage.md").exists()
    assert (artifact / "tools" / "role_ops.py").exists()
    assert (artifact / "tools" / "memory.py").exists()
    assert (artifact / "tools" / "context_router.py").exists()
    assert (artifact / "tools" / "file_ops.py").exists()
    assert (artifact / "tools" / "graph_index.py").exists()
    assert (artifact / "tools" / "workflow_index.py").exists()
    assert (artifact / "assets" / "templates" / "AGENT.md").exists()
    assert (artifact / "assets" / "templates" / "brain" / "graph" / "schema.yaml").exists()
    assert (artifact / "assets" / "templates" / "interview-planner-system.md").exists()
    assert (artifact / "assets" / "templates" / "persona" / "narrative.md").exists()
    assert not (artifact / "assets" / "templates" / "self-model").exists()
    assert not (artifact / "agents").exists()
    assert not (artifact / "scripts").exists()
    assert not (artifact / "tools" / "__pycache__").exists()


def test_build_skill_includes_graph_schema_template(tmp_path):
    artifact = build_skill(output_root=tmp_path)

    assert (artifact / "assets" / "templates" / "brain" / "graph" / "schema.yaml").exists()


def test_upgrade_role_bootstraps_missing_graph_schema(tmp_path, monkeypatch):
    role_home = tmp_path / ".roleMe"
    role_dir = role_home / "self"
    role_dir.mkdir(parents=True)
    (role_dir / "role.json").write_text(
        '{"roleName":"self","schemaVersion":"1.0"}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("ROLEME_HOME", str(role_home))
    monkeypatch.setattr("sys.argv", ["upgrade_role.py", "self"])

    runpy.run_path("scripts/upgrade_role.py", run_name="__main__")

    assert (role_dir / "brain" / "graph" / "schema.yaml").exists()
    assert (role_dir / "brain" / "graph" / "indexes").is_dir()


def test_validate_role_exits_nonzero_for_graph_warning(tmp_role_home, monkeypatch, capsys):
    from tools.graph_index import EdgeRecord, save_graph
    from tools.role_ops import initialize_role

    role_path = initialize_role("self", skill_version="0.1.0")
    save_graph(
        role_path,
        nodes=[],
        edges=[
            EdgeRecord(
                id="edge-orphan",
                type="related_to",
                from_node="missing-source",
                to_node="missing-target",
            )
        ],
    )
    monkeypatch.setattr("sys.argv", ["validate_role.py", "self"])

    try:
        runpy.run_path("scripts/validate_role.py", run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("validate_role.py should exit with non-zero status")

    output = capsys.readouterr().out
    assert "orphan edge source" in output


def test_validate_role_script_imports_tools_when_run_by_path(tmp_role_home, tmp_path):
    from tools.role_ops import initialize_role

    initialize_role("self", skill_version="0.1.0")

    result = subprocess.run(
        [
            sys.executable,
            str(Path.cwd() / "scripts" / "validate_role.py"),
            "self",
        ],
        cwd=tmp_path,
        env={"ROLEME_HOME": str(tmp_role_home)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert "ModuleNotFoundError" not in result.stderr
    assert result.returncode == 0
    assert "ok: self" in result.stdout


def test_build_skill_ignores_python_cache_files(tmp_path, monkeypatch):
    (tmp_path / "bundle" / "references").mkdir(parents=True)
    (tmp_path / "tools" / "__pycache__").mkdir(parents=True)
    (tmp_path / "templates" / "persona").mkdir(parents=True)

    (tmp_path / "bundle" / "SKILL.template.md").write_text("---\nname: roleme\n---\n", encoding="utf-8")
    (tmp_path / "bundle" / "skill.yaml").write_text(
        'name: "roleMe"\nversion: "0.1.0"\ndescription: "portable"\nentry: "SKILL.md"\n',
        encoding="utf-8",
    )
    (tmp_path / "bundle" / "references" / "usage.md").write_text("usage\n", encoding="utf-8")
    (tmp_path / "tools" / "role_ops.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "memory.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "context_router.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "__pycache__" / "memory.cpython-314.pyc").write_text("compiled", encoding="utf-8")
    (tmp_path / "templates" / "AGENT.md").write_text("agent\n", encoding="utf-8")
    (tmp_path / "templates" / "interview-planner-system.md").write_text("planner\n", encoding="utf-8")
    (tmp_path / "templates" / "persona" / "narrative.md").write_text("persona\n", encoding="utf-8")

    monkeypatch.setitem(build_skill.__globals__, "repo_root", lambda: tmp_path)

    artifact = build_skill(output_root=tmp_path / "out")

    assert not (artifact / "tools" / "__pycache__").exists()
    assert not list((artifact / "tools").glob("*.pyc"))


def test_build_skill_preserves_skill_frontmatter(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    manifest = (artifact / "skill.yaml").read_text(encoding="utf-8")

    assert skill_md.startswith("---\n")
    assert "name: roleme" in skill_md
    assert "description:" in skill_md
    assert 'entry: "SKILL.md"' in manifest


def test_build_skill_includes_reload_reminder_after_initialization(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "重新调用 `/roleMe <角色名>`" in skill_md
    assert "重新调用 `/roleMe <角色名>`" in usage_md


def test_build_skill_removes_default_self_semantics(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "默认加载 `self`" not in skill_md
    assert "~/.roleMe/self" not in usage_md
    assert "当前已有这些角色" in usage_md


def test_build_skill_includes_workflow_archive_guidance(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "帮我总结这个项目的工作方式" in skill_md
    assert "帮我总结成通用的工作方式" in skill_md
    assert "projects/<project-slug>/workflows/index.md" in skill_md
    assert "brain/workflows/index.md" in usage_md
    assert "一个 workflow，一个文件" in skill_md
    assert "一个 workflow，一个文件" in usage_md
    assert "workflow.md" not in skill_md
    assert "workflow.md" not in usage_md
    assert "general-workflow.md" not in skill_md
    assert "general-workflow.md" not in usage_md
    assert ".current-role.json" in usage_md
    assert "重新执行 `/roleMe <角色名>`" in usage_md


def test_build_skill_includes_harness_readability_guidance(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "未被结构化写入角色包的上下文，不应假定模型已经知道" in skill_md
    assert "归档内容优先追求对智能体可读" in skill_md
    assert "设计原则：为智能体可读性而设计" in usage_md
    assert "更适合被智能体消费的上下文" in usage_md


def test_build_skill_includes_role_storage_guidance(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "不要去 `~/.agents/skills/roleme/roles/`" in skill_md
    assert "角色包不保存在 skill 安装目录里" in usage_md
    assert "ROLEME_STATE_HOME" in usage_md


def test_build_skill_includes_natural_language_archive_guidance(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "应主动进行归档，而不必等待用户显式下达“归档”指令" in skill_md
    assert "判断不够确定时，优先写入 `memory/episodes/` 或项目记忆" in skill_md
    assert "## 自然语言归档" in usage_md
    assert "用户只需要自然表达内容，系统会先总结，再选择目标位置。" in usage_md


def test_build_skill_documents_context_graph_as_background_mechanism(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "Context Graph 是后台机制" in usage_md
    assert "不改变用户正常对话方式" in usage_md
    assert "ROLEME_GRAPH_ROUTING=0" in usage_md
    assert "ROLEME_GRAPH_ARCHIVE=0" in usage_md
    assert "用户不需要直接维护 Graph" in skill_md


def test_publish_skill_writes_repo_publish_directory(tmp_path, monkeypatch):
    (tmp_path / "bundle" / "references").mkdir(parents=True)
    (tmp_path / "tools").mkdir()
    (tmp_path / "templates" / "persona").mkdir(parents=True)

    (tmp_path / "bundle" / "SKILL.template.md").write_text("---\nname: roleme\n---\n", encoding="utf-8")
    (tmp_path / "bundle" / "skill.yaml").write_text(
        'name: "roleMe"\nversion: "0.1.0"\ndescription: "portable"\nentry: "SKILL.md"\n',
        encoding="utf-8",
    )
    (tmp_path / "bundle" / "references" / "usage.md").write_text("usage\n", encoding="utf-8")
    (tmp_path / "tools" / "role_ops.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "memory.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "context_router.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "templates" / "AGENT.md").write_text("agent\n", encoding="utf-8")
    (tmp_path / "templates" / "interview-planner-system.md").write_text("planner\n", encoding="utf-8")
    (tmp_path / "templates" / "persona" / "narrative.md").write_text("persona\n", encoding="utf-8")

    monkeypatch.setitem(publish_skill.__globals__, "repo_root", lambda: tmp_path)

    artifact = publish_skill()

    assert artifact == tmp_path / "skills" / "roleme"
    assert (artifact / "skill.yaml").exists()
    assert (artifact / "SKILL.md").exists()
    assert not (artifact / "agents").exists()
    assert (artifact / "references" / "usage.md").exists()
    assert (artifact / "tools" / "role_ops.py").exists()
    assert (artifact / "tools" / "context_router.py").exists()
    assert (artifact / "assets" / "templates" / "AGENT.md").exists()
    assert (artifact / "assets" / "templates" / "interview-planner-system.md").exists()
    assert (artifact / "assets" / "templates" / "persona" / "narrative.md").exists()


def test_build_script_runs_publish_when_executed_directly(tmp_path, monkeypatch):
    (tmp_path / "bundle" / "references").mkdir(parents=True)
    (tmp_path / "tools").mkdir()
    (tmp_path / "templates" / "persona").mkdir(parents=True)

    (tmp_path / "bundle" / "SKILL.template.md").write_text("---\nname: roleme\n---\n", encoding="utf-8")
    (tmp_path / "bundle" / "skill.yaml").write_text(
        'name: "roleMe"\nversion: "0.1.0"\ndescription: "portable"\nentry: "SKILL.md"\n',
        encoding="utf-8",
    )
    (tmp_path / "bundle" / "references" / "usage.md").write_text("usage\n", encoding="utf-8")
    (tmp_path / "tools" / "role_ops.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "memory.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "context_router.py").write_text("", encoding="utf-8")
    (tmp_path / "tools" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "templates" / "AGENT.md").write_text("agent\n", encoding="utf-8")
    (tmp_path / "templates" / "interview-planner-system.md").write_text("planner\n", encoding="utf-8")
    (tmp_path / "templates" / "persona" / "narrative.md").write_text("persona\n", encoding="utf-8")

    monkeypatch.setitem(build_skill.__globals__, "repo_root", lambda: tmp_path)
    monkeypatch.setitem(publish_skill.__globals__, "repo_root", lambda: tmp_path)

    namespace = {
        "__name__": "__main__",
        "publish_skill": publish_skill,
    }
    exec("if __name__ == '__main__':\n    publish_skill()", namespace)

    assert (tmp_path / "skills" / "roleme" / "skill.yaml").exists()
    assert (tmp_path / "skills" / "roleme" / "SKILL.md").exists()
