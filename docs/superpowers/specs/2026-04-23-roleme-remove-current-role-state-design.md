# roleMe 移除 current role 状态设计文档

日期：2026-04-23  
状态：草案，待确认

## 背景

`roleMe` 当前通过 `ROLEME_HOME/.current-role.json` 记录最近一次加载的角色。加载 `/roleMe <角色名>` 后，工具层会把角色名、角色目录和加载时间写入这个全局状态文件；后续自然语言归档、workflow 归档等写入入口再通过 `get_current_role_state()` 判断“当前角色”。

这个模型在单窗口使用时足够简单，但在多窗口、多会话并行时会产生串写风险：

1. 窗口 A 加载 `zhaochao`
2. 窗口 B 加载 `股民`
3. `.current-role.json` 被 B 覆盖成 `股民`
4. 窗口 A 后续触发归档时，如果工具层重新读取全局 current，就可能写入 `股民`

用户的实际使用方式是：每个窗口加载一次角色后，后续自然语言都应默认归档到该窗口已加载的角色；用户不希望每次显式说明角色名，也不需要 `/roleMe current`。

因此，本设计决定彻底移除 `.current-role.json` 作为 roleMe 运行时状态的机制。

## 目标

- 删除全局 current role 指针语义。
- 加载角色时不再写入 `.current-role.json`。
- 写入类 API 不再从全局状态推断目标角色。
- workflow 归档、自然语言归档等持久化动作必须携带确定的 role identity。
- 多窗口加载不同角色时，写入目标由各自会话持有的角色上下文决定，互不覆盖。
- 文档、测试和打包产物不再宣称 `.current-role.json` 是当前角色来源。

## 非目标

- 不设计每窗口一个 `.current-role.<session-id>.json` 的替代状态文件。
- 不保留 `.current-role.json` 作为 fallback。
- 不实现 `/roleMe current` 的新会话态能力。
- 不主动删除用户本地已有的旧 `.current-role.json` 文件。
- 不改变角色包主体目录结构，如 `persona/`、`memory/`、`brain/`、`projects/`。
- 不重构 context graph、memory lifecycle 或 workflow index 的主体模型。

## 核心决策

### 1. roleMe 不再维护全局当前角色

移除以下函数及其语义：

- `current_role_state_paths()`
- `current_role_state_path()`
- `set_current_role_state()`
- `get_current_role_state()`

同时移除 `CurrentRoleState` 数据类，除非仍有非 current 语义的调用方需要保留结构化返回值。

### 2. 加载入口只返回角色上下文

`load_role_bundle(role_name)` 的职责收敛为：

- 校验并定位角色目录
- 读取 resident files
- 按需初始化当前 Git 仓库对应的项目上下文
- 构建 frozen snapshot
- 返回 `RoleBundle`

它不再写入任何 current state。

`load_query_context_bundle(role_name, query, ...)` 同理，只返回 query context，不写 current state。

### 3. 写入 API 必须解析出明确 role

所有会修改角色包的 API 必须拥有明确的 role identity。对 workflow 归档入口，采用以下接口：

```python
def archive_general_workflow(
    plan: WorkflowArchivePlan,
    role_name: str | None = None,
) -> WorkflowArchiveResult:
    ...


def archive_project_workflow(
    plan: WorkflowArchivePlan,
    role_name: str | None = None,
) -> WorkflowArchiveResult:
    ...
```

角色解析规则：

1. 如果传入 `role_name`，优先使用参数。
2. 如果没有参数，但 `plan.role_name` 存在，使用 `plan.role_name`。
3. 如果两者都存在但不一致，抛出 `ValueError`。
4. 如果两者都不存在，抛出 `ValueError`，不写任何文件。

示例错误：

```text
Workflow archive requires role_name.
Workflow archive role_name conflicts with plan.role_name.
```

### 4. 上层会话负责隐式角色绑定

用户仍然不需要在自然语言中反复说角色名。

加载 `/roleMe zhaochao` 后，当前会话应持有该次加载返回的 `RoleBundle.role_name` 或 `RoleBundle.role_path`。后续当助手判断需要归档时，应把该 role identity 写入 `WorkflowArchivePlan.role_name`，或作为 `role_name` 参数传入写入 API。

这意味着“隐式角色”存在于会话上下文中，而不是存在于全局文件中。

