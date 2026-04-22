# roleMe 记忆生命周期与内部能力设计文档

日期：2026-04-22  
状态：待评审  

## 概述

本设计用于把 `ai-digital-avatar` 中值得吸收的机制，转化为 `roleMe` 自身的能力增强。

本次目标不是把 `roleMe` 改造成 AI 数字分身，也不是让 AI 扮演用户。`roleMe` 的核心定位保持不变：

> `roleMe` 是用户角色上下文运行时。它让用户加载某个角色身份，并让 AI 根据该角色的身份、记忆、项目上下文和工作方式理解用户。

`ai-digital-avatar` 对 `roleMe` 的主要启发有四点：

- 会话应该有生命周期
- 新记忆应该先有暂存区
- 用户纠正和协作经验应该有学习闭环
- 能力应该有索引入口，但不必变成重型插件运行时

因此，本设计覆盖五个阶段：

- P1：`memory/inbox` 与 `memory/learnings` 机制
- P2：`doctor` 基础扩展与分阶段健康检查框架
- P3：内部 skills / capability cards
- P4：session finalize / session summary
- P5：workflow router 与 internal skill router 融合

## 背景判断

`ai-digital-avatar` 更偏人本位：它有 `SOUL.md`、workspace lifecycle、显式 skill routes、ontology、session manager 和 self evolution。

`roleMe` 更适合保持“模型本位优先，人本位治理”的混合路线：

- Markdown 面向模型，作为主要上下文存储
- Context Graph 面向治理，作为后台索引、来源、冲突和关系层
- Workflow 面向协作，记录用户怎样做事
- Doctor 面向维护，防止角色包长期熵增

本设计吸收 `ai-digital-avatar` 的机制，但不吸收它的主语：

- 不引入 `SOUL.md`
- 不把 AI 定义成用户的数字分身
- 不做显式 ontology CRUD 作为用户主入口
- 不把内部 skills 做成可执行插件系统

## 目标

- 为新记忆建立保守暂存层，避免一次性污染 `USER.md` 和 `MEMORY.md`
- 为用户纠正、失败经验、确认过的协作方式建立学习候选区
- 扩展 `doctor`，让它能发现角色包的结构漂移、索引失效和内部能力卡问题
- 增加内部 skills / capability cards，让角色包可以沉淀不依赖外部 skill 的私有能力
- 增加 session finalize，将本轮会话输出为可归档摘要和候选记忆
- 扩展 context router，让 workflow 与 internal skill 能在同一套渐进式披露策略下被稳定发现
- 保持 Context Graph 后台治理，不让 graph 替代 Markdown 主存储

## 非目标

- 不实现 AI 数字分身人格
- 不引入 `SOUL.md`
- 不实现脚本型内部插件执行
- 不实现权限系统、依赖安装、外部 skill marketplace
- 不自动把所有 inbox / learning 内容提升到 resident memory
- 不强制用户每轮会话都执行 finalize
- 不实现多技能自动编排引擎
- 不让 internal skill 自动调用外部工具或外部 skill
- 不把 graph 变成用户必须手动维护的主数据结构

## 兼容性与破坏性评估

本设计属于对现有 `roleMe` 架构的增量增强，不应破坏当前已经成立的核心边界：

- `persona/` 仍然是用户角色身份层，不变成 AI 人格层
- `memory/USER.md` 与 `memory/MEMORY.md` 仍然是 resident memory 的主要来源
- `brain/`、`projects/`、`workflows/` 仍然是按需上下文层
- Markdown 仍然是正文权威
- Context Graph 仍然是后台治理层，不替代 Markdown
- `context_router.py` 仍然只负责发现和加载上下文，不负责自动执行多步技能链

### 对现有角色包的影响

已有角色包不应因为缺少新增目录而无法加载。

第一版兼容策略：

- `load_role_bundle()` 不要求旧角色包必须存在 `memory/inbox/`、`memory/learnings/`、`memory/sessions/` 或 `skills/`
- `REQUIRED_FILES` 不加入新增目录，避免破坏旧角色包
- `initialize_role()` 为新角色创建新增目录和索引
- `doctor_role()` 对旧角色包缺少新增目录只给 warning，不放入 `missing_files`
- 后续可由 `upgrade_role.py` 或 doctor repair 显式补齐旧角色包结构

### 对 resident snapshot 的影响

新增层默认不进入 resident snapshot。

保持常驻层不变：

```text
persona/narrative.md
persona/communication-style.md
persona/decision-rules.md
memory/USER.md
memory/MEMORY.md
```

`memory/inbox/`、`memory/learnings/`、`memory/sessions/`、`skills/` 都只能通过按需路由或显式命令进入上下文，避免常驻层膨胀。

