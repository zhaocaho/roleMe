# AGENT.md

## 角色定义

当前正在加载角色 **`<role-name>`**。

## 常驻加载层

这些文件在角色激活时读取，并构造成当前会话使用的冻结快照：

- `self-model/identity.md`
- `self-model/communication-style.md`
- `self-model/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

## 按需加载层

这些文件只在任务需要时再读取：

- `self-model/disclosure-layers.md`
- `brain/index.md`
- `brain/topics/*`
- `projects/index.md`
- `projects/<project-name>/*`
- `memory/episodes/*`

## 记忆触发策略

- 用户给出稳定偏好、长期约定或持久事实时，应写入 `USER.md` 或 `MEMORY.md`
- 回答前若需要历史偏好或长期结论，先查 `MEMORY.md`，不足时再查 `memory/episodes/`
- 写入记忆后立即持久化，但默认不刷新当前会话的常驻记忆块
- 只有重新加载或切换角色时，才重建冻结快照
