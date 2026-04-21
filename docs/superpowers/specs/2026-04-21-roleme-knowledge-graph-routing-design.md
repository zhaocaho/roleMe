# roleMe Knowledge Graph Routing 设计文档

日期：2026-04-21  
状态：已确认设计方向，待实现规划

## 概述

当前 `roleMe` 已经形成了稳定的角色包结构：

- `persona/` 提供协作身份和沟通偏好
- `memory/` 保存长期偏好、长期结论和 episode
- `brain/` 保存通用知识、主题和通用 workflow
- `projects/` 保存项目上下文、项目记忆和项目 workflow
- `context_router.py` 根据用户 query 做渐进式上下文发现

这套结构解决了“不要一次性加载全部上下文”的问题，但在长期使用中会暴露三个更深层的痛点：

- **加载效率低**：上下文发现依赖线性索引和逐层 markdown 链接，路径偏长
- **知识命中率低**：query 与知识文件标题、关键词、索引写法不一致时，容易漏掉真正相关内容
- **知识错误风险**：旧规则、过期 workflow、低置信度总结、项目经验和通用原则之间的冲突缺少结构化判断

本设计引入一套面向智能体消费的知识图谱层。它不是替代 markdown 文件，也不是把所有知识塞进 resident snapshot，而是在现有角色包结构之上建立一层可检索、可校验、可演化的结构化索引。

一句话概括：`roleMe` 继续用 markdown 保存正文，用 graph 管理“它是什么、从哪里来、适用于哪里、和什么有关、现在是否可信”。

## 目标

- 用图谱统一管理通用 workflow、项目 workflow、记忆、项目经验、规则、决策、概念和证据
- 提升 `context_router.py` 对自然语言 query 的知识命中率
- 保持渐进式披露原则，只加载本次任务所需的正文文件
- 支持记录型归档：自然语言归档和 workflow 归档时，同时写 markdown 正文和图谱节点/关系
- 支持召回型读取：用户发起任务时，先做图谱召回，再展开相关文件
- 支持知识可靠性判断：过期、废弃、被替代、冲突、低置信度知识不应无条件进入强上下文
- 保持本地优先、可导出、可测试，不引入外部数据库或在线图谱服务
- 与现有 `brain/workflows/index.md`、`projects/<project>/workflows/index.md` 兼容，避免一次性迁移所有角色包

## 非目标

- 不在第一阶段引入向量数据库、图数据库或外部服务
- 不在第一阶段自动抽取所有历史 markdown 的完整实体关系
- 不让 graph 成为正文存储位置，正文仍保存在现有 markdown 文件中
- 不把所有图谱摘要预加载进 resident snapshot
- 不把低置信度模型总结自动提升为长期规则
- 不强制所有 query 都走 workflow，未命中时仍回退到现有路由

## 核心判断

`ai-digital-avatar` skill 中的 ontology 设计提供了有价值的参考：

- 用 `schema.yaml` 定义实体和关系
- 用 `graph.jsonl` 做本地追加式记录
- 在工作流完成后写入 `Document`、`Decision`、`Knowledge` 等实体
- 把 ontology 作为工作流产物和记忆系统的一部分

但它更偏“记录型 ontology”，适合追踪事实、产物和决策；`roleMe` 还需要“召回型图谱”和“证据型图谱”，以解决上下文加载、知识命中和知识错误问题。

因此本设计采用三类能力合一：

```text
Record Graph    负责沉淀：workflow、记忆、项目经验、决策、文档
Retrieval Graph 负责召回：query -> 节点 -> 关系扩展 -> 文件路径
Evidence Graph  负责校验：来源、置信度、时效、冲突、替代关系
```

三者共享同一套节点和边，不拆成三套存储。

## 总体架构

底层采用一套 Graph Core：

```text
brain/graph/
├── schema.yaml
├── nodes.jsonl
├── edges.jsonl
└── indexes/
    ├── by-type.json
    ├── by-path.json
    └── aliases.json
```

上层不拆成五套图谱系统，而是围绕同一套 Graph Core 提供三类能力视角：

