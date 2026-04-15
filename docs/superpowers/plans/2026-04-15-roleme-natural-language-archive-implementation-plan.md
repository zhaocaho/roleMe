# roleMe Natural Language Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach `roleMe`'s packaged skill docs to support proactive natural-language archive behavior without adding new runtime code.

**Architecture:** Keep runtime untouched and express the new behavior entirely through `skill/SKILL.md` and `skill/references/usage.md`. Protect the change with packaging tests so the published `skills/roleme/` artifact always includes the new guidance after running the build script.

**Tech Stack:** Markdown docs, pytest, existing `scripts/build_skill.py` packaging flow

---

### Task 1: Lock the new guidance with tests

**Files:**
- Modify: `tests/test_repo_scripts.py`
- Test: `tests/test_repo_scripts.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_skill_includes_natural_language_archive_guidance(tmp_path):
    artifact = build_skill(output_root=tmp_path)
    skill_md = (artifact / "SKILL.md").read_text(encoding="utf-8")
    usage_md = (artifact / "references" / "usage.md").read_text(encoding="utf-8")

    assert "应主动进行归档" in skill_md
    assert "判断不够确定时，优先写入 `memory/episodes/` 或项目记忆" in skill_md
    assert "## 自然语言归档" in usage_md
    assert "用户只需要自然表达内容，系统会先总结，再选择目标位置。" in usage_md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_repo_scripts.py::test_build_skill_includes_natural_language_archive_guidance -v`
Expected: FAIL because the packaged docs do not contain the new archive guidance yet.

- [ ] **Step 3: Write minimal implementation**

Update the skill docs so the packaged artifact includes:

- proactive archive behavior in `skill/SKILL.md`
- a dedicated natural-language archive section in `skill/references/usage.md`

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_repo_scripts.py::test_build_skill_includes_natural_language_archive_guidance -v`
Expected: PASS

### Task 2: Update packaged docs and verify the full packaging flow

**Files:**
- Modify: `skill/SKILL.md`
- Modify: `skill/references/usage.md`
- Generate: `skills/roleme/SKILL.md`
- Generate: `skills/roleme/references/usage.md`
- Test: `tests/test_repo_scripts.py`

- [ ] **Step 1: Update the runtime rules in `skill/SKILL.md`**

Add short rules covering:

- proactive archive behavior after role load
- summarize before classification
- conservative fallback to `episode` / project memory
- reload reminder after resident updates

- [ ] **Step 2: Add a natural-language archive section to `skill/references/usage.md`**

Document:

- users do not need to specify paths
- default trigger scenarios
- archive decision order
- low-confidence fallback behavior
- short receipt style

- [ ] **Step 3: Rebuild the published skill artifact**

Run: `python3 scripts/build_skill.py`
Expected: prints the updated `skills/roleme` output path with no error.

- [ ] **Step 4: Run the targeted packaging tests**

Run: `./.venv/bin/python -m pytest tests/test_repo_scripts.py -q`
Expected: PASS

