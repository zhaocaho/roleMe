# roleMe Workflow Summary Preload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preload current-project and global workflow summary sections into the resident snapshot without loading workflow bodies, so workflow routing has stable candidate visibility before query-specific discovery runs.

**Architecture:** Keep the change split across the existing resident/discovered boundary. Extend `tools/memory.py` with workflow-summary snapshot builders, then have `tools/context_router.py` consume the richer resident snapshot while preserving the current workflow discovery and scoring path. Validate the new resident sections, failure fallback behavior, and query-time routing with focused unit and integration tests.

**Tech Stack:** Python 3, pytest, markdown-based role bundles, existing `tools/context_router.py`, `tools/memory.py`, and `tools/role_ops.py`

---

## File Map

- Modify: `tools/memory.py`
  - Add helpers that resolve the current project from `cwd`, parse workflow indexes, render resident snapshot workflow summary sections, and keep the existing resident budget behavior stable.
- Modify: `tools/context_router.py`
  - Keep `discover_workflow_paths()` behavior intact while updating `build_context_snapshot()` to compose the richer resident snapshot cleanly.
- Modify: `tests/test_memory.py`
  - Add resident snapshot tests for project/global workflow summary sections, missing-index fallback, invalid-index fallback, and budget behavior.
- Modify: `tests/test_context_router.py`
  - Add end-to-end snapshot composition coverage and real-language workflow routing coverage with the new resident sections present.
- Modify: `tests/integration/test_role_roundtrip.py`
  - Add regression coverage that `load_query_context_bundle()` returns a resident snapshot containing workflow summary sections when the current `cwd` matches a known project.

## Task 1: Add failing resident snapshot tests for workflow summaries

**Files:**
- Modify: `tests/test_memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test for current-project and global workflow summary sections**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory.py::test_build_frozen_snapshot_includes_current_project_and_global_workflow_summaries -v`
Expected: FAIL because `build_frozen_snapshot()` only emits `RESIDENT_PATHS` content today.

- [ ] **Step 3: Add failing fallback tests for missing or invalid workflow indexes**

```python
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
    (project_dir / "context.md").parent.mkdir(parents=True, exist_ok=True)
    (project_dir / "context.md").write_text("# roleMe\n\n项目摘要。\n", encoding="utf-8")
    invalid_dir = project_dir / "workflows"
    invalid_dir.mkdir(parents=True, exist_ok=True)
    (invalid_dir / "index.md").write_text("# 工作流索引\n\n- bad shape\n", encoding="utf-8")

    snapshot = build_frozen_snapshot(role_path, max_chars=1200)

    assert "## Current Project Workflow Summaries" not in snapshot
    assert "## Global Workflow Summaries" not in snapshot
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_memory.py -k "workflow_summaries" -v`
Expected: FAIL because the resident snapshot does not yet know how to parse or skip workflow summary sections.

- [ ] **Step 5: Commit the red tests**

```bash
git add tests/test_memory.py
git commit -m "test: cover resident workflow summary preload"
```

## Task 2: Implement resident workflow summary builders in `tools/memory.py`

**Files:**
- Modify: `tools/memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Add helper signatures for current-project detection and summary rendering**

```python
from tools.workflow_index import WorkflowIndexEntry, parse_workflow_index