Session 召回需要更严格的边界：

- 只有“回顾 / 继续 / 最近 / 上次 / 复盘 / 经验教训 / 提升”类意图才允许查询 `memory/sessions/index.md`
- 普通任务请求、普通 workflow 路由、普通 memory recall 不查询 sessions
- 命中 session index 后，只加载最相关的 session 正文
- session 正文不进入 resident snapshot
- doctor 不走 session recall；它只审计 session index，并在候选治理、提升审查、索引异常或 deep repair 时读取必要 session 正文

### 对 Context Graph 的影响

本设计需要扩展 graph schema，新增 `MemoryCandidate`、`Learning`、`Skill`、`Session` 四类节点。

兼容策略：

- 新 schema 必须向后兼容旧 graph 文件
- 旧 graph 中不存在这些节点时不需要迁移
- 新节点只在对应 Markdown 文件写入成功后再写入
- graph 写入失败不得影响 Markdown 写入
- graph recall 不应把 `MemoryCandidate` 当成稳定 `Memory` 参与普通长期记忆召回
- `Learning` 默认不参与 resident recall，只用于 doctor、提升建议和按需审查
- `Session` 不参与普通 recall；doctor 只能审计 session index 和必要的 session 正文，用于健康检查、候选治理、提升审查和索引修复

### 对现有 workflow 路由的影响

P5 会扩展 router，但不应改变现有 workflow 的优先级。

兼容策略：

- 当前项目 workflow 仍然最高优先级
- 全局 workflow 仍然优先于 internal skill
- internal skill 只在没有 workflow 明确命中时参与
- 同层级候选歧义时继续回退，不强行选择
- graph 不可用时仍回退 Markdown index 路由

### 对工具层的影响

本设计会增加确定性文件写入函数，但不要求重构现有工具边界。

允许新增或扩展：

- `tools/memory.py`：inbox、learnings、session summary 的确定性写入
- `tools/role_ops.py`：初始化、doctor、导出、角色包结构维护
- `tools/context_router.py`：internal skill 的按需发现
- `tools/graph_index.py`：新增节点类型的 schema 检查和索引

不建议在本次实现中拆出复杂 runtime、engine、store 层。只有当单个文件职责明显失控时，再做最小拆分。

## 用户使用场景

### 场景一：用户表达了不确定的新偏好

用户说：

> 以后写设计文档可能还是先给我一版短摘要吧。

系统判断这不是强稳定规则，因为用户用了“可能”。默认写入：

```text
memory/inbox/inbox-<date>-<seq>.md
suggested_target: user
confidence: medium
recurrence: 1
```

后续如果用户多次确认，再建议提升到 `memory/USER.md`。

### 场景二：用户纠正了协作方式

用户说：

> 不要一上来写实现，先出设计文档。

系统判断这是协作方式纠正，写入：

```text
memory/learnings/learning-<date>-<seq>.md
type: correction
applies_to: global
```

如果该 learning 多次出现或用户明确说“以后都这样”，再建议提升到 `memory/USER.md` 或对应 workflow。

### 场景三：用户要求沉淀一个私有能力

用户说：

> 把我做 PRD review 的方法沉淀成一个内部 skill。

系统创建：

```text
skills/prd-review.md
skills/index.md
```

该能力卡描述适用场景、输入、步骤、输出和边界。它不执行脚本，不调用外部工具，只作为角色私有的可路由能力说明。

### 场景四：用户自然触发内部能力

用户说：

> 帮我 review 一下这份 PRD。

如果当前项目没有更匹配的 workflow，router 可命中：

```text
skills/index.md
skills/prd-review.md
```

然后把这张能力卡加入 `context_snapshot`，让模型按用户沉淀的 review 方法工作。

### 场景五：workflow 与 internal skill 同时命中

用户说：

> 开始做这个需求的 PRD。

如果同时存在：

```text
projects/<slug>/workflows/requirements.md
brain/workflows/prd-writing.md
skills/prd-writing.md
```

系统按下面顺序选择：

1. 当前项目 workflow
2. 全局 workflow
3. internal skill

因此第一优先加载项目 workflow。如果当前项目没有匹配 workflow，但全局 workflow 命中，则加载全局 workflow；只有项目和全局 workflow 都没有明确命中时，才加载 internal skill。

原因是 workflow 代表用户已经沉淀的工作推进方式，项目 workflow 又比全局 workflow 更贴近当前上下文；internal skill 更像能力说明，不应覆盖明确的工作流。

### 场景六：结束一轮工作并沉淀会话

用户说：

