# roleMe Workflow 摘要预加载设计文档

日期：2026-04-16  
状态：已确认设计方向，待实现规划

## 概述

当前 `roleMe` 的 workflow 命中主要依赖两层能力：

- `context_router` 按用户 query 识别当前项目与候选 workflow
- workflow 索引中的自然语言信号为路由提供匹配依据

但在实际使用中，这套机制仍有一个明显短板：

- 模型在真正接到用户任务前，并不知道“当前项目有哪些 workflow”与“全局有哪些 workflow”
- 命中质量过度依赖用户这一轮话术是否刚好撞上 workflow 索引中的关键词

例如用户直接说：

> 用端到端开发流程来实现以下需求：  
> 1. 活期转账页面。  
> 2. 余额查询页面。  
> 注意：按照软件需求规格说明书完成前后端和数据库代码。

从协作意图上看，这已经非常接近 `coresys-devops` 项目的端到端交付 workflow；但如果当前模型尚不知道该项目存在这个 workflow，或者只能在当轮 query 中被动猜测，就会出现命中率不稳定的问题。

本设计要补上的能力是：

- 角色加载时，如果当前 `cwd` 能识别到项目，则预加载该项目的 workflow 摘要块
- 同时预加载全局 workflow 摘要块
- 摘要块只保留轻量的结构化信号，不预加载具体 workflow 正文
- 当用户后续任务与某个摘要块足够匹配时，再按需展开对应 workflow 正文

一句话概括：先让模型知道“当前有哪些 workflow 可选”，再在真正命中时展开具体流程正文。

## 目标

- 在角色加载阶段预加载当前项目的 workflow 摘要块
- 在角色加载阶段预加载全局 workflow 摘要块
- 预加载范围只限当前 `cwd` 对应的项目，不依赖角色包里记录的其他项目
- workflow 摘要块只包含轻量的目录级语义信号，不加载正文
- 将项目 workflow 与全局 workflow 的候选信息提前暴露给后续路由与回答阶段
- 保持“命中后再展开正文”的渐进式披露原则
- 提升自然语言请求对 workflow 的命中率，尤其是“完整实现”“前后端数据库联动”“按规格说明书完成”这类真实表达
- workflow 索引不存在、格式非法或无可解析条目时，安静跳过，不影响角色其余加载流程

## 非目标

- 不在本次设计中预加载具体 workflow 正文
- 不把所有项目的 workflow 一起预加载到 resident 层
- 不因为存在 workflow 摘要块就强制所有开发任务进入 workflow
- 不在本次设计中引入新的在线分类器或复杂推理服务
- 不改变 workflow 正文文件作为唯一流程细则来源的定位

## 方案选择

本轮讨论过三类方案：

### 方案 A：角色加载时预加载 workflow 摘要块

- 角色加载时识别当前项目
- 解析当前项目 `workflows/index.md`
- 解析全局 `brain/workflows/index.md`
- 生成项目 workflow 摘要块与全局 workflow 摘要块
- 具体 workflow 正文仍在命中后按需展开

### 方案 B：仅增强路由阶段匹配

- 不改加载流程
- 只在 `discover_workflow_paths()` 阶段读取 workflow 索引并做更宽松的语义匹配

### 方案 C：加载阶段与路由阶段同时做增强

- 加载阶段预加载摘要块
- 路由阶段再次读取与强化匹配

最终选择：**方案 A，并扩展为同时预加载当前项目与全局 workflow 摘要块。**

选择理由：

- 直接解决“模型在接任务前不知道有哪些 workflow”这个根问题
- 保留上下文轻量，不把正文塞进 resident 层
- 与现有渐进式披露分层更一致：加载层只带目录信号，路由层负责具体展开

## 设计一：架构与数据流

系统分成两层：

### 一、加载层

职责：

- 在加载角色时，根据当前 `cwd` 识别当前项目
- 如果当前项目存在，则尝试读取 `projects/<project-slug>/workflows/index.md`
- 同时尝试读取 `brain/workflows/index.md`
- 解析出可用 workflow 条目后，生成轻量 workflow 摘要块

加载层只负责把“有哪些 workflow 可选”整理出来，不负责展开正文。

### 二、路由层

职责：

- 在用户发起具体任务时，先参考 resident snapshot 中已加载的 workflow 摘要块
- 判断当前请求更接近哪个项目级或全局 workflow
- 命中后再去展开对应 workflow 正文
- 未命中则退回普通上下文路由

### 数据流

```text
加载角色
-> 识别当前 cwd 对应项目
-> 解析项目 workflows/index.md
-> 解析 brain/workflows/index.md
-> 生成 workflow 摘要块并写入 resident snapshot

用户发起任务
-> 先参考 resident snapshot 中的 workflow 摘要块
-> 判断更接近哪个候选 workflow
-> 命中后展开对应 workflow 正文
-> 未命中则按普通项目 / brain 路由继续
```

这个设计的核心收益是：模型在真正接任务前，就已经知道当前项目与全局范围内“有哪些流程可选”，不再完全依赖用户单轮 query 去撞关键词。

## 设计二：命中优先级与冲突规则

加载阶段同时带入项目 workflow 摘要块与全局 workflow 摘要块，但真正命中时仍遵循固定优先级：

1. 当前项目的具体 workflow
2. 全局的具体 workflow
3. 普通项目上下文
4. 普通知识上下文

具体规则如下：

- 如果当前 `cwd` 能识别到项目，且项目 workflow 摘要块里存在明显匹配项：
  - 直接命中该项目 workflow，并展开正文
- 如果项目 workflow 摘要块存在，但没有足够匹配的条目：
  - 再检查全局 workflow 摘要块
