# roleMe 记忆生命周期与内部能力实现计划

> **给执行智能体：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步执行本计划。步骤使用 checkbox（`- [ ]`）语法跟踪进度。

**目标：** 在不改变 resident snapshot 行为的前提下，增加保守的记忆候选缓冲区、session summary、声明式 internal skills，以及安全的 router / doctor 支持。

**架构：** Markdown 继续作为正文权威，Context Graph 作为 best-effort 治理层。`tools/memory.py` 只增加聚焦的确定性写入函数，`tools/role_ops.py` 继续负责角色包初始化和健康检查，`tools/context_router.py` 只扩展上下文发现。模板变更需要同时同步到根目录 `templates/` 和打包目录 `skills/roleme/assets/templates/`。

**技术栈：** Python 3.12、pytest、本地 Markdown role bundle、JSONL Context Graph。

---

## 来源设计

- 设计文档：`docs/superpowers/specs/2026-04-22-roleme-memory-lifecycle-internal-skills-design.md`
- 现有测试：`tests/test_memory.py`、`tests/test_role_ops.py`、`tests/test_context_router.py`、`tests/test_graph_index.py`
- 现有工具：`tools/memory.py`、`tools/role_ops.py`、`tools/context_router.py`、`tools/graph_index.py`、`tools/workflow_index.py`
- 打包镜像：`skills/roleme/tools/*`、`skills/roleme/assets/templates/*`

## 文件结构

- 修改：`tools/memory.py`
  - 增加 `InboxEntry`、`LearningEntry`、`SessionSummary`、`InternalSkill` dataclass。
  - 增加 inbox、learnings、sessions、internal skills 的确定性写入函数。
  - 增加仅服务这些新文件的轻量 Markdown metadata 解析 / 渲染 helper。
  - Graph 写入继续通过现有 `_safe_persist_graph()` 保持 best-effort。
- 修改：`tools/role_ops.py`
  - 为新角色初始化新增 optional indexes。
  - 扩展 `DoctorReport` warnings，不引入严重等级。
  - 保持 `REQUIRED_FILES` 不变。
- 修改：`tools/context_router.py`
  - 增加 `is_session_recall_query()`。
  - 在项目 / 全局 workflow 发现之后、普通上下文 fallback 之前增加 internal skill discovery。
  - 仅当 `is_session_recall_query()` 返回 true 时启用 session recall discovery。
- 修改：`tools/graph_index.py`
  - 通过 schema / template 更新接纳新增 node types；只有现有校验硬编码 node type 时才改代码。
- 修改：`templates/brain/graph/schema.yaml` 和 `skills/roleme/assets/templates/brain/graph/schema.yaml`
  - 按阶段增量增加 node types：P1 增加 `MemoryCandidate` 和 `Learning`，P3 增加 `Skill`，P4 增加 `Session`。
- 修改：`templates/brain/index.md` 和 `skills/roleme/assets/templates/brain/index.md`
  - 只有当前测试确实需要时，才增加指向 `brain/workflows/index.md` 的可选入口；否则保持不变。
- 角色初始化时创建 / 修改这些生成索引：
  - `memory/inbox/index.md`
  - `memory/learnings/index.md`
  - `memory/sessions/index.md`
  - `skills/index.md`
- 增加测试：
  - `tests/test_memory_lifecycle.py`
  - `tests/test_internal_skills.py`
  - `tests/test_session_summary.py`
  - 扩展 `tests/test_role_ops.py`
  - 扩展 `tests/test_context_router.py`
  - 扩展 `tests/test_graph_index.py`

## 实现注意事项

- 不要把新增 optional directories 加入 `REQUIRED_FILES`。
- 不要把 `memory/inbox/`、`memory/learnings/`、`memory/sessions/` 或 `skills/` 加入 `RESIDENT_PATHS`。
- 为保持根目录工具和打包工具一致，要么手动同步变更到 `skills/roleme/tools/*`，要么运行仓库已有的打包流程。用测试和 `git diff` 验证。
- 每个任务完成后单独提交。

---

### 任务 1：P1 Inbox 与 Learnings 写入器

**文件：**
- 修改：`tools/memory.py`
- 修改：`tools/role_ops.py`
- 修改：`templates/brain/graph/schema.yaml`
- 修改：`skills/roleme/assets/templates/brain/graph/schema.yaml`
- 实现后同步镜像：`skills/roleme/tools/memory.py`
- 实现后同步镜像：`skills/roleme/tools/role_ops.py`
- 测试：`tests/test_memory_lifecycle.py`
- 测试：`tests/test_role_ops.py`

- [ ] **步骤 1：为初始化和 P1 schema 写失败测试**

添加到 `tests/test_role_ops.py`：

```python
def test_initialize_role_creates_memory_lifecycle_indexes(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    assert (role_path / "memory" / "inbox" / "index.md").exists()
    assert (role_path / "memory" / "learnings" / "index.md").exists()
    assert "# Inbox" in (role_path / "memory" / "inbox" / "index.md").read_text(encoding="utf-8")
    assert "# Learnings" in (role_path / "memory" / "learnings" / "index.md").read_text(encoding="utf-8")


def test_initialize_role_graph_schema_supports_p1_node_types(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    schema_text = (role_path / "brain" / "graph" / "schema.yaml").read_text(encoding="utf-8")

    assert "  - MemoryCandidate" in schema_text
    assert "  - Learning" in schema_text
```

创建 `tests/test_memory_lifecycle.py`：

```python
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
    index_text = (role_path / "memory" / "inbox" / "index.md").read_text(encoding="utf-8")
    assert "inbox-20260422-001: Short design summaries -> memory/inbox/inbox-20260422-001.md" in index_text
    graph = load_graph(role_path)
    assert any(node.type == "MemoryCandidate" and node.path == "memory/inbox/inbox-20260422-001.md" for node in graph.nodes)


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
    index_text = (role_path / "memory" / "learnings" / "index.md").read_text(encoding="utf-8")
    assert "learning-20260422-001: Design before implementation -> memory/learnings/learning-20260422-001.md" in index_text
    graph = load_graph(role_path)
    assert any(node.type == "Learning" and node.path == "memory/learnings/learning-20260422-001.md" for node in graph.nodes)


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
    assert not (role_path / "memory" / "learnings" / "learning-20260422-002.md").exists()


def test_candidate_markdown_survives_graph_write_failure(tmp_role_home, monkeypatch):
    role_path = initialize_role("self", skill_version="0.1.0")
    monkeypatch.setattr(
        memory,
        "_persist_graph",
        lambda role_path, nodes, edges: (_ for _ in ()).throw(RuntimeError("graph boom")),
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
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

```bash
pytest tests/test_role_ops.py::test_initialize_role_creates_memory_lifecycle_indexes \
  tests/test_role_ops.py::test_initialize_role_graph_schema_supports_p1_node_types \
  tests/test_memory_lifecycle.py -v