会话绑定协议：

- `/roleMe <角色名>` 成功加载后，助手必须在当前会话的工作状态中记录 `loaded_role_name` 和 `loaded_role_path`。
- 该状态来自刚刚返回的 `RoleBundle`，不得从 `.current-role.json` 读取。
- 后续自然语言归档 planner 必须从 `loaded_role_name` 填充 `WorkflowArchivePlan.role_name`。
- 如果当前会话没有 `loaded_role_name`，自然语言归档必须拒绝写入，并提示用户先执行 `/roleMe <角色名>`。
- 上下文压缩或会话恢复时，摘要必须保留“当前会话已加载角色：<role_name>，路径：<role_path>”这类稳定状态；如果摘要中没有该状态，就视为未加载角色。
- 工具层不负责猜测会话角色，只负责校验调用方传入的 role identity。

## 用户体验

### 加载角色

用户执行：

```text
/roleMe zhaochao
```

系统加载角色并返回 frozen snapshot。不会创建或更新：

```text
ROLEME_HOME/.current-role.json
```

### 自然语言归档

用户在同一窗口继续说：

```text
帮我总结这个项目的工作方式
```

助手应使用当前会话已经加载的 `zhaochao` 作为写入目标，生成包含 `role_name="zhaochao"` 的归档计划，然后调用写入 API。

如果当前会话没有加载过角色，助手不能再通过 `.current-role.json` 猜测角色，应直接提示用户先执行：

```text
/roleMe <角色名>
```

### `/roleMe current`

该命令不再作为支持命令保留。命令列表中必须移除 `/roleMe current`。

如果用户仍然输入 `/roleMe current`，行为固定为返回不支持提示：

```text
/roleMe current 已不再支持全局当前角色查询。请在当前会话重新执行 /roleMe <角色名>。
```

该路径不得读取 `.current-role.json` 或任何替代状态文件。

## 代码影响

### `tools/role_ops.py`

需要修改：

- 删除 current state 相关函数和数据类。
- 删除 `roleme_state_home()` 中仅为 current state fallback 服务的逻辑；如果无其他调用，应一并移除。
- `load_role_bundle()` 删除 `set_current_role_state(role_name)` 调用。
- `load_query_context_bundle()` 删除 `set_current_role_state(role_name)` 调用。
- `archive_general_workflow()` 改为从参数或 `plan.role_name` 解析目标角色。
- `archive_project_workflow()` 改为从参数或 `plan.role_name` 解析目标角色。

建议新增私有 helper：

```python
def _resolve_archive_role_name(
    explicit_role_name: str | None,
    plan_role_name: str | None,
) -> str:
    ...
```

该 helper 负责：

- 标准化角色名
- 校验缺失
- 校验冲突

### Mutation API inventory

所有持久化入口必须明确目标角色来源：

| API | 是否修改角色包 | 目标角色来源 | 本次要求 |
| --- | --- | --- | --- |
| `initialize_role(role_name, skill_version)` | 是 | `role_name` 参数 | 保持显式参数，不依赖 current |
| `initialize_role_from_interview(role_name, ...)` | 是 | `role_name` 参数 | 保持显式参数，不依赖 current |
| `load_role_bundle(role_name)` | 可能写项目 bootstrap | `role_name` 参数解析出的 `role_path` | 删除 current 写入 |
| `load_query_context_bundle(role_name, query, ...)` | 可能写项目 bootstrap | `role_name` 参数解析出的 `role_path` | 删除 current 写入 |
| `maybe_bootstrap_project_from_cwd(role_path)` | 是 | `role_path` 参数 | 保持显式路径 |
| `archive_general_workflow(plan, role_name=None)` | 是 | `role_name` 参数或 `plan.role_name` | 新增显式解析，缺失时报错 |
| `archive_project_workflow(plan, role_name=None)` | 是 | `role_name` 参数或 `plan.role_name` | 新增显式解析，缺失时报错 |
| `archive_decision(role_path, ...)` | 是 | `role_path` 参数 | 保持显式路径 |
| `write_memory(role_path, target, content)` | 是 | `role_path` 参数 | 保持显式路径 |
| `write_inbox_entry(role_path, entry)` | 是 | `role_path` 参数 | 保持显式路径 |
| `write_learning_entry(role_path, entry)` | 是 | `role_path` 参数 | 保持显式路径 |
| `write_internal_skill(role_path, skill)` | 是 | `role_path` 参数 | 保持显式路径 |
| `write_session_summary(role_path, summary)` | 是 | `role_path` 参数 | 保持显式路径 |
| `summarize_and_write(role_path, target, source_text)` | 是 | `role_path` 参数 | 保持显式路径 |
| `upsert_markdown_index_entry(index_path, ...)` | 是 | 调用方传入文件路径 | 不解析角色 |
| `append_unique_project_memory(memory_path, entries)` | 是 | 调用方传入文件路径 | 不解析角色 |

