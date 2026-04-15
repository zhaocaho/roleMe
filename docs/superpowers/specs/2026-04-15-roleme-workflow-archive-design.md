# roleMe Workflow Archive 设计文档

日期：2026-04-15  
状态：已确认，可进入实现规划

## 概述

当前 `roleMe` 已经具备三类稳定能力：

- 加载用户角色上下文
- 将稳定偏好和长期结论写入 `memory/`
- 通过 `brain/`、`projects/` 做渐进式发现

但它还缺少一个非常关键的协作闭环：

- 用户在真实协作中跑出了一套工作方式
- 用户自然地说一句“帮我总结这个项目的工作方式”或“帮我总结成通用的工作方式”
- 助手不仅生成一段总结文本，还能直接把这份 workflow 沉淀进当前已加载角色的角色包

这份设计要补上的，就是这个“自然语言触发的 workflow 归档能力”。

目标不是新增一个必须记忆的命令，而是在已加载角色的前提下，让用户继续用自然语言说话，助手自动完成：

- 判断用户想归档的是项目级 workflow 还是通用 workflow
- 基于当前对话和已有角色资产做归纳
- 把结果写到当前角色下正确的文件位置
- 更新索引，让后续渐进式检索能够重新发现这些 workflow

## 目标

- 支持在已加载角色的会话中，用自然语言触发 workflow 归档
- 归档动作只允许写入当前已加载角色，不允许跨角色写入
- 支持两类归档目标：
  - 项目级 workflow
  - 通用 workflow
- 为项目级 workflow 提供明确主文档，而不是把内容散落在 `context.md`、`memory.md` 中
- 为通用 workflow 提供 `brain/` 主文档和 `memory/` 摘要提升
- 保持现有 `persona/`、`memory/`、`brain/`、`projects/` 分层，不引入新的顶层目录
- 保持当前“索引优先、正文按需展开”的渐进式加载方式
- 在自动写入的前提下加入足够的误写防护

## 非目标

- 不新增强制使用的显式命令
- 不支持在一个会话中把 workflow 写入非当前角色
- 不做一个通用的任意文档知识库导入系统
- 不在本次设计中实现跨项目批量归档
- 不在本次设计中引入复杂的自治总结代理或后台任务
- 不在 v1 中解决多会话同时加载不同角色时的隔离冲突；v1 以当前 `ROLEME_HOME` 下最近一次成功加载的角色为准

## 用户体验

### 触发前提

只有在 `/roleMe <角色名>` 已成功加载角色之后，这个能力才生效。

一旦角色已加载，后续相关操作都默认视为“与当前角色相关”，不再允许把 workflow 写到别的角色目录。

### 触发方式

用户不需要显式说“写进角色里”或“存到 roleMe”。

只要自然语言表达明显属于以下两类意图，就直接进入归档流程：

- 项目级归档
  - “帮我总结这个项目的工作方式”
  - “把这个项目里的协作方式沉淀一下”
  - “把我们在这个项目里的 workflow 记下来”
- 通用归档
  - “帮我总结成通用的工作方式”
  - “把刚才这套方法沉淀成通用 workflow”
  - “把我们的协作方式整理成通用规则”

### 默认行为

- 默认直接写入，不要求二次确认
- 写完后明确告诉用户写到了哪些文件
- 如果信息基本够用，则直接归档
- 只有在“项目名无法推断”或“当前内容明显不足以形成非空总结”时，才允许补一句很短的追问
- 写入是立即持久化的，但 resident 层默认不会在当前冻结快照里自动刷新
- 如果本次写入提升了 `USER.md` / `MEMORY.md`，应明确提示用户：如需让新的默认规则立刻成为当前会话底座，需要重新执行 `/roleMe <角色名>`

## 当前架构约束

当前实现已经有以下特征：

