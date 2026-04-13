# roleMe Hermes-Compatible Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `roleMe` to follow Hermes-style memory and context architecture while preserving the role-bundle model and making `/roleMe` load user role context instead of assistant persona.

**Architecture:** Replace the old `self-model` contract with a Hermes-compatible `persona` identity layer, keep bounded resident memory in `USER.md` and `MEMORY.md`, and add deterministic routing for progressive context discovery through `brain/` and `projects/`. Keep the runtime lightweight: file-based role bundles, explicit templates, deterministic tools, and test-first behavior changes.

**Tech Stack:** Python 3, pytest, Markdown role/context files, file-based role bundles under `~/.roleMe/`

---

## File Map

- Modify: `tools/role_ops.py`
  Role bundle schema, initialization, resident/on-demand contract, doctor checks.
- Modify: `tools/memory.py`
  Hermes-style memory operations, bounded snapshot generation, add/replace/remove/recall/compact behavior.
- Create: `tools/context_router.py`
  Deterministic routing helpers for `brain/`, `projects/`, and disclosure-driven progressive lookup.
- Modify: `tools/__init__.py`
  Export any new public helpers if needed.
- Modify: `templates/AGENT.md`
  Rewrite as user-role loading protocol with progressive disclosure routing guidance.
- Rename/Create: `templates/persona/narrative.md`
  User-role first-person identity template.
- Rename/Create: `templates/persona/communication-style.md`
  User-role communication defaults template.
- Rename/Create: `templates/persona/decision-rules.md`
  User-role decision pattern template.
- Rename/Create: `templates/persona/disclosure-layers.md`
  Progressive disclosure rules and deeper identity boundary template.
- Remove/replace usage of: `templates/self-model/*`
  Legacy assistant-facing naming to be migrated to `persona/*`.
- Modify: `templates/memory/USER.md`
  Structured durable preference store with machine-editable marker block.
- Modify: `templates/memory/MEMORY.md`
  Structured summary/index store with machine-editable marker block.
- Modify: `templates/brain/index.md`
  Hermes-style topic index for progressive discovery.
- Modify: `templates/projects/index.md`
  Project overlay discovery rules.
- Modify: `skill/SKILL.md`
  Runtime contract and command semantics in Chinese, aligned to user-role loading.
- Modify: `skill/references/usage.md`
  User-facing explanation of role loading, memory, and progressive disclosure.
- Modify: `scripts/build_skill.py`
  Package `persona/` templates and any new runtime tool file.
- Modify: `tests/test_role_ops.py`
  Schema, initialization, and bundle loading contract tests.
- Modify: `tests/test_memory.py`
  Memory add/replace/remove/recall/compact tests.
- Create: `tests/test_context_router.py`
  Progressive routing and lookup tests.
- Modify: `tests/test_repo_scripts.py`
  Packaging assertions for `persona/` and new runtime files.
- Modify: `tests/integration/test_role_roundtrip.py`
  End-to-end role init/load/memory/package flow with new contract.

## Task 1: Rename `self-model` Contract to `persona`

**Files:**
- Modify: `tools/role_ops.py`
- Modify: `tools/memory.py`
- Modify: `templates/AGENT.md`
- Create: `templates/persona/narrative.md`
- Create: `templates/persona/communication-style.md`
- Create: `templates/persona/decision-rules.md`
- Create: `templates/persona/disclosure-layers.md`
- Modify: `tests/test_role_ops.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_initialize_role_creates_persona_files(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")

    assert (role_path / "persona" / "narrative.md").exists()
    assert not (role_path / "self-model").exists()


def test_load_role_bundle_uses_persona_resident_paths(tmp_role_home):
    initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")

    assert "persona/narrative.md" in bundle.resident_files
    assert "persona/disclosure-layers.md" in bundle.on_demand_paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_role_ops.py -v`  
Expected: FAIL because the code still creates and loads `self-model/*`

- [ ] **Step 3: Write minimal implementation**

Update `tools/role_ops.py` and `tools/memory.py` constants:

```python
RESIDENT_PATHS = [
    "persona/narrative.md",
    "persona/communication-style.md",
    "persona/decision-rules.md",
    "memory/USER.md",
    "memory/MEMORY.md",
]
```