实现前必须用搜索确认没有剩余 `get_current_role_state()` 调用。若发现新的写入入口，必须加入本清单并明确目标角色来源。

### `skills/roleme/tools/role_ops.py`

如果该文件是打包后的同步副本，应与 `tools/role_ops.py` 保持一致。若项目已有构建脚本负责同步，应优先通过构建流程生成；否则需要同步修改。

### 文档和打包模板

需要同步移除或改写：

- `skills/roleme/SKILL.md`
- `skills/roleme/references/usage.md`
- `bundle/SKILL.template.md`
- `bundle/references/usage.md`

需要删除的旧说法包括：

- 当前角色以 `ROLEME_HOME/.current-role.json` 为准
- 自然语言归档只能写当前角色
- 当前角色由 `.current-role.json` 记录
- `ROLEME_STATE_HOME` 作为 current role 状态文件位置

新的文档说法应是：

- 加载角色后，当前会话持有角色上下文。
- 自然语言归档写入当前会话已加载的角色。
- 写入工具必须显式获得 role identity。
- 如果当前会话没有加载角色，应先执行 `/roleMe <角色名>`。

### 测试

需要更新 `tests/test_role_ops.py`：

- 删除 `get_current_role_state` 相关导入。
- 删除 current state 持久化测试。
- 删除 role home 不可写时 fallback 到 temp state home 的测试。
- 新增加载不写 `.current-role.json` 的测试。
- 新增归档 API 使用 `plan.role_name` 的测试。
- 新增归档 API 使用显式 `role_name` 参数的测试。
- 新增缺少 role identity 时报错的测试。
- 新增显式 `role_name` 与 `plan.role_name` 冲突时报错的测试。
- 新增旧 `.current-role.json` 存在时不会被读取、覆盖或删除的测试。
- 新增 `/roleMe current` 文档/命令语义不再读取 current 文件的测试；若项目没有命令解析层，则仅做文档测试。

需要更新 `tests/test_repo_scripts.py`：

- 不再断言打包文档包含 `.current-role.json`。
- 增加断言：打包文档包含会话绑定角色或显式 role identity 的说明。

## 测试用例草案

### 加载不写 current 文件

```python
def test_load_role_bundle_does_not_write_current_role_state(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")

    bundle = load_role_bundle("self")

    assert bundle.role_name == "self"
    assert not (tmp_role_home / ".current-role.json").exists()
```

### 加载不读取或覆盖旧 current 文件

```python
def test_load_role_bundle_ignores_existing_current_role_state(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    legacy_state = tmp_role_home / ".current-role.json"
    legacy_state.write_text(
        '{"roleName": "legacy", "rolePath": "/tmp/legacy", "loadedAt": "2026-04-15T11:30:00+08:00"}\n',
        encoding="utf-8",
    )

    bundle = load_role_bundle("self")

    assert bundle.role_name == "self"
    assert legacy_state.read_text(encoding="utf-8") == (
        '{"roleName": "legacy", "rolePath": "/tmp/legacy", "loadedAt": "2026-04-15T11:30:00+08:00"}\n'
    )
```

### query context 加载不写 current 文件

```python
def test_load_query_context_bundle_does_not_write_current_role_state(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")

    bundle = load_query_context_bundle("self", query="帮我总结成通用的工作方式")

    assert bundle.role_name == "self"
    assert not (tmp_role_home / ".current-role.json").exists()
```

### workflow 归档使用 plan.role_name

