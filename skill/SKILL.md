---
name: roleme
description: Use when the user wants to initialize, switch, inspect, optimize, export, or diagnose a role bundle with /roleMe.
---

# roleMe

`/roleMe` 默认加载 `self`，若不存在则进入初始化流程。

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
- 常驻层与渐进层的边界由角色包内的 `AGENT.md` 决定
- 对话中的记忆触发优先依赖 `AGENT.md` 声明的策略，而不是额外命令
- 只有确定性的文件操作才调用 `tools/role_ops.py` 或 `tools/memory.py`
- 打包产物中不包含开发仓库的 `scripts/`