And update initialization to create `persona/` instead of `self-model/`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_role_ops.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/role_ops.py tools/memory.py templates/AGENT.md templates/persona tests/test_role_ops.py tests/test_memory.py
git commit -m "refactor: rename self-model contract to persona"
```

## Task 2: Add Hermes-Style Memory CRUD Semantics

**Files:**
- Modify: `tools/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_replace_memory_entry_updates_existing_value(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    write_memory(role_path, target="user", content="默认中文沟通")

    replace_memory_entry(role_path, target="user", old_content="默认中文沟通", new_content="默认中英双语沟通")

    result = recall(role_path, "双语")
    assert result["summary_hits"] == ["- 默认中英双语沟通"]


def test_remove_memory_entry_deletes_existing_value(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    write_memory(role_path, target="memory", content="先结论后细节")

    remove_memory_entry(role_path, target="memory", content="先结论后细节")

    result = recall(role_path, "先结论")
    assert result["summary_hits"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory.py -v`  
Expected: FAIL because replace/remove APIs do not exist

- [ ] **Step 3: Write minimal implementation**

Add deterministic helpers in `tools/memory.py`:

```python
def replace_memory_entry(role_path: Path, target: str, old_content: str, new_content: str) -> bool:
    ...


def remove_memory_entry(role_path: Path, target: str, content: str) -> bool:
    ...
```

Rules:

- only operate inside the marker block
- match normalized bullet entries
- reject unsafe replacement content
- return whether a change happened

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_memory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/memory.py tests/test_memory.py
git commit -m "feat: add memory replace and remove operations"
```

## Task 3: Make Memory Bounded and Hermes-Like

**Files:**
- Modify: `tools/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_frozen_snapshot_prioritizes_resident_sections(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    snapshot = build_frozen_snapshot(role_path, max_chars=240)

    assert "persona/narrative.md" in snapshot
    assert len(snapshot) <= 240


def test_compact_memory_keeps_newest_entries_within_budget(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    for index in range(6):
        write_memory(role_path, target="memory", content=f"item {index}")

    compact_memory(role_path, target="memory", max_entries=3)

    result = recall(role_path, "item")
    assert result["summary_hits"] == ["- item 3", "- item 4", "- item 5"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory.py -v`  
Expected: FAIL because compaction currently keeps the oldest entries and snapshot still uses legacy persona paths

- [ ] **Step 3: Write minimal implementation**

Adjust:

- resident snapshot generation to use `persona/*`
- compaction strategy to preserve the most recent entries
- helper normalization so new and replaced entries behave consistently

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_memory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/memory.py tests/test_memory.py
git commit -m "refactor: align memory snapshot and compaction with hermes model"
```

## Task 4: Add Progressive Context Routing

**Files:**
- Create: `tools/context_router.py`
- Modify: `tools/role_ops.py`
- Modify: `templates/AGENT.md`
- Modify: `templates/brain/index.md`
- Modify: `templates/projects/index.md`
- Create: `tests/test_context_router.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_route_context_prefers_brain_for_domain_queries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    result = route_context_lookup(role_path, query="帮我分析这个 AI 产品策略")

    assert result.primary_path == "brain/index.md"


def test_route_context_prefers_projects_for_project_queries(tmp_role_home):
    role_path = initialize_role("self", skill_version="0.1.0")
    result = route_context_lookup(role_path, query="这个仓库里的 roleMe 重构怎么推进")

    assert result.primary_path == "projects/index.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_context_router.py -v`  
Expected: FAIL because router does not exist

- [ ] **Step 3: Write minimal implementation**

Create `tools/context_router.py` with deterministic helpers:

```python
@dataclass(frozen=True)
class ContextRoute:
    primary_path: str
    fallback_paths: list[str]


def route_context_lookup(role_path: Path, query: str) -> ContextRoute:
    ...
```

Rules:

- use simple deterministic heuristics first
- prefer `brain/index.md` for domain-like queries
- prefer `projects/index.md` for repo/project-like queries
- keep `memory/episodes/*` as fallback when summary memory is insufficient

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_context_router.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/context_router.py tools/role_ops.py templates/AGENT.md templates/brain/index.md templates/projects/index.md tests/test_context_router.py
git commit -m "feat: add progressive context routing"
```

## Task 5: Rewrite Templates to Match Hermes-Compatible User Role Semantics

**Files:**
- Modify: `templates/AGENT.md`
- Modify: `templates/memory/USER.md`
- Modify: `templates/memory/MEMORY.md`
- Modify: `templates/brain/index.md`
- Modify: `templates/projects/index.md`
- Create: `templates/persona/narrative.md`
- Create: `templates/persona/communication-style.md`
- Create: `templates/persona/decision-rules.md`
- Create: `templates/persona/disclosure-layers.md`
- Modify: `tests/test_repo_scripts.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_built_artifact_contains_persona_templates(tmp_path):
    artifact = publish_skill(output_root=tmp_path)

    assert (artifact / "assets" / "templates" / "persona" / "narrative.md").exists()
    assert not (artifact / "assets" / "templates" / "self-model").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repo_scripts.py -v`  
Expected: FAIL because the packaged templates still use `self-model`

- [ ] **Step 3: Write minimal implementation**

Rewrite template text in Chinese so that:

- `AGENT.md` defines user-role interpretation
- `persona/*` defines identity, style, rules, disclosure
- `USER.md` and `MEMORY.md` keep marker-block sections
- `brain/index.md` and `projects/index.md` explain progressive discovery

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_repo_scripts.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates tests/test_repo_scripts.py
git commit -m "refactor: rewrite templates for hermes-compatible role context"
```

## Task 6: Align Packaging and Skill Docs

**Files:**
- Modify: `scripts/build_skill.py`
- Modify: `skill/SKILL.md`
- Modify: `skill/references/usage.md`
- Modify: `tests/test_repo_scripts.py`
- Modify: `tests/integration/test_role_roundtrip.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_skill_packages_persona_and_router(tmp_path):
    artifact = publish_skill(output_root=tmp_path)

    assert (artifact / "tools" / "context_router.py").exists()
    assert (artifact / "assets" / "templates" / "persona" / "narrative.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repo_scripts.py tests/integration/test_role_roundtrip.py -v`  
Expected: FAIL because build output does not yet include the new files and contract

- [ ] **Step 3: Write minimal implementation**

Update packaging and docs so that:

- built skill includes `persona/` templates
- built skill includes `tools/context_router.py`
- `skill/SKILL.md` and `skill/references/usage.md` explain the new user-role semantics in Chinese

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_repo_scripts.py tests/integration/test_role_roundtrip.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build_skill.py skill tests/test_repo_scripts.py tests/integration/test_role_roundtrip.py
git commit -m "docs: align packaged skill with hermes-compatible runtime"
```

## Task 7: End-to-End Verification

**Files:**
- Modify: `tests/integration/test_role_roundtrip.py`
- Modify: `tests/test_memory.py`
- Modify: `tests/test_role_ops.py`
- Modify: `tests/test_context_router.py`

- [ ] **Step 1: Write the failing integration assertions**

```python
def test_role_roundtrip_uses_persona_memory_and_progressive_paths(tmp_role_home, tmp_path):
    role_path = initialize_role("self", skill_version="0.1.0")
    bundle = load_role_bundle("self")

    assert "persona/narrative.md" in bundle.resident_files
    assert "brain/index.md" in bundle.on_demand_paths
```

- [ ] **Step 2: Run full test suite to verify failures are real**

Run: `python -m pytest -q`  
Expected: FAIL only in newly added expectations if earlier tasks are incomplete

- [ ] **Step 3: Finish any minimal integration fixes**

Ensure all public contracts line up:

- role initialization
- resident snapshot
- memory CRUD
- progressive routing
- package output

- [ ] **Step 4: Run full test suite to verify it passes**

Run: `python -m pytest -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests tools templates skill scripts
git commit -m "test: verify hermes-compatible roleme refactor"
```

## Notes for Execution

- Keep the runtime deterministic and file-based.
- Do not introduce a full Hermes session/runtime stack unless explicitly requested later.
- Prefer small public helpers over a large orchestration class.
- Keep Chinese user-facing docs and templates aligned with the spec.
- Preserve marker-block editing for memory files so the model can help with deterministic add/replace/remove behavior.

## Review Notes

The writing-plans skill asks for a plan-reviewer subagent loop, but this session is not authorized for subagent delegation by default. Do a careful local review against:

- `docs/superpowers/specs/2026-04-13-roleme-skill-design.md`
- `tools/role_ops.py`
- `tools/memory.py`
- `tests/`
