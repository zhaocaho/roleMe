# roleMe Ontology-Inspired Context Graph 设计文档

日期：2026-04-21  
状态：完整设计，待实现规划

## 概述

`roleMe` 当前已经具备稳定的角色包结构：

- `persona/`：保存人物自述、沟通风格、决策规则和披露边界
- `memory/`：保存长期偏好、长期结论和 episode
- `brain/`：保存通用知识、主题和通用 workflow
- `projects/`：保存项目上下文、项目记忆和项目 workflow
- `context_router.py`：根据用户 query 做渐进式上下文发现

这套结构解决了“不要一次性加载全部上下文”的问题，但长期使用会出现三个更深层的问题：

- **加载效率低**：上下文发现依赖线性索引和逐层 markdown 链接，路径偏长
- **知识命中率低**：用户表达和知识文件标题、关键词、索引写法不一致时，容易漏掉真正相关内容
- **知识错误风险**：旧规则、过期 workflow、低置信度总结、项目经验和通用原则之间的冲突缺少结构化判断

本设计引入一套面向智能体消费的 **Ontology-Inspired Context Graph**。它借鉴 ontology 的实体、关系、类型约束和证据思想，但不采用传统 OWL/RDF/推理机架构；它是 roleMe 本地角色包内的一套结构化上下文索引、归档和可信度治理机制。

一句话概括：

```text
roleMe 继续用 markdown 保存正文，
用 Ontology-Inspired Context Graph 管理“它是什么、从哪里来、适用于哪里、和什么有关、现在是否可信”。
```

## 目标

- 用一套 Context Graph Core 统一管理 workflow、记忆、项目经验、规则、决策、概念、主题、证据和文件
- 支持 Archive 能力：归档时同时写 markdown 正文和 graph 节点/关系
- 支持 Recall 能力：使用时从 query 命中相关节点，再展开必要 markdown 正文
- 支持 Trust 能力：通过来源、状态、置信度、替代、冲突和证据关系降低知识错误
- 保持渐进式披露原则，只加载本次任务所需的正文文件
- 保持 markdown 作为正文权威，Graph 作为路由、关系和可靠性元数据权威
- 保持本地优先、可导出、可测试，不依赖外部图数据库、向量数据库或在线 ontology 服务
- 与现有 `brain/workflows/index.md`、`projects/<project>/workflows/index.md`、`memory/USER.md`、`memory/MEMORY.md` 等结构兼容

## 非目标

- 不用 RDF、OWL、SPARQL 或外部图数据库实现
- 不把 Graph 当作正文存储，正文仍保存在现有 markdown 文件中
- 不把完整 Graph 预加载进 resident snapshot
- 不让用户直接维护 `nodes.jsonl`、`edges.jsonl` 或内部索引
- 不把低置信度模型总结自动提升为长期规则
- 不让 Graph routing 成为唯一入口；Graph 不可用时必须能回退现有渐进式披露逻辑

## 核心定位

`ai-digital-avatar` skill 中的 ontology 设计提供了有价值的参考：

- 用 `schema.yaml` 定义实体和关系
- 用 `graph.jsonl` 做本地结构化记录
- 在工作流完成后写入 `Document`、`Decision`、`Knowledge` 等实体
- 把 ontology 作为工作流产物和记忆系统的一部分

但 `roleMe` 的目标不只是记录事实和产物，还要服务上下文加载、知识命中和知识可信度治理。因此本设计不是传统 ontology 平台，也不是纯搜索索引，而是：

```text
轻量本体建模 + 本地结构化索引 + 上下文召回 + 证据可信度治理
```

## 一套 Core，三类能力

本设计只有一套 Context Graph Core。Archive、Recall、Trust 是三类能力视角，不是三套存储，也不是三套路由系统。

```text
Archive：写入和沉淀
  workflow、记忆、项目经验、决策、主题知识、证据、文件关系

Recall：读取和命中
  query -> 节点 -> 关系扩展 -> 文件路径 -> markdown 正文

Trust：校验和治理
  来源、置信度、状态、过期、冲突、替代、证据
```

`Workflow`、`Project`、`Rule`、`Memory`、`Concept` 等都是节点类型或领域对象，不是独立图谱。后续设计和实现不得以这些领域名拆出新的图谱层。

## 存储结构

Graph 存储在角色包内：

```text
brain/graph/
├── schema.yaml
├── nodes.jsonl
├── edges.jsonl
└── indexes/
    ├── by-type.json
    ├── by-path.json
    ├── by-alias.json
    └── by-project.json
```

文件职责：

```text
schema.yaml    声明节点类型、边类型、状态、字段和校验规则
nodes.jsonl    当前节点状态，每行一个 node，不做事件日志
edges.jsonl    当前边状态，每行一个 edge，不做事件日志
indexes/*      派生索引，可删除重建，不是权威数据源
```

版本边界：

```text
schema.yaml 必须声明 graph_schema_version
nodes.jsonl / edges.jsonl 中的每个 node / edge 对象必须带 schema_version
indexes/* 必须带 index_version；版本不匹配时直接重建
role.json 的 schemaVersion 仍表示角色包版本，不替代 Graph schema 版本
```

JSONL 文件不使用文件头或混合 metadata 行，保持“每行一个 node / edge 对象”的解析模型。若未来需要表达 Graph 数据集级别元信息，应新增 `brain/graph/manifest.json`，不得把 manifest 混入 nodes / edges JSONL。

正文仍保存在现有 markdown 结构中：

```text
brain/workflows/*.md
brain/topics/*.md
projects/<project>/workflows/*.md
projects/<project>/memory.md
memory/USER.md
memory/MEMORY.md
memory/episodes/*.md
```

权威边界：

```text
markdown 是正文权威：
  流程步骤、规则正文、项目说明、记忆正文以 markdown 为准

Graph 是路由、关系和可靠性元数据权威：
  status、confidence、supersedes、contradicts、evidenced_by、derived_from 以 Graph 为准

indexes/* 是缓存：
  可删除，可重建，不作为权威来源
```

状态和变更来源边界：

```text
nodes.jsonl / edges.jsonl 保存当前状态
Evidence / Episode 保存状态变更、知识提升、替代和失效的来源
```

任何会改变知识生命周期的操作，例如 `supersedes`、`invalidated_by`、`promoted_to`、`generalizes`，都必须保留 `Evidence` 或 `Episode` 来源，避免当前状态覆盖历史依据。

## 完整节点模型

