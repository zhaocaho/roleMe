# roleMe 打包产物工作流索引设计文档

日期：2026-04-16  
状态：已完成设计评审，待实现规划

## 概述

当前 `roleMe` 已经支持把 workflow 写入角色包，并且 `context_router` 也开始具备按任务意图做 workflow 路由的能力。

但现状仍有两个核心问题：

- 打包后的 skill 产物还没有完整支持新的 workflow 组织方式
- workflow 仍然围绕 `workflow.md`、`general-workflow.md` 这类聚合文件设计，而不是“一份 workflow，一个文件”

这会带来三个直接问题：

- 一个文件容易不断追加不同流程，最后重新变成大杂烩
- 路由依赖固定文件名和旧路径，难以支持后续新增的独立 workflow
- 开发仓库与打包产物在 workflow 结构上不一致，导致“本地能用”和“下载后能用”不是同一套系统

本设计的目标是把 workflow 体系正式切换到：

- 不内置任何默认 workflow 模板
- 一旦创建 workflow，就必须生成独立文件
- workflow 的发现以 `workflows/index.md` 为主入口
- 打包产物与开发仓库运行时遵循同一套目录、路由和写入约定

一句话概括：`roleMe` 不负责预置 workflow，但负责把 workflow 管理成“索引入口 + 单 workflow 单文件”的稳定结构。

## 目标

- 让打包后的 `roleme` skill 原生支持 `workflows/index.md + 独立 workflow 文件` 结构
- 明确项目级 workflow 与全局 workflow 的统一目录约定
- 让 workflow 的发现依赖索引路由，而不是目录扫描或固定文件名猜测
- 保证渐进式披露只命中当前最相关的 workflow 内容
- 让创建或更新 workflow 时，正文始终落在独立文件中
- 保证开发仓库与打包产物的文档和运行时代码一致

## 非目标

- 不在本次设计中内置任何默认 workflow 集合
- 不要求角色初始化时自动创建空 workflow 模板
- 不把 workflow 创作过程做成强表单或复杂 schema 系统
- 不保留对旧 `workflow.md`、`general-workflow.md` 的兼容读取或兼容写入
- 不在本次设计中引入自动执行 workflow 引擎

## 关键决策

### 一、不内置 workflow

`roleMe` 不提供默认 workflow 模板，也不在角色初始化时预建任何具体 workflow 文件。

workflow 目录和 `index.md` 采用惰性创建：

- 当某一层第一次归档 workflow 时，再创建对应 `workflows/` 目录
- 同时创建该层的 `workflows/index.md`
- 没有 workflow 时，允许该目录完全不存在

这能保证“支持 workflow 管理”与“预置 workflow 内容”是两回事。

### 二、一个 workflow 一个文件

workflow 正文不得再写入聚合型文件。

每次创建或更新 workflow 时：

- 必须落到一个独立的 `workflows/<workflow-slug>.md`
- 不允许把多个流程混写到同一个 workflow 正文文件
- `workflows/index.md` 只负责登记和路由，不承载完整流程正文

### 三、`workflows/index.md` 是主路由入口

workflow 是否命中，不靠扫描目录中的所有 `.md` 文件，也不靠猜 `workflow-xxx.md` 这类固定命名。

真正的命中入口是：

- `projects/<project-slug>/workflows/index.md`
- `brain/workflows/index.md`

路由器先读索引，再决定选中哪个 workflow 正文文件。

### 四、直接切换，不兼容旧结构

本设计采用直接切换策略。

切换后：

- 不再读取 `projects/<project-slug>/workflow.md`
- 不再读取 `brain/topics/general-workflow.md`
- 不再向这些旧路径写入任何 workflow 内容

既有角色包如果仍保留旧文件，运行时也不会再把它们视为 workflow 来源。

## 目录结构

### 全局 workflow

```text
brain/
  index.md
  workflows/
    index.md
    <workflow-slug>.md
```

职责约定：

- `brain/index.md`
  作为 brain 总入口，只保留对 `workflows/index.md` 的索引入口
- `brain/workflows/index.md`
  全局 workflow 路由入口
- `brain/workflows/<workflow-slug>.md`
  某个全局通用 workflow 的独立正文

### 项目 workflow

```text
projects/
  <project-slug>/
    context.md
    memory.md
    overlay.md
    workflows/
      index.md
      <workflow-slug>.md
```

职责约定：

- `context.md`
  项目入口页，只保存项目摘要和 `workflows/index.md` 的入口，不再承载流程正文
- `memory.md`
  保存项目记忆与结论，不承载 workflow 正文
- `overlay.md`
  保存项目级协作偏置，不承载 workflow 正文
