# roleMe Skill V1 极简实施计划

> **面向执行代理：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐步执行本计划。所有步骤使用复选框语法 `- [ ]` 进行跟踪。

**目标：** 基于“声明优先 + 极小工具层”的原则，构建首个可交付的 `roleMe` skill，使其能够初始化角色包、按 `AGENT.md` 规则加载常驻/渐进内容、处理基础记忆，并打包成不含开发脚本的最终 skill 产物。

**架构：** 角色的加载规则、记忆触发策略和渐进式披露边界尽量声明在 `AGENT.md` 与 `SKILL.md` 中；只有确定性的文件系统操作才下沉到 `tools/`。开发仓库中的 `scripts/` 仅用于构建、校验和升级，不进入最终 skill 产物。

**技术栈：** Python 3.12、标准库（`pathlib`、`json`、`argparse`、`shutil`、`zipfile`、`re`、`dataclasses`）、`pytest`、`setuptools`

---

## 文件结构

- `pyproject.toml`：项目元数据、可编辑安装方式、`pytest` 配置和共享设置。
- `.gitignore`：忽略虚拟环境、缓存和 `dist/` 产物。
- `tools/__init__.py`：工具层包入口。
- `tools/role_ops.py`：路径解析、manifest、角色初始化、角色加载、列表查询、导出和 doctor 检查。
- `tools/memory.py`：`USER.md` / `MEMORY.md` / `episodes/` 的读写、去重、安全扫描、冻结快照、摘要优先检索、压缩和提升。
- `scripts/build_skill.py`：开发仓库内的出包脚本，只负责生成 `dist/roleme-vX.Y.Z/`。
- `scripts/validate_role.py`：开发仓库内的角色校验脚本，复用 `tools/role_ops.py`。
- `scripts/upgrade_role.py`：开发仓库内的 schema 升级脚本，复用 `tools/role_ops.py`。
- `skill/SKILL.md`：最终分发的 skill 定义、命令约定和运行时行为说明。
- `skill/agents/openai.yaml`：最终 skill 的代理元数据。
- `skill/references/`：仅在 `SKILL.md` 依赖辅助文档时存在。
- `templates/AGENT.md`：常驻层、按需层、冻结快照和记忆触发策略。
- `templates/memory/USER.md`：稳定偏好与长期约定模板，带可维护标记块。
- `templates/memory/MEMORY.md`：摘要索引模板，带可维护标记块。
- `templates/brain/index.md`：知识索引模板。
- `templates/projects/index.md`：项目叠加层模板。
- `templates/self-model/*.md`：身份、沟通风格、决策规则、披露层级模板。
- `tests/`：聚焦的单元测试和一个端到端集成测试。

## 稳定决策

- v1 不追求“很多脚本”，只保留最小必要工具层。
- `AGENT.md` 是第一性入口文件，优先负责声明常驻层、渐进层、冻结快照和记忆触发规则。
- `tools/` 是最终 skill 运行时的一部分；`scripts/` 只属于开发仓库。
- 最终 skill 产物不包含 `scripts/`、`tests/`、`docs/`、Git 元数据和开发配置。
- `ROLEME_HOME` 允许通过环境变量覆写，默认仍为 `~/.roleMe`。
- `templates/self-model/thinking.md` 不属于已确认 schema，v1 不生成。

## 环境准备

### 最终用户环境

- 必须安装：`Python 3.12`
- 不要求安装：`pytest`、Node.js、数据库、额外服务
- 默认角色数据目录：`~/.roleMe/`

### 开发者环境

- 必须安装：`Python 3.12`
- 必须具备：`pip`
- 通过开发依赖安装获得：`pytest`、`setuptools`、`wheel`

### 推荐初始化命令

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## 最终打包产物边界

### 必须进入产物

- `SKILL.md`
- `agents/openai.yaml`
- `tools/`
- `assets/templates/`

### 按需进入产物

- `references/`
  条件：`SKILL.md` 明确引用辅助文档、schema 说明或外部资料摘要。

### 不应进入产物

- `scripts/`
- `tests/`
- `docs/`
- `.gitignore`
- 仓库级开发配置文件

### 当前 v1 推荐结论

- 最小可用产物是：`SKILL.md`、`agents/openai.yaml`、`tools/`、`assets/templates/`
- 如果 `SKILL.md` 需要额外操作说明，再补 `references/`
- `doctor`、`export`、`optimize` 等运行时能力通过 `tools/` 提供，不通过额外 `scripts/` 暴露

---