- 如果全局 workflow 也没有足够匹配项：
  - 不强行进入 workflow，退回普通上下文路由
- 如果当前 `cwd` 识别不到项目：
  - 只使用全局 workflow 摘要块做候选集

### 明显匹配的判断信号

命中不应只依赖单个关键词，而应综合以下信号：

- 用户是否表达完整流程意图
- 是否提到前后端、数据库、联调、验收、上线等完整交付信号
- 是否提到 PRD、软件需求规格说明书、用户故事、开发计划、端到端等流程信号
- 是否与某个 workflow 的 `applies_to`、`keywords`、`summary` 有多处重合

### 冲突规则

- 项目候选与全局候选同时匹配时，项目优先
- 同一作用域内多个 workflow 都接近时，只选最高分的一项，不同时展开多个正文
- 第一名与第二名过于接近时，宁可不自动命中，也不要误触发错误 workflow
- 若已命中某个 workflow，但后续阶段发现任务性质变化，允许回退并切换 workflow

## 设计三：摘要块格式与加载失败回退

resident snapshot 中的 workflow 摘要块应采用轻量结构化文本，不直接放原始索引全文，也不放正文。

### 当前项目 workflow 摘要块示例

```md
## Current Project Workflows
project: coresys-devops

- slug: end-to-end-delivery
  title: 端到端交付 workflow
  applies_to: 当用户要求按完整交付流程推进需求实现时使用
  keywords: 端到端开发流程, 软件需求规格说明书, 前后端, 数据库, 完整实现, 联调, 验收
  summary: 用于从需求澄清、PRD、计划、TDD、启动验证、E2E 到上线发布的完整闭环
```

### 全局 workflow 摘要块示例

```md
## Global Workflows

- slug: requirements
  title: 需求分析 workflow
  applies_to: 当用户要梳理需求、澄清范围、整理故事时使用
  keywords: 需求, 范围, 用户故事, PRD
  summary: 用于把模糊需求收敛成可规划输入
```

### 摘要块内容约束

- 只保留 `slug`、`title`、`applies_to`、`keywords`、`summary`
- 不把具体 workflow 正文写进 resident snapshot
- 系统内部需要保留 `slug -> file path` 的映射，用于命中后展开正文
- 项目 workflow 与全局 workflow 要分开生成，避免丢失优先级语义

### 加载失败回退

如果当前 `cwd` 对应项目，但项目 workflow 索引文件存在以下情况：

- 不存在
- 格式不合法
- 没有可解析条目

则直接不加载该项目的 workflow 摘要块。

全局 workflow 索引同理。

补充回退约束：

- workflow 摘要块缺失不影响角色其余内容加载
- workflow 索引解析失败时，不自动回退到加载具体 workflow 正文
- 正常用户对话中不抛出阻断式错误
- 如需排查，可在调试日志中记录失败原因

## 设计四：测试策略与验收标准

### 一、加载成功

给定当前 `cwd` 对应某个项目，且项目 `workflows/index.md` 与全局 `brain/workflows/index.md` 都为合法结构时：

- 角色加载后会生成项目 workflow 摘要块
- 角色加载后会生成全局 workflow 摘要块
- 摘要块只包含 `slug`、`title`、`applies_to`、`keywords`、`summary`
- 摘要块中不包含具体 workflow 正文

### 二、加载回退

分别验证以下情况：

- 项目 workflow 索引不存在
- 项目 workflow 索引格式非法
- 项目 workflow 索引为空
- 全局 workflow 索引不存在
- 全局 workflow 索引格式非法
- 全局 workflow 索引为空

预期：

- 只跳过对应摘要块
- 角色其余加载流程不受影响
- 不抛出阻断式错误

### 三、路由命中

应优先补真实用户话术回归，而不是只测理想关键词。示例包括：

- “用端到端开发流程来实现以下需求”
- “按照软件需求规格说明书完成前后端和数据库代码”
- “把这个需求按完整流程落下来”
- “先走需求到交付的完整闭环”

预期：

- 若当前项目存在匹配 workflow，优先命中项目 workflow
- 若项目不匹配但全局匹配，则命中全局 workflow
- 命中后才展开具体 workflow 正文

### 四、误命中控制

应验证以下场景不会被 workflow 摘要块错误带偏：

- 普通问答
- 局部 bug 修复
- 单文件小改动
- 与 workflow 无关的项目讨论

预期：

- 仅因为加载了摘要块，不会默认进入 workflow
- 只有匹配度足够时才展开正文
- 项目 workflow 与全局 workflow 分数接近时，宁可不自动命中

### 验收标准

- 当前 `cwd` 对应项目时，角色加载结果中能稳定带上项目 workflow 摘要块
- 全局 workflow 索引存在时，角色加载结果中能稳定带上全局 workflow 摘要块
- workflow 摘要缺失或损坏时，不影响角色正常加载
- 真实自然语言话术的 workflow 命中率明显高于当前实现
- 普通任务不会因为摘要预加载而被 workflow 污染
- 回归测试覆盖项目优先、全局回退、加载失败回退、误命中控制四类场景

## 实现边界建议

后续实现时，建议把“workflow 摘要生成”与“workflow 正文发现”保持为两个独立职责：

- 摘要生成负责把索引解析结果转成 resident snapshot 可用的轻量文本
- 正文发现继续负责根据 query 选择并展开具体 workflow 文件

这样可以避免加载层和路由层各自维护一套相互漂移的规则。

## 后续步骤

本设计确认后，下一步应进入 `writing-plans`，产出实现计划，明确：

- workflow 摘要块生成位置
- resident snapshot 拼装方式
- 当前项目识别接入点
- tests 覆盖范围与回归样例