```python
def test_archive_general_workflow_uses_plan_role_name_without_current_state(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    plan = parse_workflow_archive_response({
        "kind": "general",
        "role_name": "self",
        "workflow_slug": "general-collaboration",
        "workflow_title": "通用协作工作流",
        "workflow_summary": "适合需要先设计再执行的任务",
        "workflow_applies_to": "当用户需要先对齐工作方式、再进入执行时使用",
        "workflow_keywords": ["协作", "设计", "执行"],
        "workflow_doc_markdown": "# 通用协作工作流\n\n先澄清场景，再开始执行。\n",
        "context_summary_markdown": "",
        "user_rules": [],
        "memory_summary": [],
        "project_memory": [],
    })

    result = archive_general_workflow(plan)

    assert result.role_name == "self"
    assert (role_path / "brain" / "workflows" / "general-collaboration.md").exists()
```

### project workflow 归档使用 plan.role_name

```python
def test_archive_project_workflow_uses_plan_role_name_without_current_state(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    plan = parse_workflow_archive_response({
        "kind": "project",
        "role_name": "self",
        "project_title": "roleMe",
        "project_slug": "roleme",
        "workflow_slug": "requirements",
        "workflow_title": "roleMe 项目工作流",
        "workflow_summary": "用于把模糊需求整理成可规划输入",
        "workflow_applies_to": "当用户想梳理需求、澄清范围、整理用户故事时使用",
        "workflow_keywords": ["需求", "requirement", "scope"],
        "workflow_doc_markdown": "# roleMe 项目工作流\n\n先确认角色边界，再设计能力。\n",
        "context_summary_markdown": "# roleMe\n\n该项目聚焦角色包与工作流沉淀。\n",
        "user_rules": [],
        "memory_summary": [],
        "project_memory": ["先确认角色边界，再设计能力"],
    })

    result = archive_project_workflow(plan)

    assert result.role_name == "self"
    assert (role_path / "projects" / "roleme" / "workflows" / "requirements.md").exists()
```

### workflow 归档缺少 role_name 时报错

```python
def test_archive_general_workflow_requires_role_name(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    plan = parse_workflow_archive_response({
        "kind": "general",
        "workflow_slug": "general-collaboration",
        "workflow_title": "通用协作工作流",
        "workflow_summary": "适合需要先设计再执行的任务",
        "workflow_applies_to": "当用户需要先对齐工作方式、再进入执行时使用",
        "workflow_keywords": ["协作", "设计", "执行"],
        "workflow_doc_markdown": "# 通用协作工作流\n\n先澄清场景，再开始执行。\n",
        "context_summary_markdown": "",
        "user_rules": [],
        "memory_summary": [],
        "project_memory": [],
    })

    with pytest.raises(ValueError, match="role_name"):
        archive_general_workflow(plan)
```

### project workflow 缺少 role_name 时报错

```python
def test_archive_project_workflow_requires_role_name(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    plan = parse_workflow_archive_response({
        "kind": "project",
        "project_title": "roleMe",
        "project_slug": "roleme",
        "workflow_slug": "requirements",
        "workflow_title": "roleMe 项目工作流",
        "workflow_summary": "用于把模糊需求整理成可规划输入",
        "workflow_applies_to": "当用户想梳理需求、澄清范围、整理用户故事时使用",
        "workflow_keywords": ["需求", "requirement", "scope"],
        "workflow_doc_markdown": "# roleMe 项目工作流\n\n先确认角色边界，再设计能力。\n",
        "context_summary_markdown": "# roleMe\n\n该项目聚焦角色包与工作流沉淀。\n",
        "user_rules": [],
        "memory_summary": [],
        "project_memory": [],
    })

    with pytest.raises(ValueError, match="role_name"):
        archive_project_workflow(plan)
```

### 显式 role_name 冲突时报错

```python
def test_archive_general_workflow_rejects_conflicting_role_names(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    initialize_role("other", skill_version="0.1.0")
    plan = parse_workflow_archive_response({
        "kind": "general",
        "role_name": "self",
        "workflow_slug": "general-collaboration",
        "workflow_title": "通用协作工作流",
        "workflow_summary": "适合需要先设计再执行的任务",
        "workflow_applies_to": "当用户需要先对齐工作方式、再进入执行时使用",
        "workflow_keywords": ["协作", "设计", "执行"],
        "workflow_doc_markdown": "# 通用协作工作流\n\n先澄清场景，再开始执行。\n",
        "context_summary_markdown": "",
        "user_rules": [],
        "memory_summary": [],
        "project_memory": [],
    })

    with pytest.raises(ValueError, match="conflicts"):
        archive_general_workflow(plan, role_name="other")
```