```text
Archive View    写入和沉淀：workflow、记忆、项目经验、决策、文档
Recall View     读取和命中：query -> concept/workflow/project -> file
Trust View      校验和治理：来源、置信度、状态、冲突、替代关系
```

Graph Core 只保存结构化索引和轻量摘要；正文文件仍在：

```text
brain/workflows/*.md
brain/topics/*.md
projects/<project>/workflows/*.md
projects/<project>/memory.md
memory/USER.md
memory/MEMORY.md
memory/episodes/*.md
```

## 是否需要五层图谱

不需要把 `Workflow`、`Memory`、`Project`、`Evidence`、`Concept` 做成五套独立图谱。

五类图谱适合作为设计分析维度，用来确保系统覆盖调度、记忆、项目、证据和语义命中；但如果按五层分别实现，会导致 schema、写入、查询、doctor 和迁移都过度复杂。

本设计最终选择：

```text
一套 Graph Core
三类能力视角
少量一等节点
按阶段扩展节点和关系
```

第一阶段只把 `Project`、`Workflow`、`Rule`、`Evidence`、`Concept`、`File` 做成一等节点。`Memory / Principle / Topic / Source / Decision` 等能力先作为远景保留，不进入第一阶段实现。

## 长期领域模型

本节描述长期领域模型，用来保证未来扩展方向一致；其中只有 `Project`、`Workflow`、`Rule`、`Evidence`、`Concept`、`File` 进入 v1 实现。

### Workflow Graph

Workflow Graph 是第一优先级。它负责回答“当前任务应该用哪个流程”。

核心节点：

```yaml
Workflow:
  id: string
  title: string
  scope: global | project
  project_slug: string?
  path: string
  summary: string
  applies_to: string
  keywords: string[]
  status: active | draft | deprecated | superseded
  confidence: high | medium | low
  created_at: string
  updated_at: string

Skill:
  id: string
  name: string
  path: string
  summary: string

Rule:
  id: string
  title: string
  summary: string
  path: string?
  scope: role | global | project
  status: active | draft | deprecated | superseded
```

核心关系：

```yaml
Workflow belongs_to Project
Workflow applies_to Concept
Workflow depends_on Rule
Workflow specializes Workflow
Workflow supersedes Workflow
Workflow evidenced_by Evidence
```

典型行为：

```text
当前 cwd 命中 Project(roleme)
用户说“开始开发这个需求”
-> 召回 roleme 项目 workflow
-> 若项目 workflow 不存在，回退到通用 workflow
-> 展开 workflow 正文、依赖规则和必要证据
```

### Memory / Principle Graph

Memory / Principle Graph 负责长期协作规则、稳定偏好和方法论沉淀。

核心节点：

```yaml
Preference:
  id: string
  title: string
  summary: string
  scope: role | global | project
  path: string
  status: active | draft | deprecated | superseded
  confidence: high | medium | low

Principle:
  id: string
  title: string
  summary: string
  scope: role | global | project
  path: string?
  status: active | draft | deprecated | superseded
  confidence: high | medium | low

Decision:
  id: string
  title: string
  summary: string
  decided_at: string
  scope: role | global | project
  status: active | stale | superseded
  confidence: high | medium | low

Memory:
  id: string
  title: string
  summary: string
  path: string
  memory_type: user | memory | project_memory | episode
```

核心关系：

```yaml
Principle derived_from Episode
Principle supports Workflow
Preference applies_to Workflow
Decision supersedes Decision
Memory promoted_to Principle
Memory contradicts Memory
Memory evidenced_by Evidence
```

典型行为：

```text
用户提出新需求
-> 命中“新需求先问使用什么 workflow”的 Preference
-> 命中“TDD 覆盖完整性”的 Principle
-> 这些节点影响后续协作，但不必全部展开 episode 正文
```

### Project Graph

Project Graph 负责把当前仓库、项目上下文、项目 workflow、项目记忆和文档聚合起来。

核心节点：

```yaml
Project:
  id: string
  slug: string
  title: string
  repo_path: string?
  summary: string
  status: active | archived
  updated_at: string

Repository:
  id: string
  path: string
  slug: string
  current: boolean

Document:
  id: string
  title: string
  path: string
  doc_type: prd | plan | workflow | spec | note | code_doc
  status: active | draft | deprecated | superseded
```

