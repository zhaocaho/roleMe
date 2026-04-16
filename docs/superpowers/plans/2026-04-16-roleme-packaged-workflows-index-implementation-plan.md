# roleMe 打包产物工作流索引 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `roleMe` 的 workflow 体系从旧的单文件路径切换为 `workflows/index.md + 单 workflow 单文件`，并让开发仓库与打包产物保持一致。

**Architecture:** 新增 `tools/workflow_index.py` 作为 workflow 索引注册表的唯一读写入口，集中处理 slug、解析、渲染和 upsert。`tools/role_ops.py` 扩展 workflow 归档契约并改写到 `brain/workflows/`、`projects/<slug>/workflows/`；`tools/context_router.py` 改为先读 `workflows/index.md` 再按条目打分命中目标文件；最后通过 `bundle/` 文档更新和 `scripts/build_skill.py` 重建，让 `skills/roleme/` 发布产物同步新结构。

**Tech Stack:** Python 3.12, pytest, Markdown role bundles, 本地文件系统打包脚本

---

## File Map

- Create: `tools/workflow_index.py`
  负责 workflow 索引条目数据结构、slug 规范化、Markdown 解析、渲染与 upsert。
- Create: `tests/test_workflow_index.py`
  覆盖 workflow 索引模块的 round-trip、slug 规范化、更新去重和缺字段忽略逻辑。
- Modify: `tools/role_ops.py`
  扩展 `WorkflowArchivePlan`，改写项目级/全局 workflow 归档路径，并维护 `workflows/index.md` 与入口链接。
- Modify: `tools/context_router.py`
  使用 workflow 索引条目做项目优先、全局回退、低置信度不注入的命中逻辑。
- Modify: `tests/test_role_ops.py`
  用 TDD 固定新的 workflow 归档契约和落盘路径。
- Modify: `tests/test_context_router.py`
  用 TDD 固定基于 `workflows/index.md` 的路由与渐进式披露边界。
- Modify: `tests/integration/test_role_roundtrip.py`
  覆盖自然语言归档后的 roundtrip 行为与 resident reload 提醒。
- Modify: `bundle/SKILL.template.md`
  把打包后 skill 的运行时原则、默认归档路径和 workflow 组织说明改为新结构。
- Modify: `bundle/references/usage.md`
  把使用说明中的 workflow 目录、入口和自然语言归档示例改为新结构。
- Modify: `tests/test_repo_scripts.py`
  固定打包后产物文档必须包含 `workflows/index.md` 与“一个 workflow，一个文件”的说明。
- Regenerate: `skills/roleme/SKILL.md`
  由构建脚本生成，不能手改。
- Regenerate: `skills/roleme/references/usage.md`
  由构建脚本生成，不能手改。
- Regenerate: `skills/roleme/tools/role_ops.py`
  由构建脚本从 `tools/role_ops.py` 复制。
- Regenerate: `skills/roleme/tools/context_router.py`
  由构建脚本从 `tools/context_router.py` 复制。
- Create/Modify: `docs/superpowers/plans/2026-04-16-roleme-packaged-workflows-index-implementation-plan.md`
  当前计划文档。

### Task 1: 建立 workflow 索引共享模块

**Files:**
- Create: `tools/workflow_index.py`
- Create: `tests/test_workflow_index.py`
- Test: `tests/test_workflow_index.py`

- [ ] **Step 1: 先写 workflow 索引模块的失败测试**

```python
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


def test_upsert_workflow_index_entry_replaces_existing_slug_without_duplication(tmp_path: Path):
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
```

- [ ] **Step 2: 运行新测试，确认它们先失败**

Run: `python3 -m pytest tests/test_workflow_index.py -v`
Expected: FAIL，因为 `tools/workflow_index.py` 还不存在。

- [ ] **Step 3: 写最小实现，提供 workflow 索引数据结构与读写能力**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class WorkflowIndexEntry:
    slug: str
    title: str
    file: str
    applies_to: str
    keywords: tuple[str, ...]
    summary: str