- `memory/USER.md` 和 `memory/MEMORY.md` 适合存 bullet 型稳定偏好和长期结论
- `brain/index.md` 与 `brain/topics/*` 适合存可渐进检索的主题文档
- 当前实现里，`projects/index.md` 与 `projects/<project-name>/*` 适合存项目级上下文；本设计会把路径规范收敛为 `projects/<project-slug>/*`
- 当前项目发现主要从 `projects/index.md` 指向 `context.md`
- 当前并没有“workflow 归档”专用的数据结构或工具入口

这意味着新能力不应把整篇 workflow 正文塞进 `USER.md` 或 `MEMORY.md`，而应：

- 让正文进入 `brain/` 或 `projects/`
- 让 `memory/` 只存提升后的规则和结论
- 让索引仍然承担“可发现性入口”的职责

## 当前角色状态模型

“当前已加载角色”不能只靠会话语义理解，必须有确定性的状态来源。

### 状态文件

建议新增：

```text
ROLEME_HOME/.current-role.json
```

内容示例：

```json
{
  "roleName": "self",
  "rolePath": "/Users/example/.roleMe/self",
  "loadedAt": "2026-04-15T11:30:00+08:00"
}
```

### 状态写入与读取规则

- 当 `/roleMe <角色名>` 成功加载角色时，必须更新 `.current-role.json`
- `/roleMe current` 应直接读取这个状态文件
- workflow 归档动作只能通过该状态文件解析当前角色
- 若状态文件不存在、损坏或指向的角色目录无效，则归档动作必须拒绝执行

### v1 边界

为保持实现确定且最小，v1 将 `.current-role.json` 视为当前 `ROLEME_HOME` 下的权威 active-role 指针。

这意味着：

- 同一 `ROLEME_HOME` 下若存在多个并发会话，后一次加载会覆盖前一次 active-role 状态
- 多会话隔离不是本次能力的目标
- 归档安全边界依赖该状态文件，而不是对自然语言上下文做猜测

## 归档类型与目标文件

### 一、项目级 workflow

当用户意图是“总结这个项目的工作方式”时，默认写入当前角色下：

```text
projects/<project-slug>/
  workflow.md
  context.md
  memory.md
```

并确保 `projects/index.md` 中存在该项目入口。

#### 文件职责

- `projects/<project-slug>/workflow.md`
  作为该项目 workflow 的主文档，保存完整正文
- `projects/<project-slug>/context.md`
  保存项目上下文摘要、适用场景，以及指向 `workflow.md` 的入口
- `projects/<project-slug>/memory.md`
  保存项目层面的长期约定、启发式规则、踩坑提醒，使用 bullet 风格
- `projects/index.md`
  继续作为项目入口索引，而不是正文承载文件

### 二、通用 workflow

当用户意图是“总结成通用的工作方式”时，默认写入当前角色下：

```text
brain/topics/general-workflow.md
brain/index.md
memory/USER.md
memory/MEMORY.md
```

#### 文件职责

- `brain/topics/general-workflow.md`
  作为角色层面的通用 workflow 主文档，保存完整正文
- `brain/index.md`
  记录该通用 workflow 的索引入口，保证后续按需发现
- `memory/USER.md`
  存应该长期默认遵守的协作规则
- `memory/MEMORY.md`
  存高价值长期结论和摘要，不存整篇正文

## 项目身份推断规则

当触发的是项目级归档时，系统需要同时得到：

- `project_title`
  供用户阅读的项目名称
- `project_slug`
  供文件系统、索引与路由使用的稳定 ASCII 路径名

### `project_title` 推断顺序

1. 用户在当轮消息里显式给出项目名
2. 当前工作区或仓库名
3. 当前角色下如果仅存在一个项目，则复用该项目标题
4. 若仍无法判断，才允许补一句很短的追问

### `project_slug` 生成规则

1. 优先复用已有项目目录的 slug
2. 否则从 `project_title` 或当前仓库名派生 slug
3. slug 仅允许 `[a-z0-9-]`
4. 空格、下划线和分隔符统一折叠为 `-`
5. 去掉首尾 `-`
6. 若结果为空，则回退为 `project-<short-hash>`

### 为什么必须区分 title 和 slug

