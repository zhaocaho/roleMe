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

## 当前架构约束

当前实现已经有以下特征：

- `memory/USER.md` 和 `memory/MEMORY.md` 适合存 bullet 型稳定偏好和长期结论
- `brain/index.md` 与 `brain/topics/*` 适合存可渐进检索的主题文档
- `projects/index.md` 与 `projects/<project-name>/*` 适合存项目级上下文
- 当前项目发现主要从 `projects/index.md` 指向 `context.md`
- 当前并没有“workflow 归档”专用的数据结构或工具入口

这意味着新能力不应把整篇 workflow 正文塞进 `USER.md` 或 `MEMORY.md`，而应：

- 让正文进入 `brain/` 或 `projects/`
- 让 `memory/` 只存提升后的规则和结论
- 让索引仍然承担“可发现性入口”的职责

## 归档类型与目标文件

### 一、项目级 workflow

当用户意图是“总结这个项目的工作方式”时，默认写入当前角色下：

```text
projects/<project-name>/
  workflow.md
  context.md
  memory.md
```

并确保 `projects/index.md` 中存在该项目入口。

#### 文件职责

- `projects/<project-name>/workflow.md`
  作为该项目 workflow 的主文档，保存完整正文
- `projects/<project-name>/context.md`
  保存项目上下文摘要、适用场景，以及指向 `workflow.md` 的入口
- `projects/<project-name>/memory.md`
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

## 项目名推断规则

当触发的是项目级归档时，项目名按以下优先级推断：

1. 用户在当轮消息里显式给出项目名
2. 当前工作区或仓库名
3. 当前角色下如果仅存在一个项目，则复用该项目名
4. 若仍无法判断，才允许补一句很短的追问

这条规则的目标是让“这个项目”在大多数真实会话中都能自动落到正确项目，而不是频繁打断用户。

## 结构化归档契约

为了避免模型只输出普通总结文本，归档前需要先产出一个结构化结果，再交给工具层落盘。

建议引入统一的归档结构：

```json
{
  "kind": "general",
  "project_name": null,
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
- `project_name` 必填
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

- `WorkflowArchiveKind`
  - `project`
  - `general`
- `WorkflowArchivePlan`
  - `kind`
  - `role_name`
  - `project_name`
  - `workflow_title`
  - `workflow_doc_markdown`
  - `context_summary_markdown`
  - `user_rules`
  - `memory_summary`
  - `project_memory`
- `WorkflowArchiveResult`
  - `role_name`
  - `project_name`
  - `written_paths`

### 新增函数

建议新增以下确定性函数：

- `resolve_current_project_name(...)`
  - 推断当前项目名
- `archive_general_workflow(...)`
  - 写入 `brain/topics/general-workflow.md`
  - 更新 `brain/index.md`
  - 将规则和摘要提升到 `USER.md` / `MEMORY.md`
- `archive_project_workflow(...)`
  - 写入 `projects/<project>/workflow.md`
  - 更新 `projects/<project>/context.md`
  - 追加 `projects/<project>/memory.md`
  - 保证 `projects/index.md` 可发现
- `upsert_markdown_index_entry(...)`
  - 负责去重更新 `brain/index.md` 和 `projects/index.md`
- `write_or_merge_workflow_doc(...)`
  - 负责主文档写入
- `append_unique_project_memory(...)`
  - 负责项目级 bullet 去重追加

### 与现有工具的关系

- `memory/USER.md`、`memory/MEMORY.md` 继续复用 `tools/memory.py`
- `write_memory()` 和 `summarize_and_write()` 继续负责 bullet 型写入
- workflow 主文档的写入逻辑放在 `tools/role_ops.py`
- `skill/` 镜像目录中的同名工具也需要同步更新

这样既不破坏现有分层，也避免把整篇文档误塞进 `memory.py`

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

- `projects/index.md` 继续指向 `projects/<project-name>/context.md`
- `projects/<project-name>/context.md` 中显式链接 `workflow.md`
- 路由器仍保持“先索引，再正文”的机制

这样做的原因是：

- 最小化对 `context_router.py` 的改动
- 保持现有项目索引结构不失效
- 让 `workflow.md` 通过 `context.md` 成为可继续发现的下一层内容

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
- 主文档覆盖前必须先读取旧内容进行整合

## 交互流程

### 项目级归档流程

1. 识别用户意图为 `project_workflow`
2. 确认当前角色已加载
3. 解析项目名
4. 读取当前项目已有的 `context.md`、`workflow.md`、`memory.md`
5. 结合当前对话产出 `WorkflowArchivePlan`
6. 写入主文档、上下文摘要、项目 memory、项目索引
7. 回复用户最终写入路径

### 通用归档流程

1. 识别用户意图为 `general_workflow`
2. 确认当前角色已加载
3. 读取已有 `brain/topics/general-workflow.md`、`brain/index.md`、`USER.md`、`MEMORY.md`
4. 结合当前对话产出 `WorkflowArchivePlan`
5. 写入主文档、更新索引、提升规则与摘要
6. 回复用户最终写入路径

## 示例

### 示例一：项目级

用户说：

```text
帮我总结这个项目的工作方式
```

系统行为：

- 将意图判定为项目级归档
- 推断项目名，例如 `roleMe`
- 生成并写入：
  - `projects/roleMe/workflow.md`
  - `projects/roleMe/context.md`
  - `projects/roleMe/memory.md`
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
- `test_archive_requires_loaded_role_context`
- `test_project_name_resolution_prefers_explicit_then_workspace_then_existing_project`
- `test_context_router_can_discover_project_workflow_from_context_link`

### 测试重点

- 角色未加载时不会误写
- 项目名推断顺序符合预期
- 主文档为整合覆盖而非盲目追加
- `USER.md`、`MEMORY.md`、项目 `memory.md` 会去重
- 索引文件不会插入重复条目
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