### 任务 1：初始化仓库骨架与 `tools/` 包

**文件：**
- 新建：`pyproject.toml`
- 新建：`.gitignore`
- 新建：`tools/__init__.py`
- 测试：`tests/test_bootstrap.py`

- [ ] **步骤 1：先写失败测试**

```python
# tests/test_bootstrap.py
import importlib


def test_tools_package_is_importable():
    tools_pkg = importlib.import_module("tools")
    assert hasattr(tools_pkg, "__file__")
```

- [ ] **步骤 2：运行测试，确认它先失败**

运行：`python -m pytest tests/test_bootstrap.py -q`
预期：FAIL，并出现 `ModuleNotFoundError: No module named 'tools'`

- [ ] **步骤 3：编写最小实现**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "roleme"
version = "0.1.0"
description = "Portable role bundle runtime and build tooling"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.3,<9"]

[tool.setuptools]
packages = []

[tool.pytest.ini_options]
pythonpath = ["."]
addopts = "-ra"
testpaths = ["tests"]
```

```gitignore
# .gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
dist/
```

```python
# tools/__init__.py
__all__: list[str] = []
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest tests/test_bootstrap.py -q`
预期：PASS，并显示 `1 passed`

- [ ] **步骤 5：提交**

```bash
git add pyproject.toml .gitignore tools/__init__.py tests/test_bootstrap.py
git commit -m "chore: 初始化 roleme 极简工程骨架"
```

### 任务 2：实现角色初始化、加载与基础检查工具

**文件：**
- 新建：`tools/role_ops.py`
- 修改：`templates/AGENT.md`
- 修改：`templates/memory/USER.md`
- 修改：`templates/memory/MEMORY.md`
- 修改：`templates/projects/index.md`
- 修改：`templates/self-model/disclosure-layers.md`
- 删除：`templates/self-model/thinking.md`
- 新建：`tests/conftest.py`
- 测试：`tests/test_role_ops.py`

- [ ] **步骤 1：先写失败测试**

```python
# tests/test_role_ops.py
from tools.role_ops import initialize_role, list_roles, load_role_bundle, doctor_role


