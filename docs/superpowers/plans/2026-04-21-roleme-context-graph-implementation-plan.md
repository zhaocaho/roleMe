# roleMe Context Graph 实现计划

> **给智能体执行者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行。本计划使用 checkbox（`- [ ]`）跟踪进度。

**目标：** 为 roleMe 增加本地 Context Graph：Markdown 继续作为正文权威，Graph 负责后台路由、关系、可信度、诊断和安全回退。

**架构：** 分层落地：先统一关键文件原子写入，再实现 Graph 存储、schema、索引和诊断基础层；随后把 Graph 写入接入 workflow / memory 归档；最后在 doctor、optimize 和 fallback 稳定后，把 Graph Recall 接入 `context_router.py`。整个过程保持旧 Markdown 索引和 `discover_context_paths()` 兼容，Graph 始终是后台增强，不改变用户正常交流方式。

**技术栈：** Python 3.12、pytest、JSON / JSONL、本地 YAML 风格 schema 文本、Markdown 角色包、现有 `tools/role_ops.py`、`tools/memory.py`、`tools/context_router.py`、`tools/workflow_index.py`。不新增第三方依赖。

---

## 1. 背景与目标

### 背景

roleMe 已经有稳定的角色包结构和渐进式上下文加载能力，但长期使用后会出现三个问题：

- 线性 Markdown 索引命中效率有限，用户表达和索引关键词不一致时容易漏召回。
- 归档写入同时涉及 Markdown 正文、workflow index、memory、项目文件，当前缺少统一的原子写和 partial state 表达。
- 旧知识、低置信总结、被替代 workflow、项目经验提升为通用原则等场景缺少结构化可信度治理。

### 目标

- 新增本地 Context Graph，记录节点、关系、状态、置信度和证据。
- Markdown 继续作为正文权威，Graph 只作为后台路由、关系和可信度元数据权威。
- Archive 写入同时更新 Markdown 和 Graph，并能表达 partial failure。
- Recall 在 Graph 健康时增强命中，在 Graph 缺失、损坏、关闭或 stale 时回退旧 Markdown 路由。
- doctor / optimize 能发现并修复确定性一致性问题。

### 非目标

- 不引入 RDF、OWL、SPARQL、外部图数据库或向量数据库。
- 不让用户直接维护 `nodes.jsonl`、`edges.jsonl`、`entry_key` 或内部索引。
- 不改变用户正常对话方式；Graph 是后台机制。
- 不把 Graph 作为正文存储；正文仍在 Markdown。
- 不在普通角色加载时扫描全部 Markdown 或自动全量迁移旧角色包。
- 不在本期支持并发写入；默认单进程写入。未来如支持 automation 并发写入，再引入文件锁。
- 不新增权限、多角色、多租户模型；角色隔离仍以 `ROLEME_HOME/<role>` 目录为边界。

### 成功标准

- `python3 -m pytest -v` 全量通过。
- Graph 文件缺失、损坏、关闭时，旧 `discover_context_paths()` 路由行为不抛异常，核心回归测试通过。
- `ROLEME_GRAPH_ROUTING=0` 时完全使用旧 Markdown 路由。
- `ROLEME_GRAPH_ARCHIVE=0` 时 Markdown 正文和 index 仍正常写入，Graph 不写入。
- 关键角色包写入点不再直接调用 `Path.write_text()`，统一走 `tools/file_ops.py`。
- 发布包包含 `skills/roleme/tools/file_ops.py`、`skills/roleme/tools/graph_index.py`、`skills/roleme/assets/templates/brain/graph/schema.yaml`。
- `doctor_role()` 能报告 Graph 基础问题，`optimize_graph()` 能重建 indexes 并修复孤儿边等确定性问题。
- 普通用户交流中不暴露 Graph routing / archive / entry_key 细节。

## 2. 范围与需求

### 功能范围

- 原子文件写入：Markdown、JSON、JSONL 的关键写入使用公共 API。
- Graph schema：新角色包默认携带 `brain/graph/schema.yaml`。
- Graph core：节点、边、确定性 ID、JSONL load/save、索引重建。
- Archive：项目 bootstrap、通用 workflow、项目 workflow、USER / MEMORY、项目 memory、episode、decision、brain topic 写入 Graph。
- Trust：状态、置信度、证据、替代、冲突的基础校验。
- doctor / optimize：诊断 Graph 与 Markdown 不一致，并执行确定性修复。
- Recall：Graph 候选与旧 Markdown 路由合并，支持强/弱召回 gate。
- upgrade / validate / build_skill：旧角色包 bootstrap、校验、发布包打包。
- 文档：说明 Context Graph 是后台机制，不改变用户正常交流方式。

### 不包含范围

- 不做外部服务集成。
- 不做数据库迁移。
- 不做 UI。
- 不做多进程写锁。
- 不把所有历史 Markdown 自动迁移为 active Graph 节点。

### 用户场景

主流程：

1. 用户自然提出任务。
2. roleMe 加载 resident snapshot，不加载完整 Graph。
3. `context_router.py` 在后台尝试 Graph Recall。
4. Graph 健康时增强 workflow / rule / preference 命中。
5. Graph 不可用时回退旧 Markdown 路由。
6. 用户仍只感知到正常回答或必要的冲突确认。

异常流程：

- Graph 缺失：跳过 Graph，使用旧路由。
- Graph JSONL 损坏：doctor 报告 warning，Recall 回退旧路由。
- Graph stale：旧 Markdown index 命中作为强候选参与排序。
- Archive Graph 写入失败：Markdown 可成功，返回 partial state，用户回执说明后台索引未完全同步。
- entry-backed 旧条目无法稳定定位：doctor 报告建议，不强行建 active 节点。

### 影响范围

- 运行时工具：`tools/file_ops.py`、`tools/graph_index.py`、`tools/role_ops.py`、`tools/memory.py`、`tools/context_router.py`、`tools/workflow_index.py`
- 脚本：`scripts/build_skill.py`、`scripts/upgrade_role.py`、`scripts/validate_role.py`
- 模板：`templates/brain/graph/schema.yaml`
- 发布包：`skills/roleme/`
- 测试：`tests/test_file_ops.py`、`tests/test_graph_index.py`、`tests/test_role_ops.py`、`tests/test_memory.py`、`tests/test_context_router.py`、`tests/test_repo_scripts.py`

