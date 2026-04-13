# roleMe 使用说明

`roleMe` 用来初始化、加载、切换和维护“用户角色包”。

每个角色默认保存在本地：

```text
~/.roleMe/<角色名>/
```

加载角色以后，不是让模型变成这个角色，而是让你在当前对话里以这个角色的身份被理解。助手仍然是助手，但会优先通过这个角色的身份、记忆、知识和项目上下文来理解你。

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
- 如果角色不存在，进入该角色的初始化流程

### 查看角色

```text
/roleMe list
/roleMe current
```

### 维护角色

```text
/roleMe optimize [角色名]
/roleMe export [角色名]
/roleMe doctor [角色名]
```

## 角色是怎样加载的

### 常驻层

角色激活后，默认带入这些内容：

- `persona/narrative.md`
- `persona/communication-style.md`
- `persona/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

### 按需层

这些内容只在需要时展开：

- `persona/disclosure-layers.md`
- `brain/index.md`
- `brain/topics/*`
- `projects/index.md`
- `projects/<project-name>/*`
- `memory/episodes/*`

### 渐进式披露

如果对话进入某个知识领域，助手应先查 `brain/index.md`，再逐步进入相关主题文件，而不是一开始就加载所有知识文档。

如果问题明显和某个项目有关，助手应先查 `projects/index.md`，再进入对应项目目录。

如果摘要记忆不够，才回退到 `memory/episodes/*` 查看更细节的历史记录。

### 冻结快照

角色激活时，会基于常驻层生成当前会话使用的冻结快照。

这意味着：

- 新记忆可以写入本地文件
- 当前会话默认不会立刻重建整块常驻上下文
- 重新加载或重新切换角色后，才会拿到新的冻结快照

## 初始化访谈如何工作

### 动态访谈，不是固定问卷

初始化访谈不是硬编码的固定问答。

系统会维护一份结构化状态：

- 已经知道什么
- 还缺什么
- 哪些槽位信息不足，需要继续追问

大模型应根据这些信息缺口来决定“下一问最值得问什么”。不同模型可以问出不同问题，只要最终都能落到同一套角色包结构里。

这里的重点不是“换一个模型就问不一样的问题”，而是“同一个模型在不同情景里，也应该能根据上下文问出不同的问题”。系统约束的是归纳方向和落盘结构，不是追问路径本身。

### 稳定的落盘结构

不管访谈过程怎么问，最终都要落到这些位置：

- `persona/`
  保存人物自述、沟通风格、决策规则、披露边界
- `memory/`
  保存稳定偏好、长期约定和高价值摘要
- `brain/`
  保存可渐进检索的主题知识索引和主题文档
- `projects/`
  保存项目级上下文、overlay 和项目记忆

### Planner 契约

当前实现提供了动态访谈的基础接口：

- `begin_role_interview(role_name)`
- `submit_interview_answer(session, answer, slot=None)`
- `build_interview_planner_prompt(session)`
- `finalize_role_interview(session, skill_version)`

其中 `build_interview_planner_prompt()` 会输出一份给大模型使用的 planner prompt，里面包含：

- 已知答案
- 当前信息缺口评估
- 下一问应返回的结构化字段

同时它还会明确约束：

- 这不是固定问卷
- 槽位只是归档目标，不是提问顺序脚本
- 当前应只问一个信息增益最高的问题

### 结构化返回契约

为了让自然对话后的归档更稳定，planner 的结构化输出现在建议至少包含：

- `target_slot`
  这轮答案主要归到哪个槽位
- `question`
  下一句真正要问用户的问题
- `rationale`
  为什么这句在当前上下文里最值得问
- `answer_mode`
  `append` 表示补充已有内容，`replace` 表示这轮是在纠正旧内容
- `ready_to_finalize`
  是否已经足够进入 review

这层契约不是为了限制模型怎么问，而是为了在模型问完以后，系统能更稳定地接住结果。

这样模型可以“先思考，再发问”，而不是只能执行固定问卷。

## 初始化后会生成什么

首次初始化至少会生成：

- `AGENT.md`
- `role.json`
- `persona/`
- `brain/index.md`
- `memory/USER.md`
- `memory/MEMORY.md`
- `projects/index.md`

## 记忆如何工作

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

## 使用建议

- 把真正稳定的偏好写进角色，而不是每次重复告诉模型
- 把项目级规则放在 `projects/`，不要混进基础身份层
- 不要把所有背景都塞进 `AGENT.md`，让知识和细节按需展开
