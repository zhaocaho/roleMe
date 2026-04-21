from __future__ import annotations

from pathlib import Path
import re

from tools.file_ops import atomic_write_text
from tools.workflow_index import WorkflowIndexEntry, parse_workflow_index


ENTRY_START = "<!-- ROLEME:ENTRIES:START -->"
ENTRY_END = "<!-- ROLEME:ENTRIES:END -->"
RESIDENT_PATHS = [
    "persona/narrative.md",
    "persona/communication-style.md",
    "persona/decision-rules.md",
    "memory/USER.md",
    "memory/MEMORY.md",
]
UNSAFE_PATTERNS = [
    re.compile(r"ignore previous instructions", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"[\u200b-\u200f\u2060\ufeff]"),
]
SPLIT_PATTERN = re.compile(r"[;\n]+")


def _read_entries(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    block = text.split(ENTRY_START, maxsplit=1)[1].split(ENTRY_END, maxsplit=1)[0]
    return [line.strip() for line in block.strip().splitlines() if line.strip()]


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
    atomic_write_text(path, updated)


def _is_safe(text: str) -> bool:
    return not any(pattern.search(text) for pattern in UNSAFE_PATTERNS)


def _normalize_entry(content: str) -> str:
    return f"- {content.strip().strip('-').strip()}"


def _store_name(target: str) -> str:
    if target == "memory":
        return "MEMORY.md"
    if target in {"user", "preference"}:
        return "USER.md"
    raise ValueError(f"Unsupported memory target: {target}")


def _store_path(role_path: Path, target: str) -> Path:
    return role_path / "memory" / _store_name(target)


def _slugify_workspace(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _find_git_repo_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _resolve_current_project_slug(role_path: Path) -> str | None:
    projects_dir = role_path / "projects"
    if not projects_dir.exists():
        return None

    project_slugs = {path.name for path in projects_dir.iterdir() if path.is_dir()}
    repo_root = _find_git_repo_root()
    if repo_root is None:
        return None

    workspace_slug = _slugify_workspace(repo_root.name)
    return workspace_slug if workspace_slug in project_slugs else None


def _read_workflow_entries(index_path: Path) -> list[WorkflowIndexEntry]:
    if not index_path.exists() or not index_path.is_file():
        return []

    text = index_path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    return parse_workflow_index(text)


def _render_workflow_summary_section(
    title: str,
    entries: list[WorkflowIndexEntry],
    project_slug: str | None = None,
) -> str:
    if not entries:
        return ""

    lines = [f"## {title}"]
    if project_slug is not None:
        lines.append(f"project: {project_slug}")
    lines.append("")

    for entry in entries:
        lines.extend(
            [
                f"- slug: {entry.slug}",
                f"  title: {entry.title}",
                f"  applies_to: {entry.applies_to}",
                f"  keywords: {', '.join(entry.keywords)}",
                f"  summary: {entry.summary}",
            ]
        )

    return "\n".join(lines).strip()


def build_frozen_snapshot(role_path: Path, max_chars: int = 2_000) -> str:
    section_budget = max(1, max_chars // len(RESIDENT_PATHS))
    chunks: list[str] = []
    for relative in RESIDENT_PATHS:
        header = f"## {relative}\n"
        content_budget = max(0, section_budget - len(header))
        path = role_path / relative
        if relative.startswith("memory/"):
            content = "\n".join(_read_entries(path))
        else:
            content = path.read_text(encoding="utf-8").strip()
        chunks.append(f"{header}{content[:content_budget]}")

    project_slug = _resolve_current_project_slug(role_path)
    if project_slug is not None:
        project_section = _render_workflow_summary_section(
            "Current Project Workflow Summaries",
            _read_workflow_entries(
                role_path / "projects" / project_slug / "workflows" / "index.md"
            ),
            project_slug=project_slug,
        )
        if project_section:
            chunks.append(project_section)

    global_section = _render_workflow_summary_section(
        "Global Workflow Summaries",
        _read_workflow_entries(role_path / "brain" / "workflows" / "index.md"),
    )
    if global_section:
        chunks.append(global_section)

    return "\n\n".join(chunks)[:max_chars]


def write_memory(role_path: Path, target: str, content: str):
    if target == "episode":
        episodes_dir = role_path / "memory" / "episodes"
        episode_path = episodes_dir / f"episode-{len(list(episodes_dir.glob('*.md'))) + 1:03d}.md"
        atomic_write_text(episode_path, content.strip() + "\n")
        return episode_path

    store_path = _store_path(role_path, target)
    bullet = _normalize_entry(content)
    if not _is_safe(bullet):
        return None

    entries = _read_entries(store_path)
    if bullet not in entries:
        _replace_entries(store_path, entries + [bullet])
    return None


def replace_memory_entry(
    role_path: Path,
    target: str,
    old_content: str,
    new_content: str,
) -> bool:
    store_path = _store_path(role_path, target)
    old_bullet = _normalize_entry(old_content)
    new_bullet = _normalize_entry(new_content)
    if not _is_safe(new_bullet):
        return False

    entries = _read_entries(store_path)
    try:
        index = entries.index(old_bullet)
    except ValueError:
        return False

    updated_entries = list(entries)
    updated_entries[index] = new_bullet
    deduped_entries: list[str] = []
    for entry in updated_entries:
        if entry not in deduped_entries:
            deduped_entries.append(entry)
    _replace_entries(store_path, deduped_entries)
    return True


def remove_memory_entry(role_path: Path, target: str, content: str) -> bool:
    store_path = _store_path(role_path, target)
    bullet = _normalize_entry(content)
    entries = _read_entries(store_path)
    if bullet not in entries:
        return False

    _replace_entries(store_path, [entry for entry in entries if entry != bullet])
    return True


def summarize_and_write(role_path: Path, target: str, source_text: str) -> None:
    store_path = _store_path(role_path, target)
    entries = _read_entries(store_path)
    seen = set(entries)
    normalized: list[str] = []
    for fragment in SPLIT_PATTERN.split(source_text):
        clean_fragment = fragment.strip(" .。；;")
        if not clean_fragment:
            continue
        bullet = _normalize_entry(clean_fragment)
        if bullet not in seen and _is_safe(bullet):
            seen.add(bullet)
            normalized.append(bullet)
    _replace_entries(store_path, entries + normalized)


def recall(role_path: Path, query: str) -> dict[str, list[str]]:
    summary_hits: list[str] = []
    for relative in ["memory/USER.md", "memory/MEMORY.md"]:
        summary_hits.extend(
            entry
            for entry in _read_entries(role_path / relative)
            if query in entry
        )
    if summary_hits:
        return {"summary_hits": summary_hits, "episode_hits": []}

    episode_hits: list[str] = []
    for path in sorted((role_path / "memory" / "episodes").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if query in text:
            episode_hits.append(text)
    return {"summary_hits": [], "episode_hits": episode_hits}


def compact_memory(role_path: Path, target: str, max_entries: int) -> None:
    store_path = _store_path(role_path, target)
    entries = _read_entries(store_path)
    _replace_entries(store_path, entries[-max_entries:])