SECTION_PATTERN = re.compile(r"^##\s+([A-Za-z0-9_-]+)\s*$", re.MULTILINE)
FIELD_PATTERN = re.compile(r"^- ([a-z_]+):\s*(.*)$")


def normalize_workflow_slug(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value.casefold()).strip("-_")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "workflow"


def parse_workflow_index(text: str) -> list[WorkflowIndexEntry]:
    entries: list[WorkflowIndexEntry] = []
    sections = list(SECTION_PATTERN.finditer(text))
    for index, match in enumerate(sections):
        slug = match.group(1).strip()
        start = match.end()
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        block = text[start:end].strip().splitlines()
        fields: dict[str, str] = {}
        for raw_line in block:
            line = raw_line.strip()
            field_match = FIELD_PATTERN.match(line)
            if field_match:
                fields[field_match.group(1)] = field_match.group(2).strip()
        required = {"title", "file", "applies_to", "keywords", "summary"}
        if not required.issubset(fields):
            continue
        entries.append(
            WorkflowIndexEntry(
                slug=slug,
                title=fields["title"],
                file=fields["file"],
                applies_to=fields["applies_to"],
                keywords=tuple(
                    item.strip() for item in fields["keywords"].split(",") if item.strip()
                ),
                summary=fields["summary"],
            )
        )
    return entries


