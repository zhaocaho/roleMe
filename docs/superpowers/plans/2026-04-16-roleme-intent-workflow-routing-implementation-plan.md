# roleMe Intent Workflow Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add intent-driven workflow routing that prefers project workflows over global workflows, keeps project `context.md` in the discovered bundle, and works from nested Git subdirectories.

**Architecture:** Extend `tools/context_router.py` with three focused helpers: ancestor Git-root discovery, lightweight workflow-intent detection, and project/global workflow candidate selection. Keep `tools/role_ops.py` unchanged for project bootstrap semantics so loading from subdirectories still does not create project directories; this feature only affects runtime context discovery.

**Tech Stack:** Python 3.12, pytest, Markdown role bundles under `~/.roleMe/`

---

## File Map

- Modify: `tools/context_router.py`
  Add nested repo-root detection, workflow intent scoring, workflow bundle selection, and project-aware discovered path assembly.
- Modify: `tests/test_context_router.py`
  Add TDD coverage for nested workdirs, project `context.md + workflow` bundling, global workflow fallback, and low-confidence no-op behavior.
- Create/Modify: `docs/superpowers/specs/2026-04-16-roleme-intent-workflow-routing-design.md`
  Already updated; keep aligned if implementation reveals wording drift.

### Task 1: Write Failing Routing Tests

**Files:**
- Modify: `tests/test_context_router.py`
- Test: `tests/test_context_router.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_discover_context_paths_prefers_current_project_workflow_from_nested_subdirectory(
    tmp_role_home,
    tmp_path,
    monkeypatch,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    repo_root = tmp_path / "roleMe"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "packages" / "ui").mkdir(parents=True)
    monkeypatch.chdir(repo_root / "packages" / "ui")

    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- roleMe: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text(
        "# roleMe\n\n项目摘要。\n",
        encoding="utf-8",
    )
    (project_dir / "workflow-requirements.md").write_text(
        "# roleMe Requirements Workflow\n\n## 适用任务\n\n开始需求、梳理需求。\n",
        encoding="utf-8",
    )

    assert discover_context_paths(role_path, query="开始需求") == [
        "projects/index.md",
        "projects/roleme/context.md",
        "projects/roleme/workflow-requirements.md",
    ]


def test_discover_context_paths_falls_back_to_global_workflow_when_project_missing(
    tmp_role_home,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "topics").mkdir(parents=True, exist_ok=True)
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n- 通用需求工作流: topics/general-workflow-requirements.md\n",
        encoding="utf-8",
    )
    (role_path / "brain" / "topics" / "general-workflow-requirements.md").write_text(
        "# 通用需求工作流\n\n## 适用任务\n\n开始需求、拆解目标。\n",
        encoding="utf-8",
    )

    assert discover_context_paths(role_path, query="开始需求") == [
        "brain/index.md",
        "brain/topics/general-workflow-requirements.md",
    ]


def test_discover_context_paths_does_not_inject_workflow_for_low_confidence_requests(
    tmp_role_home,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    project_dir = role_path / "projects" / "roleme"
    project_dir.mkdir(parents=True, exist_ok=True)
    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- roleMe: projects/roleme/context.md\n",
        encoding="utf-8",
    )
    (project_dir / "context.md").write_text("# roleMe\n\n项目摘要。\n", encoding="utf-8")
    (project_dir / "workflow.md").write_text("# roleMe Workflow\n\n通用流程。\n", encoding="utf-8")

    result = discover_context_paths(role_path, query="读一下这个文件")

    assert "projects/roleme/workflow.md" not in result
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python3 -m pytest tests/test_context_router.py -k "workflow or nested or low_confidence" -v`
Expected: FAIL because `context_router.py` does not yet detect current project from nested directories, does not choose intent-specific workflow files, and still uses only the old project-index scoring path.

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_context_router.py
git commit -m "test: cover intent workflow routing"
```

### Task 2: Implement Minimal Workflow Routing

**Files:**
- Modify: `tools/context_router.py`
- Test: `tests/test_context_router.py`

- [ ] **Step 1: Add minimal helpers for repo-root, intent, and workflow selection**

```python
WORKFLOW_INTENT_PATTERNS = {
    "requirements": ("需求", "requirement", "story", "scope"),
    "bugfix": ("bug", "报错", "异常", "修复", "fix"),
    "analysis": ("分析", "排查", "诊断", "原因", "analy"),
}


def _find_git_repo_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None
```

- [ ] **Step 2: Implement project-aware workflow bundle selection**

```python
def _discover_project_workflow_paths(
    role_path: Path,
    query: str,
) -> list[str]:
    ...
    return [
        "projects/index.md",
        f"projects/{slug}/context.md",
        f"projects/{slug}/{workflow_name}",
    ]
```

- [ ] **Step 3: Wire workflow routing into `discover_context_paths()`**

```python
def discover_context_paths(role_path: Path, query: str, max_brain_depth: int = 1) -> list[str]:
    workflow_paths = discover_workflow_paths(role_path, query)
    if workflow_paths:
        return workflow_paths
    ...
```

- [ ] **Step 4: Re-run the focused tests and verify they pass**

Run: `python3 -m pytest tests/test_context_router.py -k "workflow or nested or low_confidence" -v`
Expected: PASS

- [ ] **Step 5: Commit the green implementation**

```bash
git add tools/context_router.py tests/test_context_router.py
git commit -m "feat: add intent workflow routing"
```

### Task 3: Run Regression Coverage

**Files:**
- Modify: none
- Test: `tests/test_context_router.py`

- [ ] **Step 1: Run the full context-router test module**

Run: `python3 -m pytest tests/test_context_router.py -v`
Expected: PASS

- [ ] **Step 2: Run targeted role-op tests to confirm project bootstrap behavior is unchanged**

Run: `python3 -m pytest tests/test_role_ops.py::test_load_role_bundle_bootstraps_project_from_git_repo_root tests/test_role_ops.py::test_load_role_bundle_does_not_bootstrap_project_from_git_subdirectory -v`
Expected: PASS

- [ ] **Step 3: Commit if any follow-up fixes were needed**

```bash
git add tools/context_router.py tests/test_context_router.py docs/superpowers/specs/2026-04-16-roleme-intent-workflow-routing-design.md
git commit -m "test: verify context routing regressions"
```