所有节点都遵循统一基础结构，类型专属字段放入 `metadata`。

```yaml
node:
  id: string
  type: Project | Workflow | Rule | Preference | Principle | Memory | Episode | Decision | Evidence | Concept | Topic | File
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

`metadata` 中允许放类型专属字段，但以下字段具有跨类型约束：

```yaml
metadata:
  entry_key: string?  # entry-backed 节点必填
```

`Preference`、`Principle`、`Memory`、`Decision` 等从共享 markdown 文件中的条目抽取时，必须使用 entry-backed 节点，并写入稳定的 `metadata.entry_key`。用户不需要感知 `entry_key`，它只用于内部去重、更新和迁移。

### Project

表示一个 roleMe 项目上下文，通常对应 `projects/<project>/` 和某个仓库。

```yaml
Project:
  type: Project
  scope: project
  project_slug: string
  path: projects/<project>/context.md
  metadata:
    repo_path: string?
```

### Workflow

表示通用 workflow 或项目 workflow。

```yaml
Workflow:
  type: Workflow
  scope: global | project
  project_slug: string?
  path: brain/workflows/<workflow>.md | projects/<project>/workflows/<workflow>.md
  metadata:
    applies_to: string
```

### Rule

表示稳定协作规则、执行约束或 workflow 依赖规则。

```yaml
Rule:
  type: Rule
  scope: role | global | project
  path: string?
  metadata:
    rule_kind: collaboration | git | testing | archive | workflow | safety
```

### Preference

表示用户长期偏好，通常来源于 `memory/USER.md`。

```yaml
Preference:
  type: Preference
  scope: role | project
  path: memory/USER.md | projects/<project>/memory.md
  metadata:
    preference_kind: language | communication | workflow | git | tooling | other
```

### Principle

表示长期有效的方法论、工程原则或可复用结论，通常来源于 `memory/MEMORY.md`、项目复盘或主题知识。

```yaml
Principle:
  type: Principle
  scope: role | global | project
  path: memory/MEMORY.md | brain/topics/<topic>.md | projects/<project>/memory.md
  metadata:
    principle_kind: engineering | product | agent | workflow | testing | other
```

### Memory

表示长期记忆条目或项目记忆条目。

```yaml
Memory:
  type: Memory
  scope: role | project
  path: memory/USER.md | memory/MEMORY.md | projects/<project>/memory.md
  metadata:
    memory_type: user | memory | project_memory
```

### Episode

表示一次具体会话、复盘或待沉淀原始片段。

```yaml
Episode:
  type: Episode
  scope: role | project
  path: memory/episodes/<episode>.md
  metadata:
    episode_kind: conversation | review | project_retro | archive_source
```

### Decision

表示明确形成的决策。

```yaml
Decision:
  type: Decision
  scope: role | global | project
  path: string?
  metadata:
    decided_at: string
    rationale: string
    alternatives: string[]
```

### Evidence

表示某个节点或关系的来源和可信度依据。

`Source` 不作为独立节点。来源信息统一内嵌在 `Evidence.metadata` 中，避免把来源模型拆成额外层级。

```yaml
Evidence:
  type: Evidence
  scope: role | global | project
  path: string?
  metadata:
    source_type: user_statement | document | code | test | commit | model_summary | external
    source_path: string?
    quote: string?
    last_verified_at: string?
```

### Concept

表示用于召回的语义概念，比如 `progressive disclosure`、`context routing`、`TDD`、`workflow governance`。

```yaml
Concept:
  type: Concept
  scope: role | global | project
  path: string?
  aliases: string[]
  keywords: string[]
  metadata:
    domain: string?
```

### Topic

表示主题知识入口，通常对应 `brain/topics/<topic>.md`。

```yaml
Topic:
  type: Topic
  scope: global | project
  path: brain/topics/<topic>.md
  metadata:
    topic_kind: method | domain | project | technical | product
```

### File

表示可被加载的 markdown 文件或关键文档。

`File` 只用于没有更强语义类型的文件。如果某个文件已经被建模为 `Workflow`、`Topic`、`Memory`、`Episode` 等语义节点，则不再为同一路径创建额外 `File` 节点，避免同一个 path 出现多份状态。

```yaml
File:
  type: File
  scope: role | global | project
  path: string
  metadata:
    file_kind: workflow | topic | memory | episode | project_context | project_memory | spec | plan | doc
```

## 完整关系模型

所有边都遵循统一结构。

```yaml
edge:
  id: string
  from: string
  to: string
  type: belongs_to | contains | applies_to | depends_on | specializes | generalizes | supersedes | evidenced_by | derived_from | promoted_to | supports | contradicts | mentions | related_to | covers | records | invalidated_by | verifies
  weight: number
  rationale: string
  created_at: string
  metadata: object
```

核心关系语义：

```text
belongs_to       节点属于某项目或作用域
contains         项目或主题包含某对象
applies_to       workflow/rule/preference 适用于某概念或场景
depends_on       workflow 依赖某规则、概念或前置条件
specializes      项目 workflow 特化通用 workflow
generalizes      项目经验上升为通用原则
supersedes       新节点替代旧节点
evidenced_by     节点由证据支撑
derived_from     节点从 episode、memory、decision 或 document 提炼而来
promoted_to      低层记忆被提升为原则、偏好或 workflow
supports         规则、原则或证据支持某 workflow/decision
contradicts      两个节点存在冲突
mentions         文件提到某概念或对象
related_to       弱相关关系，只用于辅助召回
covers           topic 覆盖 concept
records          file/memory/episode 记录 decision/evidence
invalidated_by   证据或决策使某节点失效
verifies         test/code/commit 验证某证据或规则
```

## ID、路径和状态规则

### ID 规则

ID 必须可重复生成，避免标题变化导致重复节点。

```text
path-backed node:
  id = stable_hash(type + scope + project_slug + normalized_path)

entry-backed node:
  id = stable_hash(type + scope + project_slug + normalized_path + entry_key)

concept-like node without path:
  id = stable_hash(type + scope + project_slug + normalized_title)

edge:
  id = stable_hash(from + type + to)