> 结束本轮，帮我整理一下。

系统生成：

```text
memory/sessions/YYYY-MM-DD-001.md
memory/sessions/index.md
```

内容包括：

- 本轮完成的工作
- 决策
- 产出物
- inbox candidates
- learning candidates
- suggested promotions

默认不自动提升 resident memory，除非用户确认或已有明确规则。

`memory/sessions/index.md` 是 session 的主路由入口，不要求 router 扫描所有 session 正文。

建议格式：

```markdown
# Sessions

## 2026-04-22-001
- file: 2026-04-22-001.md
- started_at: 2026-04-22T09:30:00+08:00
- ended_at: 2026-04-22T11:00:00+08:00
- summary: 讨论 roleMe P1-P5 记忆生命周期、内部能力和路由边界
- keywords: roleMe, inbox, learnings, internal skills, finalize, router
- inbox_candidates: 2
- learning_candidates: 1
- promotions: 3
```

后续只有当 query 属于回顾、继续、最近、复盘、经验教训或提升类意图时，router 才读取该 index 并决定是否加载具体 session 文件。

doctor 不通过 router 召回 session。doctor 只审计该 index，并在候选治理、提升审查、索引异常或 deep repair 时读取必要 session 正文。

### 场景七：doctor 提醒长期未处理候选

用户执行：

```text
/roleMe doctor zhaochao
```

如果某条 inbox 已 pending 超过 14 天，doctor 输出 warning。用户可以选择：

- 提升到 `USER.md`、`MEMORY.md`、project memory 或 workflow
- 继续保留
- 关闭

### 场景八：旧角色包加载

用户加载一个旧角色包：

```text
/roleMe old-role
```

即使该角色包没有 `memory/inbox/`、`memory/learnings/`、`memory/sessions/`、`skills/`，也应正常加载。

`doctor` 可以提示“建议补齐新增结构”，但不能阻断角色加载。

## 总体设计

目标结构如下：

```text
~/.roleMe/<role-name>/
  AGENT.md
  role.json
  persona/
  memory/
    USER.md
    MEMORY.md
    episodes/
    inbox/
      index.md
      <entry-id>.md
    learnings/
      index.md
      <learning-id>.md
    sessions/
      index.md
      YYYY-MM-DD-001.md
  brain/
    index.md
    topics/
    workflows/
    graph/
  projects/
    index.md
    <project-slug>/
      context.md
      overlay.md
      memory.md
      workflows/
  skills/
    index.md
    <skill-slug>.md
```

新增内容分四类：

- `memory/inbox/`：尚未确定是否稳定的新信息
- `memory/learnings/`：用户纠正、错误复盘、确认过的协作规则候选
- `memory/sessions/`：会话过程归档、回顾入口和候选提升来源
- `skills/`：角色私有的声明式能力卡

这些新增层默认都是按需层，不进入 resident snapshot。

## P1：Memory Inbox 与 Learnings

### 设计意图

当前 `roleMe` 已支持将稳定偏好写入 `USER.md`，将长期结论写入 `MEMORY.md`，将细节写入 `episodes/`。

问题是：很多新信息在产生时还不确定是否稳定。如果直接写入 `USER.md` 或 `MEMORY.md`，会污染常驻层；如果只写入 episode，又缺少后续提升路径。

因此新增两个缓冲区：

- `memory/inbox/`：信息候选区
- `memory/learnings/`：协作经验候选区

### Inbox

`inbox` 用于存放还不能判断稳定性的信息。

适合写入：

- 用户临时表达的偏好
- 还没确认是否长期有效的事实
- 一次性任务中出现但可能有复用价值的信息
- 归档分类不确定的内容

不适合写入：

- 已明确是长期偏好的内容，应写入 `USER.md`
- 已明确是长期方法论的内容，应写入 `MEMORY.md`
- 已明确属于项目的内容，应写入 `projects/<slug>/memory.md`

建议文件格式：

```markdown
# <entry-title>

- id: inbox-20260422-001
- status: pending
- source: user_statement
- recurrence: 1
- created_at: 2026-04-22T10:00:00+08:00
- last_seen_at: 2026-04-22T10:00:00+08:00
- suggested_target: user | memory | project:<slug> | workflow:<slug> | skill:<slug> | episode | unknown
- confidence: low | medium | high

## Summary

一句话摘要。

## Evidence

原始来源的简短摘录或描述。

## Promotion Notes

后续提升、关闭或迁移的判断依据。
```

`source`、`confidence` 和 `Promotion Notes` 都属于结构化契约。写入 API 不应丢弃这些字段；doctor 也可以基于这些字段判断候选是否长期未处理、是否具备提升条件。

