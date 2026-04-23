# roleMe Remove Current Role State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `.current-role.json` runtime dependency completely and make role-targeted writes resolve role identity explicitly from session-provided inputs.

**Architecture:** Keep role resolution deterministic by removing global current-role state APIs from `tools/role_ops.py` and requiring workflow archive entrypoints to resolve target role from `role_name` argument or `plan.role_name`. Preserve existing role bundle structure and graph/memory pipelines by continuing to pass explicit `role_path` into lower-level writers.

**Tech Stack:** Python 3, pytest, markdown docs, roleMe skill bundle templates.

---

### Task 1: Convert Tests To No-Current-State Semantics (RED)

**Files:**
- Modify: `tests/test_role_ops.py`
- Test: `tests/test_role_ops.py`

- [ ] **Step 1: Replace current-state tests with no-state and explicit-role tests**

```python
# remove import
# -    get_current_role_state,

def test_load_role_bundle_does_not_write_current_role_state(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")
    assert bundle.role_name == "self"
    assert not (tmp_role_home / ".current-role.json").exists()


def test_load_role_bundle_ignores_existing_current_role_state(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    legacy = tmp_role_home / ".current-role.json"
    legacy.write_text(
        '{"roleName": "legacy", "rolePath": "/tmp/legacy", "loadedAt": "2026-04-15T11:30:00+08:00"}\n',
        encoding="utf-8",
    )
    bundle = load_role_bundle("self")
    assert bundle.role_name == "self"
    assert legacy.read_text(encoding="utf-8") == (
        '{"roleName": "legacy", "rolePath": "/tmp/legacy", "loadedAt": "2026-04-15T11:30:00+08:00"}\n'
    )


def test_archive_project_workflow_requires_role_name(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    plan = parse_workflow_archive_response(
        {
            "kind": "project",
            "project_title": "roleMe",
            "project_slug": "roleme",
            "workflow_slug": "requirements",
            "workflow_title": "roleMe 项目工作流",
            "workflow_summary": "用于把模糊需求整理成可规划输入",
            "workflow_applies_to": "当用户想梳理需求、澄清范围、整理用户故事时使用",
            "workflow_keywords": ["需求", "requirement", "scope"],
            "workflow_doc_markdown": "# roleMe 项目工作流\n\n先确认角色边界，再设计能力。\n",
            "context_summary_markdown": "# roleMe\n\n该项目聚焦角色包与工作流沉淀。\n",
            "user_rules": [],
            "memory_summary": [],
            "project_memory": [],
        }
    )
    with pytest.raises(ValueError, match="role_name"):
        archive_project_workflow(plan)
```

- [ ] **Step 2: Add project workflow role-resolution coverage**

```python
def test_archive_project_workflow_uses_plan_role_name_without_current_state(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    plan = parse_workflow_archive_response(
        {
            "kind": "project",
            "role_name": "self",
            "project_title": "roleMe",
            "project_slug": "roleme",
            "workflow_slug": "requirements",
            "workflow_title": "roleMe 项目工作流",
            "workflow_summary": "用于把模糊需求整理成可规划输入",
            "workflow_applies_to": "当用户想梳理需求、澄清范围、整理用户故事时使用",
            "workflow_keywords": ["需求", "requirement", "scope"],
            "workflow_doc_markdown": "# roleMe 项目工作流\n\n先确认角色边界，再设计能力。\n",
            "context_summary_markdown": "# roleMe\n\n该项目聚焦角色包与工作流沉淀。\n",
            "user_rules": [],
            "memory_summary": [],
            "project_memory": ["先确认角色边界，再设计能力"],
        }
    )
    result = archive_project_workflow(plan)
    assert result.role_name == "self"
    assert (role_path / "projects" / "roleme" / "workflows" / "requirements.md").exists()


def test_archive_project_workflow_rejects_conflicting_role_names(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    initialize_role("other", skill_version="0.1.0")
    plan = parse_workflow_archive_response(
        {
            "kind": "project",
            "role_name": "self",
            "project_title": "roleMe",
            "project_slug": "roleme",
            "workflow_slug": "requirements",
            "workflow_title": "roleMe 项目工作流",
            "workflow_summary": "用于把模糊需求整理成可规划输入",
            "workflow_applies_to": "当用户想梳理需求、澄清范围、整理用户故事时使用",
            "workflow_keywords": ["需求", "requirement", "scope"],
            "workflow_doc_markdown": "# roleMe 项目工作流\n\n先确认角色边界，再设计能力。\n",
            "context_summary_markdown": "# roleMe\n\n该项目聚焦角色包与工作流沉淀。\n",
            "user_rules": [],
            "memory_summary": [],
            "project_memory": [],
        }
    )
    with pytest.raises(ValueError, match="conflicts"):
        archive_project_workflow(plan, role_name="other")


def test_archive_general_workflow_rejects_unknown_role(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    plan = parse_workflow_archive_response(
        {
            "kind": "general",
            "role_name": "ghost",
            "workflow_slug": "general-collaboration",
            "workflow_title": "通用协作工作流",
            "workflow_summary": "适合需要先设计再执行的任务",
            "workflow_applies_to": "当用户需要先对齐工作方式、再进入执行时使用",
            "workflow_keywords": ["协作", "设计", "执行"],
            "workflow_doc_markdown": "# 通用协作工作流\n\n先澄清场景，再开始执行。\n",
            "context_summary_markdown": "",
            "user_rules": [],
            "memory_summary": [],
            "project_memory": [],
        }
    )
    with pytest.raises(FileNotFoundError, match="Role does not exist"):
        archive_general_workflow(plan)


def test_archive_project_workflow_rejects_unknown_role(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    plan = parse_workflow_archive_response(
        {
            "kind": "project",
            "role_name": "ghost",
            "project_title": "roleMe",
            "project_slug": "roleme",
            "workflow_slug": "requirements",
            "workflow_title": "roleMe 项目工作流",
            "workflow_summary": "用于把模糊需求整理成可规划输入",
            "workflow_applies_to": "当用户想梳理需求、澄清范围、整理用户故事时使用",
            "workflow_keywords": ["需求", "requirement", "scope"],
            "workflow_doc_markdown": "# roleMe 项目工作流\n\n先确认角色边界，再设计能力。\n",
            "context_summary_markdown": "# roleMe\n\n该项目聚焦角色包与工作流沉淀。\n",
            "user_rules": [],
            "memory_summary": [],
            "project_memory": [],
        }
    )
    with pytest.raises(FileNotFoundError, match="Role does not exist"):
        archive_project_workflow(plan)
```

