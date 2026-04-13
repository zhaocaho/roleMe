# roleMe 使用说明

本文档面向最终使用 `roleMe` skill 的用户。

## 这个 skill 是做什么的

`roleMe` 用来初始化、加载、切换和维护“数字分身”角色包。  
每个角色都放在本地：

```text
~/.roleMe/<角色名>/
```

角色加载后，会优先带入稳定人格和核心记忆，再根据任务逐步展开知识、项目叠加层和更深记忆。

## 基本命令

### 默认加载

```text
/roleMe
```

行为：

- 如果 `~/.roleMe/self` 已存在，直接加载 `self`
- 如果不存在，进入 `self` 的初始化流程

### 加载指定角色

```text
/roleMe <角色名>
```

行为：

- 如果角色已存在，直接加载
- 如果不存在，进入该角色的初始化流程

### 查看可用角色

```text
/roleMe list
```

### 查看当前角色

```text
/roleMe current
```

### 优化角色

```text
/roleMe optimize [角色名]
```

主要用于整理与压缩记忆内容。

### 导出角色

```text
/roleMe export [角色名]
```

用于导出角色包，便于复制、迁移或备份。

### 检查角色

```text
/roleMe doctor [角色名]
```

用于检查角色包结构、缺失文件和 schema 问题。

## 角色是怎么加载的

### 常驻层

角色激活后，默认带入这些内容：

- `self-model/identity.md`
- `self-model/communication-style.md`
- `self-model/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

### 按需层

这些内容只在需要时再展开：

- `brain/index.md`
- `brain/topics/*`
- `projects/index.md`
- `projects/<project-name>/*`
- `memory/episodes/*`

### 冻结快照

角色激活时会根据常驻层生成当前会话使用的冻结快照。

含义是：

- 新记忆会被写入本地文件
- 但当前会话默认不会立刻重建常驻记忆块
- 重新加载或切换角色时，才会拿到新的冻结快照

## 初始化时会生成什么

首次初始化至少会生成：

- `AGENT.md`
- `role.json`
- `self-model/`
- `brain/index.md`
- `memory/USER.md`
- `memory/MEMORY.md`
- `projects/index.md`

## 记忆怎么工作

### `USER.md`

保存稳定偏好和长期约定，例如：

- 语言偏好
- 回答结构偏好
- 协作规则

### `MEMORY.md`

保存高价值摘要和索引，例如：

- 已确认的重要习惯
- 项目长期约定摘要
- 指向更深层记忆的入口

### `episodes/`

保存更细节的会话型记忆，默认不常驻加载。

## 角色包可以直接复制吗

可以。  
只要 `schemaVersion` 兼容，角色目录可以直接复制到另一台机器的 `~/.roleMe/` 下使用。

## 使用建议

- 把真正稳定的偏好写进角色，而不是一次次重复告诉模型
- 把项目级规则放在 `projects/`，不要混进基础人格层
- 不要把所有背景都塞进 `AGENT.md`，让知识和细节进入按需层