## 3. 技术方案约束

### 状态流转与召回行为

| 状态 | 默认召回行为 | 说明 |
| --- | --- | --- |
| `active` | 可进入强/弱召回 | 当前有效 |
| `draft` | 默认不进入强上下文 | 草稿，只在明确需要时使用 |
| `stale` | 可低权重召回 | 可能过期，需要降权 |
| `deprecated` | 默认过滤 | 仅用户询问历史时加载 |
| `superseded` | 默认过滤 | 被替代，仅历史追溯使用 |
| `invalidated` | 硬过滤 | 不得作为执行依据 |
| `archived` | 默认过滤 | 历史归档，仅历史查询使用 |

### 幂等性

- 重复归档同一 workflow 不产生重复 `Workflow` 节点。
- 重复归档同一 memory entry 不产生重复 active entry-backed 节点。
- 同一 `from + type + to` 只保留一条边，重复写入时更新 `weight`、`rationale` 或 `metadata`。
- index rebuild 可重复执行，结果稳定。

### 并发与重试

- 本期默认单进程写入，不设计文件锁。
- 原子写保证单次写失败不留下半行 JSON/JSONL。
- 暂不实现自动重试；失败由 partial state、doctor、optimize 暴露和恢复。
- 未来如果 automation 并发写入角色包，再新增文件锁和重试策略。

### 权限与角色隔离

- 不新增权限系统。
- 不新增多租户模型。
- 角色边界仍是 `ROLEME_HOME/<role>`。
- Graph 文件只写入当前角色包内，不写 skill 安装目录作为状态源。

## 4. 依赖与影响

- 外部依赖：无新增第三方依赖。
- 运行环境：Python 3.12，pytest。
- 数据依赖：现有角色包 Markdown、workflow index、memory entry、projects index。
- 关键路径依赖：`file_ops.py` 必须先完成；Graph Recall 必须等 Archive、doctor、optimize、fallback 稳定后才能接入。
- fallback：任何 Graph 读取异常都不得阻断旧 Markdown 路由。

### 设计文档与当前代码关联

| 设计要求 | 当前代码入口 | 计划任务 |
| --- | --- | --- |
| 公共原子写 API | `tools/workflow_index.py::upsert_workflow_index_entry`、`tools/memory.py::_replace_entries`、`tools/role_ops.py` 多处写入 | 任务 1-2 |
| 新角色包默认携带 `brain/graph/schema.yaml` | `tools/role_ops.py::initialize_role`、`templates/`、`scripts/build_skill.py` | 任务 3、任务 9 |
| Graph load/save/index/doctor/optimize | 当前无 `tools/graph_index.py` | 任务 4-5 |
| 项目 bootstrap 写 Project 节点 | `tools/role_ops.py::maybe_bootstrap_project_from_cwd` | 任务 6 |
| 通用 workflow 归档写 Graph | `tools/role_ops.py::archive_general_workflow` | 任务 6 |
| 项目 workflow 归档写 Graph | `tools/role_ops.py::archive_project_workflow`、`append_unique_project_memory` | 任务 6 |
| USER / MEMORY / episode 写 Graph | `tools/memory.py::write_memory`、`replace_memory_entry`、`remove_memory_entry` | 任务 7 |
| 项目 memory 写 Graph | `tools/role_ops.py::append_unique_project_memory` | 任务 7 |
| 主题知识写 Topic / Concept | `tools/role_ops.py::initialize_role_from_interview` 中的 `brain_topics` 落盘 | 任务 7 |
| 决策归档写 Decision / Evidence | 当前无独立 public API，需要在 `tools/role_ops.py` 增加最小 `archive_decision` 入口 | 任务 7 |
| Graph Recall 合并旧路由 | `tools/context_router.py::discover_context_paths` | 任务 10 |
| build / upgrade / validate 覆盖 Graph | `scripts/build_skill.py`、`scripts/upgrade_role.py`、`scripts/validate_role.py` | 任务 8-9 |

约束：计划任务只围绕上表中的设计要求和当前代码入口展开；不得额外引入外部服务、数据库、UI、权限系统、向量检索或未在设计文档中出现的新能力。

## 5. 风险分析

| 风险 | 影响 | 缓解措施 |
| --- | --- | --- |
| Markdown 写入成功但 Graph 写入失败 | Graph 与正文不一致 | `ArchiveResult` 表达 partial state，doctor/optimize 可发现和修复 |
| Graph stale 过滤新 Markdown | 召回错误 | stale 时旧 Markdown index 命中必须作为强候选 |
| entry marker 泄漏到 resident snapshot | 用户上下文污染 | `build_frozen_snapshot()` 读取 memory 时剥离 marker |
| `File` 节点误删 | 历史证据链断裂 | optimize 仅在无入边、无证据依赖、无历史价值时物理删除 |
| 静态禁止 `Path.write_text()` 误报 | 测试维护成本上升 | 限定检查生产关键工具文件；测试 fixture 不纳入检查 |
| Recall 过早接管主路由 | 正常交流受影响 | 任务 1-8 完成并通过后才允许执行任务 10 |

## 6. 测试与质量保障

- 单测：`test_file_ops.py`、`test_graph_index.py`、`test_memory.py`、`test_role_ops.py`、`test_context_router.py`
- 集成测试：`tests/integration/test_role_roundtrip.py`
- 回归测试：`python3 -m pytest -v`
- 数据校验：`doctor_graph()`、`doctor_role()`、`validate_role.py`
- 边界测试：Graph 缺失、损坏、关闭、stale、重复 ID、孤儿边、entry_key 缺失、JSONL 写失败
- 高风险测试：partial state、幂等 upsert、弱召回 gate、旧路由 fallback、发布包产物检查

## 7. 上线方案

- 发布方式：本地发布 `skills/roleme/`，不涉及服务端灰度。
- 默认开关：
  - `ROLEME_GRAPH_ARCHIVE` 默认开启。
  - `ROLEME_GRAPH_ROUTING` 仅在写入、doctor、fallback、回归测试稳定后开启。