- `workflows/index.md`
  该项目的 workflow 路由入口
- `workflows/<workflow-slug>.md`
  某个项目 workflow 的独立正文

## 索引文件契约

`workflows/index.md` 采用“可人工维护、可稳定解析”的轻量注册表格式。

每个 workflow 以一个独立 section 表示，格式如下：

```markdown
# 工作流索引

## requirements
- title: 需求分析 workflow
- file: requirements.md
- applies_to: 当用户想梳理需求、澄清范围、确认目标、整理用户故事时使用
- keywords: 需求, requirement, story, scope, 澄清
- summary: 用于把模糊需求整理成可进入规划的明确输入
```

每个条目的字段要求如下：

- `## <workflow-slug>`
  该 workflow 的稳定标识
- `title`
  人类可读标题
- `file`
  相对于当前 `workflows/` 目录的目标文件名
- `applies_to`
  自然语言适用场景，是主匹配信号
- `keywords`
  辅助召回关键词，支持中英文逗号分隔
- `summary`
  面向索引页的简述，不重复正文

约束如下：

- `file` 必须指向当前目录中的单个 markdown 文件
- `file` 与 section slug 必须一一对应，不允许多个条目指向同一文件
- 缺少 `title`、`file`、`applies_to`、`keywords`、`summary` 任一字段的条目，不参与 workflow 路由
- workflow 正文文件内容本身不强制固定模板，但索引条目必须满足上述结构

## 路由规则

### 一、项目优先，全局回退

workflow 路由固定遵循下面的顺序：

1. 识别当前活动项目
2. 若存在 `projects/<slug>/workflows/index.md`，优先在该索引内选 workflow
3. 若项目级未命中，再读取 `brain/workflows/index.md`
4. 若全局也未命中，则回退到普通的 `project / brain / memory` 渐进式发现逻辑

同一 query 同时命中项目级与全局条目时，始终选择项目级。

### 二、索引驱动，不做目录扫描

路由器不直接扫描 `workflows/` 目录中的所有文件，不靠存在某个文件名就视为可用 workflow。

只有在 `workflows/index.md` 中注册过的 workflow，才有资格参与路由。

### 三、打分信号

每个候选条目使用下列信号做确定性打分：

- `applies_to` 文本重合度：最高权重
- `keywords` 命中数：中等权重
- `title` 文本重合度：低权重
- `file` 文件名词干：弱信号，仅用于辅助

推荐的 v1 打分规则：

- `applies_to` 每命中一个 query token 记 5 分
- `keywords` 每命中一个 token 记 3 分
- `title` 每命中一个 token 记 2 分
- `file` 词干每命中一个 token 记 1 分

候选 workflow 必须同时满足：

- 总分大于等于 4
- 第一名至少比第二名高 2 分

否则视为歧义或无命中，直接回退到普通上下文发现逻辑，不自动选 workflow。

### 四、渐进式披露边界

一旦命中 workflow，默认只带入以下两份内容：

- 对应层级的 `workflows/index.md`
- 被选中的 `workflows/<workflow-slug>.md`

默认不额外带入：

- 同目录中的其他 workflow 文件
- `context.md`
- `overlay.md`
- `memory.md`
- 其他 brain topic

只有在后续 query 明确需要时，才继续展开这些内容。

### 五、歧义处理

歧义处理规则固定如下：

- 项目级与全局同时命中：选项目级
- 同层级多个候选分数接近：不选 workflow，回退普通发现逻辑
- query 只有任务语气但没有真实匹配信号：不选 workflow

设计原则是：宁可少命中，也不要误命中。

## 归档与写入规则

### 一、项目级 workflow 写入

当归档结果属于某个项目时：

- 创建或更新 `projects/<project-slug>/workflows/<workflow-slug>.md`
- 创建或更新 `projects/<project-slug>/workflows/index.md`
- 确保 `projects/<project-slug>/context.md` 中存在到 `workflows/index.md` 的入口
- 项目记忆仍写入 `projects/<project-slug>/memory.md`

不得发生以下行为：

- 不得写入 `projects/<project-slug>/workflow.md`
- 不得把多个 workflow 合并写回一个项目总 workflow 文件

### 二、全局 workflow 写入

当归档结果属于通用 workflow 时：

- 创建或更新 `brain/workflows/<workflow-slug>.md`
- 创建或更新 `brain/workflows/index.md`
- 确保 `brain/index.md` 中存在到 `workflows/index.md` 的入口
- 稳定规则和长期摘要仍分别写入 `memory/USER.md` 与 `memory/MEMORY.md`

不得发生以下行为：

- 不得写入 `brain/topics/general-workflow.md`
- 不得把多个通用 workflow 合并写回一个全局总 workflow 文件