`memory/inbox/index.md` 只保留轻量索引：

```markdown
# Inbox

## pending
- inbox-20260422-001: <title> -> memory/inbox/inbox-20260422-001.md

## promoted

## closed
```

### Inbox 计数与提升

Inbox 不是稳定记忆，而是“待判断候选”。它也需要计数，但计数含义不同于 learning：

- `recurrence` 表示相同或高度相似的信息再次出现的次数
- `last_seen_at` 表示最近一次出现时间
- 相似判断优先使用规范化后的 `summary + suggested_target`，后续可用 graph 节点或文本相似度辅助

当新信息进入 inbox 时：

1. 先查 `memory/inbox/index.md` 中的 pending 条目
2. 若存在相同 `suggested_target` 且摘要语义接近的条目，则更新原条目的 `recurrence` 和 `last_seen_at`
3. 若不存在相似条目，则创建新的 inbox 条目

Inbox 的提升建议规则：

- `recurrence >= 3` 且 `confidence != low`：doctor 建议提升
- 用户明确说“以后都这样”“这是固定规则”：可立即建议提升
- `suggested_target=user`：建议提升到 `memory/USER.md`
- `suggested_target=memory`：建议提升到 `memory/MEMORY.md`
- `suggested_target=project:<slug>`：建议提升到 `projects/<slug>/memory.md`
- `suggested_target=workflow:<slug>`：建议提升到对应 workflow
- `suggested_target=skill:<slug>`：建议补充到对应 internal skill

提升不是自动执行。默认流程是：

1. doctor 或 finalize 给出 promotion suggestion
2. 用户确认
3. 写入目标文件
4. inbox 条目标记为 `promoted`
5. 若目标是 `USER.md` 或 `MEMORY.md`，提醒重新执行 `/roleMe <角色名>` 刷新 resident snapshot

### Learnings

`learnings` 用于存放“系统应该从交互中学到什么”，但还不应立刻提升为常驻规则。

适合写入：

- 用户纠正：“不要这样做”
- 用户确认：“以后就按这个方式”
- 工具失败后的可复用经验
- workflow 执行后的改进建议
- 多次出现的协作偏好

建议文件格式：

```markdown
# <learning-title>

- id: learning-20260422-001
- type: correction | confirmation | error | workflow | discovery
- status: pending | promoted | closed
- recurrence: 1
- priority: normal | high | critical
- created_at: 2026-04-22T10:00:00+08:00
- last_seen_at: 2026-04-22T10:00:00+08:00
- applies_to: global | project:<slug> | workflow:<slug> | skill:<slug>

## Rule Candidate

候选规则。

## How To Apply

具体应用方式。

## Evidence

为什么产生这条 learning。

## Promotion Target

建议提升到 `memory/USER.md`、`memory/MEMORY.md`、某个 workflow、某个 internal skill，或关闭。
```

`Evidence` 与 `Promotion Target` 也属于结构化契约。重复 learning 命中时应追加 Evidence，并保留明确的提升目标，避免后续 doctor 只能从自由文本中猜测。

提升策略：

- `priority=critical`：允许立即建议提升，但仍需要用户确认
- `recurrence >= 3`：建议提升
- `pending` 超过 30 天：doctor 提醒审查
- 不确定时继续保留 pending

### Learning 计数与提升

Learning 的 `recurrence` 表示同一条协作经验、纠正或失败模式重复出现的次数。

当写入 learning 时：

1. 先按 `type + applies_to + Rule Candidate` 的规范化文本查找 pending 条目
2. 若匹配到已有条目，则递增 `recurrence`，更新 `last_seen_at`，并追加 Evidence
3. 若没有匹配条目，则创建新条目，`recurrence=1`

Learning 的提升目标由 `Promotion Target` 决定：

- 用户稳定偏好：提升到 `memory/USER.md`
- 长期方法论或协作原则：提升到 `memory/MEMORY.md`
- 项目特定经验：提升到 `projects/<slug>/memory.md`
- 工作流步骤或边界变化：提升到对应 workflow 文件
- 能力使用方法：提升到对应 internal skill

提升建议规则：

- `priority=critical`：立即建议提升，但仍需要用户确认
- `recurrence >= 3`：建议提升
- 用户明确说“以后都这样”：建议提升
- `pending` 超过 30 天：doctor 要求审查，用户选择提升、继续观察或关闭

提升执行后：

1. 目标文件写入成功
2. learning 条目标记为 `promoted`
3. graph 增加 `promoted_to` 关系
4. 如果目标是 resident memory，提醒重新加载角色

### 与 Context Graph 的关系