- 当前 markdown 路径发现逻辑依赖 ASCII 风格路径
- 工作区名可能带空格、中文或其他不稳定字符
- 索引展示名应保留人类可读性，但路径必须稳定可检索

文件系统路径和索引路径一律使用 `project_slug`，文档标题和索引展示名使用 `project_title`。

## 结构化归档契约

为了避免模型只输出普通总结文本，归档前需要先产出一个结构化结果，再交给工具层落盘。

建议引入统一的归档结构：

```json
{
  "kind": "general",
  "project_title": null,
  "project_slug": null,
  "workflow_title": "通用协作工作流",
  "workflow_doc_markdown": "# 通用协作工作流\n\n...",
  "context_summary_markdown": "## 适用场景\n\n...",
  "user_rules": [
    "先澄清场景，再开始执行",
    "先给结论，再补细节"
  ],
  "memory_summary": [
    "当流程可以复用时，应沉淀为通用工作方式"
  ],
  "project_memory": []
}
```

项目级归档时：

- `kind` 为 `project`
- `project_title` 必填
- `project_slug` 必填
- `project_memory` 可包含项目特有约定与坑点

### 字段职责

- `workflow_doc_markdown`
  最终写入主文档的完整正文
- `context_summary_markdown`
  写入 `context.md` 或作为主文档入口说明的摘要
- `user_rules`
  提升到 `USER.md` 的长期默认规则
- `memory_summary`
  提升到 `MEMORY.md` 的长期结论摘要
- `project_memory`
  提升到项目 `memory.md` 的项目级规则和经验

## 工具层设计

### 新增数据结构

建议在 `tools/role_ops.py` 中新增：

- `CurrentRoleState`
  - `role_name`
  - `role_path`
  - `loaded_at`
- `ProjectIdentity`
  - `title`
  - `slug`
- `WorkflowArchiveKind`
  - `project`
  - `general`
- `WorkflowArchivePlan`
  - `kind`
  - `role_name`
  - `project_title`
  - `project_slug`
  - `workflow_title`
  - `workflow_doc_markdown`
  - `context_summary_markdown`
  - `user_rules`
  - `memory_summary`
  - `project_memory`
- `WorkflowArchiveResult`
  - `role_name`
  - `project_title`
  - `project_slug`
  - `written_paths`

### 新增函数

建议新增以下确定性函数：

- `set_current_role_state(...)`
  - 在成功加载角色时写入 `.current-role.json`
- `get_current_role_state(...)`
  - 读取并校验当前 active-role 状态
- `resolve_current_project_identity(...)`
  - 推断 `project_title` 与 `project_slug`
- `archive_general_workflow(...)`
  - 写入 `brain/topics/general-workflow.md`
  - 更新 `brain/index.md`
  - 将规则和摘要提升到 `USER.md` / `MEMORY.md`
- `archive_project_workflow(...)`
  - 写入 `projects/<project-slug>/workflow.md`
  - 更新 `projects/<project-slug>/context.md`
  - 追加 `projects/<project-slug>/memory.md`
  - 保证 `projects/index.md` 可发现
- `upsert_markdown_index_entry(...)`
  - 负责去重更新 `brain/index.md` 和 `projects/index.md`
- `write_or_merge_workflow_doc(...)`
  - 负责主文档写入
- `append_unique_project_memory(...)`
  - 负责项目级 bullet 去重追加
- `sanitize_archived_markdown(...)`
  - 对 workflow 正文、context 摘要和项目 memory 做安全过滤

### 与现有工具的关系

- `memory/USER.md`、`memory/MEMORY.md` 继续复用 `tools/memory.py`
- `write_memory()` 和 `summarize_and_write()` 继续负责 bullet 型写入
- workflow 主文档的写入逻辑放在 `tools/role_ops.py`
- `skill/` 镜像目录中的同名工具也需要同步更新

这样既不破坏现有分层，也避免把整篇文档误塞进 `memory.py`

## 写入后的生效语义

workflow 归档完成后，不同文件层级的“可生效时间”不同，spec 必须明确这一点。

### 立即持久化