核心关系：

```yaml
Project owns Repository
Project contains Workflow
Project contains Document
Project records Decision
Project has_memory Memory
Project uses Concept
Project generalizes_to Principle
Project specializes Workflow
```

典型行为：

```text
当前 cwd = /Users/zhaochao/code/project/roleMe
-> 识别 Project(roleme)
-> 优先召回 roleMe 项目 workflow 和项目 memory
-> 再补充通用 workflow / 通用原则
```

### Evidence / Trust Graph

Evidence / Trust Graph 负责降低知识错误风险。它不替代判断，但为路由和回答提供可靠性信号。

核心节点：

```yaml
Evidence:
  id: string
  title: string
  source_type: user_statement | document | code | test | commit | model_summary | external
  source_path: string?
  quote: string?
  summary: string
  created_at: string
  last_verified_at: string?
  confidence: high | medium | low
  status: active | stale | invalidated

Source:
  id: string
  path: string?
  url: string?
  source_type: user_statement | document | code | test | commit | model_summary | external
  authority: primary | secondary | inferred
```

核心关系：

```yaml
Knowledge evidenced_by Evidence
Rule evidenced_by Evidence
Workflow evidenced_by Evidence
Evidence verified_by Test
Evidence invalidated_by Evidence
Knowledge contradicts Knowledge
Knowledge supersedes Knowledge
Knowledge scoped_to Project
```

典型行为：

```text
召回旧 workflow
-> 发现它被新 workflow supersedes
-> 不加载旧正文，改加载新 workflow
```

```text
召回某条方法论
-> confidence = low 且 source_type = model_summary
-> 可以作为辅助线索，但不能作为强规则覆盖用户当前指令
```

### Concept / Topic Graph

Concept / Topic Graph 负责提升命中率，尤其处理用户表达和知识名称不一致的问题。

核心节点：

```yaml
Concept:
  id: string
  title: string
  aliases: string[]
  summary: string
  keywords: string[]
  domain: string
  status: active | deprecated | superseded

Topic:
  id: string
  title: string
  path: string
  summary: string
  keywords: string[]

Alias:
  id: string
  value: string
  normalized: string
```

核心关系：

```yaml
Alias alias_of Concept
Concept related_to Concept
Concept maps_to Workflow
Concept maps_to Rule
Concept mentioned_by File
Topic covers Concept
Workflow applies_to Concept
Rule applies_to Concept
```

典型行为：

```text
用户说“大脑加载慢、知识命中率低、知识错误”
-> 命中 Concept(progressive disclosure)
-> 命中 Concept(context routing)
-> 命中 Concept(graph recall)
-> 命中 Concept(evidence check)
-> 再连接到 workflow、rule、file
```

## 实现边界

本设计的长期目标覆盖记录、召回、可信度和演化治理，但第一阶段必须收窄到可验证的最小闭环。

第一阶段只实现：

```text
Project
Workflow
Rule
Evidence
Concept
File
```

第一阶段只实现这些关系：

```text
belongs_to
applies_to
depends_on
specializes
supersedes
evidenced_by
mentions
related_to
```

第一阶段不实现：

```text
Memory / Principle Graph 的完整写入
Topic Graph 的通用语义网络
Source 节点和外部来源权威评分
复杂冲突解释
项目局部独立 graph.jsonl
全量历史 markdown 自动抽取
向量召回
```

这样设计后，用户能先获得最直接的收益：

```text
更准地命中通用 workflow 和项目 workflow
避免废弃或被替代的 workflow 误入上下文
让 workflow 的来源和依赖规则有结构化记录
graph 损坏时仍能回退现有路由
```

## 用户复杂度边界

Graph 是内部机制，不应增加用户日常使用负担。

用户仍然通过现有入口使用 `roleMe`：

```text
/roleMe <角色名>
自然语言归档
workflow 归档
doctor
optimize
```

用户不需要理解或手动维护：

```text
nodes.jsonl
edges.jsonl
Evidence
Concept alias
trust_filter
graph_expand
```