- 上线步骤：
  1. 完成任务 1-8。
  2. 跑全量测试。
  3. 执行任务 10 接入 Recall。
  4. 再跑全量测试和发布后回归。
  5. 执行 `python3 scripts/build_skill.py` 发布本地 skill 包。
- 健康检查：
  - `python3 -m pytest -v`
  - `python3 scripts/validate_role.py <role_name>`
  - `doctor_role(<role_name>)`
- 运行期诊断：本期只通过 doctor / validate 输出本地诊断，不新增日志、Tracing 或监控系统。

## 8. 回滚方案

- 快速关闭 Graph Recall：设置 `ROLEME_GRAPH_ROUTING=0`。
- 关闭 Graph 写入：设置 `ROLEME_GRAPH_ARCHIVE=0`。
- 保留 `brain/graph/` 文件，不删除 Markdown 正文。
- 旧路由继续使用 `brain/index.md`、`projects/index.md`、`brain/workflows/index.md`、`projects/<project>/workflows/index.md`。
- 回滚验证：
  - `python3 -m pytest tests/test_context_router.py -v`
  - `python3 -m pytest tests/integration/test_role_roundtrip.py -v`
- 数据一致性：Graph 不是正文权威；关闭 Graph 后 Markdown 正文仍可继续工作。后续可通过 doctor / optimize 修复 Graph。

## 9. 排期与里程碑

| 里程碑 | 范围 | 任务 | 验收 |
| --- | --- | --- | --- |
| M1 | 原子写可靠性 | 任务 1-2 | file_ops 测试通过，关键工具无直接 `write_text()` |
| M2 | Graph 基础层 | 任务 3-5 | schema、Graph core、doctor/optimize 测试通过 |
| M3 | Archive 与发布基础 | 任务 6-9 | project bootstrap、workflow、memory、topic、decision archive 写 Graph，upgrade/validate/build_skill 通过 |
| M4 | Recall 与最终交付 | 任务 10-12 | Graph Recall 接入，全量测试和发布后回归通过 |

关键路径：任务 1 -> 任务 4 -> 任务 6 -> 任务 8 -> 任务 10。

## 10. 验证与验收

### 完成标准（DoD）

- `python3 -m pytest -v` 通过。
- `python3 -m pytest tests/test_context_router.py -v` 通过。
- `python3 -m pytest tests/integration/test_role_roundtrip.py -v` 通过。
- `python3 -m pytest tests/test_repo_scripts.py -v` 通过。
- `python3 scripts/build_skill.py` 成功生成 `skills/roleme/`。
- 发布包包含：
  - `skills/roleme/tools/file_ops.py`
  - `skills/roleme/tools/graph_index.py`
  - `skills/roleme/assets/templates/brain/graph/schema.yaml`
- project bootstrap、workflow archive、memory archive、topic archive、decision archive 均有对应 Graph 写入测试。
- `ROLEME_GRAPH_ROUTING=0` 时旧路由测试通过。
- Graph 缺失/损坏时 `discover_context_paths()` 不抛异常。
- 自然语言归档入口遇到 Graph partial failure 时不会返回完整成功回执。

### 数据对比方案

- 归档前后对比 Markdown 文件：正文仍写入原路径。
- 归档前后对比 `nodes.jsonl` / `edges.jsonl`：新增或 upsert 对应节点和边。
- 删除 `indexes/*` 后运行 `optimize_graph()`：索引可重建。
- 设置 `ROLEME_GRAPH_ROUTING=0` 后同一 query 仍可走旧 Markdown fallback。

## 文件职责

- 新增 `tools/file_ops.py`：提供 `atomic_write_text()`、`atomic_write_json()`、`atomic_rewrite_jsonl()`，所有关键角色包写入统一走这里。
- 新增 `tools/graph_index.py`：Graph dataclass、确定性 ID、JSONL 读写、索引重建、doctor、optimize、recall 数据结构和查询。
- 新增 `templates/brain/graph/schema.yaml`：新角色包默认携带的 Graph schema。
- 修改 `tools/role_ops.py`：初始化 Graph 目录；项目 bootstrap、workflow 归档、项目 memory、brain topic、decision 归档写 Graph；聚合 Graph doctor；返回 partial state。
- 修改 `tools/memory.py`：写 USER / MEMORY / episode 时写入稳定 entry marker，并同步 Preference / Principle / Episode / Evidence 节点。
- 修改 `tools/workflow_index.py`：workflow index 写入改为公共原子写 API。
- 修改 `tools/context_router.py`：增加 Graph Recall 前置分支，与旧 Markdown 路由合并并安全回退。
- 验证 `scripts/build_skill.py`：当前脚本复制 `tools/` 和 `templates/`，应通过测试确保 `file_ops.py`、`graph_index.py` 和 Graph schema 被打包；只有测试失败时才修改脚本。
- 修改 `scripts/upgrade_role.py`：旧角色包升级时只补齐 Graph schema，不做全量 Markdown 扫描。
- 修改 `scripts/validate_role.py`：校验 Graph schema、nodes、edges、indexes 的基础健康状态。
- 新增或修改测试：`tests/test_file_ops.py`、`tests/test_graph_index.py`、`tests/test_role_ops.py`、`tests/test_memory.py`、`tests/test_context_router.py`、`tests/test_repo_scripts.py`。

## 阶段 1：原子写基础层

### 任务 1：新增 `tools/file_ops.py`

**文件：**
- 新增：`tools/file_ops.py`
- 新增：`tests/test_file_ops.py`

- [x] **步骤 1：写失败测试**

创建 `tests/test_file_ops.py`：