```

预期：FAIL，因为 `InboxEntry`、`LearningEntry`、`write_inbox_entry()`、`write_learning_entry()` 尚不存在，初始化也还没有创建新索引。

- [ ] **步骤 3：实现 dataclass 和确定性写入器**

在 `tools/memory.py` 中增加 imports：

```python
from dataclasses import dataclass
from datetime import datetime, timezone
```

在 constants 附近增加：

```python
@dataclass(frozen=True)
class InboxEntry:
    id: str
    title: str
    summary: str
    evidence: str
    source: str
    suggested_target: str
    confidence: str
    promotion_notes: str
    created_at: str
    last_seen_at: str
    recurrence: int = 1
    status: str = "pending"


@dataclass(frozen=True)
class LearningEntry:
    id: str
    title: str
    rule_candidate: str
    how_to_apply: str
    evidence: str
    promotion_target: str
    learning_type: str
    applies_to: str
    created_at: str
    last_seen_at: str
    recurrence: int = 1
    priority: str = "normal"
    status: str = "pending"
```

增加 helpers：

```python
def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ensure_lifecycle_indexes(role_path: Path) -> None:
    indexes = {
        role_path / "memory" / "inbox" / "index.md": "# Inbox\n\n## pending\n\n## promoted\n\n## closed\n",
        role_path / "memory" / "learnings" / "index.md": "# Learnings\n\n## pending\n\n## promoted\n\n## closed\n",
    }
    for path, content in indexes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            atomic_write_text(path, content)