### project workflow 显式 role_name 冲突时报错

```python
def test_archive_project_workflow_rejects_conflicting_role_names(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    initialize_role("other", skill_version="0.1.0")
    plan = parse_workflow_archive_response({
        "kind": "project",
        "role_name": "self",
        "project_title": "roleMe",
        "project_slug": "roleme",
        "workflow_slug": "requirements",
        "workflow_title": "roleMe 项目工作流",
        "workflow_summary": "用于把模糊需求整理成可规划输入",
        "workflow_applies_to": "当用户想梳理需求、澄清范围、整理用户故事时使用",
        "workflow_keywords": ["需求", "requirement", "scope"],
        "workflow_doc_markdown": "# roleMe 项目工作流\n\n先确认角色边界，再设计能力。\n",
        "context_summary_markdown": "# roleMe\n\n该项目聚焦角色包与工作流沉淀。\n",
        "user_rules": [],
        "memory_summary": [],
        "project_memory": [],
    })

    with pytest.raises(ValueError, match="conflicts"):
        archive_project_workflow(plan, role_name="other")
```

## 迁移策略

这是 breaking change。

迁移原则：

- 不做兼容 fallback。
- 不读取旧 `.current-role.json`。
- 不主动删除旧 `.current-role.json`。
- 所有写入路径必须显式获得 role identity。
- 老脚本如果依赖“先 load，再 archive 不带角色名”的流程，需要改为传入 `role_name`。

旧文件处理：

用户本地已有的 `.current-role.json` 可以保留在磁盘上，但新版本不会读取它。后续如需清理，可由用户手动删除，或另起独立清理任务。

## 风险与缓解

### 风险：自然语言归档缺少 role identity

如果上层 skill 只生成归档内容，没有把当前会话角色写入 plan，工具层会拒绝写入。

缓解：

- 更新 `SKILL.md` 和 `usage.md`，明确自然语言归档必须使用当前会话加载的角色。
- 在 `/roleMe <角色名>` 加载回执和会话摘要中保留 `loaded_role_name` / `loaded_role_path`。
- 增加缺少 role identity 的测试。

### 风险：旧文档重新引入 current 语义

`bundle/` 和 `skills/roleme/` 都有文档副本，容易只改一处。

缓解：

- 更新 repo script 测试，断言打包文档不再包含 `.current-role.json`。
- 增加断言，确认文档包含“会话加载角色”或“显式 role identity”的新语义。

### 风险：并发写同一个角色仍可能冲突

本设计解决的是“不同窗口加载不同角色时串写”的问题。如果多个窗口都写同一个角色包，同一文件仍可能出现最后写入覆盖或追加顺序竞争。

缓解：

- 保持当前原子写文件策略。
- 对 append 类写入继续使用去重逻辑。
- 文件级锁不是本次范围，可作为后续独立设计。

### 风险：`/roleMe current` 用户预期变化

移除全局 current 后，`/roleMe current` 不再有确定来源。

缓解：

- 文档移除该命令。
- 如代码层仍保留命令解析，应返回固定不支持提示，且不得读取 `.current-role.json`。

## 验收标准

- `load_role_bundle()` 不创建 `.current-role.json`。
- `load_query_context_bundle()` 不创建 `.current-role.json`。
- `archive_general_workflow()` 不调用 `get_current_role_state()`。
- `archive_project_workflow()` 不调用 `get_current_role_state()`。
- 缺少 role identity 的归档调用失败且不写文件。
- role identity 冲突的归档调用失败且不写文件。
- 已存在的旧 `.current-role.json` 不会被读取、覆盖或删除。
- `/roleMe current` 从文档命令列表移除；如果仍有解析路径，则返回固定不支持提示。
- 文档中不再出现 `.current-role.json` 作为当前角色来源。
- 打包产物文档与 skill 源文档语义一致。
- 现有角色加载、项目 bootstrap、workflow summary preload、Graph archive 相关测试继续通过。

## 后续工作

实现通过后，可以另起设计处理两个并发增强：

- 同一角色多窗口写入时的文件级锁。
- 会话运行时如何显式暴露当前加载角色，用于 `/roleMe current` 这类非核心诊断能力。