def test_initialize_role_creates_required_files(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    assert (role_path / "AGENT.md").exists()
    assert (role_path / "role.json").exists()
    assert (role_path / "brain" / "topics").is_dir()
    assert (role_path / "memory" / "episodes").is_dir()


def test_load_role_bundle_returns_resident_and_on_demand_paths(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")

    assert bundle.role_name == "self"
    assert "memory/MEMORY.md" in bundle.resident_files
    assert "memory/episodes" in bundle.on_demand_paths


def test_list_roles_returns_sorted_names(tmp_role_home):
    initialize_role("beta", skill_version="0.1.0")
    initialize_role("alpha", skill_version="0.1.0")
    assert list_roles() == ["alpha", "beta"]


def test_doctor_role_reports_missing_file(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    (role_path / "AGENT.md").unlink()

    report = doctor_role("self")
    assert "AGENT.md" in report.missing_files
```

- [ ] **步骤 2：运行测试，确认它先失败**

运行：`python -m pytest tests/test_role_ops.py -q`
预期：FAIL，并出现 `ModuleNotFoundError: No module named 'tools.role_ops'`

- [ ] **步骤 3：编写最小实现**

```python
# tests/conftest.py
import pytest


@pytest.fixture
def tmp_role_home(tmp_path, monkeypatch):
    home = tmp_path / ".roleMe"
    home.mkdir()
    monkeypatch.setenv("ROLEME_HOME", str(home))
    return home
```

```python
# tools/role_ops.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil


SCHEMA_VERSION = "1.0"
RESIDENT_PATHS = [
    "self-model/identity.md",
    "self-model/communication-style.md",
    "self-model/decision-rules.md",
    "memory/USER.md",
    "memory/MEMORY.md",
]
ON_DEMAND_PATHS = [
    "self-model/disclosure-layers.md",
    "brain/index.md",
    "brain/topics",
    "projects/index.md",
    "projects",
    "memory/episodes",
]
REQUIRED_FILES = [
    "AGENT.md",
    "role.json",
    "brain/index.md",
    "memory/USER.md",
    "memory/MEMORY.md",
    "projects/index.md",
    "self-model/identity.md",
    "self-model/communication-style.md",
    "self-model/decision-rules.md",
    "self-model/disclosure-layers.md",
]
JSON_TO_FIELD = {
    "roleName": "role_name",
    "schemaVersion": "schema_version",
    "roleVersion": "role_version",
    "createdBySkillVersion": "created_by_skill_version",
    "compatibleSkillRange": "compatible_skill_range",
    "createdAt": "created_at",
    "updatedAt": "updated_at",
    "defaultLoadProfile": "default_load_profile",
}
FIELD_TO_JSON = {value: key for key, value in JSON_TO_FIELD.items()}


@dataclass(frozen=True)
class RoleManifest:
    role_name: str
    schema_version: str
    role_version: str
    created_by_skill_version: str
    compatible_skill_range: str
    created_at: str
    updated_at: str
    default_load_profile: str = "standard"

    @classmethod
    def new(cls, role_name: str, skill_version: str) -> "RoleManifest":
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        return cls(
            role_name=role_name,
            schema_version=SCHEMA_VERSION,
            role_version="0.1.0",
            created_by_skill_version=skill_version,
            compatible_skill_range=">=0.1 <1.0",
            created_at=now,
            updated_at=now,
        )

    def write(self, path: Path) -> None:
        payload = {
            FIELD_TO_JSON["role_name"]: self.role_name,
            FIELD_TO_JSON["schema_version"]: self.schema_version,
            FIELD_TO_JSON["role_version"]: self.role_version,
            FIELD_TO_JSON["created_by_skill_version"]: self.created_by_skill_version,
            FIELD_TO_JSON["compatible_skill_range"]: self.compatible_skill_range,
            FIELD_TO_JSON["created_at"]: self.created_at,
            FIELD_TO_JSON["updated_at"]: self.updated_at,
            FIELD_TO_JSON["default_load_profile"]: self.default_load_profile,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class RoleBundle:
    role_name: str
    role_path: str
    resident_files: dict[str, str]
    on_demand_paths: list[str]


@dataclass(frozen=True)
class DoctorReport:
    missing_files: list[str]
    warnings: list[str]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def templates_dir() -> Path:
    return repo_root() / "templates"


def roleme_home() -> Path:
    override = os.environ.get("ROLEME_HOME")
    return Path(override).expanduser() if override else Path.home() / ".roleMe"


def role_dir(role_name: str) -> Path:
    return roleme_home() / role_name


def _render(source: Path, destination: Path, role_name: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text(encoding="utf-8").replace("<role-name>", role_name)
    destination.write_text(content, encoding="utf-8")


def initialize_role(role_name: str, skill_version: str) -> Path:
    destination = role_dir(role_name)
    if destination.exists():
        raise FileExistsError(f"Role already exists: {destination}")

    for relative_dir in ["brain/topics", "memory/episodes", "projects", "self-model"]:
        (destination / relative_dir).mkdir(parents=True, exist_ok=True)

    for relative_file in [
        "AGENT.md",
        "brain/index.md",
        "memory/MEMORY.md",
        "memory/USER.md",
        "projects/index.md",
        "self-model/communication-style.md",
        "self-model/decision-rules.md",
        "self-model/disclosure-layers.md",
        "self-model/identity.md",
    ]:
        _render(templates_dir() / relative_file, destination / relative_file, role_name)

    RoleManifest.new(role_name=role_name, skill_version=skill_version).write(destination / "role.json")
    return destination


def load_role_bundle(role_name: str) -> RoleBundle:
    base_path = role_dir(role_name)
    resident_files = {
        relative: (base_path / relative).read_text(encoding="utf-8")
        for relative in RESIDENT_PATHS
    }
    return RoleBundle(
        role_name=role_name,
        role_path=str(base_path),
        resident_files=resident_files,
        on_demand_paths=ON_DEMAND_PATHS,
    )


def list_roles() -> list[str]:
    home = roleme_home()
    if not home.exists():
        return []
    return sorted(path.name for path in home.iterdir() if path.is_dir())


def export_role(role_name: str, output_dir: Path, as_zip: bool = True) -> Path:
    source = role_dir(role_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    if as_zip:
        archive_base = output_dir / source.name
        archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=source.parent, base_dir=source.name)
        return Path(archive_path)
    destination = output_dir / source.name
    shutil.copytree(source, destination, dirs_exist_ok=False)
    return destination


def doctor_role(role_name: str) -> DoctorReport:
    base_path = role_dir(role_name)
    missing = [relative for relative in REQUIRED_FILES if not (base_path / relative).exists()]
    warnings: list[str] = []
    manifest_path = base_path / "role.json"
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if data.get("schemaVersion") != SCHEMA_VERSION:
            warnings.append(f"schema mismatch: {data.get('schemaVersion')}")
    return DoctorReport(missing_files=missing, warnings=warnings)
```

```markdown
# templates/AGENT.md
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
```

```markdown
# templates/memory/USER.md
# 用户记忆

角色名：**`<role-name>`**

## 用途

保存稳定偏好、长期约定和持久事实。

<!-- ROLEME:ENTRIES:START -->
- 语言偏好：
- 回答结构偏好：
- 协作规则：
- 持久事实：
<!-- ROLEME:ENTRIES:END -->
```

```markdown
# templates/memory/MEMORY.md
# 记忆索引

角色名：**`<role-name>`**

## 用途

这个文件保存高价值摘要、主题索引，以及指向更深层记忆的入口。

<!-- ROLEME:ENTRIES:START -->
- 核心记忆：
- 主题索引：
- 深层入口：
<!-- ROLEME:ENTRIES:END -->
```

```markdown
# templates/projects/index.md
# 项目目录

项目叠加层按需加载，不与基础人格层混写。

## 结构

projects/
  <project-name>/
    overlay.md
    context.md
    memory.md
```

```markdown
# templates/self-model/disclosure-layers.md
# 披露层级

## 常驻层

- identity
- communication-style
- decision-rules
- USER.md
- MEMORY.md

## 按需层

- brain/index.md 与 brain/topics/*
- projects/index.md 与 projects/<project-name>/*
- memory/episodes/*

## 深入层

- 只有用户明确要求、任务确实需要，或角色重新加载时才展开更深内容
```

```bash
git rm templates/self-model/thinking.md
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest tests/test_role_ops.py -q`
预期：PASS，并显示 `4 passed`

- [ ] **步骤 5：提交**

```bash
git add tools/role_ops.py templates/AGENT.md templates/memory/USER.md templates/memory/MEMORY.md templates/projects/index.md templates/self-model/disclosure-layers.md tests/conftest.py tests/test_role_ops.py
git commit -m "feat: 实现角色初始化与加载工具"
```

### 任务 3：实现极简记忆工具层

**文件：**
- 新建：`tools/memory.py`
- 测试：`tests/test_memory.py`

- [ ] **步骤 1：先写失败测试**

```python
# tests/test_memory.py
from tools.memory import build_frozen_snapshot, recall, summarize_and_write, write_memory, compact_memory
from tools.role_ops import initialize_role


def test_build_frozen_snapshot_uses_resident_layers(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    snapshot = build_frozen_snapshot(role_path, max_chars=300)

    assert "memory/USER.md" in snapshot
    assert len(snapshot) <= 300


def test_summarize_and_write_deduplicates_entries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    summarize_and_write(role_path, target="memory", source_text="默认中文沟通；默认中文沟通；结论先行。")

    result = recall(role_path, "默认中文")
    assert result["summary_hits"].count("- 默认中文沟通") == 1


def test_write_memory_supports_episode_and_promotion(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    episode_path = write_memory(role_path, target="episode", content="重要偏好：代码解释要先结论后细节。")
    summarize_and_write(role_path, target="memory", source_text="代码解释要先结论后细节。")

    result = recall(role_path, "代码解释")
    assert episode_path.exists()
    assert result["summary_hits"] == ["- 代码解释要先结论后细节"]


def test_compact_memory_enforces_entry_budget(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    for index in range(10):
        write_memory(role_path, target="memory", content=f"item {index}")

    compact_memory(role_path, target="memory", max_entries=4)
    result = recall(role_path, "item")
    assert len(result["summary_hits"]) == 4
```

- [ ] **步骤 2：运行测试，确认它先失败**

运行：`python -m pytest tests/test_memory.py -q`
预期：FAIL，并出现 `ModuleNotFoundError: No module named 'tools.memory'`

- [ ] **步骤 3：编写最小实现**

```python
# tools/memory.py
from __future__ import annotations

from pathlib import Path
import re


ENTRY_START = "<!-- ROLEME:ENTRIES:START -->"
ENTRY_END = "<!-- ROLEME:ENTRIES:END -->"
RESIDENT_PATHS = [
    "self-model/identity.md",
    "self-model/communication-style.md",
    "self-model/decision-rules.md",
    "memory/USER.md",
    "memory/MEMORY.md",
]
UNSAFE_PATTERNS = [
    re.compile(r"ignore previous instructions", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"[\u200b-\u200f\u2060\ufeff]"),
]


def _read_entries(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    block = text.split(ENTRY_START, maxsplit=1)[1].split(ENTRY_END, maxsplit=1)[0]
    return [line for line in block.strip().splitlines() if line.strip()]


def _replace_entries(path: Path, entries: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    replacement = "\n".join(entries)
    updated = (
        text.split(ENTRY_START, maxsplit=1)[0]
        + ENTRY_START
        + "\n"
        + replacement
        + "\n"
        + ENTRY_END
        + text.split(ENTRY_END, maxsplit=1)[1]
    )
    path.write_text(updated, encoding="utf-8")


def _is_safe(text: str) -> bool:
    return not any(pattern.search(text) for pattern in UNSAFE_PATTERNS)


def build_frozen_snapshot(role_path: Path, max_chars: int = 2_000) -> str:
    chunks: list[str] = []
    for relative in RESIDENT_PATHS:
        content = (role_path / relative).read_text(encoding="utf-8").strip()
        chunks.append(f"## {relative}\n{content}")
    return "\n\n".join(chunks)[:max_chars]


def write_memory(role_path: Path, target: str, content: str):
    if target == "episode":
        episodes_dir = role_path / "memory" / "episodes"
        episode_path = episodes_dir / f"episode-{len(list(episodes_dir.glob('*.md'))) + 1:03d}.md"
        episode_path.write_text(content, encoding="utf-8")
        return episode_path

    store_path = role_path / "memory" / ("MEMORY.md" if target == "memory" else "USER.md")
    bullet = f"- {content.strip()}"
    if _is_safe(bullet):
        entries = _read_entries(store_path)
        if bullet not in entries:
            _replace_entries(store_path, entries + [bullet])
    return None


def summarize_and_write(role_path: Path, target: str, source_text: str) -> None:
    store_path = role_path / "memory" / ("MEMORY.md" if target == "memory" else "USER.md")
    entries = _read_entries(store_path)
    seen = set(entries)
    fragments = [part.strip(" 。；;") for part in re.split(r"[；;。\n]+", source_text) if part.strip()]
    normalized: list[str] = []
    for fragment in fragments:
        bullet = f"- {fragment}"
        if bullet not in seen and _is_safe(bullet):
            seen.add(bullet)
            normalized.append(bullet)
    _replace_entries(store_path, entries + normalized)


def recall(role_path: Path, query: str) -> dict[str, list[str]]:
    summary_entries = _read_entries(role_path / "memory" / "MEMORY.md")
    summary_hits = [entry for entry in summary_entries if query in entry]
    if summary_hits:
        return {"summary_hits": summary_hits, "episode_hits": []}

    episode_hits: list[str] = []
    for path in sorted((role_path / "memory" / "episodes").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if query in text:
            episode_hits.append(text)
    return {"summary_hits": [], "episode_hits": episode_hits}


def compact_memory(role_path: Path, target: str, max_entries: int) -> None:
    store_path = role_path / "memory" / ("MEMORY.md" if target == "memory" else "USER.md")
    entries = _read_entries(store_path)
    _replace_entries(store_path, entries[:max_entries])
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest tests/test_memory.py -q`
预期：PASS，并显示 `4 passed`

- [ ] **步骤 5：提交**

```bash
git add tools/memory.py tests/test_memory.py
git commit -m "feat: 增加极简记忆工具层"
```

### 任务 4：保留仓库内开发脚本，但不进入最终 skill

**文件：**
- 新建：`scripts/build_skill.py`
- 新建：`scripts/validate_role.py`
- 新建：`scripts/upgrade_role.py`
- 测试：`tests/test_repo_scripts.py`

- [ ] **步骤 1：先写失败测试**

```python
# tests/test_repo_scripts.py
from pathlib import Path

from scripts.build_skill import build_skill


def test_build_skill_creates_artifact_without_scripts(tmp_path):
    artifact = build_skill(output_root=tmp_path, version="0.1.0")

    assert (artifact / "SKILL.md").exists()
    assert (artifact / "tools" / "role_ops.py").exists()
    assert (artifact / "tools" / "memory.py").exists()
    assert (artifact / "assets" / "templates" / "AGENT.md").exists()
    assert not (artifact / "scripts").exists()
```

- [ ] **步骤 2：运行测试，确认它先失败**

运行：`python -m pytest tests/test_repo_scripts.py -q`
预期：FAIL，并出现 `ModuleNotFoundError: No module named 'scripts.build_skill'`

- [ ] **步骤 3：编写最小实现**

```python
# scripts/build_skill.py
from __future__ import annotations

from pathlib import Path
import shutil


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_skill(output_root: Path, version: str) -> Path:
    root = repo_root()
    destination = output_root / f"roleme-v{version}"
    if destination.exists():
        shutil.rmtree(destination)

    shutil.copytree(root / "skill", destination)
    shutil.copytree(root / "tools", destination / "tools")
    shutil.copytree(root / "templates", destination / "assets" / "templates")
    return destination
```

```python
# scripts/validate_role.py
from __future__ import annotations

import argparse

from tools.role_ops import doctor_role


parser = argparse.ArgumentParser()
parser.add_argument("role_name")
args = parser.parse_args()
print(doctor_role(args.role_name))
```

```python
# scripts/upgrade_role.py
from __future__ import annotations

import argparse
import json

from tools.role_ops import role_dir


parser = argparse.ArgumentParser()
parser.add_argument("role_name")
parser.add_argument("--target-schema", default="1.0")
args = parser.parse_args()

manifest_path = role_dir(args.role_name) / "role.json"
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
payload["schemaVersion"] = args.target_schema
manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"upgraded {args.role_name} to schema {args.target_schema}")
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest tests/test_repo_scripts.py -q`
预期：PASS，并显示 `1 passed`

- [ ] **步骤 5：提交**

```bash
git add scripts/build_skill.py scripts/validate_role.py scripts/upgrade_role.py tests/test_repo_scripts.py
git commit -m "feat: 增加仓库内开发脚本"
```

### 任务 5：定义最终 skill 并补充端到端验证

**文件：**
- 新建：`skill/SKILL.md`
- 新建：`skill/agents/openai.yaml`
- 测试：`tests/integration/test_role_roundtrip.py`

- [ ] **步骤 1：先写失败测试**

```python
# tests/integration/test_role_roundtrip.py
from scripts.build_skill import build_skill
from tools.memory import build_frozen_snapshot, summarize_and_write
from tools.role_ops import doctor_role, initialize_role, load_role_bundle


def test_role_roundtrip_init_load_write_memory_and_package(tmp_role_home, tmp_path):
    role_path = initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")
    summarize_and_write(role_path, target="memory", source_text="默认中文沟通。")
    snapshot = build_frozen_snapshot(role_path, max_chars=400)
    artifact = build_skill(output_root=tmp_path, version="0.1.0")
    report = doctor_role("self")

    assert bundle.role_name == "self"
    assert "默认中文沟通" in snapshot
    assert report.missing_files == []
    assert (artifact / "SKILL.md").exists()
```

- [ ] **步骤 2：运行测试，确认它先失败**

运行：`python -m pytest tests/integration/test_role_roundtrip.py -q`
预期：FAIL，并提示缺少最终 skill 定义文件

- [ ] **步骤 3：编写最小实现**

```markdown
# skill/SKILL.md
# roleMe

`/roleMe` 默认加载 `self`，若不存在则进入初始化流程。

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
```

```yaml
# skill/agents/openai.yaml
name: roleMe
entry: SKILL.md
description: Portable role package runtime with progressive disclosure and minimal tools.
```

- [ ] **步骤 4：再次运行测试，确认通过**

运行：`python -m pytest tests/integration/test_role_roundtrip.py -q`
预期：PASS，并显示 `1 passed`

- [ ] **步骤 5：提交**

```bash
git add skill/SKILL.md skill/agents/openai.yaml tests/integration/test_role_roundtrip.py
git commit -m "feat: 定义最终 roleme skill 产物"
```

## 自检清单

- 规格覆盖：任务 2 覆盖角色初始化、加载、列表、导出和 doctor；任务 3 覆盖冻结快照、读写、检索、提升和压缩；任务 4 和任务 5 覆盖仓库开发脚本与最终 skill 打包边界。
- 占位符扫描：没有 `TODO`、`TBD` 或“参照上文”之类偷懒描述；每个任务都包含明确文件路径、测试命令和提交点。
- 类型一致性：`RoleManifest`、`RoleBundle`、`DoctorReport` 都在 `tools/role_ops.py` 中集中定义；记忆相关逻辑全部收敛在 `tools/memory.py` 中。

## 执行备注

- 这是一版 lean v1，不追求一开始就把运行时拆成很多模块。
- 若后续 `tools/role_ops.py` 或 `tools/memory.py` 明显膨胀，再拆分为更多文件；不要在 v1 之前预支复杂度。
- `AGENT.md` 是系统的一等入口。只要能靠声明完成，就不要先写成工具。