- `workflow.md`
- `context.md`
- 项目 `memory.md`
- `brain/index.md`
- `brain/topics/general-workflow.md`
- `memory/USER.md`
- `memory/MEMORY.md`

以上文件都应在本次归档动作中立即写入磁盘。

### 对当前会话的影响

- 新写入的项目级或通用正文文档，可以在后续显式的 context lookup 中被重新发现
- `USER.md` 和 `MEMORY.md` 属于 resident 层；当前会话的冻结快照默认不会自动刷新

### 用户提示要求

如果本次归档提升了 resident 规则或摘要，助手在回复中必须附带一句明确提示：

- 内容已经写入当前角色
- 如需让新的 resident 规则立刻成为当前会话底座，需要重新执行 `/roleMe <角色名>`

本次设计不新增强制性的 refresh 命令。

## 文档合并策略

### 主文档

主文档采用“整合后覆盖”的策略，而不是盲目追加。

流程如下：

1. 读取已有主文档
2. 结合当前对话与已有文档内容，由模型产出一版整合后的完整正文
3. 工具层将整合后的结果覆盖写回主文档

这样可以避免：

- 文档越写越碎
- 重复段落不断堆积
- 同一 workflow 出现多个彼此冲突的版本

### 索引与摘要

- `brain/index.md` 和 `projects/index.md` 使用去重追加
- `USER.md`、`MEMORY.md`、项目 `memory.md` 使用去重 bullet 追加

## 路由与可发现性

为了让后续查询能重新找到这些 workflow，本次设计需要同时更新索引与文档引用关系。

### 通用 workflow

- `brain/index.md` 中增加 `general-workflow.md` 的入口
- 后续领域相关查询可先命中 `brain/index.md`，再进入 `general-workflow.md`

### 项目级 workflow

- `projects/index.md` 继续指向 `projects/<project-slug>/context.md`
- `projects/<project-slug>/context.md` 中显式链接 `workflow.md`
- `discover_project_paths()` 需要从被选中的 `context.md` 再向下跟进一跳 markdown 链接
- 该一跳跟进只允许读取同一项目目录下的 markdown 文件，避免演变成任意递归遍历
- 当 `context.md` 中存在 `workflow.md` 链接时，路由结果应至少包含：
  - `projects/index.md`
  - `projects/<project-slug>/context.md`
  - `projects/<project-slug>/workflow.md`

这样做的原因是：

- 只增加项目级一跳 link follow，仍然保持最小化改动
- 保持现有项目索引结构不失效
- 让 `workflow.md` 真正进入后续可再发现链路，而不是只被写入但永远不被读取

## 误写防护

由于产品行为是“默认直接写入”，因此防护规则必须明确、保守、确定。

### 必须满足的前提

- 当前角色已加载
- 归档目标只能是当前角色
- 归档文本不能是明显空洞或信息不足的内容

### 防护规则

- 未加载角色时，拒绝执行归档
- 不支持通过自然语言把内容写进非当前角色
- 当项目名无法推断时，才允许短追问
- 当当前对话缺少足够可归纳内容时，拒绝写入，并说明原因
- `USER.md` / `MEMORY.md` 继续沿用现有 unsafe pattern 检查
- `workflow.md`、`context.md`、项目 `memory.md`、`brain/topics/general-workflow.md` 也必须经过安全过滤
- 主文档覆盖前必须先读取旧内容进行整合

### 安全过滤范围

所有自动写入的 markdown 正文都必须经过统一过滤，而不只是 bullet 型 memory。

至少包括：

- prompt injection 语句
- system prompt / developer prompt 相关内容
- 零宽字符与隐藏控制字符
- 会破坏后续加载边界的元指令型文本

如果过滤后正文内容变得过短、失去主要语义，归档动作应拒绝写入，而不是保存一份残缺文档。

## 交互流程

### 项目级归档流程