### 三、slug 规则

workflow 必须拥有稳定 slug。

建议生成规则：

- 若调用方提供合法 slug，则优先使用
- 否则根据 workflow 标题生成 slug
- 统一转小写
- 非字母数字字符归一化为 `-`
- 连续连接符折叠
- 若重名，则追加 `-2`、`-3` 等后缀

一旦 workflow 建立，其 slug 应保持稳定，后续更新应写回同一文件。

### 四、未形成独立 workflow 时的处理

如果一次归档内容还不足以形成独立 workflow，例如：

- 只有一句模糊偏好
- 只是项目协作提醒
- 还没有明确的 workflow 主题和边界

则不应强行创建 workflow 文件，而应优先写入：

- `projects/<project-slug>/memory.md`
- `brain/topics/...`
- `memory/USER.md`
- `memory/MEMORY.md`

workflow 目录只承载真正形成独立流程的内容。

## 对现有文件的影响

### `context.md`

项目 `context.md` 的职责从“可能包含 workflow 入口甚至正文”收缩为：

- 项目摘要
- 当前仓库 / 工作区信息
- `workflows/index.md` 入口

它不再承担具体 workflow 正文。

### `brain/index.md`

`brain/index.md` 继续作为全局知识入口，但对 workflow 只保留一层入口：

- `workflows/index.md`

它不再直接索引具体 workflow 正文文件。

### 历史设计文档

现有涉及旧路径的设计文档仅作为历史记录保留。

实现与打包产物必须以本设计为准，不再沿用旧文档中的以下约定：

- `projects/<project-slug>/workflow.md`
- `brain/topics/general-workflow.md`
- 任何基于旧路径的 fallback 逻辑

## 结合现有代码的合理性评估

本设计在现有代码基础上是合理的，但不是“只改几个路径”的轻量调整，而是一次围绕 workflow 数据模型、索引写入和路由发现的结构性改造。

当前代码的主要约束如下。

### 一、归档数据模型还不够支撑新结构

`tools/role_ops.py` 中的 `WorkflowArchivePlan` 目前只有：

- `workflow_title`
- `workflow_doc_markdown`
- `context_summary_markdown`

它还没有以下信息：

- `workflow_slug`
- workflow 索引条目字段
- 工作流目标文件名

这意味着当前归档逻辑只能把 workflow 当作“单份正文 + 一段摘要”处理，还不能稳定表达“一个 workflow 对应一个独立文件 + 一个索引注册项”。

因此，本设计要落地，必须先扩展归档契约，而不是只改写入路径。

### 二、现有索引写入工具只适合简单链接，不适合 workflow 注册表

当前 `upsert_markdown_index_entry()` 写入的是：

```text
- 标签: 路径
  - 摘要
```

这类简单列表足够支撑 `brain/index.md` 或 `projects/index.md` 的普通入口，但不够支撑 `workflows/index.md` 的注册表职责，因为新结构要求索引条目至少具备：

- slug
- title
- file
- applies_to
- keywords
- summary

如果继续复用现有 helper，会出现两个问题：

- 不能稳定更新同一个 workflow 条目
- 不能支持路由器读取结构化字段做打分

因此，本设计是合理的，但实现上应新增面向 workflow 的专用 index 读写函数，而不是继续复用普通索引 helper。

### 三、当前 workflow 写入逻辑会覆盖单一旧文件

当前：

- `archive_general_workflow()` 固定写 `brain/topics/general-workflow.md`
- `archive_project_workflow()` 固定写 `projects/<slug>/workflow.md`

并且项目级写入时，会把 `context_summary_markdown` 直接写回 `context.md`，再补一句 `- Workflow: workflow.md`。

这套逻辑和新设计的冲突点非常直接：

- 它天然只能维护一个项目总 workflow 文件
- 也天然只能维护一个全局总 workflow 文件
- `context.md` 被当成 workflow 入口和摘要混合页，不符合新结构的职责边界

所以旧写法不能平移到新目录，必须把“workflow 正文写入”“workflow 索引写入”“context 入口维护”拆成三个独立动作。

### 四、当前路由逻辑仍然硬编码旧文件路径

`tools/context_router.py` 当前的 workflow 发现逻辑仍然建立在这些假设上：

- 项目级 workflow 命中 `workflow-<intent>.md` 或 `workflow.md`
- 全局 workflow 命中 `brain/topics/general-workflow-<intent>.md` 或 `brain/topics/general-workflow.md`

这说明现有实现虽然已经有了“意图路由”的方向，但仍然没有真正切到“索引驱动”。

新设计要落地，至少需要新增三类能力：