当 graph 影响行为时，系统只在必要时用自然语言说明结果，例如：

```text
已命中当前项目 workflow。
旧 workflow 已被新 workflow 替代，已改用新版本。
这条规则缺少证据，只作为辅助参考。
```

## 统一 Schema

第一阶段节点遵循统一基础结构，类型专属字段放入 `metadata`。远景类型只在设计说明中保留，不进入 v1 schema 校验。

```yaml
node:
  id: string
  type: Project | Workflow | Rule | Evidence | Concept | File
  title: string
  summary: string
  path: string?
  scope: role | global | project
  project_slug: string?
  keywords: string[]
  aliases: string[]
  status: active | draft | stale | deprecated | superseded | invalidated | archived
  confidence: high | medium | low
  created_at: string
  updated_at: string
  metadata: object
```

```yaml
edge:
  id: string
  from: string
  to: string
  type: belongs_to | applies_to | depends_on | specializes | supersedes | evidenced_by | mentions | related_to
  weight: number
  rationale: string
  created_at: string
  metadata: object
```

约束：

- `id` 必须稳定
- 有 `path` 的节点，`id` 由 `type + scope + project_slug + normalized_path` 派生
- 无 `path` 的概念节点，`id` 由 `type + normalized_title` 派生
- 有正文的节点必须提供 `path`
- `Workflow`、`Rule` 被提升为强上下文前，优先使用带 `evidenced_by` 的节点
- v1 中缺少 evidence 不阻断加载，但会降低 trust score
- v2 起，新归档的 workflow 必须创建 Evidence
- `deprecated`、`superseded`、`invalidated` 节点默认不进入强上下文
- `supersedes` 关系优先级高于普通相似度命中
- `project` scope 节点必须带 `project_slug`

## 写入协议

图谱写入必须是 markdown 写入的结构化伴随动作，而不是替代动作。

### 一致性规则

markdown 和 graph 的权威边界如下：

```text
markdown 是正文权威：流程步骤、规则正文、项目说明、记忆正文以 markdown 为准
graph 是路由和可靠性权威：status、confidence、supersedes、evidenced_by 以 graph 为准
```

当两者冲突时：

```text
router 以 graph 状态为准
doctor 必须报告冲突
optimize 可以生成修复建议
不得静默忽略冲突
```

写入顺序固定为：

```text
1. 写正文 markdown 文件
2. 更新 markdown index
3. upsert graph node / edge
4. 运行轻量一致性校验
5. 返回写入结果
```

任一步失败时，不应伪装为成功。返回结果必须能表达 partial state，例如：

```text
markdown_written: true
index_updated: true
graph_updated: false
doctor_warnings: [...]
```

第一阶段不要求真正事务回滚，但必须保证重复执行同一次归档操作是幂等的。

### 归档通用 workflow

```text
写 brain/workflows/<workflow>.md
更新 brain/workflows/index.md
upsert Workflow node(scope=global)
upsert Concept nodes
upsert applies_to / depends_on / evidenced_by edges
```

### 归档项目 workflow

```text
写 projects/<project>/workflows/<workflow>.md
更新 projects/<project>/workflows/index.md
upsert Project node
upsert Workflow node(scope=project, project_slug=<project>)
upsert belongs_to / specializes / depends_on / evidenced_by edges
```

### 后续扩展：归档长期偏好

```text
写 memory/USER.md
upsert Preference node
upsert evidenced_by edge
必要时连接 applies_to Workflow 或 applies_to Concept
```

### 后续扩展：归档长期结论或方法论

```text
写 memory/MEMORY.md 或 brain/topics/<topic>.md
upsert Principle / Concept / Topic node
upsert derived_from / evidenced_by / supports edges
```

### 后续扩展：归档项目经验

```text
写 projects/<project>/memory.md 或 memory/episodes/<episode>.md
upsert Memory / Episode node
连接 Project
如果经验可复用，建立 generalizes_to Principle
如果影响流程，建立 supports Workflow
```

## 读取协议

`context_router.py` 后续读取流程应从线性索引路由升级为图谱增强路由：