Inbox 和 Learnings 写入 Markdown 后，可以同步写入 Context Graph：

- Inbox 条目对应 `MemoryCandidate` 节点
- Learning 条目对应 `Learning` 节点
- Evidence 节点记录来源

本设计选择扩展 Context Graph schema，而不是把这些新概念塞进现有 `Memory` 或 `Episode` 节点的 metadata。原因是：

- `MemoryCandidate` 与稳定 `Memory` 语义不同，前者是待判断候选，不应被普通记忆召回混用
- `Learning` 与 `Preference` / `Principle` 语义不同，前者是可提升的协作经验候选，不一定长期有效
- `Skill` 是角色私有能力卡，和 `Workflow` 有相近路由方式，但不是流程正文

因此实现时需要同步更新：

- `templates/brain/graph/schema.yaml`
- `skills/roleme/assets/templates/brain/graph/schema.yaml`

新增 node types：

```yaml
- MemoryCandidate
- Learning
- Skill
- Session
```

Graph schema 按实现阶段增量扩展：

- P1：新增 `MemoryCandidate`、`Learning`
- P3：新增 `Skill`
- P4：新增 `Session`

这样 schema、doctor 检查和写入 API 的上线节奏保持一致，避免 P1 提前承担 P3/P4 的未实现能力。

Graph 写入失败时不得影响 Markdown 写入。

Session summary 也应进入 Context Graph，但不能参与普通长期记忆召回。

本设计选择新增 `Session` 节点，而不是只把 session 当作 `Evidence`：

- `Session` 表示一次会话摘要文件，服务回顾、继续、候选治理和提升审查
- `Evidence` 表示某个候选、学习、决策或提升的来源证据
- `Session` 可以通过 `records` 边连接 `MemoryCandidate`、`Learning`、`Decision`
- `Learning`、`MemoryCandidate` 可以通过 `evidenced_by` 边指向对应 session 或 evidence

`Session` 节点不参与普通 `Memory` / `Preference` / `Principle` recall。

Session 正文展开有两条严格入口：

- router 只有在回顾、继续、最近、上次、复盘、经验教训、提升类 query 中才可通过 `memory/sessions/index.md` 展开具体 session
- doctor 默认只审计 `memory/sessions/index.md`；只有 index 显示存在候选、提升建议、索引异常，或用户执行深度 doctor / repair 时，才读取具体 session 正文

doctor 读取 session 的目的仅限健康检查、候选治理、提升审查和索引修复，不参与普通上下文召回。

## P2：Doctor 基础扩展与分阶段健康检查框架

### 设计意图

随着 role package 增加 inbox、learnings、workflows、internal skills 和 graph，长期使用后容易出现：

- 索引指向不存在文件
- workflow index 字段不完整
- graph 节点指向失效路径
- learning 长期 pending
- inbox 长期未处理
- internal skill 缺少必要字段

`doctor` 应从“检查必需文件”扩展为“检查角色包健康度”。

### 检查范围

`doctor_role()` 的检查应按能力阶段增量启用，避免 P2 依赖 P3/P4/P5 尚未实现的结构。

基础检查始终启用：

- required files 是否存在
- workflow index 是否能被解析
- workflow index 的 `file` 是否存在
- Context Graph 是否有损坏 JSONL
- Graph 节点路径是否指向存在的 Markdown 文件

P1 启用 inbox / learnings 检查：

- `memory/inbox/index.md` 中的条目是否指向存在文件
- `memory/learnings/index.md` 中的条目是否指向存在文件
- pending inbox 是否超过 14 天
- pending learning 是否超过 30 天

P3 启用 internal skills 检查：

- internal skills index 是否能被解析
- internal skill 正文是否包含必要字段

P4 启用 sessions 检查：

- `memory/sessions/index.md` 中的条目是否指向存在文件
- sessions index 中是否存在长期未处理的 candidates 或 promotions

新增推荐目录缺失时只给 `optional_structure_missing` 类 warning，不放入 `missing_files`，也不阻断角色加载。只有当对应 index 已存在但解析失败、或 index 指向不存在的正文文件时，doctor 才给具体索引 warning。

### 输出

保持当前 `DoctorReport` 的简单结构：

```python
DoctorReport(
    missing_files=["memory/USER.md"],
    warnings=["memory/learnings/learning-20260422-001.md has been pending for more than 30 days"],
)
```

不在 P2 引入复杂严重等级。warning 文案应足够清晰，方便用户决定是否修复。

## P3：Internal Skills / Capability Cards

### 设计意图

`ai-digital-avatar` 内置了子 skills 和 skill routes，这提供了很好的能力索引体验。

