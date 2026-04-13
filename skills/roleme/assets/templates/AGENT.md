# AGENT.md

## 当前用户角色

当前用户已加载角色 **`<role-name>`**。

后续对话中，助手应保持助手身份，但应优先通过该角色来理解用户的意图、表达方式、决策习惯与长期偏好。

## 常驻加载层

这些文件在角色激活时读取，并构成当前会话的稳定角色底座：

- `persona/narrative.md`
- `persona/communication-style.md`
- `persona/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

## 按需加载层

这些文件只在任务确实需要时再读取：

- `persona/disclosure-layers.md`
- `brain/index.md`
- `brain/topics/*`
- `projects/index.md`
- `projects/<project-name>/*`
- `memory/episodes/*`

## 渐进式披露与路由原则

- 先用常驻层理解当前用户角色，再判断是否需要更深信息
- 触及知识领域时，先查 `brain/index.md`，再逐步进入相关主题文档
- 触及项目语境时，先查 `projects/index.md`，再进入对应项目目录
- 记忆检索时，先看 `MEMORY.md`，不足时再查 `memory/episodes/`
- 更深层的个人信息是否披露，遵循 `persona/disclosure-layers.md`

## 记忆写回规则

- 用户给出稳定偏好、长期约定或持续成立的事实时，写入 `memory/USER.md` 或 `memory/MEMORY.md`
- 需要保留细节或证据的会话内容，写入 `memory/episodes/`
- 写入记忆后应立即持久化到文件
- 当前会话的常驻快照默认不自动刷新，除非角色被重新加载