```

默认采用单边模型：同一个 `from + type + to` 只能存在一条边。重复写入同一关系时，Archive 应合并或更新 `weight`、`rationale`、`metadata`，不得生成多条等价边。

如果未来确实需要表达同一对节点之间的多条不同语义关系，必须显式增加 `metadata.qualifier` 或类似字段，并同步升级 edge id 规则；在本设计中不默认启用多边模型。

`entry-backed node` 用于多个知识条目共享同一个 markdown 文件的场景，例如：

```text
memory/USER.md 中的多条 Preference
memory/MEMORY.md 中的多条 Principle
projects/<project>/memory.md 中的多条 Memory
同一个 episode 文件中抽取出的多个 Decision
```

`entry_key` 可由以下来源生成：

```text
显式 block id
heading path
归档时生成的 entry slug
markdown marker 内条目内容 hash
```

`entry_key` 的稳定性优先级为：

```text
显式 block id > heading path > 归档生成 entry slug > 内容 hash
```

内容 hash 只能作为导入旧条目、没有稳定定位信息时的兜底来源。用户后续编辑条目正文时，不得因为内容 hash 变化而静默创建新的 active 节点；实现必须通过 replace、supersedes 或重新绑定 entry_key 的流程处理旧节点。

没有 `entry_key` 时，不得为同一 path 内的多条内容创建多个同类型节点。doctor 必须报告 entry-backed 类型缺少 `metadata.entry_key` 的节点，避免同一文件内的多条偏好、原则、记忆或决策被错误合并。

新 Archive 产生的 entry-backed 条目必须把稳定定位信息写回 markdown 正文，例如使用显式 block id、heading path 或内部 markdown marker。该 marker 是后台约束，用户不需要理解或维护；普通对话、普通归档和普通编辑方式不改变。旧条目在 optimize 回填时如果无法稳定定位，只报告建议，不强行迁移为 active 节点，也不依赖内容 hash 建立长期 active 绑定。

### 路径规则

```text
使用 role_path 内相对路径
统一 POSIX 分隔符
去掉前导 ./
不保留绝对路径
绝对路径只允许放 metadata.repo_path 等非路由字段
```

### 状态规则

```text
active       当前有效
draft        草稿，不进入强上下文
stale        可能过期，可低权重召回
deprecated   已不推荐，默认不加载
superseded   已被替代，默认不加载
invalidated  已失效，不得进入上下文
archived     历史归档，仅用户询问历史时使用
```

### 置信度规则

```text
high    用户明确确认、权威文档、测试或代码支撑
medium  多次一致经验、项目复盘、稳定模型总结但证据不完整
low     单次模型总结、未确认推断、来源不完整
```

低置信度节点可以参与召回，但不得覆盖用户当前明确要求。

## Archive 写入协议

Archive 是写入和沉淀能力。任何归档都应先写 markdown 正文，再写 Graph 节点和关系。

写入顺序：

```text
1. 写正文 markdown 文件
2. 更新对应 markdown index
3. 读取 nodes.jsonl / edges.jsonl 当前状态
4. upsert node / edge 到内存结构
5. 原子重写 nodes.jsonl / edges.jsonl
6. 重建 indexes/*
7. 运行轻量一致性校验
8. 返回写入结果
```

失败返回必须表达 partial state：

```yaml
markdown_written: true
index_updated: true
graph_updated: false
doctor_warnings:
  - "graph write failed"
```

Archive 结果类型必须能表达分段状态，不能只返回写入路径：

```yaml
archive_result:
  written_paths: string[]
  markdown_written: boolean
  index_updated: boolean
  graph_updated: boolean
  graph_skipped: boolean
  requires_reload: boolean
  doctor_warnings: string[]
```

现有 `WorkflowArchiveResult` 可以兼容保留，但内部归档流程应使用更完整的 `ArchiveResult` 或等价结构。所有 workflow、memory、episode、project bootstrap 和 topic archive 入口都必须能返回或记录 partial state。

调用层不得吞掉 partial state。任何自然语言归档、workflow 归档或项目 bootstrap 入口收到 `index_updated=false`、`graph_updated=false` 或非空 `doctor_warnings` 时，都必须在后台保留结构化结果，并在用户回执中用简短语言说明“正文已写入，但后台索引/Graph 未完全同步”。不得在 Graph 写入失败时只返回“已归档”这类完整成功回执。该提示只说明后台同步状态，不要求用户理解或手动维护 Graph。

文件写入要求：

```text
写入临时文件
fsync 可用时刷新文件
atomic rename 替换目标文件
任何失败都不得留下半行 JSON
```

原子写不得散落在各模块中重复实现。实现必须提供公共文件操作层，例如：

```text
atomic_write_text(path, content)
atomic_rewrite_jsonl(path, records)
atomic_write_json(path, payload)
```

`memory.py`、`workflow_index.py`、`role_ops.py` 和 `graph_index.py` 写关键文件时必须通过公共原子写 API。测试需要覆盖写入失败时不留下半行 JSON、不破坏已有正文、不产生损坏索引。

并发假设：

```text
默认单进程写入
如果后续支持并发 automation 写入，再引入文件锁
```

### 归档项目 workflow

```text
写 projects/<project>/workflows/<workflow>.md
更新 projects/<project>/workflows/index.md
upsert Project
upsert Workflow(scope=project)
upsert Evidence
upsert Workflow belongs_to Project
upsert Workflow applies_to Concept
upsert Workflow evidenced_by Evidence
```

### 归档通用 workflow

```text
写 brain/workflows/<workflow>.md
更新 brain/workflows/index.md
upsert Workflow(scope=global)
upsert Concept
upsert Evidence
upsert Workflow applies_to Concept
upsert Workflow evidenced_by Evidence
```

### 归档长期偏好

```text
写 memory/USER.md
upsert Preference
upsert Evidence
upsert Preference evidenced_by Evidence
必要时 upsert Preference applies_to Concept
```

### 归档长期原则

```text
写 memory/MEMORY.md 或 brain/topics/<topic>.md
upsert Principle
upsert Concept / Topic
upsert Evidence
upsert Principle evidenced_by Evidence
必要时 upsert Principle supports Workflow
```

### 归档项目经验

```text
写 projects/<project>/memory.md 或 memory/episodes/<episode>.md
upsert Project
upsert Memory 或 Episode
upsert Evidence
upsert Memory belongs_to Project
必要时 upsert Memory promoted_to Principle
必要时 upsert Project generalizes Principle
```

### 归档决策

```text
写 memory/episodes/<episode>.md 或项目 memory
upsert Decision
upsert Evidence
upsert Decision evidenced_by Evidence
必要时 upsert Decision supersedes Decision
必要时 upsert Decision applies_to Concept
```

### 归档主题知识

```text
写 brain/topics/<topic>.md
更新 brain/index.md
upsert Topic
upsert Concept
upsert Topic covers Concept
```

主题文档本身已经由 `Topic` 表达，不再为同一路径额外创建 `File` 节点。只有外部补充文档、规格、计划或普通 markdown 没有更强语义类型时，才创建 `File`，并可建立 `File mentions Concept`。

## Recall 读取协议

Recall 是上下文召回能力。Graph 只负责找候选节点和 path，正文仍由 markdown 按需加载。

Graph Recall 内部不得只返回 `list[str]`。为了保留 Trust 和召回决策信息，内部结果至少需要包含候选节点、路径、分数、召回层级和状态标记：

```yaml
ContextCandidate:
  node_id: string
  path: string?
  score: number
  recall_strength: strong | weak
  status: active | stale | deprecated | superseded | invalidated | archived
  confidence: high | medium | low
  reasons: string[]
  trust_flags:
    - stale
    - low_confidence
    - contradicted
    - superseded

GraphRecallResult:
  candidates: ContextCandidate[]
  fallback_required: boolean
  warnings: string[]
```

`discover_context_paths()` 可以继续作为对外兼容接口返回 path list，但必须由内部 `GraphRecallResult` 经 trust filter、弱召回 gate 和 fallback 合并后再压平成 path，避免在进入 `build_context_snapshot()` 前丢失可信度信息。

Graph Recall 是后台增强，不改变用户自然表达任务的方式。用户不需要知道节点、边、分数、强弱召回或 Graph 开关；只有当后台发现高风险冲突、多个 workflow 分差过小，或低置信知识会影响重要行为时，才用自然语言询问用户确认。

流程：

```text
build_frozen_snapshot()
-> 加载 resident 层，不加载完整 graph

graph_recall(query)
-> 从 Project / Workflow / Rule / Preference / Principle / Memory / Decision / Concept / Topic / File 找候选节点

graph_expand(nodes)
-> 沿 applies_to / depends_on / specializes / evidenced_by / derived_from / supports / covers 扩展 1-2 跳

trust_filter(nodes)
-> 排除 invalidated / deprecated / superseded
-> 降低 stale / low confidence 权重
-> 标记 contradicts / supersedes

paths_from_nodes(nodes)
-> 转成 markdown path

assemble_snapshot(paths)
-> 按 max_chars 预算加载正文
```

优先级：

```text
1. 当前项目 Project
2. 当前项目 Workflow
3. 当前项目 Workflow 依赖的 Rule / Preference / Principle
4. 通用 Workflow
5. 通用 Rule / Preference / Principle / Concept / Topic
6. 相关 Memory / Episode / Decision
7. 普通 brain/project/memory fallback
```

默认召回分层：

```text
强召回：
  Project / Workflow / Rule / Preference / Principle / Concept

弱召回：
  Memory / Episode / Decision / Topic / File
```

弱召回节点默认只作为补充候选。只有在以下场景才展开：

```text
强召回不足
用户询问历史或来源
需要解释冲突
需要验证某条规则或结论
需要从项目经验回溯证据
```

优先级排序只在节点通过强/弱召回 gate 后生效。弱召回未触发时，`Memory`、`Episode`、`Decision`、`Topic`、`File` 不进入正文加载预算，避免普通对话被历史记录和弱相关材料干扰。

异常回退：

```text
schema.yaml 缺失：跳过 graph，走旧路由
nodes.jsonl / edges.jsonl 不存在：跳过 graph，走旧路由
JSONL 解析失败：跳过 graph，doctor 报告 warning
索引文件缺失：从 nodes/edges 重建索引
索引文件损坏：丢弃并重建索引
命中节点 path 不存在：过滤该节点，doctor 报告 warning
```

索引重建触发：

```text
每次 Archive 写入后，重建受影响索引
doctor 发现索引损坏时，重建全部索引
context_router 发现索引缺失时，优先重建索引；如果重建失败，直接从 nodes/edges 查询或回退旧路由
```

预算规则：

```text
graph_recall 只返回 path 和轻量 metadata
assemble_snapshot 才读取 markdown 正文
graph 命中的正文仍受 max_chars 预算限制
Rule / Evidence 默认只加载摘要；只有需要解释冲突或来源时才展开正文
```

排序规则：

```text
score =
  text_match * 3
  + alias_match * 4
  + current_project_bonus * 5
  + workflow_scope_bonus
  + evidence_confidence_bonus
  + relationship_weight
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

当第一名和第二名分差过小时，系统应回退旧路由或请求澄清，而不是强行加载错误 workflow。

Graph 与旧 markdown 路由的候选合并规则：

```text
Graph 健康且 archive/routing 均开启：
  Graph 强候选优先，但必须合并旧 workflow index / brain index / project index 的强命中

Graph 缺失、损坏、schema 不兼容、索引重建失败：
  跳过 Graph，完全使用旧 markdown 路由

Graph 可能 stale：
  包括 ROLEME_GRAPH_ARCHIVE=0、Graph schema/index 版本落后、Graph 缺少最近写入标记或 doctor 报告 markdown 已写入但 Graph 缺失
  旧 markdown index 命中必须作为强候选参与排序
  Graph 不得单方面过滤掉新写入的 markdown 内容

Graph 命中与 markdown 命中冲突：
  active/high confidence Graph 节点可以提高候选排序
  但不得覆盖用户当前明确指令
  分差过小或冲突会影响重要执行路径时，询问用户确认
```

`discover_context_paths()` 最终仍只返回 path list，兼容现有调用方；trust flags、stale 标记和冲突原因在内部保留，用于决定是否询问、降权或回退。

## Trust 校验协议

Trust 是可靠性治理能力。它通过状态、置信度、证据、替代和冲突关系控制知识错误风险。

知识错误主要来自：

- 知识过期
- 知识被替代
- 知识之间冲突
- 低置信度模型总结被当作强规则
- 项目经验被错误提升为通用原则
- 一次性用户要求被错误提升为长期偏好

处理规则：

- 当前用户明确指令优先于 Graph 中的任何规则；如果用户指令与高置信规则冲突，系统应提示冲突并请求确认，而不是静默覆盖用户指令
- `invalidated` 节点不得进入上下文
- `superseded` 节点只作为历史背景，不作为执行依据
- `deprecated` 节点默认不加载，除非用户明确询问历史
- `stale` 节点可加载，但应降低排序
- `low` confidence 节点只能作为辅助，不可覆盖用户明确要求
- 存在 `contradicts` 关系时，应优先加载双方摘要和证据，而不是静默选择其一
- 存在 `supersedes` 关系时，应优先选择较新的 active 节点
- 从项目经验提升到通用原则时，必须保留 `derived_from` 或 `evidenced_by`

## 设计复核结论

### 节点模型复核

完整节点模型能覆盖 roleMe 的长期需求：

```text
Project / Workflow      支撑项目级和通用 workflow 治理
Rule / Preference       支撑稳定协作规则和用户偏好
Principle / Memory      支撑归纳总结、长期知识库和方法论沉淀
Episode / Decision      支撑原始上下文、复盘和决策追溯
Evidence                支撑来源、置信度和可靠性治理
Concept / Topic         支撑语义命中和主题知识组织
File                    支撑无语义类型文件的 path 召回
```

节点模型需要遵守三个边界：

```text
1. 多条记忆共用同一 markdown 文件时，必须使用 entry-backed node
2. File 只用于没有更强语义类型的文件，避免同 path 多状态
3. Source 不做独立节点，来源统一内嵌在 Evidence.metadata
```

在这些边界成立时，节点模型不会和未来结构冲突；它能支撑后续归纳总结、知识库、项目经验提升和 workflow 治理。

### Archive / Recall / Trust 协议复核

三类协议职责清晰：

```text
Archive 负责写入沉淀
Recall 负责查询命中
Trust 负责可靠性判断
```

关键约束是：

```text
markdown 是正文权威
Graph 是路由、关系和可靠性元数据权威
indexes/* 是可重建缓存
```

这样可以避免 Graph 接管正文，也避免 markdown index 和 Graph 状态互相覆盖。

主要风险集中在双写一致性，因此 Archive 必须保持：

```text
先写 markdown
再更新 markdown index
再 upsert Graph
再重建 indexes
再做一致性检查
```

如果 Graph 写入失败，系统必须返回 partial state，不能伪装成功。

### 强召回 / 弱召回复核

强弱召回分层是必要的，否则完整模型会带来上下文噪声。

默认强召回：

```text
Project / Workflow / Rule / Preference / Principle / Concept
```

默认弱召回：

```text
Memory / Episode / Decision / Topic / File
```

这保证日常任务优先命中“当前该怎么做”，而不是动辄展开历史 episode 或大量主题知识。弱召回只在来源追溯、冲突解释、历史询问和证据验证时展开。

该分层不会削弱知识库能力，因为弱召回节点仍然存在于 Graph 中，只是默认不进入强上下文。

## 运行时使用体验

用户不会直接“使用 Context Graph”。用户仍然自然表达任务、归档经验、维护角色包；Context Graph 只在内部承担 Archive、Recall 和 Trust 职责。

### 加载角色

用户执行：

```text
/roleMe zhaochao
```

系统行为：

```text
加载 resident snapshot
加载 USER / MEMORY / persona
加载当前项目 workflow summaries
检查 brain/graph 是否存在且 schema 可解析
不把完整 nodes/edges 放入 resident snapshot
```

### 发起任务

用户可以自然表达：

```text
开始开发这个需求
帮我把这个设计拆成实现计划
按这个项目的方式继续
```

系统内部流程：

```text
识别当前 cwd 对应的 Project
强召回 Project / Workflow / Rule / Preference / Principle / Concept
trust_filter 排除 deprecated / superseded / invalidated
展开命中的 workflow 正文
加载必要依赖规则和偏好
进入后续 workflow
```

用户感知到的是更稳定的路由结果：

```text
我会按当前 roleMe 项目的项目级 workflow 来拆计划。
```

如果强召回结果分差过小，系统不应强行选择，而应询问：

```text
我命中了两个接近的 workflow：项目级需求分析和通用需求分析。你希望这次按哪个来？
```

### 归档项目经验

用户说：

```text
帮我总结这个项目的工作方式
```

系统写入项目 workflow、项目记忆、Evidence 和相关关系，回执保持简短：

```text
已归档为项目 workflow，并写入 Context Graph。
```

内部写入：

```text
Project
Workflow(scope=project)
Memory(scope=project)
Evidence
Workflow belongs_to Project
Workflow evidenced_by Evidence
Memory belongs_to Project
```

### 归档通用方法

用户说：

```text
帮我总结成通用的工作方式
```

系统写入通用 workflow、Principle、Concept、Evidence 和提升关系。

内部写入：

```text
Workflow(scope=global)
Principle(scope=global)
Concept
Evidence
Principle derived_from Memory 或 Episode
Principle evidenced_by Evidence
Workflow applies_to Concept
```

用户感知：

```text
已整理为通用 workflow，并保留来源证据。
```

### 处理旧知识

当新 workflow 替代旧 workflow 时，Graph 记录：

```text
new_workflow supersedes old_workflow
old_workflow.status = superseded
new_workflow.status = active
```

后续用户说：

```text
按 roleMe workflow 治理来
```

系统过滤旧 workflow，加载当前 active workflow。

### 处理低可信知识

如果某条规则只是模型总结，没有用户确认：

```text
confidence = low
source_type = model_summary
```

它可以作为辅助线索参与召回，但不能覆盖用户当前明确要求。

例如用户说：

```text
这次先别写测试，先快速验证原型
```

如果 Graph 命中高置信 TDD 规则，系统应提示冲突：

```text
你当前要求和默认 TDD 规则有冲突。我按你这次要求先做原型验证，不自动进入完整 TDD，可以吗？
```

### 追溯来源

用户可以问：

```text
这条规则是从哪里来的？
为什么这个 workflow 替代了旧版？
这个通用方法是哪个项目总结出来的？
```

系统行为：

```text
从目标节点沿 evidenced_by / derived_from / promoted_to / supersedes 查找 Evidence、Episode、Memory 或 Decision
展开必要摘要
只在用户需要时加载完整 episode 或来源正文
```

用户感知：

```text
这条规则来自 roleMe 项目复盘，并在后续 workflow 治理中被提升为通用原则。
```

### 处理历史和弱召回

用户问历史或细节时：

```text
之前我们为什么决定这么做？
上次项目复盘里提到过什么？
这个原则有没有反例？
```

系统才展开弱召回：

```text
Memory / Episode / Decision / Topic / File
```

日常任务默认不展开这些弱召回节点，避免上下文被历史材料淹没。

### doctor / optimize

用户说：

```text
roleMe doctor zhaochao
roleMe optimize zhaochao
```

系统执行 Graph 一致性诊断和确定性修复。这里描述用户体验，完整检查和修复规则以后文 `doctor / optimize` 规范为准。

doctor 应向用户报告：

```text
Graph schema、节点、边和索引是否健康
是否存在 Markdown 与 Graph 不一致
是否存在过期、冲突、低置信度或缺少证据的知识
是否存在可自动修复的问题
是否存在需要用户确认的提升、废弃或冲突处理建议
```

optimize 只执行确定性修复：

```text
重建索引
清理可确定的坏引用
补齐可稳定推导的 Graph 元数据
生成但不自动执行需要用户确认的建议
```

optimize 的所有修复都是后台维护动作，不改变用户正常交流方式。它不得要求用户理解节点、边或 entry_key；只有涉及提升、废弃、冲突解决、历史证据删除等语义判断时，才生成建议并等待用户确认。

## 与现有架构集成

Context Graph 对现有架构的影响应控制为增量式：

```text
角色包目录结构：新增 brain/graph/，不改变 persona/memory/brain/projects 语义
渐进式披露：保留，Context Graph 只增强“先找哪个 path”
resident snapshot：不加载完整 graph
workflow index：保留为人类可读索引和 fallback
context_router.py：新增前置 graph recall 分支
role_ops.py：Archive 写入时增加 graph upsert
memory.py：写 USER/MEMORY/episode 时可同步 Archive 节点
doctor/optimize：增加 graph 一致性检查
file_ops.py：提供统一原子写文件 API
templates/brain/graph/schema.yaml：新角色包默认携带 Graph schema
scripts/upgrade_role.py：为旧角色包补齐 Graph 目录和可选回填
scripts/validate_role.py：校验 Graph schema 和基础文件结构
```

### `tools/file_ops.py`

新增模块，负责所有关键文件的原子写：

- `atomic_write_text(path, content)`
- `atomic_write_json(path, payload)`
- `atomic_rewrite_jsonl(path, records)`

`memory.py`、`workflow_index.py`、`role_ops.py`、`graph_index.py` 不应直接对关键角色文件调用 `Path.write_text()`。临时文件、fsync、atomic rename、失败清理都集中在该模块处理。

### `tools/graph_index.py`

新增模块，负责：

- 读取和写入 `brain/graph/schema.yaml`
- 读取、校验、原子重写 `nodes.jsonl`、`edges.jsonl`
- 重建 `indexes/*`
- 提供 `upsert_node()`、`upsert_edge()`、`load_graph()`、`query_nodes()`、`recall_graph()`、`doctor_graph()` 等确定性 API
- 返回结构化 `GraphRecallResult`，由 context_router 再压平成旧接口需要的 path list
- 返回结构化 doctor findings，供 `role_ops.doctor_role()` 聚合

### `tools/context_router.py`

增强模块，负责：

- 在现有 workflow 路由前尝试 `recall_graph(role_path, query)`
- 对 `GraphRecallResult` 执行 trust filter、弱召回 gate、fallback 合并
- 将最终候选转换成 path，并保留旧 `discover_context_paths()` 兼容接口
- 未命中或异常时回退现有 discover 逻辑

### `tools/role_ops.py`

增强模块，负责：

- workflow 归档时写入 Graph
- 项目自动 bootstrap 时补齐 Project 节点
- 聚合 `doctor_graph()` 的 findings，不在 `role_ops.py` 内堆叠所有 Graph 检查细节
- 对外保留现有归档 API，但内部使用可表达 partial state 的 `ArchiveResult`

### `tools/memory.py`

增强模块，负责：

- 写 `USER.md`、`MEMORY.md`、episode 时同步 Preference、Principle、Memory、Episode、Evidence 节点
- build frozen snapshot 时不加载完整 Graph

### `tools/workflow_index.py`

保持现有职责：

- `workflows/index.md` 仍是人类可读索引
- Context Graph 是结构化索引和可靠性元数据
- 两者应由同一次 Archive 操作保持一致

### `scripts/build_skill.py`

发布 skill 时必须复制：

- `tools/file_ops.py`
- `tools/graph_index.py`
- `templates/brain/graph/schema.yaml`

打包测试必须验证发布后的 `skills/roleme/assets/templates/brain/graph/schema.yaml` 存在。

### `scripts/upgrade_role.py`

升级旧角色包时必须支持：

- 创建缺失的 `brain/graph/`
- 写入当前版本 `schema.yaml`
- 在用户显式运行 optimize 时，才从现有 markdown index 和 memory 条目回填 nodes/edges

普通加载不得触发全量迁移或全量 markdown 扫描。

### `scripts/validate_role.py`

验证角色包时必须覆盖：

- Graph schema 是否存在且可解析
- nodes/edges 是否可解析
- indexes 缺失时是否可重建
- Graph schema version 是否与工具支持范围兼容

## 开关与回滚

Context Graph routing 必须可关闭，避免 Graph 损坏影响用户使用。

建议支持：

```text
ROLEME_GRAPH_ROUTING=0   禁用 Graph 召回
ROLEME_GRAPH_ARCHIVE=0   禁用 Graph 写入
```

行为：

```text
ROLEME_GRAPH_ROUTING=0:
  禁用 graph recall
  保留 graph 写入和 doctor 检查
  context_router.py 完全使用现有 discover_workflow_paths / discover_project_paths / discover_brain_paths

ROLEME_GRAPH_ARCHIVE=0:
  禁用 Archive 对 nodes.jsonl / edges.jsonl / indexes/* 的写入
  markdown 正文和 markdown index 仍按现有逻辑写入
  doctor 仍可检查已有 Graph，但不得自动修复
  Graph 可能落后于 markdown
```

这两个开关都只影响内部机制，不改变用户正常对话方式。用户仍然可以自然提出任务、归档经验、修改偏好；开关只决定 roleMe 是否使用或维护 Context Graph。

当 `ROLEME_GRAPH_ARCHIVE=0` 且 `ROLEME_GRAPH_ROUTING` 仍开启时，Recall 必须把 Graph 视为可能 stale 的候选索引，而不是完整事实来源。此时 context_router 必须保留 markdown fallback，不得仅凭 Graph 命中结果排除新写入的 markdown 内容。

开关行为必须保持后台化。除非用户显式询问诊断、来源、开关状态或出现需要确认的冲突，系统不得在普通交流中向用户解释 Graph routing / archive 的内部细节。

## doctor / optimize

doctor 应检查：

```text
schema.yaml 是否有效
nodes.jsonl / edges.jsonl 是否可解析
是否存在重复 node id / edge id
edge 是否指向不存在的节点
node.path 是否失效
workflow index 和 Graph 状态是否不一致
是否存在 superseded 但仍被 index 标 active 的内容
是否存在 low confidence 强规则
是否存在孤立 Evidence
是否存在同一路径同时被强语义节点和 File 重复建模
entry-backed 类型是否缺少 metadata.entry_key
supersedes / invalidated_by / promoted_to / generalizes 是否缺少 Evidence 或 Episode 来源
Graph 中 active 节点是否无法在 markdown index 或正文中找到入口
markdown index 或正文中 active 内容是否缺少对应 Graph 节点
```

optimize 可执行确定性修复：

```text
重建 indexes/*
标记或移除失效 File 节点
清理孤儿边
合并重复节点
修复 workflow index 与 Graph 状态不一致
把已被 superseded 的节点从默认召回中移除
从 workflow index、brain index、memory 条目回填缺失 Graph 节点
合并或移除与强语义节点同路径的冗余 File 节点
为可稳定定位的 entry-backed 条目补齐 metadata.entry_key
```

`File` 节点修复必须保守：

```text
仍被 Evidence / Decision / Episode / supersedes / derived_from 等历史链路引用的 File：
  不得物理删除，只能标记为 superseded / archived 或迁移引用后再处理

与强语义节点同 path 的冗余 File：
  优先把入边迁移到强语义节点，或把 File 标记为 superseded
  只有确认无入边、无证据依赖、无历史追溯价值时，才能物理删除

path 已失效的 File：
  doctor 报告 warning
  optimize 只在无历史引用时删除；有历史引用时保留节点并标记 stale / archived
```

Archive 出现 partial state 后，doctor 必须能报告 markdown 已写入但 Graph 缺失的对象；optimize 必须能在不改写正文语义的前提下补齐 Graph。Graph 修复失败不得阻塞现有渐进式披露和旧路由。

实现边界：

```text
graph_index.doctor_graph(role_path) 返回结构化 findings
role_ops.doctor_role(role_name) 聚合基础角色包检查和 Graph findings
graph_index.optimize_graph(role_path) 只做确定性修复
需要用户确认的提升、废弃、冲突解决只生成建议，不自动执行
```

## 测试策略

### Schema 测试

- `schema.yaml` 能被解析
- `schema.yaml` 声明 `graph_schema_version`
- 所有节点类型和边类型在 schema 中声明
- nodes / edges / indexes 版本不兼容时，doctor 报告 warning，indexes 可直接重建
- `project` scope 节点缺少 `project_slug` 时校验失败
- path-backed node 缺少 path 时校验失败
- entry-backed node 缺少 `metadata.entry_key` 时 doctor 报告 warning
- `nodes.jsonl` 出现重复 id 时 doctor 报告 warning
- `edges.jsonl` 指向不存在节点时 doctor 报告孤儿边
- 同一路径同时存在强语义节点和冗余 `File` 节点时 doctor 报告重复建模

### 写入测试

- 归档通用 workflow 后创建 Workflow、Concept、Evidence 和相关边
- 归档项目 workflow 后创建 Project、Workflow、Evidence 和相关边
- 归档长期偏好后创建 Preference 和 Evidence
- 归档长期原则后创建 Principle 和 Evidence
- 归档 episode 后创建 Episode，并能 promoted_to Principle
- 重复归档同一对象不产生重复节点
- `supersedes` 新节点后，旧节点状态变为 `superseded`
- `supersedes` / `invalidated_by` / `promoted_to` / `generalizes` 缺少 Evidence 或 Episode 来源时 doctor 报告 warning
- 写入失败不留下半行 JSON
- 所有关键 markdown、JSON、JSONL 写入都通过公共 atomic write API
- markdown 已写入但 Graph 更新失败时返回 partial state，并可由 doctor / optimize 发现和恢复
- ArchiveResult 能表达 markdown_written / index_updated / graph_updated / graph_skipped / doctor_warnings
- indexes 缺失或损坏时可由 nodes/edges 重建
- 归档主题知识时，主题文档只创建 `Topic`，不为同一路径额外创建 `File`
- 编辑 entry-backed 条目正文时，不因 content hash 变化静默创建新的 active 节点
- 新 Archive 产生的 entry-backed 条目会写入稳定 markdown marker，旧条目无法稳定定位时 optimize 只报告建议
- 自然语言归档入口在 Graph partial failure 时不会返回完整成功回执
- 生产代码中关键角色包写入不得直接调用 `Path.write_text()`，必须通过公共 atomic write API；测试、临时夹具和非角色包输出可列入允许清单

### 召回测试

- 用户使用不同说法描述同一任务，能命中同一个 Workflow
- graph recall 内部返回 `GraphRecallResult`，包含候选、分数、强弱召回、状态、置信度和 trust flags
- 当前项目 workflow 优先于通用 workflow
- 当前项目无匹配 workflow 时回退通用 workflow
- Preference / Principle 能影响执行方式
- Concept alias 能把“大脑加载慢”映射到 context routing / graph recall 相关节点
- 第一名和第二名分差过小时不强行命中错误 workflow
- graph recall 返回 path 后，正文加载仍受 `max_chars` 预算限制
- 弱召回未触发时，Memory / Episode / Decision / Topic / File 不进入正文加载预算
- `ROLEME_GRAPH_ROUTING=0` 时完全使用旧路由，但不影响 markdown 写入
- `ROLEME_GRAPH_ARCHIVE=0` 时不写 Graph，但仍能写 markdown 正文和 markdown index
- Graph 可能 stale 时，旧 markdown index 命中作为强候选参与排序，Graph 不得过滤掉新 markdown
- Graph routing / archive 细节不出现在普通用户交流中，除非用户询问诊断、来源、开关状态或需要确认冲突

### Trust 测试

- `deprecated` workflow 不进入默认上下文
- `superseded` workflow 被新 workflow 替代
- `invalidated` Evidence 不支持强规则
- `low` confidence Rule 排序低于 `high` confidence Rule
- 存在 `contradicts` 时，系统不静默选择其一

### 回归测试

- Graph 文件不存在时，现有 `discover_context_paths()` 行为不变
- Graph 命中为空时，仍能通过 `brain/index.md`、`projects/index.md` 回退
- resident snapshot 不加载完整 Graph
- `workflow_index.py` 现有解析和渲染测试继续通过
- `ROLEME_GRAPH_ROUTING=0` 时完全使用旧路由
- Graph schema 损坏时旧路由仍可工作
- indexes 删除后不影响召回，因为可从 nodes/edges 重建
- build_skill 后发布包包含 `tools/graph_index.py`、`tools/file_ops.py` 和 `assets/templates/brain/graph/schema.yaml`
- validate_role 覆盖 Graph schema、nodes/edges 解析和版本兼容检查

## 迁移策略

迁移采用增量兼容策略：

1. 新增 `brain/graph/schema.yaml`
2. 新归档内容自动写 Graph
3. doctor 提供“发现未入 Graph 的 workflow / memory / topic”的报告
4. optimize 可把已有 workflow index、brain index、memory 条目转成节点
5. 旧角色包没有 Graph 时继续使用现有渐进式披露逻辑

普通角色加载不得自动全量迁移旧 markdown，也不得因为 Graph 缺失扫描整个角色包。旧角色包的迁移分为两层：

```text
bootstrap:
  创建 brain/graph/
  写入当前 schema.yaml
  保持 nodes/edges 为空或缺省

optimize:
  用户显式触发后，从 workflow index、brain index、memory 条目回填 nodes/edges
  对无法稳定生成 entry_key 的条目只报告建议，不强行迁移为 active 节点
```

迁移过程中，markdown 文件仍是正文权威；Context Graph 只作为结构化索引、关系和可靠性元数据。

## 实现前风险与落地顺序

### 必须先确定的默认行为

实现开始前必须固定以下默认行为，避免后续模块各自解释：

```text
新角色包默认创建 brain/graph/schema.yaml
nodes.jsonl / edges.jsonl 可以为空或不存在
ROLEME_GRAPH_ARCHIVE 默认开启
ROLEME_GRAPH_ROUTING 在写入、doctor、fallback 稳定后再默认开启
普通角色加载不得触发全量迁移或全量 markdown 扫描
Graph 写入失败时，markdown 归档仍可成功，但回执必须报告 Graph partial failure
```

这些默认行为确保 Context Graph 能逐步生效，同时不影响旧角色包和正常对话。

### 高风险实现点

实现时必须优先控制以下风险：

```text
entry_key:
  优先使用显式 block id、heading path 或归档生成 entry slug
  新归档的 entry-backed 条目必须把稳定 marker 写回 markdown
  内容 hash 只作为旧条目导入兜底
  旧条目无法稳定定位时只报告建议，不强行建 active 节点
  正文编辑不得静默生成新的 active 节点

recall fallback:
  Graph Recall 必须保留旧路由 fallback
  Graph 损坏、缺失、stale、分差过小、ARCHIVE 关闭时都不得只信 Graph
  Graph 可能 stale 时，markdown index 强命中必须进入候选集合

weak recall:
  Memory / Episode / Decision / Topic / File 默认不进入正文预算
  只有强召回不足、来源追溯、冲突解释、历史询问、证据验证时展开

trust preservation:
  GraphRecallResult 在内部保留 trust flags
  不得过早压平成 path list

atomic write:
  先实现 file_ops.py
  所有关键 markdown / json / jsonl 写入必须走公共原子写 API

doctor optimize:
  doctor 只报告
  optimize 只做确定性修复
  File 节点删除必须保守，保留仍被历史链路引用的来源节点
  需要用户确认的提升、废弃、冲突处理只生成建议

user experience:
  Graph 是后台机制，不改变用户自然交流和归档方式
  普通对话不暴露 Graph routing / archive / entry_key 细节
  只有高风险冲突、低置信知识影响重要行为、或用户显式询问诊断来源时才说明后台状态
```

### 中风险实现点

以下风险不阻塞启动实现，但必须进入计划和测试：

```text
Graph schema version 与 role schema version 分离
nodes/edges 保存当前状态，不作为事件日志
同一路径有强语义节点时不得再创建 File 节点
当前项目识别沿用现有 repo slug 逻辑，Graph 实现阶段不重做项目识别
build_skill / templates / validate_role / upgrade_role 必须同步覆盖 Graph 文件
测试必须覆盖 Graph 缺失、损坏、stale、partial failure、entry_key 缺失和 indexes 删除
```

### 推荐实现顺序

为了降低定位复杂度，实现应按以下顺序推进：

```text
1. tools/file_ops.py
   提供 atomic_write_text / atomic_write_json / atomic_rewrite_jsonl

2. tools/graph_index.py 基础层
   schema / load / save / rebuild indexes / doctor_graph

3. 模板、打包、校验、升级
   templates/brain/graph/schema.yaml
   build_skill
   validate_role
   upgrade_role

4. Archive 写 Graph
   先写入 nodes/edges 和 indexes
   先不启用 Graph Recall

5. doctor / optimize
   覆盖 partial state
   覆盖 markdown 与 Graph 不一致
   支持显式 optimize 回填旧内容

6. Graph Recall
   返回 GraphRecallResult
   保留 score、强弱召回、status、confidence、trust flags

7. context_router 集成
   合并 Graph Recall 和旧路由 fallback
   保持 discover_context_paths() 兼容 path list

8. 默认开启 Graph Recall
   只在写入、doctor、fallback 和回归测试稳定后开启
```

该顺序的原则是先保证写入和诊断可靠，再让召回依赖 Graph。不得在没有 doctor、fallback 和 partial state 支持的情况下优先替换 `context_router.py` 的主路由。

## 验收标准

设计完成后的实现应满足：

- 用户自然表达任务时，可以更稳定命中项目 workflow 或通用 workflow
- 归档项目经验时，markdown 正文和 Graph 节点/关系同步更新
- 归档长期偏好、原则、决策、主题知识时，能保留来源证据和适用范围
- 被替代、废弃或失效的知识不会误入默认上下文
- 低置信度知识不会覆盖用户当前明确要求
- Graph 不存在、损坏或关闭时，不影响现有角色加载和普通路由
- doctor 能发现孤儿边、失效 path、重复节点、schema 不匹配和状态冲突
- optimize 能重建索引并修复确定性一致性问题

最终目标不是让 Context Graph 变成新的大杂烩，而是让 `roleMe` 的上下文系统做到：

```text
写入时可沉淀
读取时能命中
回答时有证据
演化时可治理
```