- [ ] **Step 3: Run targeted tests to verify RED**

Run: `python3 -m pytest tests/test_role_ops.py -k "current_role_state or archive_project_workflow_requires_role_name or conflicting_role_names or does_not_write_current_role_state or ignores_existing_current_role_state or rejects_unknown_role" -v`  
Expected: FAIL, because runtime code still writes/reads current-role state and archive APIs do not yet enforce new role resolution.

- [ ] **Step 4: Commit**

```bash
git add tests/test_role_ops.py
git commit -m "test: codify no-current-role-state behavior"
```

### Task 2: Remove Current-Role Runtime State APIs (GREEN)

**Files:**
- Modify: `tools/role_ops.py`
- Modify: `skills/roleme/tools/role_ops.py` (generated copy only via sync command)
- Test: `tests/test_role_ops.py`

- [ ] **Step 1: Remove current-state dataclass/functions and call sites**

```python
# remove dataclass
# @dataclass(frozen=True)
# class CurrentRoleState: ...

# remove helpers
# def current_role_state_paths() -> list[Path]: ...
# def current_role_state_path() -> Path: ...
# def set_current_role_state(role_name: str) -> CurrentRoleState: ...
# def get_current_role_state() -> CurrentRoleState: ...

def load_role_bundle(role_name: str) -> RoleBundle:
    role_name = normalize_role_name(role_name)
    base_path = role_dir(role_name)
    resident_files = {...}
    maybe_bootstrap_project_from_cwd(base_path)
    context_snapshot = build_frozen_snapshot(base_path)
    return RoleBundle(...)
```

- [ ] **Step 2: Remove unused fallback helpers tied only to current-state writes**

```python
# remove if now-unused:
# def roleme_state_home() -> Path: ...
# def _directory_writable(path: Path) -> bool: ...
```

- [ ] **Step 3: Keep bootstrap behavior intact**

```python
def load_query_context_bundle(...):
    ...
    maybe_bootstrap_project_from_cwd(base_path)
    discovered_paths = discover_context_paths(...)
    context_snapshot = build_context_snapshot(...)
    return QueryContextBundle(...)
```

- [ ] **Step 4: Run tests for bundle loading and bootstrap**

Run: `python3 -m pytest tests/test_role_ops.py -k "load_role_bundle or load_query_context_bundle or bootstrap" -v`  
Expected: PASS, including new no-current-file assertions.

- [ ] **Step 5: Commit**

```bash
git add tools/role_ops.py skills/roleme/tools/role_ops.py tests/test_role_ops.py
git commit -m "refactor: remove global current role state runtime"
```

### Task 3: Enforce Explicit Role Resolution In Workflow Archives

**Files:**
- Modify: `tools/role_ops.py`
- Modify: `skills/roleme/tools/role_ops.py` (generated copy only via sync command)
- Test: `tests/test_role_ops.py`

- [ ] **Step 1: Add deterministic role resolver helper**