1. 识别用户意图为 `project_workflow`
2. 通过 `.current-role.json` 确认当前角色已加载
3. 解析 `project_title` 与 `project_slug`
4. 读取当前项目已有的 `context.md`、`workflow.md`、`memory.md`
5. 结合当前对话产出 `WorkflowArchivePlan`
6. 对所有正文与摘要执行安全过滤
7. 写入主文档、上下文摘要、项目 memory、项目索引
8. 回复用户最终写入路径

### 通用归档流程

1. 识别用户意图为 `general_workflow`
2. 通过 `.current-role.json` 确认当前角色已加载
3. 读取已有 `brain/topics/general-workflow.md`、`brain/index.md`、`USER.md`、`MEMORY.md`
4. 结合当前对话产出 `WorkflowArchivePlan`
5. 对主文档与摘要执行安全过滤
6. 写入主文档、更新索引、提升规则与摘要
7. 回复用户最终写入路径，并提示 resident snapshot 不会自动刷新

## 示例

### 示例一：项目级

用户说：

```text
帮我总结这个项目的工作方式
```

系统行为：

- 将意图判定为项目级归档
- 推断 `project_title = roleMe`，`project_slug = roleme`
- 生成并写入：
  - `projects/roleme/workflow.md`
  - `projects/roleme/context.md`
  - `projects/roleme/memory.md`
  - `projects/index.md`

### 示例二：通用

用户说：

```text
帮我总结成通用的工作方式
```

系统行为：

- 将意图判定为通用归档
- 生成并写入：
  - `brain/topics/general-workflow.md`
  - `brain/index.md`
  - `memory/USER.md`
  - `memory/MEMORY.md`

## 测试策略

本能力应按 TDD 实现，至少覆盖以下测试：

- `test_archive_general_workflow_creates_topic_and_updates_indexes`
- `test_archive_general_workflow_promotes_rules_to_user_and_memory`
- `test_archive_project_workflow_creates_project_files_and_index_entry`
- `test_archive_project_workflow_merges_existing_context_without_duplicate_entries`
- `test_set_current_role_state_persists_active_role_pointer`
- `test_archive_requires_current_role_state`
- `test_project_identity_resolution_prefers_explicit_then_workspace_then_existing_project`
- `test_project_slug_uses_ascii_and_hash_fallback_when_needed`
- `test_context_router_can_discover_project_workflow_from_context_link`
- `test_archive_rejects_unsafe_workflow_doc_content`
- `test_archive_reports_reload_requirement_for_resident_updates`

### 测试重点

- 角色未加载时不会误写
- active-role 状态文件是归档动作的唯一角色来源
- 项目标题与 slug 的推断顺序符合预期
- 主文档为整合覆盖而非盲目追加
- `USER.md`、`MEMORY.md`、项目 `memory.md` 会去重
- 索引文件不会插入重复条目
- 所有自动写入 markdown 都经过安全过滤
- resident 更新后会明确提示当前会话不会自动刷新
- `workflow.md` 最终能够通过索引链路被重新发现

## 实现影响面

预计修改范围如下：

- `tools/role_ops.py`
- `skills/roleme/tools/role_ops.py`
- `tools/context_router.py`
- `skills/roleme/tools/context_router.py`
- `skill/SKILL.md`
- `skills/roleme/SKILL.md`
- `skill/references/usage.md`
- `skills/roleme/references/usage.md`
- `tests/test_role_ops.py`
- `tests/test_context_router.py`
- `tests/test_memory.py`
- `tests/integration/test_role_roundtrip.py`

如需把“结构化归档结果”的生成也收敛为统一模板，可以额外补一份 archive planner prompt，但这不是本次设计的前置条件。

## 结论

这项能力的本质，不是新增一个“总结命令”，而是把真实协作中跑出来的方法论，沉淀为当前角色的长期资产。

它应满足四个要求：

- 触发自然，不强迫用户背命令
- 写入确定，不靠模型临场发挥决定路径
- 归档分层清楚，正文、索引、摘要各归其位
- 后续可再发现，让沉淀下来的 workflow 真正参与未来协作

在这个基础上，`roleMe` 才不只是“记住你是谁”，也开始具备“记住你是怎么工作的”这一层能力。
