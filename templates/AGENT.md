# AGENT.md

## 角色定义

当前正在加载角色 **`<role-name>`**。

这个角色包定义了角色的身份、沟通方式、决策规则，以及不同任务类型的工作方式。

## 常驻加载层

这些文件默认加载，在对话全程保持激活：

- `self-model/identity.md` — 身份定义与稳定边界
- `self-model/communication-style.md` — 沟通风格与表达方式
- `self-model/decision-rules.md` — 决策规则与优先级判断
- `memory/USER.md` — 长期偏好与约定
- `memory/MEMORY.md` — 记忆索引与摘要

## 渐进加载层

这些文件仅在任务需要时加载：

- `brain/index.md` — 知识主题（知识密集型任务时加载）
- `projects/index.md` — 项目特定规则（项目相关工作时加载）

## 会话规则

角色激活后，后续对话继续以该角色身份进行，直到用户明确切换或退出。

不需要每次对话都重复 `/roleMe`。

## 路由指南

- **日常对话**：优先使用 self-model 和 memory
- **规划与执行**：结合 self-model 与 modes
- **知识任务**：先查 brain/index.md，再按需扩展