但 `roleMe` 不应把内部 skills 做成外部 skill 的镜像。第一版 internal skill 应保持声明式：

> internal skill = 角色私有、可路由、可归档、可编辑的能力卡。

它不是可执行插件，不拥有工具权限，不安装依赖，不覆盖系统或 developer 规则。

### 目录结构

```text
skills/
  index.md
  code-review.md
  prd-writing.md
```

### Index 格式

```markdown
# Internal Skills

## code-review
- title: 代码评审能力
- file: code-review.md
- applies_to: 当用户要求 review、审查代码、找风险时使用
- keywords: review, 代码评审, 风险, bug
- summary: 按风险优先级输出代码审查意见
```

该格式与 workflow index 保持相似，降低路由器和 doctor 的认知成本。

### Skill 正文格式

```markdown
# 代码评审能力

## Purpose

说明这个能力解决什么问题。

## When To Use

说明适用场景。

## Inputs

需要用户或上下文提供什么。

## Procedure

执行步骤。

## Outputs

输出格式。

## Boundaries

不做什么，遇到歧义怎么处理。

## Related Context

可选：关联 memory、brain、project、workflow。
```

### 使用入口

P3 只定义 internal skill 的存储、写入和 doctor 校验，不定义自动路由。路由融合统一由 P5 负责。

第一版在 P3 范围内只要求支持显式管理场景：

- “查看内部 skill”
- “用 code-review 这个内部 skill”
- “把这个工作方式沉淀成内部 skill”

`InternalSkill.body_markdown` 必须包含这些必要 section，doctor 以正文 Markdown 为校验来源：

- `Purpose`
- `When To Use`
- `Inputs`
- `Procedure`
- `Outputs`
- `Boundaries`

`Related Context` 是可选 section，不作为第一版必要字段。

## P4：Session Finalize / Session Summary

### 设计意图

`ai-digital-avatar` 的 session finalize 有一个重要价值：会话不是无痕结束，而是有沉淀动作。

`roleMe` 应增加轻量 finalize：

- 总结本轮工作
- 记录产出
- 生成 inbox 候选
- 生成 learning 候选
- 提醒需要提升的 resident 规则

### 命令与自然语言

可支持两类入口：

- 显式命令：`/roleMe finalize`
- 自然语言：“结束本轮”、“帮我整理本轮记忆”、“归档这次会话”

Finalize 的内容提炼由模型完成。确定性工具函数只接收结构化 `SessionSummary`，负责写入 session 文件、更新 `memory/sessions/index.md`，并在 Graph 可用时尝试写入 `Session` 节点；工具层不负责推理本轮完成了什么。

### 输出内容

Finalize 应生成一个 session summary 文件。文件名使用日内递增序号，避免同一天多轮 finalize 互相覆盖：

```text
memory/sessions/YYYY-MM-DD-001.md
```

建议格式：

```markdown
# Session Summary - 2026-04-22-001

- session_id: 2026-04-22-001
- date: 2026-04-22
- started_at: 2026-04-22T09:30:00+08:00
- ended_at: 2026-04-22T11:00:00+08:00

## Work Completed

- 本轮完成了什么。

## Decisions

- 形成了哪些决定。

## Artifacts

- 产生或修改了哪些文件。

## Inbox Candidates

- 可能需要后续判断的记忆。

## Learning Candidates

- 可能需要提升为协作规则的经验。

## Suggested Promotions

- 建议提升到 USER / MEMORY / project / workflow / skill 的内容。
```

如果后续需要“每日总览”，可由多个 session summary 汇总生成，但第一版不把多轮会话追加到同一个 `YYYY-MM-DD.md` 文件中。

### 与 Inbox / Learnings 的关系

Finalize 不应自动把所有内容写入 resident memory。

默认行为：

- 明确稳定的内容：可建议写入 `USER.md` / `MEMORY.md`
- 不确定内容：写入 `memory/inbox/`
- 用户纠正或方法论经验：写入 `memory/learnings/`
- 项目相关且明确稳定的内容：写入 `projects/<slug>/memory.md`
- 项目相关但仍不确定的内容：写入全局 `memory/inbox/`，并将 `suggested_target` 写成 `project:<slug>`

如果提升了 resident 层，应提醒用户重新执行 `/roleMe <角色名>`。

## P5：Workflow Router 与 Internal Skill Router 融合

### 设计意图

P3 定义了 internal skills 的声明式能力卡。但如果它们只能被用户显式点名，价值会比较有限。

P5 的目标是在不引入重型自动编排引擎的前提下，让 `context_router.py` 可以把 workflow 与 internal skill 放进同一套上下文发现机制里：

