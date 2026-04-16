# roleMe Intent Workflow Routing 设计文档

日期：2026-04-16  
状态：已确认设计方向，待实现规划

## 概述

当前 `roleMe` 已经具备两层稳定能力：

- 角色 resident snapshot 负责提供稳定底座
- `brain/`、`projects/` 负责按 query 做渐进式发现

但当前项目级 workflow 的使用仍然偏“显式入口”：

- 项目 `context.md` 可以把 `workflow.md` 链出来
- 如果 query 明显像“这个项目怎么协作”，可以发现 `workflow.md`
- 但当用户自然地说“开始需求”“先分析下这个问题”“帮我修这个 bug”时，系统还不能稳定地命中最合适的 workflow

这会带来两个协作摩擦：

- 用户需要把话说得很像在“叫工具”，而不是自然表达任务意图
- 项目 workflow 和通用 workflow 都存在时，缺少明确且稳定的优先级

本设计要补上的，就是“意图驱动的 workflow 路由”：

- 用户只需要自然表达当前想做什么
- 外层路由负责识别当前更像需求、修复还是分析
- 路由优先命中当前项目的 workflow 文件
- 如果项目没有合适的文件，再回退到通用 workflow
- 真正的流程正文只保存在 workflow 文件中，外层只做发现、选择和渐进式披露

一句话概括：workflow 的内容沉淀在 workflow 文件里，context router 只负责把“这次最该看的那份 workflow”带进来。

## 目标

- 支持对自然语言任务意图做宽松识别，而不是依赖固定命令式文案
- 在 query 没有显式说“这个项目”时，也能优先利用当前项目上下文
- 将 workflow 路由优先级固定为：
  - 当前项目的意图型 workflow
  - 当前项目的通用 workflow
  - 全局的意图型 workflow
  - 全局的通用 workflow
- 保持渐进式披露，只拉本次最相关的 workflow，而不是一次性加载所有流程文档
- 让 workflow 文件成为唯一的流程正文来源，不把流程规则复制散落到 `context.md`、`memory.md` 中
- 保持对现有 `workflow.md` 的兼容，不要求已有角色包立即迁移

## 非目标

- 不在本次设计中引入真正的模型推理服务或在线分类器
- 不做复杂的多步骤 workflow 自动执行引擎
- 不在 v1 中支持任意无限扩展的 workflow 类型体系
- 不让 `context.md` 承担流程正文，它仍然只是项目入口与摘要层
- 不要求用户记住新的命令或触发短语

## 用户体验

### 触发方式

用户只需要自然表达任务意图，例如：

- “开始需求”
- “先把这个需求梳理一下”
- “看看这个报错为什么会出现”
- “先分析下这个问题”
- “把这个 bug 修掉”

系统不要求这些话必须命中固定关键词，也不要求用户显式提到：

- “按 workflow 来”
- “这个项目”
- “roleMe 项目”

如果外层能判断出“这是当前项目里的一个需求 / 修复 / 分析类任务”，就应优先使用当前项目 workflow。

### 预期行为

当角色已加载且当前 `cwd` 对应一个已知项目时：

- 用户说“开始需求”
  优先拉 `projects/<slug>/workflow-requirements.md`
- 用户说“帮我分析下这个问题”
  优先拉 `projects/<slug>/workflow-analysis.md`
- 用户说“修一下这个 bug”
  优先拉 `projects/<slug>/workflow-bugfix.md`

如果项目下没有对应文件，则回退：

- `projects/<slug>/workflow.md`
- `brain/topics/general-workflow-<intent>.md`
- `brain/topics/general-workflow.md`

如果 query 与 workflow 类任务无关，则维持当前发现逻辑，不强行注入 workflow。

## 设计原则

### 一、项目大于全局

只要能合理判断这是当前项目内的任务，就优先命中项目 workflow，而不是通用 workflow。

### 二、意图宽松识别，不绑死文案

系统不依赖“开始需求”“修 bug”“分析问题”这些精确短语。

更合理的方式是把 query 识别到某个“意图族”，例如：

- `requirements`
- `bugfix`
- `analysis`

只要表达的大意接近该意图族，就允许命中对应 workflow。

### 三、workflow 正文只写在 workflow 文件里

项目协作流程、阶段步骤、输入输出约定、回退规则，都放到 workflow 文件中。

外层文件只承担：

- 入口
- 摘要
- 索引
- 路由

不重复承载完整流程正文。

### 四、渐进式披露只带最相关的一份

对于 workflow 路由，默认只选择一份最高优先级且最匹配的 workflow 文件。

除非该文件内部再链接出必要补充文档，否则不继续扩展更多 workflow 文件，避免一次带入多个流程造成噪音。

## 文件约定