```text
build_frozen_snapshot()
-> 加载 resident 层和轻量 graph summary

graph_recall(query)
-> 从 Concept / Workflow / Project / Rule / File 找候选节点

graph_expand(nodes)
-> 沿 applies_to / depends_on / specializes / evidenced_by 扩展 1-2 跳

trust_filter(nodes)
-> 排除 deprecated / superseded / invalidated
-> 标记 low confidence / stale

paths_from_nodes(nodes)
-> 转成 markdown path

assemble_snapshot(paths)
-> 按预算加载正文
```

优先级：

```text
1. 当前项目 Project 节点
2. 当前项目 Workflow 节点
3. 当前项目 workflow 依赖的 Rule / Evidence
4. 通用 Workflow 节点
5. 通用 Concept / Rule
6. 普通 brain/project/memory fallback
```

未命中图谱时，系统必须回退现有 `discover_context_paths()` 逻辑。

### v1 排序规则

图谱召回应使用确定性评分，避免实现随意导致命中不稳定。

第一阶段建议评分：

```text
score =
  text_match * 3
  + alias_match * 4
  + current_project_bonus * 5
  + workflow_scope_bonus
  + evidence_confidence_bonus
  - stale_penalty
  - low_confidence_penalty
```

硬过滤：

```text
invalidated: block
superseded: block unless user asks history
deprecated: block unless user asks history
missing_path for path-backed node: block and doctor warning
```

推荐加分：

```text
current_project_bonus: 当前 cwd 对应项目命中
workflow_scope_bonus: project workflow 高于 global workflow
evidence_confidence_bonus: high > medium > low
```

当第一名和第二名分差过小时，系统应回退旧路由或请求澄清，而不是强行加载错误 workflow。

## 错误知识处理

知识错误主要来自四类情况：

- 知识过期
- 知识被替代
- 知识之间冲突
- 低置信度模型总结被当作强规则

图谱层通过以下字段和关系控制风险：

```yaml
status: active | stale | deprecated | superseded | invalidated
confidence: high | medium | low
last_verified_at: string?
source_type: user_statement | document | code | test | commit | model_summary | external
```

处理规则：

- `invalidated` 节点不得进入上下文
- `superseded` 节点只作为历史背景，不作为执行依据
- `deprecated` 节点默认不加载，除非用户明确询问历史
- `stale` 节点可加载，但应降低排序
- `low` confidence 节点只能作为辅助，不可覆盖用户明确要求
- 后续引入 `contradicts` 关系后，应优先加载双方摘要和证据，而不是静默选择其一
- 存在 `supersedes` 关系时，应优先选择较新的 active 节点

## 与现有模块的集成

### `tools/graph_index.py`

新增模块，负责：

- 读取和写入 `brain/graph/schema.yaml`
- 追加或更新 `nodes.jsonl`、`edges.jsonl`
- 按 type/path/alias 构建轻量索引
- 提供 `upsert_node()`、`upsert_edge()`、`load_graph()`、`query_nodes()` 等确定性 API

### `tools/context_router.py`

增强模块，负责：

- 在现有 workflow 路由前尝试 `graph_recall(query)`
- 将命中的节点转换成 path
- 对 `superseded`、`deprecated`、`invalidated` 节点做过滤
- 未命中时回退现有 discover 逻辑

### `tools/role_ops.py`

增强模块，负责：

- workflow 归档时写入 graph
- 项目自动 bootstrap 时补齐 Project 节点，并可在 metadata 中记录仓库路径
- doctor 检查 graph schema、孤儿边、失效 path、重复节点

### `tools/memory.py`

增强模块，负责：

- v1 不改变 `USER.md`、`MEMORY.md`、episode 的写入行为
- 后续扩展时，可在写记忆时补充 Memory / Preference / Principle / Evidence 节点
- build frozen snapshot 时只加入轻量 graph summary，不加入完整 graph

### `tools/workflow_index.py`

保持现有职责：

- `workflows/index.md` 仍是人类可读索引
- graph 是结构化索引
- 两者应由同一次归档操作保持一致

## 第一阶段实现范围