def render_workflow_index(entries: list[WorkflowIndexEntry]) -> str:
    lines = ["# 工作流索引", ""]
    for entry in entries:
        lines.extend(
            [
                f"## {entry.slug}",
                f"- title: {entry.title}",
                f"- file: {entry.file}",
                f"- applies_to: {entry.applies_to}",
                f"- keywords: {', '.join(entry.keywords)}",
                f"- summary: {entry.summary}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def upsert_workflow_index_entry(index_path: Path, entry: WorkflowIndexEntry) -> None:
    existing = parse_workflow_index(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    updated: list[WorkflowIndexEntry] = []
    replaced = False
    for current in existing:
        if current.slug == entry.slug:
            updated.append(entry)
            replaced = True
        else:
            updated.append(current)
    if not replaced:
        updated.append(entry)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(render_workflow_index(updated), encoding="utf-8")
```

- [ ] **Step 4: 重新运行新测试，确认 workflow 索引模块通过**

Run: `python3 -m pytest tests/test_workflow_index.py -v`
Expected: PASS

- [ ] **Step 5: 提交共享模块**

```bash
git add tools/workflow_index.py tests/test_workflow_index.py
git commit -m "feat: add workflow index helpers"
```

### Task 2: 重塑归档契约并改写 workflow 落盘路径

**Files:**
- Modify: `tools/role_ops.py`
- Modify: `tests/test_role_ops.py`
- Modify: `tests/integration/test_role_roundtrip.py`
- Test: `tests/test_role_ops.py`
- Test: `tests/integration/test_role_roundtrip.py`

- [ ] **Step 1: 先写失败测试，固定新的 workflow 归档契约和新路径**

```python
def test_parse_workflow_archive_response_returns_structured_workflow_plan():
    plan = parse_workflow_archive_response(
        {
            "kind": "general",
            "project_title": None,
            "project_slug": None,
            "workflow_slug": "general-collaboration",
            "workflow_title": "通用协作工作流",
            "workflow_summary": "适合需要先设计再执行的任务",
            "workflow_applies_to": "当用户需要先对齐工作方式、再进入执行时使用",
            "workflow_keywords": ["协作", "设计", "执行"],
            "workflow_doc_markdown": "# 通用协作工作流\n\n先澄清场景，再开始执行。\n",
            "context_summary_markdown": "## 全局上下文\n\n用于沉淀通用协作流程。\n",
            "user_rules": ["先澄清场景，再开始执行"],
            "memory_summary": ["可复用流程应沉淀为通用工作方式"],
            "project_memory": [],
        }
    )

    assert plan == WorkflowArchivePlan(
        kind="general",
        role_name=None,
        project_title=None,
        project_slug=None,
        workflow_slug="general-collaboration",
        workflow_title="通用协作工作流",
        workflow_summary="适合需要先设计再执行的任务",
        workflow_applies_to="当用户需要先对齐工作方式、再进入执行时使用",
        workflow_keywords=["协作", "设计", "执行"],
        workflow_doc_markdown="# 通用协作工作流\n\n先澄清场景，再开始执行。",
        context_summary_markdown="## 全局上下文\n\n用于沉淀通用协作流程。",
        user_rules=["先澄清场景，再开始执行"],
        memory_summary=["可复用流程应沉淀为通用工作方式"],
        project_memory=[],
    )


def test_parse_workflow_archive_response_derives_routable_defaults_for_legacy_payload():
    plan = parse_workflow_archive_response(
        {
            "kind": "project",
            "project_title": "roleMe",
            "project_slug": "roleme",
            "workflow_title": "roleMe 项目工作流",
            "workflow_doc_markdown": "# roleMe 项目工作流\n\n先确认角色边界，再设计能力。\n",
            "context_summary_markdown": "## 项目上下文\n\n该项目聚焦角色包与工作流沉淀。\n",
            "user_rules": [],
            "memory_summary": [],
            "project_memory": [],
        }
    )

    assert plan.workflow_slug == "roleme-项目工作流"
    assert plan.workflow_summary == "该项目聚焦角色包与工作流沉淀。"
    assert plan.workflow_applies_to == "该项目聚焦角色包与工作流沉淀。"
    assert "roleme" in plan.workflow_keywords
    assert "项目工作流" in plan.workflow_keywords


def test_archive_general_workflow_writes_workflow_directory_and_index(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    load_role_bundle("self")
    plan = parse_workflow_archive_response(
        {
            "kind": "general",
            "role_name": "self",
            "project_title": None,
            "project_slug": None,
            "workflow_slug": "general-collaboration",
            "workflow_title": "通用协作工作流",
            "workflow_summary": "适合需要先设计再执行的任务",
            "workflow_applies_to": "当用户需要先对齐工作方式、再进入执行时使用",
            "workflow_keywords": ["协作", "设计", "执行"],
            "workflow_doc_markdown": "# 通用协作工作流\n\n先澄清场景，再开始执行。\n",
            "context_summary_markdown": "## 全局上下文\n\n用于沉淀通用协作流程。\n",
            "user_rules": ["先澄清场景，再开始执行"],
            "memory_summary": ["可复用流程应沉淀为通用工作方式"],
            "project_memory": [],
        }
    )

    result = archive_general_workflow(plan)
    role_path = Path(get_current_role_state().role_path)

    assert "brain/workflows/index.md" in result.written_paths
    assert "brain/workflows/general-collaboration.md" in result.written_paths
    assert "- 工作流索引: workflows/index.md" in (
        role_path / "brain" / "index.md"
    ).read_text(encoding="utf-8")


def test_archive_project_workflow_writes_project_workflow_directory_and_context_link(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    load_role_bundle("self")
    plan = parse_workflow_archive_response(
        {
            "kind": "project",
            "role_name": "self",
            "project_title": "roleMe",
            "project_slug": "roleme",
            "workflow_slug": "requirements",
            "workflow_title": "需求分析 workflow",
            "workflow_summary": "用于把模糊需求整理成可规划输入",
            "workflow_applies_to": "当用户想梳理需求、澄清范围、整理用户故事时使用",
            "workflow_keywords": ["需求", "requirement", "scope"],
            "workflow_doc_markdown": "# 需求分析 workflow\n\n先澄清边界，再整理故事。\n",
            "context_summary_markdown": "# roleMe\n\n该项目聚焦角色包与工作流沉淀。\n",
            "user_rules": [],
            "memory_summary": [],
            "project_memory": ["先确认角色边界，再设计能力"],
        }
    )

    result = archive_project_workflow(plan)

    assert "projects/roleme/workflows/index.md" in result.written_paths
    assert "projects/roleme/workflows/requirements.md" in result.written_paths
    assert "- 工作流索引: workflows/index.md" in (
        role_path / "projects" / "roleme" / "context.md"
    ).read_text(encoding="utf-8")
```

- [ ] **Step 2: 运行 role_ops 与 roundtrip 定向测试，确认它们先失败**

Run: `python3 -m pytest tests/test_role_ops.py -k "workflow_archive or archive_general_workflow or archive_project_workflow" tests/integration/test_role_roundtrip.py -k "workflow" -v`
Expected: FAIL，因为 `WorkflowArchivePlan` 还没有 `workflow_slug` 等字段，旧 payload 也还不会自动补出可路由的 metadata，归档函数也还在写旧路径。

- [ ] **Step 3: 扩展归档契约并把写入逻辑改成 `workflows/` 目录**

```python
from tools.workflow_index import (
    WorkflowIndexEntry,
    normalize_workflow_slug,
    upsert_workflow_index_entry,
)


@dataclass(frozen=True)
class WorkflowArchivePlan:
    kind: str
    role_name: str | None
    project_title: str | None
    project_slug: str | None
    workflow_slug: str
    workflow_title: str
    workflow_summary: str
    workflow_applies_to: str
    workflow_keywords: list[str]
    workflow_doc_markdown: str
    context_summary_markdown: str
    user_rules: list[str]
    memory_summary: list[str]
    project_memory: list[str]


def _first_meaningful_line(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip(" -#\t")
        if line:
            return line
    return ""


def _derive_workflow_metadata(
    payload: dict[str, object],
    workflow_title: str,
    workflow_slug: str,
) -> tuple[str, str, list[str]]:
    context_summary = str(payload.get("context_summary_markdown", "")).strip()
    workflow_summary = (
        str(payload.get("workflow_summary", "")).strip()
        or _first_meaningful_line(context_summary)
        or workflow_title
    )
    workflow_applies_to = (
        str(payload.get("workflow_applies_to", "")).strip()
        or _first_meaningful_line(context_summary)
        or workflow_title
    )
    workflow_keywords = [
        str(item).strip()
        for item in payload.get("workflow_keywords", [])
        if str(item).strip()
    ]
    if not workflow_keywords:
        tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", f"{workflow_title} {workflow_slug}")
        workflow_keywords = list(dict.fromkeys(token.casefold() for token in tokens if token.strip()))
    return workflow_summary, workflow_applies_to, workflow_keywords


def parse_workflow_archive_response(raw: str | dict[str, object]) -> WorkflowArchivePlan:
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    workflow_title = str(payload.get("workflow_title", "")).strip()
    if not workflow_title:
        raise ValueError("workflow_title is required.")
    workflow_slug = str(payload.get("workflow_slug", "")).strip() or normalize_workflow_slug(workflow_title)
    workflow_summary, workflow_applies_to, workflow_keywords = _derive_workflow_metadata(
        payload,
        workflow_title,
        workflow_slug,
    )
    return WorkflowArchivePlan(
        kind=str(payload.get("kind", "")).strip().lower(),
        role_name=str(payload.get("role_name")).strip() if payload.get("role_name") is not None else None,
        project_title=str(payload.get("project_title")).strip() if payload.get("project_title") is not None else None,
        project_slug=str(payload.get("project_slug")).strip() if payload.get("project_slug") is not None else None,
        workflow_slug=workflow_slug,
        workflow_title=workflow_title,
        workflow_summary=workflow_summary,
        workflow_applies_to=workflow_applies_to,
        workflow_keywords=workflow_keywords,
        workflow_doc_markdown=str(payload.get("workflow_doc_markdown", "")).strip(),
        context_summary_markdown=str(payload.get("context_summary_markdown", "")).strip(),
        user_rules=[str(item).strip() for item in payload.get("user_rules", []) if str(item).strip()],
        memory_summary=[str(item).strip() for item in payload.get("memory_summary", []) if str(item).strip()],
        project_memory=[str(item).strip() for item in payload.get("project_memory", []) if str(item).strip()],
    )


def archive_general_workflow(plan: WorkflowArchivePlan) -> WorkflowArchiveResult:
    role_path = Path(get_current_role_state().role_path)
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    workflow_filename = f"{plan.workflow_slug}.md"
    (workflows_dir / workflow_filename).write_text(
        sanitize_archived_markdown(plan.workflow_doc_markdown) + "\n",
        encoding="utf-8",
    )
    upsert_workflow_index_entry(
        workflows_dir / "index.md",
        WorkflowIndexEntry(
            slug=plan.workflow_slug,
            title=plan.workflow_title,
            file=workflow_filename,
            applies_to=plan.workflow_applies_to,
            keywords=tuple(plan.workflow_keywords),
            summary=plan.workflow_summary,
        ),
    )
    upsert_markdown_index_entry(
        role_path / "brain" / "index.md",
        label="工作流索引",
        target="workflows/index.md",
        summary="按需路由全局 workflow。",
    )
    for rule in plan.user_rules:
        write_memory(role_path, target="user", content=sanitize_archive_entry(rule))
    for item in plan.memory_summary:
        write_memory(role_path, target="memory", content=sanitize_archive_entry(item))
    return WorkflowArchiveResult(
        role_name=get_current_role_state().role_name,
        project_title=None,
        project_slug=None,
        written_paths=[
            f"brain/workflows/{workflow_filename}",
            "brain/workflows/index.md",
            "brain/index.md",
            "memory/USER.md",
            "memory/MEMORY.md",
        ],
        requires_reload=bool(plan.user_rules or plan.memory_summary),
    )


def archive_project_workflow(plan: WorkflowArchivePlan) -> WorkflowArchiveResult:
    role_path = Path(get_current_role_state().role_path)
    project_dir = role_path / "projects" / plan.project_slug
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    workflow_filename = f"{plan.workflow_slug}.md"
    (workflows_dir / workflow_filename).write_text(
        sanitize_archived_markdown(plan.workflow_doc_markdown) + "\n",
        encoding="utf-8",
    )
    upsert_workflow_index_entry(
        workflows_dir / "index.md",
        WorkflowIndexEntry(
            slug=plan.workflow_slug,
            title=plan.workflow_title,
            file=workflow_filename,
            applies_to=plan.workflow_applies_to,
            keywords=tuple(plan.workflow_keywords),
            summary=plan.workflow_summary,
        ),
    )
    context_path = project_dir / "context.md"
    base_context = (
        sanitize_archived_markdown(plan.context_summary_markdown)
        if plan.context_summary_markdown
        else f"# {plan.project_title}\n\n项目上下文待补充。"
    )
    if "- 工作流索引: workflows/index.md" not in base_context:
        base_context = base_context.rstrip() + "\n\n- 工作流索引: workflows/index.md"
    context_path.write_text(base_context.strip() + "\n", encoding="utf-8")
    append_unique_project_memory(project_dir / "memory.md", plan.project_memory)
    upsert_markdown_index_entry(
        role_path / "projects" / "index.md",
        label=plan.project_title,
        target=f"projects/{plan.project_slug}/context.md",
        summary="记录项目上下文与 workflow 索引入口。",
    )
    return WorkflowArchiveResult(
        role_name=get_current_role_state().role_name,
        project_title=plan.project_title,
        project_slug=plan.project_slug,
        written_paths=[
            f"projects/{plan.project_slug}/workflows/{workflow_filename}",
            f"projects/{plan.project_slug}/workflows/index.md",
            f"projects/{plan.project_slug}/context.md",
            f"projects/{plan.project_slug}/memory.md",
            "projects/index.md",
        ],
        requires_reload=False,
    )
```

- [ ] **Step 4: 重新运行 role_ops 与 roundtrip 定向测试，确认新契约和新路径通过**

Run: `python3 -m pytest tests/test_role_ops.py -k "workflow_archive or archive_general_workflow or archive_project_workflow" tests/integration/test_role_roundtrip.py -k "workflow" -v`
Expected: PASS

- [ ] **Step 5: 提交归档契约与新路径改造**

```bash
git add tools/role_ops.py tests/test_role_ops.py tests/integration/test_role_roundtrip.py
git commit -m "feat: archive workflows into indexed directories"
```

### Task 3: 把 context_router 切到索引驱动的 workflow 路由

**Files:**
- Modify: `tools/context_router.py`
- Modify: `tests/test_context_router.py`
- Test: `tests/test_context_router.py`

- [ ] **Step 1: 先写失败测试，固定项目优先、全局回退和低置信度不注入**

```python
def test_discover_context_paths_prefers_project_workflow_index_entry(
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
    project_root = role_path / "projects" / "roleme"
    project_dir = project_root / "workflows"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_root / "context.md").write_text(
        "# roleMe\n\n项目摘要。\n\n- 参考知识: brain/topics/ai-product.md\n",
        encoding="utf-8",
    )
    (project_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## requirements\n"
        "- title: 需求分析 workflow\n"
        "- file: requirements.md\n"
        "- applies_to: 当用户想梳理需求、澄清范围、整理用户故事时使用\n"
        "- keywords: 需求, requirement, scope\n"
        "- summary: 用于把模糊需求整理成可规划输入\n",
        encoding="utf-8",
    )
    (project_dir / "requirements.md").write_text(
        "# 需求分析 workflow\n\n先澄清边界，再整理故事。\n",
        encoding="utf-8",
    )

    assert discover_context_paths(role_path, query="开始梳理这个需求") == [
        "projects/index.md",
        "projects/roleme/context.md",
        "projects/roleme/workflows/index.md",
        "projects/roleme/workflows/requirements.md",
    ]


def test_discover_context_paths_falls_back_to_global_workflow_index_when_project_missing(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "brain" / "index.md").write_text(
        "# 知识索引\n\n- 工作流索引: workflows/index.md\n",
        encoding="utf-8",
    )
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## analysis\n"
        "- title: 问题分析 workflow\n"
        "- file: analysis.md\n"
        "- applies_to: 当用户想分析问题、排查原因、理解异常时使用\n"
        "- keywords: 分析, 排查, 诊断, why\n"
        "- summary: 用于定位问题和形成分析结论\n",
        encoding="utf-8",
    )
    (workflows_dir / "analysis.md").write_text(
        "# 问题分析 workflow\n\n先复述问题，再定位原因。\n",
        encoding="utf-8",
    )

    assert discover_context_paths(role_path, query="帮我分析这个异常原因") == [
        "brain/index.md",
        "brain/workflows/index.md",
        "brain/workflows/analysis.md",
    ]


def test_discover_context_paths_does_not_inject_ambiguous_workflow_entries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## analysis\n"
        "- title: 分析 workflow\n"
        "- file: analysis.md\n"
        "- applies_to: 分析问题和定位原因\n"
        "- keywords: 分析, 原因\n"
        "- summary: 用于分析问题\n\n"
        "## diagnose\n"
        "- title: 诊断 workflow\n"
        "- file: diagnose.md\n"
        "- applies_to: 诊断问题和定位原因\n"
        "- keywords: 诊断, 原因\n"
        "- summary: 用于诊断问题\n",
        encoding="utf-8",
    )
    (workflows_dir / "analysis.md").write_text("# 分析\n\n内容。\n", encoding="utf-8")
    (workflows_dir / "diagnose.md").write_text("# 诊断\n\n内容。\n", encoding="utf-8")

    result = discover_context_paths(role_path, query="分析这个原因")

    assert "brain/workflows/index.md" not in result
    assert "brain/workflows/analysis.md" not in result
    assert "brain/workflows/diagnose.md" not in result
```

- [ ] **Step 2: 运行 context_router 定向测试，确认索引路由测试先失败**

Run: `python3 -m pytest tests/test_context_router.py -k "workflow_index or ambiguous or falls_back_to_global" -v`
Expected: FAIL，因为 `context_router.py` 还只认识旧 `workflow.md` / `general-workflow*.md` 路径，也还不会在 workflow 命中时保留原有 `context.md` / `brain/index.md` 入口。

- [ ] **Step 3: 实现基于 workflow 索引的命中逻辑**

```python
from tools.workflow_index import WorkflowIndexEntry, parse_workflow_index


def _score_workflow_entry(query_tokens: set[str], entry: WorkflowIndexEntry) -> int:
    keyword_tokens = {keyword.casefold() for keyword in entry.keywords}
    score = 5 * _score_text(query_tokens, entry.applies_to)
    score += 3 * len(query_tokens & keyword_tokens)
    score += 2 * _score_text(query_tokens, entry.title)
    score += _score_text(query_tokens, Path(entry.file).stem)
    return score


def _select_workflow_entry(query: str, entries: list[WorkflowIndexEntry]) -> WorkflowIndexEntry | None:
    query_tokens = _tokenize(query)
    ranked = sorted(
        ((entry, _score_workflow_entry(query_tokens, entry)) for entry in entries),
        key=lambda item: item[1],
        reverse=True,
    )
    if not ranked or ranked[0][1] < 4:
        return None
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 2:
        return None
    return ranked[0][0]


def _discover_workflow_paths_from_index(role_path: Path, index_relative: str, query: str) -> list[str]:
    index_path = role_path / index_relative
    if not index_path.exists():
        return []
    entry = _select_workflow_entry(query, parse_workflow_index(index_path.read_text(encoding="utf-8")))
    if entry is None:
        return []
    workflow_relative = f"{Path(index_relative).parent.as_posix()}/{entry.file}"
    if not _is_nonempty_file(role_path / workflow_relative):
        return []
    return [index_relative, workflow_relative]


def _discover_project_workflow_paths(role_path: Path, project_slug: str, query: str) -> list[str]:
    workflow_bundle = _discover_workflow_paths_from_index(
        role_path,
        f"projects/{project_slug}/workflows/index.md",
        query,
    )
    if not workflow_bundle:
        return []
    discovered: list[str] = []
    if _is_nonempty_file(role_path / "projects/index.md"):
        discovered.append("projects/index.md")
    context_relative = f"projects/{project_slug}/context.md"
    if _is_nonempty_file(role_path / context_relative):
        discovered.append(context_relative)
    discovered.extend(workflow_bundle)
    return discovered


def _discover_global_workflow_paths(role_path: Path, query: str) -> list[str]:
    workflow_bundle = _discover_workflow_paths_from_index(role_path, "brain/workflows/index.md", query)
    if not workflow_bundle:
        return []
    discovered: list[str] = []
    if _is_nonempty_file(role_path / "brain/index.md"):
        discovered.append("brain/index.md")
    discovered.extend(workflow_bundle)
    return discovered


def discover_workflow_paths(role_path: Path, query: str) -> list[str]:
    project_slug = _resolve_current_project_slug(role_path, query)
    if project_slug:
        project_paths = _discover_project_workflow_paths(role_path, project_slug, query)
        if project_paths:
            return project_paths
    return _discover_global_workflow_paths(role_path, query)
```

- [ ] **Step 4: 重新运行 context_router 测试，确认索引路由通过**

Run: `python3 -m pytest tests/test_context_router.py -v`
Expected: PASS

- [ ] **Step 5: 提交 workflow 路由重写**

```bash
git add tools/context_router.py tests/test_context_router.py
git commit -m "feat: route workflows from index entries"
```

### Task 4: 更新打包文档并重建发布产物

**Files:**
- Modify: `bundle/SKILL.template.md`
- Modify: `bundle/references/usage.md`
- Modify: `tests/test_repo_scripts.py`
- Regenerate: `skills/roleme/SKILL.md`
- Regenerate: `skills/roleme/references/usage.md`
- Regenerate: `skills/roleme/tools/role_ops.py`
- Regenerate: `skills/roleme/tools/context_router.py`
- Test: `tests/test_repo_scripts.py`

- [ ] **Step 1: 先补失败测试，固定打包后的文档必须使用新 workflow 结构**

```python
def test_build_skill_includes_workflows_index_guidance(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "projects/<project-slug>/workflows/index.md" in skill_md
    assert "brain/workflows/index.md" in usage_md
    assert "一个 workflow，一个文件" in usage_md
    assert "workflow.md" not in skill_md
    assert "workflow.md" not in usage_md
    assert "general-workflow.md" not in skill_md
    assert "general-workflow.md" not in usage_md
```

- [ ] **Step 2: 更新 bundle 文档里的 workflow 路径和说明**

```markdown
- 项目级 workflow 写入 `projects/<project-slug>/workflows/index.md` 与 `projects/<project-slug>/workflows/<workflow-slug>.md`
- 通用 workflow 写入 `brain/workflows/index.md` 与 `brain/workflows/<workflow-slug>.md`
- `context.md` 与 `brain/index.md` 只保留到 `workflows/index.md` 的入口
- 任何新建 workflow 一旦成立，都应独立成文件，不再混写到旧的单文件 workflow 说明里
```

- [ ] **Step 3: 重建打包产物**

Run: `python3 scripts/build_skill.py`
Expected: 输出 `/Users/zhaochao/code/project/roleMe/skills/roleme`，并刷新 `skills/roleme/` 下的文档与工具文件。

- [ ] **Step 4: 运行打包脚本测试，确认发布产物与 bundle 文档同步**

Run: `python3 -m pytest tests/test_repo_scripts.py -v`
Expected: PASS

- [ ] **Step 5: 提交 bundle 文档与重建后的 skill 产物**

```bash
git add bundle/SKILL.template.md bundle/references/usage.md tests/test_repo_scripts.py skills/roleme
git commit -m "docs: publish indexed workflow guidance"
```

### Task 5: 进行完整回归并收尾

**Files:**
- Modify: 如测试暴露问题，再回到对应文件修复
- Test: `tests/test_workflow_index.py`
- Test: `tests/test_role_ops.py`
- Test: `tests/test_context_router.py`
- Test: `tests/test_repo_scripts.py`
- Test: `tests/integration/test_role_roundtrip.py`

- [ ] **Step 1: 运行完整的 workflow 相关回归测试**

Run: `python3 -m pytest tests/test_workflow_index.py tests/test_role_ops.py tests/test_context_router.py tests/test_repo_scripts.py tests/integration/test_role_roundtrip.py -v`
Expected: PASS

- [ ] **Step 2: 检查最终 diff，只保留预期文件和新结构**

Run: `git diff --stat HEAD~4..HEAD && rg -n "workflow\\.md|general-workflow\\.md" bundle tools skills/roleme -g '*.md' -g '*.py'`
Expected: `git diff --stat` 只包含计划中的文件；`rg` 不应在运行时代码、bundle 文档或打包产物中返回旧路径字符串。

- [ ] **Step 3: 如回归阶段有补丁，提交最后修复**

```bash
git add tools/workflow_index.py tools/role_ops.py tools/context_router.py tests/test_workflow_index.py tests/test_role_ops.py tests/test_context_router.py tests/test_repo_scripts.py tests/integration/test_role_roundtrip.py bundle/SKILL.template.md bundle/references/usage.md skills/roleme
git commit -m "test: verify indexed workflow migration"
```