```python
import json

import pytest

from tools.file_ops import atomic_rewrite_jsonl, atomic_write_json, atomic_write_text


def test_atomic_write_text_replaces_existing_content(tmp_path):
    path = tmp_path / "role" / "memory" / "USER.md"
    path.parent.mkdir(parents=True)
    path.write_text("old\n", encoding="utf-8")

    atomic_write_text(path, "new\n")

    assert path.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_json_writes_utf8_and_trailing_newline(tmp_path):
    path = tmp_path / "role" / "brain" / "graph" / "indexes" / "by-type.json"

    atomic_write_json(path, {"Preference": ["偏好-1"]})

    assert json.loads(path.read_text(encoding="utf-8")) == {"Preference": ["偏好-1"]}
    assert path.read_text(encoding="utf-8").endswith("\n")


def test_atomic_rewrite_jsonl_rejects_non_object_records(tmp_path):
    path = tmp_path / "nodes.jsonl"
    path.write_text('{"id":"existing"}\n', encoding="utf-8")

    with pytest.raises(TypeError, match="JSONL records must be objects"):
        atomic_rewrite_jsonl(path, [{"id": "ok"}, ["bad"]])

    assert path.read_text(encoding="utf-8") == '{"id":"existing"}\n'


def test_atomic_rewrite_jsonl_keeps_old_file_when_serialization_fails(tmp_path):
    path = tmp_path / "edges.jsonl"
    path.write_text('{"id":"edge-old"}\n', encoding="utf-8")

    with pytest.raises(TypeError):
        atomic_rewrite_jsonl(path, [{"id": "edge-new", "bad": object()}])

    assert path.read_text(encoding="utf-8") == '{"id":"edge-old"}\n'
```

- [x] **步骤 2：确认测试失败**

运行：`python3 -m pytest tests/test_file_ops.py -v`

预期：失败，提示 `ModuleNotFoundError: No module named 'tools.file_ops'`。

- [x] **步骤 3：实现最小功能**

创建 `tools/file_ops.py`：

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
            tmp_name = tmp.name
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    finally:
        if tmp_name is not None:
            tmp_path = Path(tmp_name)
            if tmp_path.exists():
                tmp_path.unlink()


def atomic_write_text(path: Path, content: str) -> None:
    _atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, content)


def atomic_rewrite_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("JSONL records must be objects")
        lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    atomic_write_text(path, "\n".join(lines).rstrip() + ("\n" if lines else ""))
