# roleMe Skill 核心架构

本文档描述当前 lean v1 架构，目标是在保持渐进式披露和 Hermes 核心记忆原则的同时，避免把 v1 过度工程化。

相关产品视角文档：[`product-module-boundary.md`](product-module-boundary.md)

## 设计原则

### 1. 声明优先

优先把规则写进 `AGENT.md` 与 `SKILL.md`：

- 哪些文件常驻加载
- 哪些文件按需加载
- 什么时候 recall
- 什么时候写入记忆
- 什么时候重建冻结快照

这类内容本质上是运行策略，不应该优先做成复杂工具链。

### 2. 极小工具层

只有确定性的文件操作放进 `tools/`：

- 初始化角色目录
- 读取角色包
- 写 `role.json`
- 更新 `USER.md` / `MEMORY.md`
- 写 `episodes/`
- 构建冻结快照
- 摘要优先检索
- 压缩与导出

当前只保留两个运行时文件：

- `tools/role_ops.py`
- `tools/memory.py`

### 3. 开发脚本不进入最终产物

`scripts/` 只属于源码仓库，用来做：

- 打包
- 校验
- 升级

最终 skill 产物不应携带这些开发脚本。

## 运行时分层

### 入口层

- `bundle/SKILL.template.md`
- 角色包内的 `AGENT.md`

两者共同定义“宿主如何使用这个 skill”与“角色如何在会话中工作”。

### 工具层

- `tools/role_ops.py`
- `tools/memory.py`

只负责可重复、可测试的文件系统与文本变更。

### 数据层

角色实际数据位于：

```text
~/.roleMe/<role-name>/
```

这层才是角色的长期状态，不放在源码仓库中。

## 角色包结构

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
```

## 记忆架构

`roleMe` 借鉴 Hermes 的核心机制，而不是照搬它的脚本形态：

- 常驻记忆有明确边界
- 常驻记忆在会话开始时构造成冻结快照
- 写入后立即持久化
- 当前会话默认不自动刷新常驻快照
- 检索优先查摘要层，再回退到情节层

对应关系：

- `memory/USER.md`：稳定偏好、长期约定、持久事实
- `memory/MEMORY.md`：高价值摘要与索引
- `memory/episodes/`：更细节、默认不常驻的情节型记忆

## 打包边界

最终产物只带运行时真正需要的内容：

- `skill.yaml`
- `SKILL.md`
- `tools/`
- `assets/templates/`
- `references/`（如果存在）

最终产物不带：

- `scripts/`
- `tests/`
- `docs/`
- Git 元数据

## 为什么不是更多模块

当前阶段刻意没有拆成大量 `runtime.py`、`paths.py`、`engine.py`、`stores.py` 这类细粒度模块，是因为：

- v1 关注的是角色包工作闭环，而不是模块数量
- 规则主要靠声明表达
- 工具层只处理确定性动作
- 真正需要更细拆分时，再从 `tools/` 中自然长出来