### 项目级 workflow

每个项目目录下允许存在以下文件：

```text
projects/<project-slug>/
  context.md
  workflow.md
  workflow-requirements.md
  workflow-bugfix.md
  workflow-analysis.md
  memory.md
```

职责如下：

- `context.md`
  项目入口页，保留项目摘要和 workflow 入口，不写完整流程正文
- `workflow.md`
  项目通用 workflow，当没有更细分的意图型 workflow 时作为回退
- `workflow-requirements.md`
  项目需求阶段 workflow
- `workflow-bugfix.md`
  项目 bug 修复阶段 workflow
- `workflow-analysis.md`
  项目问题分析 / 排障 / 诊断阶段 workflow
- `memory.md`
  保存项目级记忆与启发式结论，不承载流程正文

### 全局 workflow

全局 workflow 放在：

```text
brain/topics/
  general-workflow.md
  general-workflow-requirements.md
  general-workflow-bugfix.md
  general-workflow-analysis.md
```

职责如下：

- `general-workflow.md`
  通用协作 workflow 的默认回退
- `general-workflow-<intent>.md`
  某类任务的通用 workflow

`brain/index.md` 继续作为这些文档的索引入口。

## workflow 文件内容约定

为了不让路由依赖死板命令，workflow 文件本身需要包含可被检索的自然语言描述。

建议统一使用如下结构：

```markdown
# roleMe 需求工作流

## 适用任务

当用户希望开始需求、澄清目标、拆解范围、确认成功标准时使用。

## 默认步骤

1. 先确认目标与边界
2. 再整理用户故事与约束
3. 最后进入实现规划

## 输入 / 输出

- 输入：模糊需求、目标、约束、已有上下文
- 输出：需求摘要、边界、下一步计划

## 边界与回退

- 如果实际是在排查异常，转入问题分析 workflow
- 如果问题已经明确为缺陷修复，转入 bugfix workflow
```

这个结构的目的不是变成强 schema，而是给路由器提供稳定的自然语言信号：

- 文件名提供粗粒度意图
- `适用任务` 提供宽松语义描述
- `边界与回退` 提供切换线索

## 路由规则

### 一、当前项目识别

优先从当前 `cwd` 开始向上逐级查找 Git 仓库根目录，再用该仓库根目录来推断当前项目身份。

这意味着用户即使当前停留在：

- `src/`
- `packages/*`
- `apps/*`
- 任意仓库子目录

也应先回溯到同一个仓库根目录，再映射到角色包中的项目目录。

如果找到的当前仓库能映射到角色包里的 `projects/<slug>/`，则视为当前活动项目。

如果无法从 `cwd` 推断，则回退到现有项目发现逻辑：

- query 显式提到项目
- 角色下只有一个项目
- 项目索引文本与 query 高度匹配

### 二、意图识别

v1 支持三类意图族：

- `requirements`
- `bugfix`
- `analysis`

识别方式不要求 query 精确匹配固定话术，而是采用宽松归因：

- query 词面信号
- query 动词和名词组合
- workflow 文件名中的意图信号
- workflow 文件 `适用任务` 段落中的自然语言描述

实现上可以继续用本地规则和打分，不需要联网或引入额外模型，但效果目标应尽量接近“只要表达出这个意思就能命中”。

### 三、候选 workflow 选择

对于一次 query，候选文件的优先级固定如下：

1. `projects/<slug>/workflow-<intent>.md`
2. `projects/<slug>/workflow.md`
3. `brain/topics/general-workflow-<intent>.md`
4. `brain/topics/general-workflow.md`

如果某一级不存在，继续回退。

如果 query 没能稳定归因到某个意图族，则 v1 不因“语气像在开工”就自动注入通用 workflow。

此时应回退到普通项目 / brain / memory 发现逻辑，而不是仅凭祈使句或任务口吻自动选择 `projects/<slug>/workflow.md` 或 `brain/topics/general-workflow.md`。

这条限制的目的，是避免“读一下这个文件”“改个文案”“看下这个配置”这类普通执行请求被误判成 workflow 型任务。

### 四、渐进式披露策略

一旦选中了目标 workflow 文件：

- 将该 workflow 视为当前 query 的主流程文档
- 若命中的是项目级 workflow，则应始终同时带入 `projects/<slug>/context.md` 作为项目摘要与术语边界
- 默认带入的核心 discovered context 为：
  - `projects/index.md`
  - `projects/<slug>/context.md`
  - 选中的 `workflow*.md`
- 如该 workflow 文档中存在同目录下的一跳链接，可继续跟进一个补充文档
- 不自动把同项目下其他 workflow 文件一并带入

如果命中的是全局 workflow，则核心 discovered context 为：

- `brain/index.md`
- 选中的 `general-workflow*.md`