- workflow 继续表示“用户怎么推进一类工作”
- internal skill 表示“角色私有的可复用能力”
- router 只负责发现和加载最相关的上下文，不负责执行多步技能链

### 路由优先级

建议路由优先级如下：

1. 当前项目 workflow
2. 全局 workflow
3. 当前项目 internal skill 覆盖层（后续可选）
4. 全局 internal skill
5. brain / project / episodes 普通上下文发现

第一版只实现第 1、2、4、5 层。项目级 internal skill 覆盖层先保留扩展位，不在本次实现。

### 匹配规则

workflow 与 internal skill 都使用轻量索引条目：

```markdown
## <slug>
- title: <title>
- file: <file.md>
- applies_to: <natural language scenario>
- keywords: <comma separated keywords>
- summary: <one-line summary>
```

因此可以复用相近的确定性打分策略：

- `applies_to` 文本重合度：最高权重
- `keywords` 命中数：中等权重
- `title` 文本重合度：低权重
- `file` 文件名词干：弱信号

候选必须满足：

- 总分达到最低阈值
- 第一名与第二名有足够差距
- 若 workflow 与 internal skill 同时命中，优先 workflow

优先 workflow 的原因是：workflow 通常代表用户已沉淀的工作推进方式，而 internal skill 更像能力说明。对同一个 query，如果已经有明确 workflow，应先遵循流程。

### 渐进式披露边界

命中 workflow 时，默认加载：

- 对应 `workflows/index.md`
- 被选中的 workflow 正文

命中 internal skill 时，默认加载：

- `skills/index.md`
- 被选中的 skill 正文

不默认加载：

- 其他 workflow
- 其他 internal skill
- graph 全量内容
- projects 全量内容
- brain topics 全量内容

如果被选中的 skill 正文通过 `Related Context` 指向 workflow、brain topic 或 project 文件，后续 query 明确需要时再展开。

Session recall 使用独立的确定性入口函数：

```python
is_session_recall_query(query: str) -> bool
```

第一版只允许明显带有回顾、延续或提升意图的 query 查询 `memory/sessions/index.md`。

正例：

- “继续上次的 roleMe 设计”
- “回顾今天做了什么”
- “复盘这轮工作”
- “看看最近有什么 learning 可以提升”

反例：

- “开始实现 inbox”
- “帮我写 PRD”
- “review 这份代码”
- “新增一个 workflow”

普通任务 query 即使命中 workflow 或 internal skill，也不查询 sessions index。只有 `is_session_recall_query()` 返回 true 后，router 才能读取 sessions index，并只加载最相关的 session 正文。

### 歧义处理

P5 应保持保守：

- 同层级多个候选接近时，不自动选择
- workflow 与 internal skill 同时命中时，选 workflow
- query 只有泛泛任务语气但没有真实匹配信号时，不选
- internal skill 缺少必要 section 时，不参与路由，并由 doctor 提醒

### 与 Context Graph 的关系

Internal skill 可同步写入 Context Graph：

- `Skill` 节点记录能力卡
- `Concept` 节点记录适用场景
- `applies_to` 边连接 skill 与 concept
- `evidenced_by` 边连接 skill 与 Markdown 文件

Graph 只辅助治理和未来检索，不作为 P5 的唯一路由来源。P5 第一版仍以 Markdown index 为主。

### 输出形态

`load_query_context_bundle()` 的 `discovered_paths` 应能包含 internal skill 路径，例如：

```text
skills/index.md
skills/code-review.md
```

`context_snapshot` 中应以清晰标题区分：

```markdown
## Discovered Internal Skill: code-review

按风险优先级输出代码审查意见。
```

这样模型能知道这段上下文是“能力卡”，不是用户记忆或项目事实。

## 数据模型与 API 草案

建议新增轻量 dataclass：

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

@dataclass(frozen=True)
class InternalSkill:
    slug: str
    title: str
    applies_to: str
    keywords: list[str]
    summary: str
    body_markdown: str
