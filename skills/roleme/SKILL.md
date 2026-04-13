---
name: roleme
description: Use when the user wants to initialize, switch, inspect, optimize, export, or diagnose a role bundle with /roleMe.
---

# roleMe

`/roleMe` 默认加载 `self`。如果角色不存在，就进入初始化流程。

详细使用说明见 `references/usage.md`。

命令面：

- `/roleMe`
- `/roleMe <角色名>`
- `/roleMe list`
- `/roleMe current`
- `/roleMe optimize [角色名]`
- `/roleMe export [角色名]`
- `/roleMe doctor [角色名]`

运行时原则：

- `roleMe` 管理的是用户角色上下文，不是助手人格切换。
- 常驻层与渐进层的边界由角色包内的 `AGENT.md` 决定。
- 记忆写回优先遵循 `AGENT.md` 中的策略和 `memory/` 结构。
- 主题知识与项目上下文通过 `tools/context_router.py` 做渐进式发现，不应一次性全量加载。
- 初始化访谈可以是动态的：问题由模型根据当前已知信息和信息缺口来决定，但最终仍要落到稳定的 `persona/`、`memory/`、`brain/`、`projects/` 结构。
- 只有确定性的文件操作才调用 `tools/role_ops.py`、`tools/memory.py`、`tools/context_router.py`。
- 打包产物中不包含开发仓库的 `scripts/`。