- 解析 `workflows/index.md`
- 对索引条目做打分和选优
- 根据索引中的 `file` 字段定位目标 workflow 文件

也就是说，当前代码方向与本设计并不冲突，但需要从“固定路径选择”升级到“索引条目选择”。

### 五、测试改动面会比较大，但集中且可控

当前测试对旧结构绑定很深，尤其体现在：

- `tests/test_context_router.py`
- `tests/test_role_ops.py`
- `tests/integration/test_role_roundtrip.py`

这些测试大量断言以下旧路径：

- `projects/<slug>/workflow.md`
- `brain/topics/general-workflow.md`
- `brain/topics/general-workflow-<intent>.md`

这意味着直接切换策略会让现有 workflow 相关测试大面积失效。

但这并不代表设计不合理，反而说明“旧行为集中在少数核心函数和测试假设里”，改造边界是清楚的。只要实现时同步更新：

- 归档契约
- index 读写
- 路由发现
- 测试样例数据

这次切换是可控的，不需要做长期兼容层。

### 六、打包产物同步风险低于运行时改造风险

`scripts/build_skill.py` 当前只是复制：

- `bundle/`
- `tools/`
- `templates/`

这意味着打包脚本本身不复杂。

只要开发仓库中的以下内容改对：

- `bundle/SKILL.template.md`
- `bundle/references/usage.md`
- `tools/context_router.py`
- `tools/role_ops.py`

打包产物就会自然继承新结构。

因此，本设计真正的风险重点不在打包脚本，而在运行时契约与测试迁移。

### 七、整体判断

综合现有代码看，本设计是合理的，原因有三点：

- 当前 workflow 逻辑已经集中在少数核心函数中，具备一次性切换的条件
- 旧结构本身就是单文件聚合模型，继续叠补丁只会让后续演化更难
- 打包产物采用复制式构建，只要源代码契约统一，发布产物就能同步受益

但本设计也明确意味着：

- 不能把这次改造当成简单路径替换
- 必须把归档契约、索引模型、路由发现和测试一起改
- 计划阶段需要显式拆出“数据结构重塑”和“测试迁移”任务

## 打包产物要求

打包后的 `roleme` skill 必须与开发仓库运行时保持一致。

至少需要同步以下内容：

- `bundle/SKILL.template.md`
- `bundle/references/usage.md`
- `tools/context_router.py`
- `tools/role_ops.py`
- 打包后生成的 `skills/roleme/` 对应文件

构建脚本 `scripts/build_skill.py` 可以保持复制式打包模型，但其输出结果必须反映新的 workflow 结构与说明。

也就是说，用户下载后的 skill 应直接具备以下能力：

- workflow 归档写入到 `workflows/` 目录
- workflow 路由通过 `workflows/index.md`
- 不再读取或写入旧 `workflow.md` 路径

## 测试要求

至少覆盖以下测试场景：

1. 创建项目级 workflow
   - 生成 `projects/<slug>/workflows/<workflow-slug>.md`
   - 自动创建或更新 `projects/<slug>/workflows/index.md`
   - `context.md` 具备到 `workflows/index.md` 的入口

2. 创建全局 workflow
   - 生成 `brain/workflows/<workflow-slug>.md`
   - 自动创建或更新 `brain/workflows/index.md`
   - `brain/index.md` 具备到 `workflows/index.md` 的入口

3. 路由优先级
   - 项目级和全局都命中时，优先项目级
   - 项目级未命中时，正确回退到全局

4. 歧义与保守策略
   - 多个候选分数接近时，不自动命中 workflow
   - 只有任务口吻但没有真实匹配信号时，不自动命中 workflow

5. 渐进式披露边界
   - 命中 workflow 时，只返回 `workflows/index.md` 与目标 workflow 文件
   - 不额外注入同目录其他 workflow 文件

6. 直接切换策略
   - 旧 `workflow.md`、`general-workflow.md` 不再被读取
   - 旧路径也不再被写入

7. 打包一致性
   - 打包后的 `skills/roleme/` 文档与运行时代码遵循同一约定

## 验收标准

当以下条件全部满足时，本设计视为完成：

- `roleMe` 不内置任何默认 workflow 模板
- 任何新建 workflow 一旦成立，都以独立文件形式落到 `workflows/` 目录
- workflow 的命中依赖 `workflows/index.md`，而不是目录扫描或旧固定文件名
- workflow 路由遵循“项目优先，全局回退”的顺序
- workflow 命中后只带入最小必要内容，符合渐进式披露原则
- 开发仓库与打包后的 skill 在 workflow 结构、路由和写入行为上保持一致
- 旧 `workflow.md`、`general-workflow.md` 路径彻底退出运行时体系