```python
def _resolve_archive_role_name(
    explicit_role_name: str | None,
    plan_role_name: str | None,
) -> str:
    normalized_explicit = normalize_role_name(explicit_role_name) if explicit_role_name else ""
    normalized_plan = normalize_role_name(plan_role_name) if plan_role_name else ""
    if normalized_explicit and normalized_plan and normalized_explicit != normalized_plan:
        raise ValueError("Workflow archive role_name conflicts with plan.role_name.")
    resolved = normalized_explicit or normalized_plan
    if not resolved:
        raise ValueError("Workflow archive requires role_name.")
    return resolved
```

- [ ] **Step 2: Update archive entrypoints**

```python
def archive_general_workflow(
    plan: WorkflowArchivePlan,
    role_name: str | None = None,
) -> WorkflowArchiveResult:
    resolved_role = _resolve_archive_role_name(role_name, plan.role_name)
    role_path = role_dir(resolved_role)
    if not role_path.exists():
        raise FileNotFoundError(f"Role does not exist: {role_path}")
    ...
    return WorkflowArchiveResult(role_name=resolved_role, ...)


def archive_project_workflow(
    plan: WorkflowArchivePlan,
    role_name: str | None = None,
) -> WorkflowArchiveResult:
    resolved_role = _resolve_archive_role_name(role_name, plan.role_name)
    role_path = role_dir(resolved_role)
    if not role_path.exists():
        raise FileNotFoundError(f"Role does not exist: {role_path}")
    ...
```

- [ ] **Step 2.5: Use deterministic source-of-truth sync flow**

```bash
# 1) only edit source file
git add tools/role_ops.py

# 2) run project sync/build script to update generated skill copy
# (repo command from scripts/build_skill.py)
python3 scripts/build_skill.py

# 3) verify no unsynced drift remains
git diff -- tools/role_ops.py skills/roleme/tools/role_ops.py
```

Expected: generated copy matches source after sync; no hand-edited divergence.

- [ ] **Step 3: Run focused workflow archive tests**

Run: `python3 -m pytest tests/test_role_ops.py -k "archive_general_workflow or archive_project_workflow" -v`  
Expected: PASS for plan-role success paths, missing role_name rejection, conflict rejection, and unknown-role rejection.

- [ ] **Step 4: Commit**

```bash
git add tools/role_ops.py skills/roleme/tools/role_ops.py tests/test_role_ops.py
git commit -m "feat: require explicit role identity for workflow archives"
```

### Task 4: Update Skill Docs And Bundle Templates

**Files:**
- Modify: `skills/roleme/SKILL.md`
- Modify: `skills/roleme/references/usage.md`
- Modify: `bundle/SKILL.template.md`
- Modify: `bundle/references/usage.md`
- Test: `tests/test_repo_scripts.py`

- [ ] **Step 1: Remove global current-role language**

```md
- 当前角色以 `ROLEME_HOME/.current-role.json` 为准；自然语言归档只能写当前角色。
+ 当前角色由当前会话加载结果决定；自然语言归档必须使用会话已加载角色。
```

- [ ] **Step 2: Explicitly define unsupported `/roleMe current` behavior**

```md
`/roleMe current` 已移除。若用户输入该命令，返回固定提示：
`/roleMe current 已不再支持全局当前角色查询。请在当前会话重新执行 /roleMe <角色名>。`
```

- [ ] **Step 3: Update repo script tests to guard doc semantics**

```python
assert "不再作为当前角色来源" in usage_md
assert "当前会话已加载的角色" in usage_md
```

- [ ] **Step 4: Run doc packaging tests**

Run: `python3 -m pytest tests/test_repo_scripts.py -k "workflow_archive_guidance or natural_language_archive_guidance" -v`  
Expected: PASS, with no requirement for `.current-role.json`.

- [ ] **Step 5: Commit**

```bash
git add skills/roleme/SKILL.md skills/roleme/references/usage.md bundle/SKILL.template.md bundle/references/usage.md tests/test_repo_scripts.py
git commit -m "docs: align roleme docs with session-scoped role binding"
```

### Task 5: Regression Verification And Final Sweep

**Files:**
- Verify: `tools/role_ops.py`
- Verify: `tests/test_role_ops.py`
- Verify: `tests/test_repo_scripts.py`

- [ ] **Step 1: Ensure no runtime references remain**

Run: `rg "get_current_role_state|set_current_role_state|current_role_state_path|\\.current-role\\.json" tools/role_ops.py skills/roleme/tools/role_ops.py`  
Expected: no runtime state API references; only allowed mentions in migration docs/tests.

- [ ] **Step 2: Run full role_ops and roundtrip suites**

Run: `python3 -m pytest tests/test_role_ops.py tests/integration/test_role_roundtrip.py -v`  
Expected: PASS.

- [ ] **Step 3: Run final repo script tests**

Run: `python3 -m pytest tests/test_repo_scripts.py -v`  
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: verify removal of global current role state end-to-end"
```