虽然完整设计覆盖多类知识对象，但第一阶段只实现 Workflow Graph 最小闭环：

节点类型：

```text
Project
Workflow
Rule
Evidence
Concept
File
```

关系类型：

```text
belongs_to
applies_to
depends_on
specializes
supersedes
evidenced_by
mentions
related_to
```

第一阶段覆盖：

- 通用 workflow 图谱化
- 项目 workflow 图谱化
- 当前 cwd 到 Project 节点的识别
- query 到 Workflow / Concept 的召回
- workflow 依赖 Rule 的扩展
- `deprecated` / `superseded` workflow 过滤
- graph 未命中时回退现有路由

第一阶段暂不覆盖：

- `Preference`、`Principle`、`Decision`、`Memory`、`Episode`、`Source`、`Topic`、`Alias` 的 schema 校验和写入
- 全量历史 markdown 自动抽取
- 项目局部独立 `graph.jsonl`
- 复杂冲突解释
- 外部来源可信度评分
- 向量召回

## 测试策略

### Schema 测试

- `schema.yaml` 能被解析
- 所有节点类型和边类型在 schema 中声明
- `project` scope 节点缺少 `project_slug` 时校验失败
- 有正文的节点 path 不存在时 doctor 报告 warning

### 写入测试

- 归档通用 workflow 后创建 Workflow 节点和 `applies_to` 边
- 归档项目 workflow 后创建 Project 节点、Workflow 节点和 `belongs_to` 边
- 重复归档同一 workflow 不产生重复节点
- `supersedes` 新 workflow 后，旧 workflow 状态变为 `superseded`

### 召回测试

- 用户使用不同说法描述同一任务，能命中同一个 Workflow
- 当前项目 workflow 优先于通用 workflow
- 当前项目无匹配 workflow 时回退通用 workflow
- Concept alias 能把“大脑加载慢”映射到 context routing / graph recall 相关节点

### 可靠性测试

- `deprecated` workflow 不进入默认上下文
- `superseded` workflow 被新 workflow 替代
- `invalidated` Evidence 不支持强规则
- `low` confidence Rule 排序低于 `high` confidence Rule

### 回归测试

- graph 文件不存在时，现有 `discover_context_paths()` 行为不变
- graph 命中为空时，仍能通过 `brain/index.md`、`projects/index.md` 回退
- resident snapshot 不加载完整 graph
- `workflow_index.py` 现有解析和渲染测试继续通过

## 迁移策略

第一阶段采用增量迁移：

1. 新增 `brain/graph/schema.yaml`
2. 新归档的 workflow 自动写 graph
3. doctor 提供“发现未入图 workflow”的报告
4. optimize 后续可把已有 workflow index 批量转成 graph 节点
5. 旧角色包没有 graph 时继续使用现有渐进式披露逻辑

迁移过程中，markdown 文件仍是权威正文；graph 只作为结构化索引和可靠性元数据。

## 验收标准

设计完成后的实现应满足：

- 同一个 workflow 可以被自然语言、alias、concept 和项目上下文共同召回
- 项目 workflow 优先于通用 workflow
- workflow 命中后能加载依赖 Rule 和必要 Evidence
- 被替代或废弃的 workflow 不会误入默认上下文
- graph 不存在或损坏时，不影响现有角色加载和普通路由
- 新的归档写入能同时保持 markdown index 和 graph index 一致
- doctor 能发现孤儿边、失效 path、重复节点和 schema 不匹配

## 后续规划

第一阶段完成 Workflow Graph 最小闭环后，再逐步扩展：

1. Memory / Principle 能力：把稳定偏好、方法论、项目经验结构化
2. Evidence / Trust 能力：加强冲突、过期、来源和验证状态处理
3. Concept / Topic 能力：扩大 alias、topic、concept 的召回覆盖
4. Project 能力：支持项目局部图谱和跨项目经验提升
5. optimize / doctor：处理重复、孤儿边、过时摘要和 resident/on-demand 边界漂移

最终目标不是让图谱变成新的大杂烩，而是让 `roleMe` 的上下文系统做到：

```text
写入时可沉淀
读取时能命中
回答时有证据
演化时可治理
```
