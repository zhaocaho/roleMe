# roleMe 本地开发说明

本文档面向维护 `roleMe` skill 源码仓库的开发者，说明本地开发、测试、打包与文档维护方式。

## 目录职责

- `tools/`：最终 skill 运行时会带上的最小工具层。
- `templates/`：初始化角色包时生成的模板。
- `bundle/`：最终要被打包分发的 skill 源定义。
- `scripts/`：只在源码仓库里使用的开发脚本，不进入最终产物。
- `docs/`：仓库内部文档，不进入最终产物。

## 环境准备

推荐使用仓库根目录下的虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

如果机器上有 `python3.12`，优先使用 `python3.12`；否则当前仓库也可以先用兼容版本完成开发验证。

## 本地开发流程

推荐按下面顺序工作：

1. 新建功能分支。
2. 先补测试，再补最小实现。
3. 优先把策略写进 `templates/AGENT.md` 或 `bundle/SKILL.template.md`。
4. 只有确定性的文件操作才写进 `tools/`。
5. `scripts/` 只处理开发期构建、校验、迁移，不写运行时逻辑。

## 测试

运行全部测试：

```bash
./.venv/bin/python -m pytest -q
```

运行单个测试文件：

```bash
./.venv/bin/python -m pytest tests/test_role_ops.py -q
./.venv/bin/python -m pytest tests/test_memory.py -q
./.venv/bin/python -m pytest tests/test_repo_scripts.py -q
```

## 打包

当前打包入口是 `scripts/build_skill.py` 中的 `build_skill()` 函数。可直接这样调用：

```bash
./.venv/bin/python -c 'from pathlib import Path; from scripts.build_skill import build_skill; print(build_skill(Path("dist")))'
```

发布结果会生成到：

```text
skills/roleme/
```

当前发布产物默认包含：

- `SKILL.md`
- `agents/openai.yaml`
- `tools/`
- `assets/templates/`
- `references/`（如果 `bundle/references/` 存在）

当前发布产物默认不包含：

- `scripts/`
- `tests/`
- `docs/`

## 文档约定

- 仓库内部文档放在 `docs/`
- 最终用户需要随 skill 一起分发的说明放在 `bundle/references/`
- `bundle/SKILL.template.md` 只保留高层入口和规则，细节说明放到 `bundle/references/usage.md`
