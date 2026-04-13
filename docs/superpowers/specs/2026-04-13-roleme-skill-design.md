# roleMe Skill 设计文档

日期：2026-04-13
状态：已确认，待进入规划

## 概述

`roleMe` 是一个可复用的角色系统，用来初始化、加载、切换、优化和导出“数字分身”角色包。每个角色都存放在 `~/.roleMe/<角色名>/` 下，并且可以作为一个可移植目录，在不同机器或不同用户之间直接复制使用。

整个系统分为两层：

- 运行时层：`roleMe` skill，负责在对话过程中加载并操作角色包
- 构建层：当前仓库，负责维护模板、脚本、参考资料以及带版本号的 skill 产物

目标使用体验如下：

- `/roleMe` 默认加载 `self`
- `/roleMe <角色名>` 加载指定角色
- 如果角色不存在，skill 通过引导式对话完成初始化
- 一旦加载完成，当前会话后续都以该角色继续，直到用户明确切换或退出

## 目标

- 让角色包以纯文件形式存在，便于分发、检查和编辑
- 支持直接复制角色目录后即可使用，不依赖原作者环境
- 通过渐进式披露控制常驻上下文体积
- 将稳定身份、记忆、知识和项目叠加层解耦
- 支持后续 skill 版本化构建和 schema 迁移
- 让初始化在一次对话中完成一个可用角色的首次定义

## 非目标

- 不在 v1 中实现宿主级全局人格覆盖
- 不在 v1 中提供自动删除角色能力
- 不在 v1 中实现超出文件式索引、摘要和提升之外的完整自治记忆检索系统
- 不在 v1 中实现角色级云同步

## 核心概念

### 角色包

角色包是 `~/.roleMe/<角色名>/` 下的一个目录，包含加载该角色所需的全部文件。

### 入口文件

`AGENT.md` 是面向大模型的入口文件，它定义：

- 哪些文件需要常驻加载
- 哪些文件应按需加载
- 如何发现并使用项目叠加层
- 在任务执行中如何路由记忆与知识

### 运行时元数据

`role.json` 是面向工具和脚本的清单文件，用来定义 schema 与兼容性元数据，便于 skill 和脚本安全地校验、升级和迁移角色包。

## 角色包目录结构

```text
~/.roleMe/
  self/
    AGENT.md
    role.json
    self-model/
      identity.md
      communication-style.md
      decision-rules.md
      disclosure-layers.md
    brain/
      index.md
      topics/
    memory/
      USER.md
      MEMORY.md
      episodes/
    projects/
      index.md
      <project-name>/
        overlay.md
        context.md
        memory.md
  <other-role>/
    ...
```

## 加载契约

### 默认解析规则

- `/roleMe`
  - 若 `~/.roleMe/self` 存在，则直接加载
  - 否则初始化 `self`
- `/roleMe <角色名>`
  - 若 `~/.roleMe/<角色名>` 存在，则直接加载
  - 否则初始化该角色

### 会话激活模型

角色激活是“当前对话级”的：

- skill 读取 `AGENT.md` 和常驻加载文件
- skill 在当前对话内部生成一份角色激活摘要
- 后续轮次默认继续沿用该角色，直到用户显式切换或退出

这种设计避免了对宿主级全局人格状态的强依赖，同时保留了“加载一次，后续都像本人一样对话”的体验。

## 渐进式披露模型

### 常驻加载层

角色激活时默认加载并持续生效的文件：

