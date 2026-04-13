# roleMe 使用说明

本文档面向最终使用 `roleMe` skill 的用户。

## 这个 skill 是做什么的

`roleMe` 用来初始化、加载、切换和维护“用户角色包”。

每个角色都保存在本地：

```text
~/.roleMe/<角色名>/
```

角色加载后，不是让模型变成这个角色，而是让你在当前对话中以这个角色的身份被理解。助手仍然是助手，但会优先通过这个角色的身份、记忆、知识和项目上下文来理解你。

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

主要用于整理和压缩记忆内容。

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

- `persona/narrative.md`
- `persona/communication-style.md`
- `persona/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

### 按需层

这些内容只在需要时再展开：

- `persona/disclosure-layers.md`
- `brain/index.md`
- `brain/topics/*`
- `projects/index.md`
- `projects/<project-name>/*`
- `memory/episodes/*`

### 渐进式披露

如果对话进入某个知识领域，助手应先查 `brain/index.md`，再一步一步进入相关主题文档，而不是一开始就加载全部知识文件。

如果对话明显与某个项目有关，助手应先查 `projects/index.md`，再进入对应项目目录。

如果摘要记忆不够，助手才回退到 `memory/episodes/*` 查看更细节的历史记录。

### 冻结快照

角色激活时，会根据常驻层生成当前会话使用的冻结快照。

这意味着：

- 新记忆会被写入本地文件
- 但当前会话默认不会立刻重建常驻记忆块
- 重新加载或切换角色时，才会拿到新的冻结快照

## 初始化时会生成什么

首次初始化至少会生成：

- `AGENT.md`
- `role.json`
- `persona/`
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
- 长期结论摘要
- 指向更深层记忆的入口

### `episodes/`

保存更细节的会话型记忆，默认不常驻加载。

## 角色包可以直接复制吗

可以。

只要 `schemaVersion` 兼容，角色目录就可以直接复制到另一台机器的 `~/.roleMe/` 下使用。

## 使用建议

- 把真正稳定的偏好写进角色，而不是一次次重复告诉模型
- 把项目级规则放在 `projects/`，不要混进基础身份层
- 不要把所有背景都塞进 `AGENT.md`，让知识和细节按需展开