```

- [x] **步骤 4：确认测试通过**

运行：`python3 -m pytest tests/test_file_ops.py -v`

预期：通过。

- [ ] **步骤 5：提交**

```bash
git add tools/file_ops.py tests/test_file_ops.py
git commit -m "feat: add atomic role file writes"
```

### 任务 2：替换现有关键直接写入点

**文件：**
- 修改：`tools/workflow_index.py`
- 修改：`tools/memory.py`
- 修改：`tools/role_ops.py`
- 修改：`tests/test_repo_scripts.py`

- [x] **步骤 1：新增静态约束测试**

在 `tests/test_repo_scripts.py` 增加：

```python
from pathlib import Path


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
```

- [x] **步骤 2：确认测试失败**

运行：`python3 -m pytest tests/test_repo_scripts.py::test_critical_role_tools_do_not_write_role_files_directly -v`

预期：失败，列出 `tools/workflow_index.py`、`tools/memory.py`、`tools/role_ops.py` 中的直接 `write_text()`。

- [x] **步骤 3：替换写入 API**

在 `tools/workflow_index.py`、`tools/memory.py`、`tools/role_ops.py` 中引入：

```python
from tools.file_ops import atomic_write_json, atomic_write_text
```

替换规则：

- Markdown / 文本文件使用 `atomic_write_text(path, content)`
- JSON manifest / state 使用 `atomic_write_json(path, payload)`
- 不改变现有业务语义和返回值

- [x] **步骤 4：运行回归测试**

运行：

```bash
python3 -m pytest tests/test_file_ops.py tests/test_workflow_index.py tests/test_memory.py tests/test_role_ops.py::test_initialize_role_creates_required_files -v
python3 -m pytest tests/test_repo_scripts.py::test_critical_role_tools_do_not_write_role_files_directly -v
```

预期：全部通过。

- [ ] **步骤 5：提交**

```bash
git add tools/file_ops.py tools/workflow_index.py tools/memory.py tools/role_ops.py tests/test_file_ops.py tests/test_repo_scripts.py
git commit -m "refactor: use atomic writes for role files"
```

## 阶段 2：Graph schema 与基础存储

### 任务 3：新增 Graph schema 模板和初始化

**文件：**
- 新增：`templates/brain/graph/schema.yaml`
- 修改：`tools/role_ops.py`
- 修改：`tests/test_role_ops.py`
- 修改：`tests/test_repo_scripts.py`

- [x] **步骤 1：写失败测试**

在 `tests/test_role_ops.py` 增加：

```python
def test_initialize_role_creates_graph_schema(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    schema_path = role_path / "brain" / "graph" / "schema.yaml"
    assert schema_path.exists()
    schema_text = schema_path.read_text(encoding="utf-8")
    assert 'graph_schema_version: "1.0"' in schema_text
    assert "node_types:" in schema_text
    assert "edge_types:" in schema_text
```

在 `tests/test_repo_scripts.py` 增加：

```python
def test_build_skill_includes_graph_schema_template(tmp_path):
    artifact = build_skill(output_root=tmp_path)

    assert (artifact / "assets" / "templates" / "brain" / "graph" / "schema.yaml").exists()
```

- [x] **步骤 2：创建 schema 模板**

创建 `templates/brain/graph/schema.yaml`：

```yaml
graph_schema_version: "1.0"
node_types:
  - Project
  - Workflow
  - Rule
  - Preference
  - Principle
  - Memory
  - Episode
  - Decision
  - Evidence
  - Concept
  - Topic
  - File
edge_types:
  - belongs_to
  - contains
  - applies_to
  - depends_on
  - specializes
  - generalizes
  - supersedes
  - evidenced_by
  - derived_from
  - promoted_to
  - supports
  - contradicts
  - mentions
  - related_to
  - covers
  - records
  - invalidated_by
  - verifies
statuses:
  - active
  - draft
  - stale
  - deprecated
  - superseded
  - invalidated
  - archived
confidences:
  - high
  - medium
  - low
```

- [x] **步骤 3：确认初始化会复制模板**

如果 `initialize_role()` 已经复制整个 `templates/`，只需确保新模板被带入；否则在 `tools/role_ops.py` 中显式创建 `brain/graph/indexes` 并复制 `schema.yaml`。

- [x] **步骤 4：运行测试**

运行：`python3 -m pytest tests/test_role_ops.py::test_initialize_role_creates_graph_schema tests/test_repo_scripts.py::test_build_skill_includes_graph_schema_template -v`

预期：通过。

- [ ] **步骤 5：提交**

```bash
git add templates/brain/graph/schema.yaml tools/role_ops.py tests/test_role_ops.py tests/test_repo_scripts.py
git commit -m "feat: bootstrap context graph schema"
```

### 任务 4：实现 Graph core

**文件：**
- 新增：`tools/graph_index.py`
- 新增：`tests/test_graph_index.py`

- [x] **步骤 1：写失败测试**

创建 `tests/test_graph_index.py`，覆盖：

- path-backed node ID 不随标题变化
- entry-backed node ID 使用 `metadata.entry_key`
- `save_graph()` / `load_graph()` JSONL 往返
- `rebuild_indexes()` 生成 `by-type.json`、`by-path.json`、`by-alias.json`、`by-project.json`

测试中使用这些公开对象：

```python
from tools.graph_index import (
    EdgeRecord,
    NodeRecord,
    deterministic_edge_id,
    deterministic_node_id,
    load_graph,
    rebuild_indexes,
    save_graph,
)
```

- [x] **步骤 2：实现 dataclass 和 ID**

在 `tools/graph_index.py` 中实现：

- `NodeRecord`
- `EdgeRecord`
- `GraphData`
- `_normalize_path()`
- `deterministic_node_id()`
- `deterministic_edge_id()`

ID 规则：

```text
path-backed: type + scope + project_slug + normalized_path
entry-backed: type + scope + project_slug + normalized_path + entry_key
concept-like: type + scope + project_slug + normalized_title
edge: from + type + to
```

- [x] **步骤 3：实现 JSONL 读写和索引**

实现：

- `NodeRecord.to_dict()` / `from_dict()`
- `EdgeRecord.to_dict()` / `from_dict()`，JSON 字段使用 `"from"` / `"to"`，Python 属性使用 `from_node` / `to_node`
- `load_graph(role_path)`
- `save_graph(role_path, nodes, edges)`
- `rebuild_indexes(role_path, nodes, index_version="1.0")`

Schema 校验只需要解析本计划定义的简单 `schema.yaml` 文本结构，不引入 PyYAML 或其他第三方依赖。可先实现 `load_schema_text(role_path)` 和 `validate_schema_text(text)`，校验 `graph_schema_version`、`node_types`、`edge_types`、`statuses`、`confidences` 这些必需段落是否存在。

- [x] **步骤 4：运行测试**

运行：`python3 -m pytest tests/test_graph_index.py -v`

预期：通过。

- [ ] **步骤 5：提交**

```bash
git add tools/graph_index.py tests/test_graph_index.py
git commit -m "feat: add context graph storage core"
```

### 任务 5：实现 doctor / optimize 基础能力

**文件：**
- 修改：`tools/graph_index.py`
- 修改：`tests/test_graph_index.py`

- [x] **步骤 1：补充失败测试**

在 `tests/test_graph_index.py` 增加：

- duplicate node id 报告 warning
- orphan edge source / target 报告 warning
- entry-backed 节点缺少 `metadata.entry_key` 报告 warning
- workflow index 中 active workflow 缺少对应 `Workflow` 节点时报告 warning
- Graph 中 active `Workflow` 节点无法在 workflow index 中找到入口时报告 warning
- 孤立 `Evidence` 节点报告 warning
- `supersedes`、`invalidated_by`、`promoted_to`、`generalizes` 关系缺少 `Evidence` 或 `Episode` 来源时报告 warning
- `low` confidence 的强规则节点报告 warning
- `optimize_graph()` 删除孤儿边并重建 indexes
- 与强语义节点同 path 的 `File` 节点如仍有历史入边，不物理删除
- `optimize_graph()` 可从 workflow index 回填缺失的 `Workflow` 节点
- `optimize_graph()` 可从 brain index 回填缺失的 `Topic` 节点
- `optimize_graph()` 可从 memory 条目回填缺失的 `Preference` / `Principle` 节点
- 对无法稳定生成 `entry_key` 的旧 memory 条目，`optimize_graph()` 只报告建议，不创建 active 节点

- [x] **步骤 2：实现报告类型**

```python
@dataclass(frozen=True)
class GraphDoctorReport:
    warnings: list[str]


@dataclass(frozen=True)
class GraphOptimizeResult:
    repairs: list[str]
    warnings: list[str]
```

- [x] **步骤 3：实现 `doctor_graph()`**

检查项：

- duplicate node id / edge id
- edge 指向不存在节点
- `project` scope 缺少 `project_slug`
- path-backed 类型缺少 path
- entry-backed 类型缺少 `metadata.entry_key`
- 同一路径同时存在强语义节点和 `File`
- workflow index 和 Graph 状态不一致
- Graph active 节点无法在 Markdown index 或正文找到入口
- Markdown index 或正文中的 active 内容缺少对应 Graph 节点
- 孤立 `Evidence`
- `low` confidence 强规则
- `supersedes` / `invalidated_by` / `promoted_to` / `generalizes` 缺少 `Evidence` 或 `Episode` 来源

- [x] **步骤 4：实现 `optimize_graph()`**

只执行确定性修复：

- 删除孤儿边
- 重建 indexes
- 仅在无入边、无证据依赖、无历史追溯价值时移除冗余 `File`
- 从 workflow index 回填缺失的 `Workflow` 节点
- 从 brain index 回填缺失的 `Topic` 节点
- 从 memory 条目回填缺失的 `Preference` / `Principle` 节点
- 对无法稳定生成 `entry_key` 的旧 memory 条目只生成 warning，不强行迁移为 active 节点

- [x] **步骤 5：运行测试**

运行：`python3 -m pytest tests/test_graph_index.py -v`

预期：通过。

- [ ] **步骤 6：提交**

```bash
git add tools/graph_index.py tests/test_graph_index.py
git commit -m "feat: add context graph doctor optimize"
```

## 阶段 3：Archive 接入 Graph

### 任务 6：project bootstrap 与 workflow 归档写入 Graph

**文件：**
- 修改：`tools/role_ops.py`
- 修改：`tools/graph_index.py`
- 修改：`tests/test_role_ops.py`

- [x] **步骤 1：写失败测试**

在 `tests/test_role_ops.py` 增加：

- `maybe_bootstrap_project_from_cwd()` 在自动补齐项目文件时写入 `Project` 节点
- `archive_general_workflow()` 写入 `Workflow`、`Concept`、`Evidence`，并写入 `applies_to`、`evidenced_by`
- `archive_project_workflow()` 额外写入 `Project`，并写入 `belongs_to`
- `archive_project_workflow()` 写入 `project_memory` 时同步创建 `Memory(scope=project)` 和 `Evidence`
- `ROLEME_GRAPH_ARCHIVE=0` 时 Markdown 正常写入，返回 `graph_skipped=True`
- Graph 写入失败时返回 partial state，不能伪装完整成功

- [x] **步骤 2：扩展 `WorkflowArchiveResult`**

在 `tools/role_ops.py` 中增加字段：

```python
markdown_written: bool = True
index_updated: bool = True
graph_updated: bool = False
graph_skipped: bool = False
doctor_warnings: tuple[str, ...] = ()
```

- [x] **步骤 3：增加 upsert helper**

在 `tools/graph_index.py` 中增加：

```python
def upsert_node(nodes: list[NodeRecord], node: NodeRecord) -> list[NodeRecord]:
    if any(current.id == node.id for current in nodes):
        return [node if current.id == node.id else current for current in nodes]
    return [*nodes, node]


def upsert_edge(edges: list[EdgeRecord], edge: EdgeRecord) -> list[EdgeRecord]:
    if any(current.id == edge.id for current in edges):
        return [edge if current.id == edge.id else current for current in edges]
    return [*edges, edge]
```

- [x] **步骤 4：接入归档写 Graph**

在 `archive_general_workflow()` 中写入：

- `Workflow(scope=global, path=brain/workflows/<slug>.md)`
- `Concept(scope=global, title=workflow_applies_to)`
- `Evidence(source_type=user_statement, source_path=<workflow path>)`
- `Workflow applies_to Concept`
- `Workflow evidenced_by Evidence`

在 `archive_project_workflow()` 中额外写入：

- `Project(scope=project, project_slug=<slug>, path=projects/<slug>/context.md)`
- `Workflow belongs_to Project`
- `project_memory` 中每条新项目记忆写入 `Memory(scope=project, path=projects/<slug>/memory.md)`
- `Memory belongs_to Project`
- `Memory evidenced_by Evidence`

在 `maybe_bootstrap_project_from_cwd()` 中写入：

- `Project(scope=project, project_slug=<slug>, path=projects/<slug>/context.md)`
- `metadata.repo_path` 记录当前仓库绝对路径
- 只在当前 cwd 是 Git 仓库根目录且项目 bootstrap 实际发生时写入

- [x] **步骤 5：运行测试**

运行：`python3 -m pytest tests/test_role_ops.py -k "archive" -v`

预期：通过。

- [ ] **步骤 6：提交**

```bash
git add tools/role_ops.py tools/graph_index.py tests/test_role_ops.py
git commit -m "feat: archive workflows into context graph"
```

### 任务 7：memory、topic、decision 归档写 Graph

**文件：**
- 修改：`tools/memory.py`
- 修改：`tools/role_ops.py`
- 修改：`tools/graph_index.py`
- 修改：`tests/test_memory.py`
- 修改：`tests/test_role_ops.py`

**失败策略补充：**

- `memory.py` 的 `write_memory()`、`summarize_and_write()`、`replace_memory_entry()` 等低层记忆写入入口以 Markdown 为优先结果；Graph 同步失败时不向上抛异常，不阻断用户侧记忆落盘。
- `role_ops.py` 中有结构化返回值的归档入口，例如 workflow archive 与 `archive_decision()`，Graph 写入失败时应返回 partial state：`markdown_written=True`、`graph_updated=False`、`graph_skipped=False`，并在 `doctor_warnings` 中记录失败原因。
- `ROLEME_GRAPH_ARCHIVE=0` 仍表示显式跳过 Graph：Markdown 正常写入，返回值中 `graph_skipped=True`。

- [x] **步骤 1：写失败测试**

在 `tests/test_memory.py` 增加：

- `write_memory(..., target="user")` 会写入 `<!-- roleme-entry:<key> -->`
- USER 条目创建 `Preference` + `Evidence`
- MEMORY 条目创建 `Principle` + `Evidence`
- episode 创建 `Episode` + `Evidence`
- `build_frozen_snapshot()` 不显示 marker
- 编辑 entry-backed 条目正文不会因为 hash 变化静默创建新的 active 节点

在 `tests/test_role_ops.py` 增加：

- `initialize_role_from_interview()` 写入 `brain_topics` 时同步创建 `Topic`、`Concept` 和 `covers` 关系
- 新增 `archive_decision()` 写入 `Decision`、`Evidence` 和 `Decision evidenced_by Evidence`
- `archive_decision()` 可选写入 `supersedes` 关系时，旧 `Decision.status` 更新为 `superseded`

- [x] **步骤 2：实现 marker**

在 `tools/memory.py` 中增加：

```python
ENTRY_MARKER_PATTERN = re.compile(r"<!-- roleme-entry:([a-z0-9_-]+) -->")
```

并实现：

- `_entry_key_for(content)`
- `_format_entry_with_marker(content)`
- `_strip_entry_marker(entry)`

- [x] **步骤 3：写入 memory graph 节点**

规则：

- `target in {"user", "preference"}` -> `Preference`
- `target == "memory"` -> `Principle`
- `target == "episode"` -> `Episode`
- 每次新增条目创建 `Evidence`
- entry-backed 节点必须写 `metadata.entry_key`
- `ROLEME_GRAPH_ARCHIVE=0` 时只写 Markdown，不写 Graph

- [x] **步骤 4：写入 brain topic graph 节点**

在 `tools/role_ops.py::initialize_role_from_interview()` 的 `brain_topics` 落盘逻辑中同步写入：

- `Topic(scope=global, path=brain/topics/<topic.slug>.md)`
- `Concept(scope=global, title=<topic.title>)`
- `Topic covers Concept`

同一路径已经有 `Topic` 时，不额外创建 `File` 节点。

- [x] **步骤 5：新增最小 decision archive 入口**

在 `tools/role_ops.py` 增加 `archive_decision()`，只实现设计文档要求的确定性后台入口，不新增用户交互流程：

```python
@dataclass(frozen=True)
class DecisionArchiveResult:
    written_paths: list[str]
    markdown_written: bool
    graph_updated: bool
    graph_skipped: bool
    doctor_warnings: tuple[str, ...] = ()
```

`archive_decision(role_path, title, summary, rationale, source_path=None, supersedes_id=None)` 行为：

- 写入 `memory/episodes/<episode>.md` 或复用传入 `source_path`
- upsert `Decision`
- upsert `Evidence`
- upsert `Decision evidenced_by Evidence`
- `supersedes_id` 存在时 upsert `Decision supersedes Decision`，并把旧 decision 标为 `superseded`
- `ROLEME_GRAPH_ARCHIVE=0` 时只写 Markdown，不写 Graph

- [x] **步骤 6：运行测试**

运行：`python3 -m pytest tests/test_memory.py tests/test_role_ops.py -k "memory or topic or decision" -v`

预期：通过。

- [ ] **步骤 7：提交**

```bash
git add tools/memory.py tools/role_ops.py tools/graph_index.py tests/test_memory.py tests/test_role_ops.py
git commit -m "feat: archive role knowledge into context graph"
```

## 阶段 4：doctor、upgrade、validate、打包

### 任务 8：聚合 Graph doctor，支持 upgrade / validate

**文件：**
- 修改：`tools/role_ops.py`
- 修改：`scripts/upgrade_role.py`
- 修改：`scripts/validate_role.py`
- 修改：`tests/test_role_ops.py`
- 修改：`tests/test_repo_scripts.py`

- [x] **步骤 1：写失败测试**

覆盖：

- `doctor_role()` 包含 `doctor_graph()` warnings
- `scripts/upgrade_role.py self` 会创建缺失的 `brain/graph/schema.yaml`
- `scripts/validate_role.py self` 在 Graph 损坏时返回非 0，并输出 warning

- [x] **步骤 2：聚合 doctor**

在 `doctor_role()` 中追加：

```python
graph_report = doctor_graph(base_path)
warnings.extend(graph_report.warnings)
```

- [x] **步骤 3：更新 upgrade**

`scripts/upgrade_role.py` 只做 bootstrap：

- 创建 `brain/graph/`
- 创建 `brain/graph/indexes/`
- 缺失时写入当前 `templates/brain/graph/schema.yaml`
- 不扫描全量 Markdown

- [x] **步骤 4：更新 validate**

`scripts/validate_role.py` 输出 missing / warning，并在存在问题时 `SystemExit(1)`。

- [x] **步骤 5：运行测试**

运行：`python3 -m pytest tests/test_role_ops.py::test_doctor_role_includes_graph_warnings tests/test_repo_scripts.py -v`

预期：通过。

- [ ] **步骤 6：提交**

```bash
git add tools/role_ops.py scripts/upgrade_role.py scripts/validate_role.py tests/test_role_ops.py tests/test_repo_scripts.py
git commit -m "feat: validate and upgrade context graph"
```

### 任务 9：打包 Graph runtime

**文件：**
- 修改：`tests/test_repo_scripts.py`
- 如需要修改：`scripts/build_skill.py`
- 生成更新：`skills/roleme/`

- [x] **步骤 1：增加打包断言**

在 `test_build_skill_creates_artifact_without_scripts()` 中增加：

```python
assert (artifact / "tools" / "file_ops.py").exists()
assert (artifact / "tools" / "graph_index.py").exists()
assert (artifact / "assets" / "templates" / "brain" / "graph" / "schema.yaml").exists()
```

- [x] **步骤 2：运行测试**

运行：`python3 -m pytest tests/test_repo_scripts.py -v`

预期：通过。如果失败，修正测试 fixture 或 `build_skill()`。

- [x] **步骤 3：发布本地 skill 包**

运行：`python3 scripts/build_skill.py`

预期生成：

```text
skills/roleme/tools/file_ops.py
skills/roleme/tools/graph_index.py
skills/roleme/assets/templates/brain/graph/schema.yaml
```

- [ ] **步骤 4：提交**

```bash
git add scripts/build_skill.py tests/test_repo_scripts.py skills/roleme tools/file_ops.py tools/graph_index.py templates/brain/graph/schema.yaml
git commit -m "build: package context graph runtime"
```

## 阶段 5：Graph Recall 接入

### 进入条件

执行本阶段前必须满足：

- 任务 1-8 已完成并提交。
- `python3 -m pytest tests/test_file_ops.py tests/test_graph_index.py tests/test_role_ops.py tests/test_memory.py -v` 通过。
- `doctor_role()` 已能聚合 Graph warnings。
- `ROLEME_GRAPH_ARCHIVE=0` 的 archive fallback 测试通过。
- Graph partial state 不会被自然语言归档入口吞掉。

如果任一条件不满足，不得把 Graph Recall 接入 `discover_context_paths()` 主路径。

### 任务 10：Graph Recall 与旧 Markdown 路由合并

**文件：**
- 修改：`tools/graph_index.py`
- 修改：`tools/context_router.py`
- 修改：`tests/test_context_router.py`

- [ ] **步骤 1：写失败测试**

在 `tests/test_context_router.py` 增加：

- active/high confidence 的当前项目 `Workflow` 可被 query 命中
- `ROLEME_GRAPH_ROUTING=0` 时完全走旧路由
- `ROLEME_GRAPH_ARCHIVE=0` 时 Graph 视为 stale，旧 markdown index 命中必须作为强候选
- `invalidated`、`deprecated`、`superseded` 默认不进入上下文
- 弱召回未触发时 `Memory / Episode / Decision / Topic / File` 不进入正文预算
- 第一名和第二名分差过小时回退旧路由或请求澄清，不强行选择

- [ ] **步骤 2：增加 recall 数据结构**

在 `tools/graph_index.py` 中增加：

```python
@dataclass(frozen=True)
class ContextCandidate:
    node_id: str
    path: str | None
    score: float
    recall_strength: str
    status: str
    confidence: str
    reasons: tuple[str, ...]
    trust_flags: tuple[str, ...]


@dataclass(frozen=True)
class GraphRecallResult:
    candidates: list[ContextCandidate]
    fallback_required: bool
    warnings: list[str]
```

- [ ] **步骤 3：实现 `recall_graph()`**

规则：

- Graph 缺失、schema 缺失、JSONL 解析失败、`ROLEME_GRAPH_ROUTING=0`：`fallback_required=True`
- strong 类型：`Project / Workflow / Rule / Preference / Principle / Concept`
- weak 类型：`Memory / Episode / Decision / Topic / File`
- weak 只在强召回不足、用户问历史/来源/证据/冲突时展开
- hard filter：`invalidated`、`deprecated`、`superseded`
- `stale` 和 `low` confidence 降权
- 当前项目加权
- alias / keyword / title / summary 命中加权

- [ ] **步骤 4：接入 `context_router.py`**

在 `discover_context_paths()` 开头尝试 Graph Recall：

- Graph 不可用：返回旧逻辑
- Graph 健康：Graph 强候选优先，但合并旧 workflow / brain / project index 强命中
- Graph stale：旧 markdown index 命中必须作为强候选参与排序
- 最终仍返回 path list，兼容现有调用方

- [ ] **步骤 5：运行测试**

运行：

```bash
python3 -m pytest tests/test_context_router.py -k "graph or stale or routing" -v
python3 -m pytest tests/test_context_router.py -v
```

预期：全部通过。

- [ ] **步骤 6：提交**

```bash
git add tools/graph_index.py tools/context_router.py tests/test_context_router.py
git commit -m "feat: add graph assisted context recall"
```

## 阶段 6：回归、发布和文档

### 任务 11：全量回归与发布验证

**文件：**
- 修改：回归中发现的问题文件
- 生成更新：`skills/roleme/`

- [ ] **步骤 1：运行全量测试**

运行：`python3 -m pytest -v`

预期：通过。

- [ ] **步骤 2：运行静态写入约束测试**

运行：`python3 -m pytest tests/test_repo_scripts.py::test_critical_role_tools_do_not_write_role_files_directly -v`

预期：通过。

- [ ] **步骤 3：发布 skill 包**

运行：`python3 scripts/build_skill.py`

预期：`skills/roleme/` 包含 Graph runtime 和 schema。

- [ ] **步骤 4：发布后回归**

运行：`python3 -m pytest tests/test_repo_scripts.py tests/integration/test_role_roundtrip.py -v`

预期：通过。

- [ ] **步骤 5：提交**

```bash
git add tools scripts templates skills tests
git commit -m "test: verify context graph integration"
```

如果没有变更，不创建空提交。

### 任务 12：补充用户文档和后台机制说明

**文件：**
- 修改：`bundle/references/usage.md`
- 修改：`bundle/SKILL.template.md`
- 发布后修改：`skills/roleme/references/usage.md`
- 发布后修改：`skills/roleme/SKILL.md`
- 修改：`tests/test_repo_scripts.py`

- [ ] **步骤 1：写失败测试**

在 `tests/test_repo_scripts.py` 增加：

```python
def test_build_skill_documents_context_graph_as_background_mechanism(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "Context Graph 是后台机制" in usage_md
    assert "不改变用户正常对话方式" in usage_md
    assert "ROLEME_GRAPH_ROUTING=0" in usage_md
    assert "ROLEME_GRAPH_ARCHIVE=0" in usage_md
    assert "用户不需要直接维护 Graph" in skill_md
```

- [ ] **步骤 2：更新 `bundle/references/usage.md`**

新增章节：

````markdown
## Context Graph 后台机制

Context Graph 是 roleMe 的后台索引和可信度治理机制，不改变用户正常对话方式。

用户仍然自然提出任务、归档经验、修改偏好；系统在后台维护 Graph，用于更稳定地命中 workflow、记录来源证据、处理过期或冲突知识。

用户不需要直接维护 Graph 文件。只有当后台发现高风险冲突、低置信知识会影响重要行为，或用户显式询问诊断和来源时，系统才会说明相关状态。

可用开关：

```text
ROLEME_GRAPH_ROUTING=0   禁用 Graph 召回，保留旧 markdown 路由
ROLEME_GRAPH_ARCHIVE=0   禁用 Graph 写入，markdown 正文和索引仍正常写入
```
````

- [ ] **步骤 3：更新 `bundle/SKILL.template.md`**

新增运行时规则：

```markdown
- 用户不需要直接维护 Graph；Context Graph 是后台机制，不改变用户正常对话方式。
```

- [ ] **步骤 4：发布并测试**

运行：

```bash
python3 scripts/build_skill.py
python3 -m pytest tests/test_repo_scripts.py::test_build_skill_documents_context_graph_as_background_mechanism -v
```

预期：通过。

- [ ] **步骤 5：提交**

```bash
git add bundle/SKILL.template.md bundle/references/usage.md skills/roleme/SKILL.md skills/roleme/references/usage.md tests/test_repo_scripts.py
git commit -m "docs: describe context graph background behavior"
```

## 自检结果

- 设计覆盖：schema、存储、Archive、Recall、Trust、doctor、optimize、迁移、打包、回滚和用户体验均有对应任务。
- 模板覆盖：已补齐背景与目标、范围与需求、技术方案约束、依赖影响、风险分析、质量保障、上线方案、回滚方案、里程碑、验证与验收。
- 执行顺序：先写入可靠性，再 Graph 基础层，再 Archive，再 doctor / optimize，最后 Recall，符合设计文档要求。
- 用户体验：Graph 始终是后台机制；普通对话不暴露节点、边、entry_key、routing / archive 开关。
- 测试策略：每阶段都有失败测试、实现、通过测试和提交步骤。
- 注意事项：不要在任务 1-8 稳定前启用 Graph Recall 作为主路由；本期不支持并发写入和文件锁。