def _slugify_workspace(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _find_git_repo_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _resolve_current_project_slug(role_path: Path) -> str | None:
    projects_dir = role_path / "projects"
    if not projects_dir.exists():
        return None
    project_slugs = {path.name for path in projects_dir.iterdir() if path.is_dir()}
    repo_root = _find_git_repo_root()
    if repo_root is None:
        return None
    workspace_slug = _slugify_workspace(repo_root.name)
    return workspace_slug if workspace_slug in project_slugs else None
```

- [ ] **Step 2: Add summary-section builders that parse valid index entries only**

```python
def _read_workflow_entries(index_path: Path) -> list[WorkflowIndexEntry]:
    if not index_path.exists() or not index_path.is_file():
        return []
    text = index_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return parse_workflow_index(text)


def _render_workflow_summary_section(title: str, entries: list[WorkflowIndexEntry], project_slug: str | None = None) -> str:
    if not entries:
        return ""
    lines = [f"## {title}"]
    if project_slug:
        lines.append(f"project: {project_slug}")
    lines.append("")
    for entry in entries:
        lines.extend(
            [
                f"- slug: {entry.slug}",
                f"  title: {entry.title}",
                f"  applies_to: {entry.applies_to}",
                f"  keywords: {', '.join(entry.keywords)}",
                f"  summary: {entry.summary}",
            ]
        )
    return "\n".join(lines).strip()
```

- [ ] **Step 3: Extend `build_frozen_snapshot()` to append summary sections after the existing resident files**

```python
def build_frozen_snapshot(role_path: Path, max_chars: int = 2_000) -> str:
    section_budget = max(1, max_chars // len(RESIDENT_PATHS))
    chunks: list[str] = []
    for relative in RESIDENT_PATHS:
        header = f"## {relative}\n"
        content_budget = max(0, section_budget - len(header))
        path = role_path / relative
        if relative.startswith("memory/"):
            content = "\n".join(_read_entries(path))
        else:
            content = path.read_text(encoding="utf-8").strip()
        chunks.append(f"{header}{content[:content_budget]}")

    project_slug = _resolve_current_project_slug(role_path)
    if project_slug is not None:
        project_entries = _read_workflow_entries(
            role_path / "projects" / project_slug / "workflows" / "index.md"
        )
        project_section = _render_workflow_summary_section(
            "Current Project Workflow Summaries",
            project_entries,
            project_slug=project_slug,
        )
        if project_section:
            chunks.append(project_section)

    global_entries = _read_workflow_entries(role_path / "brain" / "workflows" / "index.md")
    global_section = _render_workflow_summary_section(
        "Global Workflow Summaries",
        global_entries,
    )
    if global_section:
        chunks.append(global_section)

    return "\n\n".join(chunks)[:max_chars]
```

- [ ] **Step 4: Run resident snapshot tests to verify they pass**

Run: `pytest tests/test_memory.py -k "workflow_summaries or build_frozen_snapshot" -v`
Expected: PASS

- [ ] **Step 5: Commit the resident snapshot implementation**

```bash
git add tools/memory.py tests/test_memory.py
git commit -m "feat: preload workflow summaries into resident snapshot"
```

## Task 3: Add failing context snapshot tests that verify resident/discovered composition

**Files:**
- Modify: `tests/test_context_router.py`
- Test: `tests/test_context_router.py`

- [ ] **Step 1: Add a failing snapshot test for resident workflow sections**

```python
def test_build_context_snapshot_includes_resident_workflow_summary_sections(
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
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
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

    snapshot = build_context_snapshot(role_path, query="开始梳理需求", max_chars=1200)

    assert "## resident" in snapshot
    assert "## Current Project Workflow Summaries" in snapshot
    assert "## discovered" in snapshot
```

- [ ] **Step 2: Run the new context snapshot test to verify it fails**

Run: `pytest tests/test_context_router.py::test_build_context_snapshot_includes_resident_workflow_summary_sections -v`
Expected: FAIL until the richer resident snapshot is visible through `build_context_snapshot()`.

- [ ] **Step 3: Add a failing real-language routing regression test**

```python
def test_discover_context_paths_matches_project_workflow_for_end_to_end_delivery_language(
    tmp_role_home,
    tmp_path,
    monkeypatch,
):
    role_path = initialize_role("self", skill_version="0.1.0")
    repo_root = tmp_path / "coresys-devops"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(repo_root)

    (role_path / "projects" / "index.md").write_text(
        "# 项目索引\n\n- coresys-devops: projects/coresys-devops/context.md\n",
        encoding="utf-8",
    )
    project_dir = role_path / "projects" / "coresys-devops"
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "context.md").write_text("# coresys-devops\n\n项目摘要。\n", encoding="utf-8")
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## end-to-end-delivery\n"
        "- title: 端到端交付 workflow\n"
        "- file: end-to-end-delivery.md\n"
        "- applies_to: 当用户要求按完整交付流程推进需求实现时使用\n"
        "- keywords: 端到端开发流程, 软件需求规格说明书, 前后端, 数据库, 完整实现\n"
        "- summary: 用于从需求澄清到上线发布的完整闭环\n",
        encoding="utf-8",
    )
    (workflows_dir / "end-to-end-delivery.md").write_text(
        "# End-to-End Delivery Workflow\n\n正文。\n",
        encoding="utf-8",
    )

    result = discover_context_paths(
        role_path,
        query="用端到端开发流程来实现以下需求，并按照软件需求规格说明书完成前后端和数据库代码",
    )

    assert result == [
        "projects/index.md",
        "projects/coresys-devops/context.md",
        "projects/coresys-devops/workflows/index.md",
        "projects/coresys-devops/workflows/end-to-end-delivery.md",
    ]
```

- [ ] **Step 4: Run the focused routing regression to verify current behavior**

Run: `pytest tests/test_context_router.py -k "end_to_end_delivery_language or resident_workflow_summary_sections" -v`
Expected: One test may already pass because routing exists; keep it as a regression guard before implementation changes.

- [ ] **Step 5: Commit the context-router red tests**

```bash
git add tests/test_context_router.py
git commit -m "test: cover workflow summary resident snapshot composition"
```

## Task 4: Refine snapshot composition and keep routing behavior stable

**Files:**
- Modify: `tools/context_router.py`
- Test: `tests/test_context_router.py`

- [ ] **Step 1: Make the resident/discovered composition explicit and stable**

```python
def build_context_snapshot(
    role_path: Path,
    query: str,
    max_chars: int = 4_000,
    max_brain_depth: int = 1,
) -> str:
    resident_budget = max(1, max_chars // 2)
    discovered_budget = max(1, max_chars - resident_budget)

    resident_snapshot = build_frozen_snapshot(role_path, max_chars=resident_budget)
    discovered_paths = discover_context_paths(
        role_path,
        query=query,
        max_brain_depth=max_brain_depth,
    )
    ...
```
Keep this function shape, but ensure the richer `resident_snapshot` survives truncation predictably and still leaves room for discovered content.

- [ ] **Step 2: If needed, add a helper that trims discovered content before cutting resident sections**

```python
def _append_discovered_chunk(
    chunks: list[str],
    role_path: Path,
    relative_path: str,
    budget: int,
    used_chars: int,
) -> int:
    full_path = role_path / relative_path
    if not full_path.exists() or not full_path.is_file():
        return used_chars
    header = f"## {relative_path}\n"
    remaining_budget = budget - used_chars - len(header) - 2
    if remaining_budget <= 0:
        return used_chars
    content = full_path.read_text(encoding="utf-8").strip()[:remaining_budget]
    chunk = f"{header}{content}"
    chunks.append(chunk)
    return used_chars + len(chunk) + 2
```

- [ ] **Step 3: Run focused context-router tests to verify the snapshot still contains resident and discovered sections**

Run: `pytest tests/test_context_router.py -k "build_context_snapshot or workflow" -v`
Expected: PASS

- [ ] **Step 4: Run the full context-router suite**

Run: `pytest tests/test_context_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit the context snapshot refinement**

```bash
git add tools/context_router.py tests/test_context_router.py
git commit -m "feat: expose workflow summaries in context snapshots"
```

## Task 5: Add query-bundle integration coverage

**Files:**
- Modify: `tests/integration/test_role_roundtrip.py`
- Test: `tests/integration/test_role_roundtrip.py`

- [ ] **Step 1: Add a failing integration test for `load_query_context_bundle()`**

```python
def test_role_roundtrip_load_query_bundle_includes_workflow_summary_sections(
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
        "- applies_to: 当用户想梳理需求时使用\n"
        "- keywords: 需求\n"
        "- summary: 用于把模糊需求整理成可规划输入\n",
        encoding="utf-8",
    )

    bundle = load_query_context_bundle("self", query="开始梳理需求", max_chars=1500)

    assert "## Current Project Workflow Summaries" in bundle.context_snapshot
```

- [ ] **Step 2: Run the integration test to verify behavior**

Run: `pytest tests/integration/test_role_roundtrip.py::test_role_roundtrip_load_query_bundle_includes_workflow_summary_sections -v`
Expected: PASS after resident snapshot preload is implemented.

- [ ] **Step 3: Run the broader roundtrip regression set**

Run: `pytest tests/integration/test_role_roundtrip.py -k "context_snapshot or workflow_summary" -v`
Expected: PASS

- [ ] **Step 4: Commit the integration regression coverage**

```bash
git add tests/integration/test_role_roundtrip.py
git commit -m "test: cover workflow summary preload in query bundles"
```

## Task 6: Full regression, spec coverage check, and cleanup

**Files:**
- Modify: `docs/superpowers/plans/2026-04-16-roleme-workflow-summary-preload-implementation-plan.md`
- Test: `tests/test_memory.py`, `tests/test_context_router.py`, `tests/integration/test_role_roundtrip.py`, `tests/test_role_ops.py`

- [ ] **Step 1: Run the targeted regression suite**

Run: `pytest tests/test_memory.py tests/test_context_router.py tests/integration/test_role_roundtrip.py tests/test_role_ops.py -v`
Expected: PASS

- [ ] **Step 2: Run a repository grep to ensure the new resident section names are consistent**

Run: `rg -n "Current Project Workflow Summaries|Global Workflow Summaries|scope-aware key|workflow summary" tools tests docs -S`
Expected: Matches only the intended implementation, tests, and spec/plan references.

- [ ] **Step 3: Review the implementation against the spec**

Checklist:
- Current `cwd` project only, not all projects
- Global workflow summaries load independently
- Missing or invalid indexes are skipped silently
- Resident snapshot contains summaries only, not workflow bodies
- Existing `discover_workflow_paths()` scoring remains the default
- Project/global collision handling is scoped if any mapping is introduced

- [ ] **Step 4: Commit the verified final state**

```bash
git add tools/memory.py tools/context_router.py tests/test_memory.py tests/test_context_router.py tests/integration/test_role_roundtrip.py tests/test_role_ops.py docs/superpowers/plans/2026-04-16-roleme-workflow-summary-preload-implementation-plan.md
git commit -m "feat: preload workflow summaries into role snapshots"
```