这保证当前上下文既有项目摘要和流程正文，又不会被多个阶段文档稀释。

## 对现有发现逻辑的影响

### 项目入口层

`projects/index.md` 和 `projects/<slug>/context.md` 仍然保留，但职责更收敛：

- `projects/index.md`
  负责项目发现
- `context.md`
  负责项目摘要与 workflow 入口
- `workflow*.md`
  负责真正的流程正文

### 查询路由层

当前 `route_context_lookup()` 更多是基于“项目 / 领域 / memory”做粗分。

本设计建议新增一层更细的 workflow 路由：

1. 先做粗粒度路由，判断是否应进入项目上下文
2. 如果进入项目上下文，再尝试基于当前项目和 query 意图选择具体 workflow，并与 `context.md` 组成同一次 discovered bundle
3. 如果项目侧未命中，再回退到全局 workflow
4. 最后再视情况补充 `brain` 主题或其他 discovered 文档

### 兼容策略

如果角色包中只有旧的 `workflow.md`：

- 仍然保持可用
- query 命中项目任务时，直接回退到该文件

如果项目尚未配置任何 workflow 文件：

- 不应报错
- 直接沿用当前 `context.md` / `brain` / `memory` 发现逻辑

## 错误处理

- 若当前角色未加载，保持现有行为，不尝试做 workflow 路由
- 若当前项目无法识别，则不阻塞回答，直接尝试全局 workflow 回退
- 若对应 intent 的 workflow 文件不存在，则自动回退到通用 workflow
- 若 query 没有形成足够稳定的 intent 信号，则不自动注入任何通用 workflow
- 若 workflow 文件存在但内容为空或过短，则视为无效候选并继续回退
- 若多个候选分数相近，则按固定优先级优先选择项目侧文件，避免结果漂移

## 测试策略

### 路由测试

- 当前 `cwd` 对应 `roleme` 项目，query 为“开始需求”，命中 `projects/roleme/workflow-requirements.md`
- 当前 `cwd` 对应 `roleme` 项目，query 为“帮我分析下这个问题”，命中 `projects/roleme/workflow-analysis.md`
- 当前 `cwd` 对应 `roleme` 项目，query 为“修一下这个 bug”，命中 `projects/roleme/workflow-bugfix.md`
- 当前 `cwd` 位于 `roleme/src/` 或 `roleme/packages/ui/`，仍能回溯到仓库根目录并命中 `projects/roleme/workflow-<intent>.md`
- 当前项目没有意图型 workflow 时，回退到 `projects/roleme/workflow.md`
- 当前项目没有任何 workflow 时，回退到 `brain/topics/general-workflow-<intent>.md`
- 项目 workflow 与全局 workflow 同时存在时，项目侧优先

### 兼容测试

- 只有旧版 `workflow.md` 时，原有 query 仍可发现 workflow
- 没有 workflow 文件时，不影响当前 `context.md` 和 `brain` 的发现逻辑
- query 只是普通执行请求但缺少稳定 intent 时，不额外拉入通用 workflow
- query 明显不是协作执行请求时，不额外拉入 workflow

### 渐进式披露测试

- 命中需求 workflow 时，不应同时拉入 bugfix / analysis workflow
- 命中项目 workflow 时，应同时保留 `projects/<slug>/context.md`
- 被命中的 workflow 可以继续一跳发现同目录补充文档
- context snapshot 中应包含 resident 与单一命中的 workflow discovered 内容

## 风险与取舍

### 一、意图识别仍然是启发式，不是真正语义理解

v1 仍然是本地规则与打分机制，不可能完全等价于大模型判断。

本设计的目标不是“完美分类”，而是把体验从“只能靠固定口令”提升到“自然表达大多能命中”。

### 二、workflow 类型先收敛，避免过早泛化

先只支持：

- `requirements`
- `bugfix`
- `analysis`

这样可以保证：

- 路由规则简单
- 文件约定清晰
- 测试边界明确

后续若验证有效，再扩展更多 workflow 类型。

### 三、保持 context 轻，不把规则再复制回去

如果把完整流程又写进 `context.md`，会重新回到“一个文件塞所有东西”的老问题。

因此本设计明确要求：

- 流程正文只在 workflow 文件里维护
- `context.md` 只做入口和摘要

## 实现建议

实现应分两步完成：

1. 先扩展 `context_router.py`
   新增 workflow 意图识别、候选枚举与优先级回退
2. 再补充测试
   覆盖项目优先、全局回退、兼容旧 `workflow.md`、渐进式披露边界

实现完成后，角色包的使用体验会从“先显式说按 workflow 来”升级成“自然表达任务意图，系统自动把当前项目最合适的 workflow 带进来”。