- `self-model/identity.md`
- `self-model/communication-style.md`
- `self-model/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

### 按需加载层

仅在任务需要时再读取的文件：

- `brain/index.md`
- `brain/topics/*`
- `projects/index.md`
- `projects/<project-name>/*`
- `memory/episodes/*`

### 披露规则

`self-model/disclosure-layers.md` 用来定义哪些信息属于默认层、条件层和深入层，确保角色既可用又不会让上下文膨胀。

## 初始化流程

当角色目录不存在时，skill 进入 `init` 模式，并通过一轮引导式建模对话完成角色初始化。

### 初始化原则

- 初始化应在一次对话中产出一个可用角色
- 初始化结果必须写成结构化文件，而不是单一的大 prompt
- 用户可以在正式落盘前修订任意一个部分
- 对话中的中间结果可以暂存，但仅在用户确认后写入角色包

### 初始化阶段

1. 身份定义采集
2. 沟通风格采集
3. 决策规则采集
4. 大脑与知识采集
5. 记忆种子采集
6. 角色摘要预览与定向修订
7. 正式写入角色包
8. 立即激活该角色

### 初始化输出

首次初始化必须至少产出：

- `AGENT.md`
- 完整的 `self-model/`
- `brain/index.md`
- `memory/USER.md`
- `memory/MEMORY.md`
- `projects/index.md`
- `role.json`

## 记忆设计

记忆模型借鉴 Hermes Agent 对“稳定人格、用户记忆、持久摘要”的分层思路，并将其适配为可移植角色包结构。

参考资料：

- https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/
- https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files/
- https://hermes-agent.nousresearch.com/docs/user-guide/features/personality/

### 记忆分层

#### `memory/USER.md`

用于存放稳定偏好和长期约定，例如：

- 语言偏好
- 回答结构偏好
- 协作规则
- 重复出现的工作方式偏好

#### `memory/MEMORY.md`

用于存放高价值、压缩后的持久记忆，例如：

- 适合跨会话保留的稳定事实
- 对已学习偏好的简要摘要
- 记忆主题索引
- 指向更深层文件的入口

#### `memory/episodes/`

用于存放默认不常驻加载的情节型或细节型记忆，例如：

- 会话级笔记
- 较长的上下文记录
- 在摘要前保留的详细证据

### v1 记忆操作

第一版应支持：

- 追加新的 episodic memory
- 将高价值记忆摘要并提升到 `MEMORY.md`
- 对重复条目进行去重
- 检索时优先查摘要层，再按需读取情节层
- 将常驻记忆控制在固定预算内

### Hermes 对齐后的核心实现思路

这一部分不应简单照搬 Hermes 的文件名或工具表面，而应借鉴它的核心机制：

- 持久记忆应有明确的容量边界
- 常驻记忆应在会话开始时注入，并采用“冻结快照”策略
- 记忆写入应立即持久化，但不强制刷新当前会话的常驻 prompt
- 写入前必须执行安全扫描
- 记忆系统应区分“总是在 prompt 中的关键记忆”和“按需检索的深层记忆”

对应到 `roleMe`，第一版建议采用“核心记忆引擎优先”的结构。Hermes 值得借鉴的是机制和边界，不是它表面的脚本形态或命令拆分。

### 核心记忆引擎

应在当前仓库中实现一个统一的 memory engine，作为所有记忆脚本和 skill 调用的底座。这个引擎至少负责：

- `memory/USER.md` 与 `memory/MEMORY.md` 的读写
- 去重与唯一匹配替换
- 容量限制与压缩策略
- 安全扫描
- 会话激活时的冻结快照构建
- `memory/episodes/` 的检索与摘要提升

建议的模块边界如下：

```text
lib/roleme/
  memory/
    engine.py
    stores.py
    security.py
    snapshot.py
    retrieval.py
```

其中：

- `engine.py` 提供统一入口，协调各子模块
- `stores.py` 负责 `USER.md`、`MEMORY.md`、`episodes/` 的存取规则
- `security.py` 负责 prompt injection、不可见字符、角色覆盖型指令等扫描
- `snapshot.py` 负责构建“当前会话注入用”的冻结记忆块
- `retrieval.py` 负责摘要优先、情节层回退的检索逻辑

### 可选入口层

在核心引擎之上，可以按需提供少量独立入口，但它们不是架构中心。它们只在以下场景下才有必要存在：

- skill 运行时需要进程级调用入口
- 构建、校验、测试需要命令行入口
- 某些操作适合被单独复用

如果没有这些需求，功能应直接落在 `lib/roleme/memory/` 中，由 skill 运行时直接调用，而不是人为拆成一组脚本。

若确实需要命令行入口，建议仅保留少量薄封装，例如：

- `scripts/memory/append_memory.py`
  - 向 `memory/episodes/` 追加一条新的情节型记忆
- `scripts/memory/retrieve_memory.py`
  - 优先读取 `MEMORY.md`，不足时回退到 `memory/episodes/`
- `scripts/memory/summarize_memory.py`
  - 将 episodic memory 压缩成候选摘要
- `scripts/memory/promote_memory.py`
  - 将高价值候选摘要提升到 `MEMORY.md`
- `scripts/memory/compact_memory.py`
  - 控制 `MEMORY.md` 和 `USER.md` 的体积
- `scripts/memory/validate_memory.py`
  - 校验 `memory/` 目录结构与内容

这些入口只是 `roleMe` 自己的工程化选择，不是 Hermes 仓库中的现成脚本列表，也不是第一版必须全部存在的交付物。

### 冻结快照规则

为了贴近 Hermes 的可预测行为，`roleMe` 的常驻记忆加载规则应明确为：

- 角色激活时读取 `USER.md` 与 `MEMORY.md`
- 生成当前会话使用的“冻结快照”
- 本会话中新增或修改的记忆应立即持久化到角色目录
- 但默认不自动刷新当前会话的常驻记忆块
- 若用户显式执行重新加载或切换角色，则重新构建快照

这个规则可以降低提示词漂移，保证会话中的角色行为更加稳定。

### 记忆安全

由于常驻记忆会直接进入后续提示词，在将内容提升到常驻文件前，系统应执行基础的 prompt injection 与指令冲突扫描。

## 知识设计

`brain/` 是角色的知识储备层。

### `brain/index.md`

这个文件是索引，不是知识堆积区。它应当：

- 概括主要知识领域
- 链接到主题文件或外部参考资料
- 帮助 skill 判断是否需要继续加载更深层资料

### 主题文件

详细知识应放在 `brain/topics/` 中，或以引用文档的形式存在。角色包需要同时支持本地文件和受控外链。

## 项目叠加层设计

`projects/` 让同一个角色在不同工作上下文中具备不同表现，而不改变其基础身份。

每个项目叠加层可以包含：

- `overlay.md`：项目特定的角色规则调整
- `context.md`：项目事实与约束
- `memory.md`：项目特定记忆

项目叠加层会调整基础角色，但不会替换基础角色。

## 命令面

运行时 skill 的第一版应支持以下命令：

- `/roleMe`
- `/roleMe <角色名>`
- `/roleMe list`
- `/roleMe current`
- `/roleMe optimize [角色名]`
- `/roleMe export [角色名]`
- `/roleMe doctor [角色名]`

### 范围说明

- 为降低误操作风险，v1 故意不提供删除能力
- `optimize` 主要负责记忆压缩、索引清理和 prompt 预算卫生
- `doctor` 主要负责 schema 校验、缺失文件检查和迁移建议

## 版本与兼容性

需要明确区分三个版本概念：

- `skillVersion`：`roleMe` skill 自身的版本
- `schemaVersion`：角色包结构契约的版本
- `roleVersion`：某个具体角色内容的版本

### `role.json`

每个角色包都必须包含一个类似如下的机器可读清单：

```json
{
  "roleName": "赵超",
  "schemaVersion": "1.0",
  "roleVersion": "0.1.0",
  "createdBySkillVersion": "0.1.0",
  "compatibleSkillRange": ">=0.1 <1.0",
  "createdAt": "2026-04-13T00:00:00+08:00",
  "updatedAt": "2026-04-13T00:00:00+08:00",
  "defaultLoadProfile": "standard"
}
```

### 兼容性规则

- 兼容的 schema 版本应可直接加载
- 较旧 schema 版本应在可能时由工具自动迁移
- 面对不兼容的未来 schema 版本时，应安全失败并给出明确提示

## 仓库职责

当前仓库是系统源码仓库，不是用户长期角色数据的默认存放位置。

它应该负责：

- 模板
- skill 源码
- 记忆脚本与其他运行时脚本
- 校验与迁移脚本
- 参考资料与示例
- 构建产物

它不应该默认承担个人角色数据仓库的职责。

### 建议源码布局

为了让“仓库开发”和“skill 打包”之间的边界清晰，建议源码层采用类似下面的组织方式：

```text
lib/
  roleme/
    memory/
      engine.py
      stores.py
      security.py
      snapshot.py
      retrieval.py
templates/
scripts/
  build_skill.py
  validate_role.py
  upgrade_role.py
skill/
  SKILL.md
  references/
  agents/
```

其中：

- `lib/roleme/` 负责可复用的核心运行时逻辑
- `templates/` 负责角色初始化时生成的目录与文档模板
- `scripts/` 默认只放构建、校验、升级这类工程脚本
- 若未来确实需要进程级记忆入口，再新增 `scripts/memory/`，并保持薄封装
- `scripts/build_skill.py` 负责把模板、核心模块、references 和 skill 定义复制到打包目录
- `skill/` 负责最终 skill 的源定义，而不是用户角色数据

### 模板需要同步改造的部分

为了让模板真正适配 Hermes 风格的记忆机制，第一版应同步改造以下模板：

- `templates/AGENT.md`
  - 增加“常驻记忆快照在角色激活时生成”的说明
  - 明确本会话写入记忆后默认不会自动刷新常驻块，除非重新加载
- `templates/memory/MEMORY.md`
  - 从纯说明性模板改为“说明区 + 机器可维护条目区”
  - 保留人类可读性，同时为脚本提供稳定编辑边界
- `templates/memory/USER.md`
  - 同样改为“说明区 + 机器可维护条目区”
  - 适合保存稳定偏好、长期约定和持久事实
- `templates/projects/index.md`
  - 明确项目层是按需加载，不应与基础人格层混写
- `templates/self-model/disclosure-layers.md`
  - 明确常驻层、按需层、深层的加载边界，与冻结快照规则保持一致

推荐 `MEMORY.md` 和 `USER.md` 都采用稳定标记块，便于脚本安全更新，例如：

```markdown
# 记忆索引

[说明性文字]

<!-- ROLEME:ENTRIES:START -->
- 条目 A
- 条目 B
<!-- ROLEME:ENTRIES:END -->
```

这样既保留了 Markdown 的可读性，也避免脚本在自由文本中做脆弱替换。

## Skill 产物布局

最终构建出的产物应当是可分发、带版本号的 skill 目录，例如：

```text
dist/roleme-v0.1.0/
  SKILL.md
  agents/openai.yaml
  lib/
    roleme/
  scripts/
  references/
  assets/templates/
```

建议第一批构建脚本包括：

- `scripts/build_skill.py`
- `scripts/validate_role.py`
- `scripts/upgrade_role.py`

### 打包规则

是的，运行时脚本应当在此仓库中创建，然后在构建 skill 时复制进最终产物，而不是在导出阶段临时拼接。

建议 `build_skill.py` 承担以下职责：

- 从仓库内的 `skill/` 复制 `SKILL.md`、`agents/openai.yaml` 和 `references/`
- 从仓库内的 `templates/` 复制角色模板到产物的 `assets/templates/`
- 从仓库内的 `lib/` 复制核心运行时模块到产物的 `lib/`
- 从仓库内的 `scripts/` 复制构建所需或运行时确有必要的入口脚本到产物的 `scripts/`
- 写入 skill 版本号并生成最终 `dist/roleme-vX.Y.Z/`
- 对产物执行一次基础校验，确保关键文件完整

这意味着：

- 角色初始化、记忆处理、校验升级都以源码形式维护在当前仓库
- 核心逻辑应优先沉淀在 `lib/roleme/`，而不是分散在脚本里
- skill 打包只是“复制与封装”，不是重新生成逻辑
- 后续如果升级记忆策略，只需要更新仓库里的核心模块并重新 build skill

## 安全性与可移植性

### 可移植性

- 复制得到的角色目录只要 `schemaVersion` 兼容，就应可直接使用
- 核心文件应避免写入机器相关的绝对路径
- 可以允许外部链接存在，但角色在没有这些链接的情况下仍应保持基本可用

### 安全性

- 角色加载时应将角色文件视作“用户信任来源”，但仍要做结构校验
- 记忆提升为常驻内容前应扫描指令冲突型文本
- 导出时默认只包含角色本地数据，除非用户明确要求附带额外资源

## 成功标准

当满足以下条件时，设计可视为成功：

- 缺失的 `self` 角色可以通过对话初始化并立即使用
- 复制来的角色包可以直接放入 `~/.roleMe/` 并加载，无需手工修改
- 激活后，角色在当前对话中保持稳定
- 常驻加载文件始终保持小而聚焦
- 记忆可以持续增长，而不会把 `AGENT.md` 变成巨型单文件
- 当前仓库可以构建出带版本号的 skill 产物，并支撑后续迁移

## 实现方向

推荐的实现顺序：

1. 最终确定角色包 schema 与 manifest
2. 实现运行时加载与初始化流程
3. 实现基于模板的文件生成
4. 实现 memory optimize 与 doctor 流程
5. 实现 build、validate、upgrade 脚本
6. 增加 export 与兼容性测试

## 本文档已确认的关键决策

- 初始化由对话驱动，并在一次流程中完成角色首次定义
- 不带参数的默认命令解析为 `self`
- 角色数据存放在 `~/.roleMe/`，而不是当前仓库
- 第一版采用渐进式披露，而不是一次性全量加载
- 记忆采用“摘要层 + 情节层”的分层结构，而不是单一平铺文件