```

建议新增函数：

```python
write_inbox_entry(role_path: Path, entry: InboxEntry) -> Path
write_learning_entry(role_path: Path, entry: LearningEntry) -> Path
write_session_summary(role_path: Path, summary: SessionSummary) -> Path
write_internal_skill(role_path: Path, skill: InternalSkill) -> Path
is_session_recall_query(query: str) -> bool
```

这些函数只做确定性文件写入和索引更新。

## 初始化与迁移

新角色初始化时应创建：

```text
memory/inbox/index.md
memory/learnings/index.md
memory/sessions/index.md
skills/index.md
```

已有角色加载时不强制迁移。`doctor` 可提示缺失的新增推荐目录，但不要把它们视为硬错误。

建议规则：

- `REQUIRED_FILES` 不立即加入这些新目录
- `doctor` 使用 warnings 提醒
- `initialize_role()` 为新角色创建完整结构
- 后续可提供 `upgrade_role.py` 补齐旧角色结构

## 测试策略

本功能需要先写测试再实现。

P1 测试：

- 初始化新角色会创建 `memory/inbox/index.md` 与 `memory/learnings/index.md`
- 写入 inbox entry 会创建正文文件并更新 index
- 重复 inbox 可增加 recurrence，而不是创建重复候选
- 写入 learning entry 会创建正文文件并更新 index
- 重复 learning 可增加 recurrence，而不是创建重复规则
- P1 graph schema 支持 `MemoryCandidate` 与 `Learning`
- graph 写入失败时 Markdown 仍保留

P2 测试：

- doctor 能发现 required files 缺失
- doctor 能发现 workflow index 指向不存在正文
- doctor 能发现 graph 损坏或 graph 节点路径失效
- doctor 能发现 inbox / learnings index 指向不存在文件
- doctor 能发现 pending inbox 超过 14 天
- doctor 能发现 pending learning 超过 30 天
- 新增推荐目录缺失时 doctor 只输出 warning，不放入 `missing_files`

P3 测试：

- 初始化新角色会创建 `skills/index.md`
- 写入 internal skill 会创建正文文件并更新 index
- P3 graph schema 支持 `Skill`
- doctor 能发现 internal skills index 解析失败
- doctor 能发现 internal skill 缺少必要 section

P4 测试：

- 初始化新角色会创建 `memory/sessions/index.md`
- session summary 会写入 `memory/sessions/YYYY-MM-DD-001.md`
- session summary 会更新 `memory/sessions/index.md`
- 同一天多次 finalize 会生成不同 session 文件，不覆盖已有 session
- P4 graph schema 支持 `Session`
- doctor 能发现 sessions index 指向不存在文件
- doctor 能发现 sessions index 中长期未处理的 candidates 或 promotions
- doctor 不作为 session recall 入口；doctor 默认只审计 `memory/sessions/index.md`
- doctor 只有在 index 显示候选、提升建议、索引异常或 deep repair 时读取必要 session 正文

P5 测试：

- context router 能按 query 命中 internal skill
- workflow 与 internal skill 同时命中时优先 workflow
- internal skill 命中时只加载 index 和被选中的 skill 正文
- `is_session_recall_query()` 能识别回顾、继续、最近、上次、复盘、经验教训、提升类正例
- `is_session_recall_query()` 不把普通任务 query 误判成 session recall
- session recall 只在回顾、继续、最近、复盘、经验教训、提升类意图中查询 sessions index
- 普通任务 query 不查询 sessions index

## 风险与取舍

### 风险一：结构继续膨胀

新增 inbox、learnings、skills、sessions 可能让角色包变复杂。

缓解方式：

- 新层全部按需加载
- resident snapshot 不包含这些目录
- doctor 只提醒，不强制用户维护

### 风险二：internal skills 变成插件系统

如果第一版就支持脚本、依赖和权限，会偏离 `roleMe` 定位。

缓解方式：

- P3 只做声明式能力卡
- 不执行脚本
- 不安装依赖
- 不覆盖外部 skill 机制

### 风险三：learnings 污染 resident memory

如果用户一次纠正就提升到 `USER.md`，会导致常驻层漂移。

缓解方式：

- 默认写入 `memory/learnings/`
- 多次出现或用户明确确认后再建议提升
- 提升 resident 层后提醒重新加载角色

## 推荐实施顺序

1. P1：补 inbox / learnings 目录结构、写入 API、`MemoryCandidate` / `Learning` graph schema，并启用 P1 doctor 检查
2. P2：抽出 doctor 基础健康检查框架，覆盖 required files、workflow index、graph 损坏和新增推荐目录 warning
3. P3：增加 internal skills index、能力卡写入、`Skill` graph schema，并启用 internal skill doctor 校验
4. P4：增加 session summary 写入、finalize 数据结构、`Session` graph schema，并启用 sessions doctor 校验
5. P5：扩展 context router，使 internal skill、workflow 和 session recall 在同一套保守路由策略下工作

这五步可以在同一个实现计划中完成，但每一步都应有独立测试。

## 结论

`roleMe` 可以吸收 `ai-digital-avatar` 的会话闭环、学习候选区和能力索引机制，但不应吸收“AI 数字分身”的主语。

最终定位应保持为：

> 模型本位的角色上下文运行时 + 人本位的记忆治理和能力索引。