def _field_value(text: str, field: str) -> str:
    match = re.search(rf"^- {re.escape(field)}: (.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _section_value(text: str, section: str) -> str:
    match = re.search(rf"^## {re.escape(section)}\n\n(.*?)(?=\n## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _normalize_candidate_key(*parts: str) -> str:
    joined = " ".join(part.strip().casefold() for part in parts)
    return re.sub(r"\s+", " ", joined)


def _replace_field(text: str, field: str, value: str | int) -> str:
    return re.sub(rf"^- {re.escape(field)}: .*$", f"- {field}: {value}", text, flags=re.MULTILINE)


def _append_section_line(text: str, section: str, line: str) -> str:
    marker = f"## {section}\n\n"
    if marker not in text:
        return text
    before, after = text.split(marker, maxsplit=1)
    if "\n## " in after:
        body, rest = after.split("\n## ", maxsplit=1)
        return before + marker + body.rstrip() + f"\n\n{line}\n\n## " + rest
    return before + marker + after.rstrip() + f"\n\n{line}\n"


def _upsert_status_index_entry(index_path: Path, status: str, entry_id: str, title: str, relative_path: str) -> None:
    text = index_path.read_text(encoding="utf-8")
    line = f"- {entry_id}: {title} -> {relative_path}"
    if entry_id in text:
        text = re.sub(rf"^- {re.escape(entry_id)}: .*$", line, text, flags=re.MULTILINE)
        atomic_write_text(index_path, text)
        return
    heading = f"## {status}"
    if heading not in text:
        text = text.rstrip() + f"\n\n{heading}\n"
    text = text.replace(heading + "\n", heading + "\n" + line + "\n", 1)
    atomic_write_text(index_path, text)
```

增加 renderers 和 writers：

```python
def _render_inbox_entry(entry: InboxEntry) -> str:
    return (
        f"# {entry.title}\n\n"
        f"- id: {entry.id}\n"
        f"- status: {entry.status}\n"
        f"- source: {entry.source}\n"
        f"- recurrence: {entry.recurrence}\n"
        f"- created_at: {entry.created_at}\n"
        f"- last_seen_at: {entry.last_seen_at}\n"
        f"- suggested_target: {entry.suggested_target}\n"
        f"- confidence: {entry.confidence}\n\n"
        "## Summary\n\n"
        f"{entry.summary}\n\n"
        "## Evidence\n\n"
        f"{entry.evidence}\n\n"
        "## Promotion Notes\n\n"
        f"{entry.promotion_notes}\n"
    )


def _render_learning_entry(entry: LearningEntry) -> str:
    return (
        f"# {entry.title}\n\n"
        f"- id: {entry.id}\n"
        f"- type: {entry.learning_type}\n"
        f"- status: {entry.status}\n"
        f"- recurrence: {entry.recurrence}\n"
        f"- priority: {entry.priority}\n"
        f"- created_at: {entry.created_at}\n"
        f"- last_seen_at: {entry.last_seen_at}\n"
        f"- applies_to: {entry.applies_to}\n\n"
        "## Rule Candidate\n\n"
        f"{entry.rule_candidate}\n\n"
        "## How To Apply\n\n"
        f"{entry.how_to_apply}\n\n"
        "## Evidence\n\n"
        f"{entry.evidence}\n\n"
        "## Promotion Target\n\n"
        f"{entry.promotion_target}\n"
    )


def _find_matching_inbox(role_path: Path, entry: InboxEntry) -> Path | None:
    inbox_dir = role_path / "memory" / "inbox"
    key = _normalize_candidate_key(entry.summary, entry.suggested_target)
    for path in sorted(inbox_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8")
        if _field_value(text, "status") != "pending":
            continue
        existing_key = _normalize_candidate_key(_section_value(text, "Summary"), _field_value(text, "suggested_target"))
        if existing_key == key:
            return path
    return None


def _find_matching_learning(role_path: Path, entry: LearningEntry) -> Path | None:
    learnings_dir = role_path / "memory" / "learnings"
    key = _normalize_candidate_key(entry.learning_type, entry.applies_to, entry.rule_candidate)
    for path in sorted(learnings_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8")
        if _field_value(text, "status") != "pending":
            continue
        existing_key = _normalize_candidate_key(
            _field_value(text, "type"),
            _field_value(text, "applies_to"),
            _section_value(text, "Rule Candidate"),
        )
        if existing_key == key:
            return path
    return None
```

```python
def write_inbox_entry(role_path: Path, entry: InboxEntry) -> Path:
    _ensure_lifecycle_indexes(role_path)
    existing = _find_matching_inbox(role_path, entry)
    if existing is not None:
        text = existing.read_text(encoding="utf-8")
        recurrence = int(_field_value(text, "recurrence") or "1") + 1
        text = _replace_field(text, "recurrence", recurrence)
        text = _replace_field(text, "last_seen_at", entry.last_seen_at)
        text = _append_section_line(text, "Evidence", entry.evidence)
        atomic_write_text(existing, text)
        return existing

    path = role_path / "memory" / "inbox" / f"{entry.id}.md"
    atomic_write_text(path, _render_inbox_entry(entry))
    relative = f"memory/inbox/{entry.id}.md"
    _upsert_status_index_entry(role_path / "memory" / "inbox" / "index.md", entry.status, entry.id, entry.title, relative)
    _upsert_candidate_graph_node(role_path, "MemoryCandidate", relative, entry.title, entry.summary, {"candidate_id": entry.id, "suggested_target": entry.suggested_target, "confidence": entry.confidence})
    return path


def write_learning_entry(role_path: Path, entry: LearningEntry) -> Path:
    _ensure_lifecycle_indexes(role_path)
    existing = _find_matching_learning(role_path, entry)
    if existing is not None:
        text = existing.read_text(encoding="utf-8")
        recurrence = int(_field_value(text, "recurrence") or "1") + 1
        text = _replace_field(text, "recurrence", recurrence)
        text = _replace_field(text, "last_seen_at", entry.last_seen_at)
        text = _append_section_line(text, "Evidence", entry.evidence)
        atomic_write_text(existing, text)
        return existing

    path = role_path / "memory" / "learnings" / f"{entry.id}.md"
    atomic_write_text(path, _render_learning_entry(entry))
    relative = f"memory/learnings/{entry.id}.md"
    _upsert_status_index_entry(role_path / "memory" / "learnings" / "index.md", entry.status, entry.id, entry.title, relative)
    _upsert_candidate_graph_node(role_path, "Learning", relative, entry.title, entry.rule_candidate, {"learning_id": entry.id, "type": entry.learning_type, "applies_to": entry.applies_to})
    return path
```

增加 graph helper：

```python
def _upsert_candidate_graph_node(
    role_path: Path,
    node_type: str,
    relative_path: str,
    title: str,
    summary: str,
    metadata: dict[str, str],
) -> None:
    if not _graph_archive_enabled():
        return
    graph = load_graph(role_path)
    node = NodeRecord(
        id=deterministic_node_id(node_type=node_type, scope="global", path=relative_path, title=title, metadata=metadata),
        type=node_type,
        scope="global",
        path=relative_path,
        title=title,
        summary=summary,
        metadata=metadata,
    )
    nodes = upsert_node(graph.nodes, node)
    _safe_persist_graph(role_path, nodes, graph.edges)
```

- [ ] **步骤 4：更新角色初始化和 graph schema 模板**

在 `tools/role_ops.py` 的 `initialize_role()` 中，在 required directories 创建之后增加：

```python
    optional_indexes = {
        role_path / "memory" / "inbox" / "index.md": "# Inbox\n\n## pending\n\n## promoted\n\n## closed\n",
        role_path / "memory" / "learnings" / "index.md": "# Learnings\n\n## pending\n\n## promoted\n\n## closed\n",
    }
    for path, content in optional_indexes.items():
        _write_if_missing(path, content)
```

更新两个 schema 文件：

```yaml
  - MemoryCandidate
  - Learning
```

把它们放在现有 memory-like node types 下方、`Episode` 之前。

- [ ] **步骤 5：同步打包工具镜像**

运行：

```bash
cp tools/memory.py skills/roleme/tools/memory.py
cp tools/role_ops.py skills/roleme/tools/role_ops.py
```

预期：无输出。

- [ ] **步骤 6：运行 P1 测试**

运行：

```bash
pytest tests/test_memory_lifecycle.py \
  tests/test_role_ops.py::test_initialize_role_creates_memory_lifecycle_indexes \
  tests/test_role_ops.py::test_initialize_role_graph_schema_supports_p1_node_types -v
```

预期：PASS。

- [ ] **步骤 7：运行现有 memory 和 role 测试**

运行：

```bash
pytest tests/test_memory.py tests/test_role_ops.py -v
```

预期：PASS。

- [ ] **步骤 8：提交 P1**

```bash
git add tools/memory.py tools/role_ops.py skills/roleme/tools/memory.py skills/roleme/tools/role_ops.py templates/brain/graph/schema.yaml skills/roleme/assets/templates/brain/graph/schema.yaml tests/test_memory_lifecycle.py tests/test_role_ops.py
git commit -m "feat: add memory lifecycle candidate writers"
```

---

### 任务 2：P2 Doctor 健康检查框架

**文件：**
- 修改：`tools/role_ops.py`
- 修改镜像：`skills/roleme/tools/role_ops.py`
- 测试：`tests/test_role_ops.py`

- [ ] **步骤 1：编写失败的 doctor 测试**

添加到 `tests/test_role_ops.py`：

```python
def test_doctor_warns_for_missing_optional_lifecycle_structure(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    shutil.rmtree(role_path / "memory" / "inbox")

    report = doctor_role("self", now=datetime.fromisoformat("2026-04-22T12:00:00+08:00"))

    assert "memory/inbox/index.md" not in report.missing_files
    assert any("optional_structure_missing: memory/inbox/index.md" in warning for warning in report.warnings)


def test_doctor_reports_lifecycle_index_missing_target(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "memory" / "inbox" / "index.md").write_text(
        "# Inbox\n\n## pending\n- inbox-20260422-404: Missing -> memory/inbox/inbox-20260422-404.md\n\n## promoted\n\n## closed\n",
        encoding="utf-8",
    )

    report = doctor_role("self")

    assert any("memory/inbox/index.md points to missing file: memory/inbox/inbox-20260422-404.md" in warning for warning in report.warnings)


def test_doctor_reports_stale_pending_inbox_and_learning(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "memory" / "inbox" / "inbox-20260401-001.md").write_text(
        "# Old Inbox\n\n"
        "- id: inbox-20260401-001\n"
        "- status: pending\n"
        "- source: user_statement\n"
        "- recurrence: 1\n"
        "- created_at: 2026-04-01T10:00:00+08:00\n"
        "- last_seen_at: 2026-04-01T10:00:00+08:00\n"
        "- suggested_target: user\n"
        "- confidence: medium\n\n"
        "## Summary\n\nold\n\n## Evidence\n\nold\n\n## Promotion Notes\n\nold\n",
        encoding="utf-8",
    )
    (role_path / "memory" / "learnings" / "learning-20260301-001.md").write_text(
        "# Old Learning\n\n"
        "- id: learning-20260301-001\n"
        "- type: correction\n"
        "- status: pending\n"
        "- recurrence: 1\n"
        "- priority: normal\n"
        "- created_at: 2026-03-01T10:00:00+08:00\n"
        "- last_seen_at: 2026-03-01T10:00:00+08:00\n"
        "- applies_to: global\n\n"
        "## Rule Candidate\n\nold\n\n## How To Apply\n\nold\n\n## Evidence\n\nold\n\n## Promotion Target\n\nmemory/USER.md\n",
        encoding="utf-8",
    )

    report = doctor_role("self")

    assert any("pending inbox older than 14 days: memory/inbox/inbox-20260401-001.md" in warning for warning in report.warnings)
    assert any("pending learning older than 30 days: memory/learnings/learning-20260301-001.md" in warning for warning in report.warnings)
```

在 `tests/test_role_ops.py` 顶部附近增加这些 imports：

```python
from datetime import datetime
import shutil
```

- [ ] **步骤 2：运行 doctor 测试，确认失败**

运行：

```bash
pytest tests/test_role_ops.py::test_doctor_warns_for_missing_optional_lifecycle_structure \
  tests/test_role_ops.py::test_doctor_reports_lifecycle_index_missing_target \
  tests/test_role_ops.py::test_doctor_reports_stale_pending_inbox_and_learning -v
```

预期：FAIL，因为 doctor 还没有检查 optional lifecycle indexes。

- [ ] **步骤 3：实现可复用 doctor helpers**

在 `tools/role_ops.py` 中增加 imports：

```python
from datetime import timedelta
```

在 `doctor_role()` 附近增加 helpers：

```python
OPTIONAL_INDEXES = [
    "memory/inbox/index.md",
    "memory/learnings/index.md",
]


def _extract_index_targets(text: str) -> list[str]:
    targets: list[str] = []
    for match in re.finditer(r"->\s*([A-Za-z0-9_./-]+\.md)", text):
        target = match.group(1).replace("\\", "/").lstrip("./")
        if target not in targets:
            targets.append(target)
    return targets


def _parse_iso_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _markdown_field(text: str, field: str) -> str:
    match = re.search(rf"^- {re.escape(field)}: (.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _warn_optional_index(role_path: Path, relative: str, warnings: list[str]) -> None:
    path = role_path / relative
    if not path.exists():
        warnings.append(f"optional_structure_missing: {relative}")
        return
    text = path.read_text(encoding="utf-8")
    for target in _extract_index_targets(text):
        if not (role_path / target).exists():
            warnings.append(f"{relative} points to missing file: {target}")


def _warn_stale_pending(
    role_path: Path,
    directory: str,
    label: str,
    max_age_days: int,
    warnings: list[str],
    now: datetime,
) -> None:
    for path in sorted((role_path / directory).glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8")
        if _markdown_field(text, "status") != "pending":
            continue
        last_seen = _parse_iso_datetime(_markdown_field(text, "last_seen_at"))
        if last_seen is None:
            warnings.append(f"{label} missing or invalid last_seen_at: {path.relative_to(role_path)}")
            continue
        if now - last_seen > timedelta(days=max_age_days):
            warnings.append(f"pending {label} older than {max_age_days} days: {path.relative_to(role_path)}")
```

更新 `doctor_role()`：

```python
    for relative in OPTIONAL_INDEXES:
        _warn_optional_index(role_path, relative, warnings)
    effective_now = now or datetime.now(timezone.utc).astimezone()
    if (role_path / "memory" / "inbox").exists():
        _warn_stale_pending(role_path, "memory/inbox", "inbox", 14, warnings, effective_now)
    if (role_path / "memory" / "learnings").exists():
        _warn_stale_pending(role_path, "memory/learnings", "learning", 30, warnings, effective_now)
```

保持 `missing_files` 只基于 `REQUIRED_FILES`。

更新函数签名，以支持确定性的 stale-age 测试：

```python
def doctor_role(role_name: str, now: datetime | None = None) -> DoctorReport:
```

在任务 2 中，`OPTIONAL_INDEXES` 只能包含 P1 lifecycle indexes。不要在任务 2 加入 `skills/index.md` 或 `memory/sessions/index.md`。等任务 3 引入 skills 结构时再加入 `skills/index.md`，等任务 4 引入 sessions 结构时再加入 `memory/sessions/index.md`。

兼容性要求：

- `now` 必须是可选参数，默认值为 `None`，保证所有现有 `doctor_role("self")` 调用继续可用。
- 在步骤 4 中，把这个签名变更同步到 `skills/roleme/tools/role_ops.py`。
- Doctor 只能对当前阶段列出的 optional indexes 发 warning，不应对尚未引入的未来结构发 warning。
- 任务 2 完成后，断言 `doctor_warnings == ()` 的 archive workflow 测试必须保持通过。

- [ ] **步骤 4：同步打包版 role_ops**

运行：

```bash
cp tools/role_ops.py skills/roleme/tools/role_ops.py
```

预期：无输出。

- [ ] **步骤 5：运行 P2 测试**

运行：

```bash
pytest tests/test_role_ops.py::test_doctor_warns_for_missing_optional_lifecycle_structure \
  tests/test_role_ops.py::test_doctor_reports_lifecycle_index_missing_target \
  tests/test_role_ops.py::test_doctor_reports_stale_pending_inbox_and_learning -v
```

预期：PASS。

- [ ] **步骤 6：运行 role ops 和 graph 测试**

运行：

```bash
pytest tests/test_role_ops.py tests/test_graph_index.py -v
```

预期：PASS。

运行 archive warning 回归测试：

```bash
pytest tests/test_role_ops.py::test_archive_general_workflow_writes_topic_index_and_memory_promotions \
  tests/test_role_ops.py::test_archive_project_workflow_writes_project_assets_and_is_rediscoverable \
  tests/test_role_ops.py::test_archive_general_workflow_returns_partial_state_when_graph_write_fails -v
```

预期：PASS。健康的 archive 用例必须仍然保持 `doctor_warnings == ()`。

- [ ] **步骤 7：提交 P2**

```bash
git add tools/role_ops.py skills/roleme/tools/role_ops.py tests/test_role_ops.py
git commit -m "feat: add staged role doctor health checks"
```

---

### 任务 3：P3 Internal Skill 能力卡

**文件：**
- 修改：`tools/memory.py`
- 修改：`tools/role_ops.py`
- 修改：`templates/brain/graph/schema.yaml`
- 修改：`skills/roleme/assets/templates/brain/graph/schema.yaml`
- 修改镜像：`skills/roleme/tools/memory.py`、`skills/roleme/tools/role_ops.py`
- 测试：`tests/test_internal_skills.py`
- 测试：`tests/test_role_ops.py`

- [ ] **步骤 1：编写失败的 internal skill 测试**

创建 `tests/test_internal_skills.py`：

```python
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
    schema_text = (role_path / "brain" / "graph" / "schema.yaml").read_text(encoding="utf-8")
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
    assert any(node.type == "Skill" and node.path == "skills/code-review.md" for node in graph.nodes)


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

    assert any("skills/code-review.md missing required section: When To Use" in warning for warning in report.warnings)
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

```bash
pytest tests/test_internal_skills.py -v
```

预期：FAIL，因为 `InternalSkill` 和 `write_internal_skill()` 尚不存在，`skills/index.md` 也尚未初始化。

- [ ] **步骤 3：实现 InternalSkill 写入器**

在 `tools/memory.py` 中增加：

```python
@dataclass(frozen=True)
class InternalSkill:
    slug: str
    title: str
    applies_to: str
    keywords: list[str]
    summary: str
    body_markdown: str
```

增加 helpers：

```python
REQUIRED_INTERNAL_SKILL_SECTIONS = [
    "Purpose",
    "When To Use",
    "Inputs",
    "Procedure",
    "Outputs",
    "Boundaries",
]


def _ensure_skills_index(role_path: Path) -> None:
    skills_dir = role_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    index = skills_dir / "index.md"
    if not index.exists():
        atomic_write_text(index, "# Internal Skills\n")


def _render_internal_skill_index_entry(skill: InternalSkill) -> str:
    return (
        f"## {skill.slug}\n"
        f"- title: {skill.title}\n"
        f"- file: {skill.slug}.md\n"
        f"- applies_to: {skill.applies_to}\n"
        f"- keywords: {', '.join(skill.keywords)}\n"
        f"- summary: {skill.summary}\n"
    )


def _upsert_internal_skill_index(index_path: Path, skill: InternalSkill) -> None:
    text = index_path.read_text(encoding="utf-8")
    entry = _render_internal_skill_index_entry(skill)
    pattern = rf"^## {re.escape(skill.slug)}\n(?:^- .*\n?)+"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, entry, text, flags=re.MULTILINE)
    else:
        text = text.rstrip() + "\n\n" + entry
    atomic_write_text(index_path, text)


def write_internal_skill(role_path: Path, skill: InternalSkill) -> Path:
    _ensure_skills_index(role_path)
    path = role_path / "skills" / f"{skill.slug}.md"
    atomic_write_text(path, skill.body_markdown.rstrip() + "\n")
    _upsert_internal_skill_index(role_path / "skills" / "index.md", skill)
    _upsert_candidate_graph_node(
        role_path,
        "Skill",
        f"skills/{skill.slug}.md",
        skill.title,
        skill.summary,
        {"skill_slug": skill.slug, "applies_to": skill.applies_to, "keywords": ", ".join(skill.keywords)},
    )
    return path
```

- [ ] **步骤 4：初始化 skills index 并增加 Skill schema**

在 `tools/role_ops.py` 中，扩展 `initialize_role()` 的 optional indexes：

```python
        role_path / "skills" / "index.md": "# Internal Skills\n",
```

本任务中，在 writer 和初始化支持存在之后，把 `skills/index.md` 加入 optional doctor indexes：

```python
OPTIONAL_INDEXES = [
    "memory/inbox/index.md",
    "memory/learnings/index.md",
    "skills/index.md",
]
```

更新两个 schema 文件：

```yaml
  - Skill
```

- [ ] **步骤 5：增加 doctor section 校验**

在 `tools/role_ops.py` 中增加：

```python
INTERNAL_SKILL_REQUIRED_SECTIONS = [
    "Purpose",
    "When To Use",
    "Inputs",
    "Procedure",
    "Outputs",
    "Boundaries",
]


def _warn_internal_skill_sections(role_path: Path, warnings: list[str]) -> None:
    skills_dir = role_path / "skills"
    if not skills_dir.exists():
        return
    for path in sorted(skills_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8")
        for section in INTERNAL_SKILL_REQUIRED_SECTIONS:
            if f"## {section}" not in text:
                warnings.append(f"{path.relative_to(role_path)} missing required section: {section}")
```

在 `doctor_role()` 中 optional index checks 之后调用 `_warn_internal_skill_sections(role_path, warnings)`。

- [ ] **步骤 6：同步打包文件**

运行：

```bash
cp tools/memory.py skills/roleme/tools/memory.py
cp tools/role_ops.py skills/roleme/tools/role_ops.py
```

预期：无输出。

- [ ] **步骤 7：运行 P3 测试**

运行：

```bash
pytest tests/test_internal_skills.py -v
```

预期：PASS。

- [ ] **步骤 8：运行相关测试集**

运行：

```bash
pytest tests/test_memory_lifecycle.py tests/test_internal_skills.py tests/test_role_ops.py -v
```

预期：PASS。

- [ ] **步骤 9：提交 P3**

```bash
git add tools/memory.py tools/role_ops.py skills/roleme/tools/memory.py skills/roleme/tools/role_ops.py templates/brain/graph/schema.yaml skills/roleme/assets/templates/brain/graph/schema.yaml tests/test_internal_skills.py tests/test_role_ops.py
git commit -m "feat: add internal skill capability cards"
```

---

### 任务 4：P4 Session Summary 写入器

**文件：**
- 修改：`tools/memory.py`
- 修改：`tools/role_ops.py`
- 修改：`templates/brain/graph/schema.yaml`
- 修改：`skills/roleme/assets/templates/brain/graph/schema.yaml`
- 修改镜像：`skills/roleme/tools/memory.py`、`skills/roleme/tools/role_ops.py`
- 测试：`tests/test_session_summary.py`

- [ ] **步骤 1：编写失败的 session 测试**

创建 `tests/test_session_summary.py`：

```python
from tools.graph_index import load_graph
from tools.memory import InboxEntry, LearningEntry, SessionSummary, write_session_summary
from tools.role_ops import doctor_role, initialize_role


def _summary(session_id: str) -> SessionSummary:
    inbox = InboxEntry(
        id="inbox-20260422-001",
        title="Short summaries",
        summary="User may prefer short summaries before design documents.",
        evidence="可能还是先给我一版短摘要吧。",
        source="user_statement",
        suggested_target="user",
        confidence="medium",
        promotion_notes="Promote after repeated confirmation.",
        created_at="2026-04-22T10:00:00+08:00",
        last_seen_at="2026-04-22T10:00:00+08:00",
    )
    learning = LearningEntry(
        id="learning-20260422-001",
        title="Design before implementation",
        rule_candidate="Do not implement before writing a design document.",
        how_to_apply="Draft design first when the user requests a feature.",
        evidence="先出设计文档。",
        promotion_target="memory/USER.md",
        learning_type="correction",
        applies_to="global",
        created_at="2026-04-22T10:00:00+08:00",
        last_seen_at="2026-04-22T10:00:00+08:00",
    )
    return SessionSummary(
        session_id=session_id,
        date="2026-04-22",
        started_at="2026-04-22T09:30:00+08:00",
        ended_at="2026-04-22T11:00:00+08:00",
        summary="讨论 roleMe 记忆生命周期。",
        keywords=["roleMe", "inbox", "session"],
        work_completed=["修订设计文档"],
        decisions=["session 文件使用日内序号"],
        artifacts=["docs/superpowers/specs/2026-04-22-roleme-memory-lifecycle-internal-skills-design.md"],
        inbox_candidates=[inbox],
        learning_candidates=[learning],
        suggested_promotions=["确认后提升到 USER"],
    )


def test_initialize_role_creates_sessions_index_and_schema(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    assert (role_path / "memory" / "sessions" / "index.md").exists()
    schema_text = (role_path / "brain" / "graph" / "schema.yaml").read_text(encoding="utf-8")
    assert "  - Session" in schema_text


def test_write_session_summary_creates_file_index_and_graph(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    path = write_session_summary(role_path, _summary("2026-04-22-001"))

    assert path == role_path / "memory" / "sessions" / "2026-04-22-001.md"
    text = path.read_text(encoding="utf-8")
    assert "- session_id: 2026-04-22-001" in text
    assert "## Suggested Promotions" in text
    index_text = (role_path / "memory" / "sessions" / "index.md").read_text(encoding="utf-8")
    assert "## 2026-04-22-001" in index_text
    assert "- file: 2026-04-22-001.md" in index_text
    graph = load_graph(role_path)
    assert any(node.type == "Session" and node.path == "memory/sessions/2026-04-22-001.md" for node in graph.nodes)


def test_write_session_summary_does_not_overwrite_same_day_session(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    first = write_session_summary(role_path, _summary("2026-04-22-001"))
    second = write_session_summary(role_path, _summary("2026-04-22-002"))

    assert first.exists()
    assert second.exists()
    assert first != second


def test_doctor_reports_missing_session_target(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "memory" / "sessions" / "index.md").write_text(
        "# Sessions\n\n## 2026-04-22-001\n- file: 2026-04-22-001.md\n- summary: missing\n- inbox_candidates: 1\n- learning_candidates: 0\n- promotions: 0\n",
        encoding="utf-8",
    )

    report = doctor_role("self")

    assert any("memory/sessions/index.md points to missing file: memory/sessions/2026-04-22-001.md" in warning for warning in report.warnings)
```

- [ ] **步骤 2：运行测试，确认失败**

运行：

```bash
pytest tests/test_session_summary.py -v
```

预期：FAIL，因为 `SessionSummary` 和 `write_session_summary()` 尚不存在。

- [ ] **步骤 3：实现 SessionSummary 写入器**

在 `tools/memory.py` 中增加：

```python
@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    date: str
    started_at: str
    ended_at: str
    summary: str
    keywords: list[str]
    work_completed: list[str]
    decisions: list[str]
    artifacts: list[str]
    inbox_candidates: list[InboxEntry]
    learning_candidates: list[LearningEntry]
    suggested_promotions: list[str]
```

增加 helpers：

```python
def _ensure_sessions_index(role_path: Path) -> None:
    sessions_dir = role_path / "memory" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    index = sessions_dir / "index.md"
    if not index.exists():
        atomic_write_text(index, "# Sessions\n")


def _render_bullets(items: list[str]) -> str:
    if not items:
        return "- none\n"
    return "\n".join(f"- {item}" for item in items) + "\n"


def _render_inbox_candidate_bullets(items: list[InboxEntry]) -> str:
    if not items:
        return "- none\n"
    return "\n".join(f"- {item.id}: {item.summary} -> {item.suggested_target}" for item in items) + "\n"


def _render_learning_candidate_bullets(items: list[LearningEntry]) -> str:
    if not items:
        return "- none\n"
    return "\n".join(f"- {item.id}: {item.rule_candidate} -> {item.promotion_target}" for item in items) + "\n"


def _render_session_summary(summary: SessionSummary) -> str:
    return (
        f"# Session Summary - {summary.session_id}\n\n"
        f"- session_id: {summary.session_id}\n"
        f"- date: {summary.date}\n"
        f"- started_at: {summary.started_at}\n"
        f"- ended_at: {summary.ended_at}\n\n"
        "## Work Completed\n\n"
        f"{_render_bullets(summary.work_completed)}\n"
        "## Decisions\n\n"
        f"{_render_bullets(summary.decisions)}\n"
        "## Artifacts\n\n"
        f"{_render_bullets(summary.artifacts)}\n"
        "## Inbox Candidates\n\n"
        f"{_render_inbox_candidate_bullets(summary.inbox_candidates)}\n"
        "## Learning Candidates\n\n"
        f"{_render_learning_candidate_bullets(summary.learning_candidates)}\n"
        "## Suggested Promotions\n\n"
        f"{_render_bullets(summary.suggested_promotions)}"
    )


def _upsert_session_index(index_path: Path, summary: SessionSummary) -> None:
    text = index_path.read_text(encoding="utf-8")
    entry = (
        f"## {summary.session_id}\n"
        f"- file: {summary.session_id}.md\n"
        f"- started_at: {summary.started_at}\n"
        f"- ended_at: {summary.ended_at}\n"
        f"- summary: {summary.summary}\n"
        f"- keywords: {', '.join(summary.keywords)}\n"
        f"- inbox_candidates: {len(summary.inbox_candidates)}\n"
        f"- learning_candidates: {len(summary.learning_candidates)}\n"
        f"- promotions: {len(summary.suggested_promotions)}\n"
    )
    pattern = rf"^## {re.escape(summary.session_id)}\n(?:^- .*\n?)+"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, entry, text, flags=re.MULTILINE)
    else:
        text = text.rstrip() + "\n\n" + entry
    atomic_write_text(index_path, text)


def write_session_summary(role_path: Path, summary: SessionSummary) -> Path:
    _ensure_sessions_index(role_path)
    path = role_path / "memory" / "sessions" / f"{summary.session_id}.md"
    if path.exists():
        raise FileExistsError(f"Session summary already exists: {path}")
    atomic_write_text(path, _render_session_summary(summary))
    _upsert_session_index(role_path / "memory" / "sessions" / "index.md", summary)
    _upsert_candidate_graph_node(
        role_path,
        "Session",
        f"memory/sessions/{summary.session_id}.md",
        f"Session {summary.session_id}",
        summary.summary,
        {"session_id": summary.session_id, "date": summary.date, "keywords": ", ".join(summary.keywords)},
    )
    return path
```

- [ ] **步骤 4：初始化 sessions index 并增加 Session schema**

在 `tools/role_ops.py` 中，扩展 `initialize_role()` 的 optional indexes：

```python
        role_path / "memory" / "sessions" / "index.md": "# Sessions\n",
```

本任务中，把 `memory/sessions/index.md` 加入 optional doctor indexes：

```python
OPTIONAL_INDEXES = [
    "memory/inbox/index.md",
    "memory/learnings/index.md",
    "skills/index.md",
    "memory/sessions/index.md",
]
```

更新两个 schema 文件：

```yaml
  - Session
```

- [ ] **步骤 5：同步打包文件**

运行：

```bash
cp tools/memory.py skills/roleme/tools/memory.py
cp tools/role_ops.py skills/roleme/tools/role_ops.py
```

预期：无输出。

- [ ] **步骤 6：运行 P4 测试**

运行：

```bash
pytest tests/test_session_summary.py -v
```

预期：PASS。

- [ ] **步骤 7：运行 lifecycle 测试集**

运行：

```bash
pytest tests/test_memory_lifecycle.py tests/test_internal_skills.py tests/test_session_summary.py tests/test_role_ops.py -v
```

预期：PASS。

- [ ] **步骤 8：提交 P4**

```bash
git add tools/memory.py tools/role_ops.py skills/roleme/tools/memory.py skills/roleme/tools/role_ops.py templates/brain/graph/schema.yaml skills/roleme/assets/templates/brain/graph/schema.yaml tests/test_session_summary.py tests/test_role_ops.py
git commit -m "feat: add session summary archive writer"
```

---

### 任务 5：P5 Internal Skill 与 Session 路由

**文件：**
- 修改：`tools/context_router.py`
- 修改镜像：`skills/roleme/tools/context_router.py`
- 测试：`tests/test_context_router.py`

- [ ] **步骤 1：编写失败的 router 测试**

添加到 `tests/test_context_router.py`：

```python
from tools.context_router import is_session_recall_query


def test_is_session_recall_query_accepts_review_and_continuation_intents():
    assert is_session_recall_query("继续上次的 roleMe 设计")
    assert is_session_recall_query("回顾今天做了什么")
    assert is_session_recall_query("复盘这轮工作")
    assert is_session_recall_query("看看最近有什么 learning 可以提升")


def test_is_session_recall_query_rejects_normal_task_intents():
    assert not is_session_recall_query("开始实现 inbox")
    assert not is_session_recall_query("帮我写 PRD")
    assert not is_session_recall_query("review 这份代码")
    assert not is_session_recall_query("新增一个 workflow")


def test_discover_context_paths_uses_internal_skill_when_workflow_missing(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    skills_dir = role_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "index.md").write_text(
        "# Internal Skills\n\n"
        "## code-review\n"
        "- title: 代码评审能力\n"
        "- file: code-review.md\n"
        "- applies_to: 当用户要求 review、审查代码、找风险时使用\n"
        "- keywords: review, 代码评审, 风险\n"
        "- summary: 按风险优先级输出代码审查意见\n",
        encoding="utf-8",
    )
    (skills_dir / "code-review.md").write_text(
        "# 代码评审能力\n\n"
        "## Purpose\n\nFind risks.\n\n"
        "## When To Use\n\nReview requests.\n\n"
        "## Inputs\n\nDiff.\n\n"
        "## Procedure\n\nInspect risks.\n\n"
        "## Outputs\n\nFindings.\n\n"
        "## Boundaries\n\nNo unrelated rewrites.\n",
        encoding="utf-8",
    )

    result = discover_context_paths(role_path, query="帮我 review 这份代码")

    assert result == ["skills/index.md", "skills/code-review.md"]


def test_discover_context_paths_prefers_workflow_over_internal_skill(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "index.md").write_text(
        "# 工作流索引\n\n"
        "## code-review\n"
        "- title: 代码评审 workflow\n"
        "- file: code-review.md\n"
        "- applies_to: 当用户要求 review、审查代码、找风险时使用\n"
        "- keywords: review, 代码评审, 风险\n"
        "- summary: 按流程审查代码\n",
        encoding="utf-8",
    )
    (workflows_dir / "code-review.md").write_text("# 代码评审 workflow\n\n先看风险。\n", encoding="utf-8")
    skills_dir = role_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "index.md").write_text(
        "# Internal Skills\n\n"
        "## code-review\n"
        "- title: 代码评审能力\n"
        "- file: code-review.md\n"
        "- applies_to: 当用户要求 review、审查代码、找风险时使用\n"
        "- keywords: review, 代码评审, 风险\n"
        "- summary: 按风险优先级输出代码审查意见\n",
        encoding="utf-8",
    )
    (skills_dir / "code-review.md").write_text("# 代码评审能力\n\n## Purpose\n\nFind risks.\n", encoding="utf-8")

    result = discover_context_paths(role_path, query="帮我 review 这份代码")

    assert result == ["brain/index.md", "brain/workflows/index.md", "brain/workflows/code-review.md"]


def test_discover_context_paths_loads_session_only_for_session_recall(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    sessions_dir = role_path / "memory" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "index.md").write_text(
        "# Sessions\n\n"
        "## 2026-04-22-001\n"
        "- file: 2026-04-22-001.md\n"
        "- summary: 讨论 roleMe inbox 和 learning 设计\n"
        "- keywords: roleMe, inbox, learning\n"
        "- inbox_candidates: 1\n"
        "- learning_candidates: 1\n"
        "- promotions: 0\n",
        encoding="utf-8",
    )
    (sessions_dir / "2026-04-22-001.md").write_text(
        "# Session Summary - 2026-04-22-001\n\n讨论 roleMe inbox 和 learning 设计。\n",
        encoding="utf-8",
    )

    recall_result = discover_context_paths(role_path, query="继续上次的 roleMe inbox 设计")
    normal_result = discover_context_paths(role_path, query="开始实现 roleMe inbox")

    assert recall_result == ["memory/sessions/index.md", "memory/sessions/2026-04-22-001.md"]
    assert "memory/sessions/index.md" not in normal_result
```

- [ ] **步骤 2：运行 router 测试，确认失败**

运行：

```bash
pytest tests/test_context_router.py::test_is_session_recall_query_accepts_review_and_continuation_intents \
  tests/test_context_router.py::test_is_session_recall_query_rejects_normal_task_intents \
  tests/test_context_router.py::test_discover_context_paths_uses_internal_skill_when_workflow_missing \
  tests/test_context_router.py::test_discover_context_paths_prefers_workflow_over_internal_skill \
  tests/test_context_router.py::test_discover_context_paths_loads_session_only_for_session_recall -v
```

预期：FAIL，因为 routing helpers 尚不存在。

- [ ] **步骤 3：实现 session recall 判定函数**

在 `tools/context_router.py` 中，在 hint sets 附近增加 constants：

```python
SESSION_RECALL_HINTS = {
    "回顾",
    "继续",
    "最近",
    "上次",
    "复盘",
    "经验教训",
    "提升",
    "recap",
    "continue",
    "previous",
    "recent",
    "retro",
    "promote",
}
```

增加函数：

```python
def is_session_recall_query(query: str) -> bool:
    normalized = query.casefold()
    return any(hint in normalized for hint in SESSION_RECALL_HINTS)
```

- [ ] **步骤 4：实现 internal skill discovery**

在 `tools/context_router.py` 中增加：

```python
def _read_internal_skill_entries(index_path: Path) -> list[WorkflowIndexEntry]:
    if not index_path.exists() or not index_path.is_file():
        return []
    try:
        return parse_workflow_index(index_path.read_text(encoding="utf-8"))
    except ValueError:
        return []


def _discover_internal_skill_paths(role_path: Path, query: str) -> list[str]:
    index_relative = "skills/index.md"
    index_path = role_path / index_relative
    entries = _read_internal_skill_entries(index_path)
    selected = _select_workflow_entry(query, entries)
    if selected is None:
        return []
    skill_relative = f"skills/{selected.file}"
    if not (role_path / skill_relative).exists():
        return []
    required = ["Purpose", "When To Use", "Inputs", "Procedure", "Outputs", "Boundaries"]
    text = (role_path / skill_relative).read_text(encoding="utf-8")
    if any(f"## {section}" not in text for section in required):
        return []
    return [index_relative, skill_relative]
```

复用现有 `_select_workflow_entry()`，让评分阈值和 workflow routing 保持一致。

- [ ] **步骤 5：实现 session discovery**

在 `tools/context_router.py` 中增加：

```python
def _discover_session_paths(role_path: Path, query: str) -> list[str]:
    if not is_session_recall_query(query):
        return []
    index_relative = "memory/sessions/index.md"
    index_path = role_path / index_relative
    if not index_path.exists():
        return []
    query_tokens = _tokenize(query)
    text = index_path.read_text(encoding="utf-8")
    blocks = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    candidates: list[tuple[int, str]] = []
    for block in blocks:
        file_match = re.search(r"^- file: (.*)$", block, flags=re.MULTILINE)
        if not file_match:
            continue
        file_name = file_match.group(1).strip()
        score = _score_text(query_tokens, block)
        if score > 0:
            candidates.append((score, file_name))
    if not candidates:
        return [index_relative]
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected_relative = f"memory/sessions/{candidates[0][1]}"
    if (role_path / selected_relative).exists():
        return [index_relative, selected_relative]
    return [index_relative]
```

- [ ] **步骤 6：把路由顺序接入 `discover_context_paths()`**

在 `tools/context_router.py` 中，在 `discover_context_paths()` 函数最开头、graph recall 之前更新：

```python
    session_paths = _discover_session_paths(role_path, query)
    if session_paths:
        return session_paths

    graph_paths = _discover_graph_context_paths(role_path, query)
    if graph_paths:
        return graph_paths

    workflow_paths = discover_workflow_paths(role_path, query)
    if workflow_paths:
        return workflow_paths

    internal_skill_paths = _discover_internal_skill_paths(role_path, query)
    if internal_skill_paths:
        return internal_skill_paths
```

Session recall 必须先于 graph recall 执行，避免 graph candidates 抢走明确的“继续 / 回顾 / 复盘 / 提升”类 query。保留现有 project workflow 和 global workflow 行为，并且只在 workflow discovery 为空之后插入 internal skill discovery。

- [ ] **步骤 7：同步打包版 context router**

运行：

```bash
cp tools/context_router.py skills/roleme/tools/context_router.py
```

预期：无输出。

- [ ] **步骤 8：运行 P5 测试**

运行：

```bash
pytest tests/test_context_router.py -v
```

预期：PASS。

- [ ] **步骤 9：运行完整测试集**

运行：

```bash
pytest -q
```

预期：PASS。

- [ ] **步骤 10：提交 P5**

```bash
git add tools/context_router.py skills/roleme/tools/context_router.py tests/test_context_router.py
git commit -m "feat: route internal skills and session recall"
```

---

## 最终验证

- [ ] 运行格式 / 空白检查：

```bash
git diff --check
```

预期：无输出。

- [ ] 运行完整测试：

```bash
pytest -q
```

预期：全部测试通过。

- [ ] 确认 resident snapshot 没有膨胀：

```bash
pytest tests/test_memory.py::test_build_frozen_snapshot_uses_resident_layers -v
```

预期：PASS，并且 resident snapshot 中没有新增 lifecycle 目录。

- [ ] 确认打包镜像已同步：

```bash
diff -u tools/memory.py skills/roleme/tools/memory.py
diff -u tools/role_ops.py skills/roleme/tools/role_ops.py
diff -u tools/context_router.py skills/roleme/tools/context_router.py
```

预期：本计划中改动过的文件无 diff 输出。
