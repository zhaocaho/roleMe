from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re

from tools.file_ops import atomic_write_text
from tools.graph_index import (
    EdgeRecord,
    NodeRecord,
    deterministic_edge_id,
    deterministic_node_id,
    doctor_graph,
    load_graph,
    rebuild_indexes,
    save_graph,
    upsert_edge,
    upsert_node,
)
from tools.workflow_index import WorkflowIndexEntry, parse_workflow_index


ENTRY_START = "<!-- ROLEME:ENTRIES:START -->"
ENTRY_END = "<!-- ROLEME:ENTRIES:END -->"
ENTRY_MARKER_PATTERN = re.compile(r"<!-- roleme-entry:([a-z0-9_-]+) -->")
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


@dataclass(frozen=True)
class InboxEntry:
    id: str
    title: str
    summary: str
    evidence: str
    source: str
    suggested_target: str
    confidence: str
    promotion_notes: str
    created_at: str
    last_seen_at: str
    recurrence: int = 1
    status: str = "pending"


@dataclass(frozen=True)
class LearningEntry:
    id: str
    title: str
    rule_candidate: str
    how_to_apply: str
    evidence: str
    promotion_target: str
    learning_type: str
    applies_to: str
    created_at: str
    last_seen_at: str
    recurrence: int = 1
    priority: str = "normal"
    status: str = "pending"


@dataclass(frozen=True)
class InternalSkill:
    slug: str
    title: str
    applies_to: str
    keywords: list[str]
    summary: str
    body_markdown: str


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    date: str
    started_at: str
    ended_at: str
    summary: str
    keywords: list[str]
    work_completed: list[str]
    decisions: list[str]
    artifacts: list[str]
    inbox_candidates: list[InboxEntry]
    learning_candidates: list[LearningEntry]
    suggested_promotions: list[str]


def _ensure_lifecycle_indexes(role_path: Path) -> None:
    indexes = {
        role_path / "memory" / "inbox" / "index.md": (
            "# Inbox\n\n## pending\n\n## promoted\n\n## closed\n"
        ),
        role_path / "memory" / "learnings" / "index.md": (
            "# Learnings\n\n## pending\n\n## promoted\n\n## closed\n"
        ),
    }
    for path, content in indexes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            atomic_write_text(path, content)


def _field_value(text: str, field: str) -> str:
    match = re.search(rf"^- {re.escape(field)}: (.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _section_value(text: str, section: str) -> str:
    match = re.search(
        rf"^## {re.escape(section)}\n\n(.*?)(?=\n## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _normalize_candidate_key(*parts: str) -> str:
    joined = " ".join(part.strip().casefold() for part in parts)
    return re.sub(r"\s+", " ", joined)


def _replace_field(text: str, field: str, value: str | int) -> str:
    return re.sub(
        rf"^- {re.escape(field)}: .*$",
        f"- {field}: {value}",
        text,
        flags=re.MULTILINE,
    )


def _append_section_line(text: str, section: str, line: str) -> str:
    marker = f"## {section}\n\n"
    if marker not in text:
        return text
    before, after = text.split(marker, maxsplit=1)
    if "\n## " in after:
        body, rest = after.split("\n## ", maxsplit=1)
        return before + marker + body.rstrip() + f"\n\n{line}\n\n## " + rest
    return before + marker + after.rstrip() + f"\n\n{line}\n"


def _upsert_status_index_entry(
    index_path: Path,
    status: str,
    entry_id: str,
    title: str,
    relative_path: str,
) -> None:
    text = index_path.read_text(encoding="utf-8")
    line = f"- {entry_id}: {title} -> {relative_path}"
    if entry_id in text:
        text = re.sub(
            rf"^- {re.escape(entry_id)}: .*$", line, text, flags=re.MULTILINE
        )
        atomic_write_text(index_path, text)
        return
    heading = f"## {status}"
    if heading not in text:
        text = text.rstrip() + f"\n\n{heading}\n"
    text = text.replace(heading + "\n", heading + "\n" + line + "\n", 1)
    atomic_write_text(index_path, text)


def _ensure_skills_index(role_path: Path) -> None:
    skills_dir = role_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    index = skills_dir / "index.md"
    if not index.exists():
        atomic_write_text(index, "# Internal Skills\n")


def _render_internal_skill_index_entry(skill: InternalSkill) -> str:
    return (
        f"## {skill.slug}\n"
        f"- title: {skill.title}\n"
        f"- file: {skill.slug}.md\n"
        f"- applies_to: {skill.applies_to}\n"
        f"- keywords: {', '.join(skill.keywords)}\n"
        f"- summary: {skill.summary}\n"
    )


def _upsert_internal_skill_index(index_path: Path, skill: InternalSkill) -> None:
    text = index_path.read_text(encoding="utf-8")
    entry = _render_internal_skill_index_entry(skill)
    pattern = rf"^## {re.escape(skill.slug)}\n(?:^- .*\n?)+"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, entry, text, flags=re.MULTILINE)
    else:
        text = text.rstrip() + "\n\n" + entry
    atomic_write_text(index_path, text)


def _ensure_sessions_index(role_path: Path) -> None:
    sessions_dir = role_path / "memory" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    index = sessions_dir / "index.md"
    if not index.exists():
        atomic_write_text(index, "# Sessions\n")


def _render_bullets(items: list[str]) -> str:
    if not items:
        return "- none\n"
    return "\n".join(f"- {item}" for item in items) + "\n"


def _render_inbox_candidate_bullets(items: list[InboxEntry]) -> str:
    if not items:
        return "- none\n"
    return (
        "\n".join(
            f"- {item.id}: {item.summary} -> {item.suggested_target}"
            for item in items
        )
        + "\n"
    )


def _render_learning_candidate_bullets(items: list[LearningEntry]) -> str:
    if not items:
        return "- none\n"
    return (
        "\n".join(
            f"- {item.id}: {item.rule_candidate} -> {item.promotion_target}"
            for item in items
        )
        + "\n"
    )


def _render_session_summary(summary: SessionSummary) -> str:
    return (
        f"# Session Summary - {summary.session_id}\n\n"
        f"- session_id: {summary.session_id}\n"
        f"- date: {summary.date}\n"
        f"- started_at: {summary.started_at}\n"
        f"- ended_at: {summary.ended_at}\n\n"
        "## Work Completed\n\n"
        f"{_render_bullets(summary.work_completed)}\n"
        "## Decisions\n\n"
        f"{_render_bullets(summary.decisions)}\n"
        "## Artifacts\n\n"
        f"{_render_bullets(summary.artifacts)}\n"
        "## Inbox Candidates\n\n"
        f"{_render_inbox_candidate_bullets(summary.inbox_candidates)}\n"
        "## Learning Candidates\n\n"
        f"{_render_learning_candidate_bullets(summary.learning_candidates)}\n"
        "## Suggested Promotions\n\n"
        f"{_render_bullets(summary.suggested_promotions)}"
    )


def _upsert_session_index(index_path: Path, summary: SessionSummary) -> None:
    text = index_path.read_text(encoding="utf-8")
    entry = (
        f"## {summary.session_id}\n"
        f"- file: {summary.session_id}.md\n"
        f"- started_at: {summary.started_at}\n"
        f"- ended_at: {summary.ended_at}\n"
        f"- summary: {summary.summary}\n"
        f"- keywords: {', '.join(summary.keywords)}\n"
        f"- inbox_candidates: {len(summary.inbox_candidates)}\n"
        f"- learning_candidates: {len(summary.learning_candidates)}\n"
        f"- promotions: {len(summary.suggested_promotions)}\n"
    )
    pattern = rf"^## {re.escape(summary.session_id)}\n(?:^- .*\n?)+"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, entry, text, flags=re.MULTILINE)
    else:
        text = text.rstrip() + "\n\n" + entry
    atomic_write_text(index_path, text)


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


def _entry_key_for(content: str) -> str:
    normalized = _strip_entry_marker(content).strip().strip("-").strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _entry_marker_key(entry: str) -> str | None:
    match = ENTRY_MARKER_PATTERN.search(entry)
    return match.group(1) if match else None


def _format_entry_with_marker(content: str) -> str:
    bullet = _normalize_entry(content)
    return f"{bullet} <!-- roleme-entry:{_entry_key_for(bullet)} -->"


def _strip_entry_marker(entry: str) -> str:
    return ENTRY_MARKER_PATTERN.sub("", entry).strip()


def _entry_content(entry: str) -> str:
    return _strip_entry_marker(entry).strip().strip("-").strip()


def _store_name(target: str) -> str:
    if target == "memory":
        return "MEMORY.md"
    if target in {"user", "preference"}:
        return "USER.md"
    raise ValueError(f"Unsupported memory target: {target}")


def _store_path(role_path: Path, target: str) -> Path:
    return role_path / "memory" / _store_name(target)


def _graph_archive_enabled() -> bool:
    return os.environ.get("ROLEME_GRAPH_ARCHIVE", "1") != "0"


def _persist_graph(role_path: Path, nodes: list[NodeRecord], edges: list[EdgeRecord]) -> None:
    save_graph(role_path, nodes, edges)
    rebuild_indexes(role_path, nodes)
    doctor_graph(role_path)


def _safe_persist_graph(role_path: Path, nodes: list[NodeRecord], edges: list[EdgeRecord]) -> None:
    try:
        _persist_graph(role_path, nodes, edges)
    except Exception:
        return


def _memory_node_type(target: str) -> str:
    if target in {"user", "preference"}:
        return "Preference"
    if target == "memory":
        return "Principle"
    if target == "episode":
        return "Episode"
    raise ValueError(f"Unsupported memory graph target: {target}")


def _upsert_memory_graph_node(
    role_path: Path,
    target: str,
    content: str,
    path: str,
    entry_key: str,
) -> None:
    if not _graph_archive_enabled():
        return

    node_type = _memory_node_type(target)
    graph = load_graph(role_path)
    evidence_key = f"evidence-{entry_key}"
    node = NodeRecord(
        id=deterministic_node_id(
            node_type=node_type,
            scope="global",
            path=path,
            title=content,
            metadata={"entry_key": entry_key},
        ),
        type=node_type,
        scope="global",
        path=path,
        title=content,
        metadata={"entry_key": entry_key},
    )
    evidence = NodeRecord(
        id=deterministic_node_id(
            node_type="Evidence",
            scope="global",
            title=f"Evidence for {evidence_key}",
            metadata={"entry_key": evidence_key},
        ),
        type="Evidence",
        scope="global",
        path=path,
        title=f"Evidence for {content}",
        metadata={"source_type": "user_statement", "source_path": path},
    )
    edge = EdgeRecord(
        id=deterministic_edge_id(node.id, "evidenced_by", evidence.id),
        type="evidenced_by",
        from_node=node.id,
        to_node=evidence.id,
    )
    nodes = upsert_node(graph.nodes, node)
    nodes = upsert_node(nodes, evidence)
    edges = upsert_edge(graph.edges, edge)
    _safe_persist_graph(role_path, nodes, edges)


def _upsert_candidate_graph_node(
    role_path: Path,
    node_type: str,
    relative_path: str,
    title: str,
    summary: str,
    metadata: dict[str, str],
) -> None:
    if not _graph_archive_enabled():
        return
    try:
        graph = load_graph(role_path)
        node = NodeRecord(
            id=deterministic_node_id(
                node_type=node_type,
                scope="global",
                path=relative_path,
                title=title,
                metadata=metadata,
            ),
            type=node_type,
            scope="global",
            path=relative_path,
            title=title,
            summary=summary,
            metadata=metadata,
        )
        nodes = upsert_node(graph.nodes, node)
        _safe_persist_graph(role_path, nodes, graph.edges)
    except Exception:
        return


def _update_memory_graph_node_title(
    role_path: Path,
    target: str,
    entry_key: str,
    new_content: str,
) -> None:
    if not _graph_archive_enabled():
        return

    node_type = _memory_node_type(target)
    graph = load_graph(role_path)
    updated_nodes: list[NodeRecord] = []
    changed = False
    for node in graph.nodes:
        if node.type == node_type and node.metadata.get("entry_key") == entry_key:
            updated_nodes.append(
                NodeRecord(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    project_slug=node.project_slug,
                    path=node.path,
                    title=new_content,
                    summary=node.summary,
                    aliases=node.aliases,
                    keywords=node.keywords,
                    status=node.status,
                    confidence=node.confidence,
                    metadata=node.metadata,
                )
            )
            changed = True
        else:
            updated_nodes.append(node)
    if changed:
        _safe_persist_graph(role_path, updated_nodes, graph.edges)


def _find_entry_index(entries: list[str], content: str) -> tuple[int | None, str | None]:
    normalized_content = content.strip().strip("-").strip()
    for index, entry in enumerate(entries):
        if _entry_content(entry) == normalized_content:
            return index, _entry_marker_key(entry) or _entry_key_for(entry)
    return None, None


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


def _render_inbox_entry(entry: InboxEntry) -> str:
    return (
        f"# {entry.title}\n\n"
        f"- id: {entry.id}\n"
        f"- status: {entry.status}\n"
        f"- source: {entry.source}\n"
        f"- recurrence: {entry.recurrence}\n"
        f"- created_at: {entry.created_at}\n"
        f"- last_seen_at: {entry.last_seen_at}\n"
        f"- suggested_target: {entry.suggested_target}\n"
        f"- confidence: {entry.confidence}\n\n"
        "## Summary\n\n"
        f"{entry.summary}\n\n"
        "## Evidence\n\n"
        f"{entry.evidence}\n\n"
        "## Promotion Notes\n\n"
        f"{entry.promotion_notes}\n"
    )


def _render_learning_entry(entry: LearningEntry) -> str:
    return (
        f"# {entry.title}\n\n"
        f"- id: {entry.id}\n"
        f"- type: {entry.learning_type}\n"
        f"- status: {entry.status}\n"
        f"- recurrence: {entry.recurrence}\n"
        f"- priority: {entry.priority}\n"
        f"- created_at: {entry.created_at}\n"
        f"- last_seen_at: {entry.last_seen_at}\n"
        f"- applies_to: {entry.applies_to}\n\n"
        "## Rule Candidate\n\n"
        f"{entry.rule_candidate}\n\n"
        "## How To Apply\n\n"
        f"{entry.how_to_apply}\n\n"
        "## Evidence\n\n"
        f"{entry.evidence}\n\n"
        "## Promotion Target\n\n"
        f"{entry.promotion_target}\n"
    )


def _find_matching_inbox(role_path: Path, entry: InboxEntry) -> Path | None:
    inbox_dir = role_path / "memory" / "inbox"
    key = _normalize_candidate_key(entry.summary, entry.suggested_target)
    for path in sorted(inbox_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8")
        if _field_value(text, "status") != "pending":
            continue
        existing_key = _normalize_candidate_key(
            _section_value(text, "Summary"),
            _field_value(text, "suggested_target"),
        )
        if existing_key == key:
            return path
    return None


def _find_matching_learning(role_path: Path, entry: LearningEntry) -> Path | None:
    learnings_dir = role_path / "memory" / "learnings"
    key = _normalize_candidate_key(
        entry.learning_type, entry.applies_to, entry.rule_candidate
    )
    for path in sorted(learnings_dir.glob("*.md")):
        if path.name == "index.md":
            continue
        text = path.read_text(encoding="utf-8")
        if _field_value(text, "status") != "pending":
            continue
        existing_key = _normalize_candidate_key(
            _field_value(text, "type"),
            _field_value(text, "applies_to"),
            _section_value(text, "Rule Candidate"),
        )
        if existing_key == key:
            return path
    return None


def build_frozen_snapshot(role_path: Path, max_chars: int = 2_000) -> str:
    section_budget = max(1, max_chars // len(RESIDENT_PATHS))
    chunks: list[str] = []
    for relative in RESIDENT_PATHS:
        header = f"## {relative}\n"
        content_budget = max(0, section_budget - len(header))
        path = role_path / relative
        if relative.startswith("memory/"):
            content = "\n".join(_strip_entry_marker(entry) for entry in _read_entries(path))
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
        relative_path = f"memory/episodes/{episode_path.name}"
        _upsert_memory_graph_node(
            role_path,
            target="episode",
            content=content.strip(),
            path=relative_path,
            entry_key=_entry_key_for(content),
        )
        return episode_path

    store_path = _store_path(role_path, target)
    bullet = _format_entry_with_marker(content)
    if not _is_safe(bullet):
        return None

    entries = _read_entries(store_path)
    entry_key = _entry_key_for(bullet)
    if all((_entry_marker_key(entry) or _entry_key_for(entry)) != entry_key for entry in entries):
        _replace_entries(store_path, entries + [bullet])
        _upsert_memory_graph_node(
            role_path,
            target=target,
            content=_entry_content(bullet),
            path=f"memory/{_store_name(target)}",
            entry_key=entry_key,
        )
    return None


def write_inbox_entry(role_path: Path, entry: InboxEntry) -> Path:
    _ensure_lifecycle_indexes(role_path)
    existing = _find_matching_inbox(role_path, entry)
    if existing is not None:
        text = existing.read_text(encoding="utf-8")
        recurrence = int(_field_value(text, "recurrence") or "1") + 1
        text = _replace_field(text, "recurrence", recurrence)
        text = _replace_field(text, "last_seen_at", entry.last_seen_at)
        text = _append_section_line(text, "Evidence", entry.evidence)
        atomic_write_text(existing, text)
        return existing

    path = role_path / "memory" / "inbox" / f"{entry.id}.md"
    atomic_write_text(path, _render_inbox_entry(entry))
    relative = f"memory/inbox/{entry.id}.md"
    _upsert_status_index_entry(
        role_path / "memory" / "inbox" / "index.md",
        entry.status,
        entry.id,
        entry.title,
        relative,
    )
    _upsert_candidate_graph_node(
        role_path,
        "MemoryCandidate",
        relative,
        entry.title,
        entry.summary,
        {
            "candidate_id": entry.id,
            "suggested_target": entry.suggested_target,
            "confidence": entry.confidence,
        },
    )
    return path


def write_learning_entry(role_path: Path, entry: LearningEntry) -> Path:
    _ensure_lifecycle_indexes(role_path)
    existing = _find_matching_learning(role_path, entry)
    if existing is not None:
        text = existing.read_text(encoding="utf-8")
        recurrence = int(_field_value(text, "recurrence") or "1") + 1
        text = _replace_field(text, "recurrence", recurrence)
        text = _replace_field(text, "last_seen_at", entry.last_seen_at)
        text = _append_section_line(text, "Evidence", entry.evidence)
        atomic_write_text(existing, text)
        return existing

    path = role_path / "memory" / "learnings" / f"{entry.id}.md"
    atomic_write_text(path, _render_learning_entry(entry))
    relative = f"memory/learnings/{entry.id}.md"
    _upsert_status_index_entry(
        role_path / "memory" / "learnings" / "index.md",
        entry.status,
        entry.id,
        entry.title,
        relative,
    )
    _upsert_candidate_graph_node(
        role_path,
        "Learning",
        relative,
        entry.title,
        entry.rule_candidate,
        {
            "learning_id": entry.id,
            "type": entry.learning_type,
            "applies_to": entry.applies_to,
        },
    )
    return path


def write_internal_skill(role_path: Path, skill: InternalSkill) -> Path:
    _ensure_skills_index(role_path)
    path = role_path / "skills" / f"{skill.slug}.md"
    atomic_write_text(path, skill.body_markdown.rstrip() + "\n")
    _upsert_internal_skill_index(role_path / "skills" / "index.md", skill)
    _upsert_candidate_graph_node(
        role_path,
        "Skill",
        f"skills/{skill.slug}.md",
        skill.title,
        skill.summary,
        {
            "skill_slug": skill.slug,
            "applies_to": skill.applies_to,
            "keywords": ", ".join(skill.keywords),
        },
    )
    return path


def write_session_summary(role_path: Path, summary: SessionSummary) -> Path:
    _ensure_sessions_index(role_path)
    path = role_path / "memory" / "sessions" / f"{summary.session_id}.md"
    if path.exists():
        raise FileExistsError(f"Session summary already exists: {path}")
    atomic_write_text(path, _render_session_summary(summary))
    _upsert_session_index(role_path / "memory" / "sessions" / "index.md", summary)
    _upsert_candidate_graph_node(
        role_path,
        "Session",
        f"memory/sessions/{summary.session_id}.md",
        f"Session {summary.session_id}",
        summary.summary,
        {
            "session_id": summary.session_id,
            "date": summary.date,
            "keywords": ", ".join(summary.keywords),
        },
    )
    return path


def replace_memory_entry(
    role_path: Path,
    target: str,
    old_content: str,
    new_content: str,
) -> bool:
    store_path = _store_path(role_path, target)
    old_bullet = _normalize_entry(old_content)
    new_bullet = _format_entry_with_marker(new_content)
    if not _is_safe(new_bullet):
        return False

    entries = _read_entries(store_path)
    old_index, old_entry_key = _find_entry_index(entries, old_bullet)
    try:
        index = entries.index(old_bullet)
    except ValueError:
        if old_index is None:
            return False
        index = old_index

    updated_entries = list(entries)
    entry_key = old_entry_key or _entry_key_for(old_bullet)
    updated_entries[index] = f"{_normalize_entry(new_content)} <!-- roleme-entry:{entry_key} -->"
    deduped_entries: list[str] = []
    for entry in updated_entries:
        if entry not in deduped_entries:
            deduped_entries.append(entry)
    _replace_entries(store_path, deduped_entries)
    _update_memory_graph_node_title(role_path, target, entry_key, new_content.strip())
    return True


def remove_memory_entry(role_path: Path, target: str, content: str) -> bool:
    store_path = _store_path(role_path, target)
    bullet = _normalize_entry(content)
    entries = _read_entries(store_path)
    matched_entries = [
        entry
        for entry in entries
        if entry == bullet or _entry_content(entry) == bullet.strip().strip("-").strip()
    ]
    if not matched_entries:
        return False

    _replace_entries(store_path, [entry for entry in entries if entry not in matched_entries])
    return True


def summarize_and_write(role_path: Path, target: str, source_text: str) -> None:
    store_path = _store_path(role_path, target)
    entries = _read_entries(store_path)
    seen = {_entry_content(entry) for entry in entries}
    normalized: list[str] = []
    for fragment in SPLIT_PATTERN.split(source_text):
        clean_fragment = fragment.strip(" .。；;")
        if not clean_fragment:
            continue
        bullet = _format_entry_with_marker(clean_fragment)
        content_key = _entry_content(bullet)
        if content_key not in seen and _is_safe(bullet):
            seen.add(content_key)
            normalized.append(bullet)
    _replace_entries(store_path, entries + normalized)
    for entry in normalized:
        _upsert_memory_graph_node(
            role_path,
            target=target,
            content=_entry_content(entry),
            path=f"memory/{_store_name(target)}",
            entry_key=_entry_key_for(entry),
        )


def recall(role_path: Path, query: str) -> dict[str, list[str]]:
    summary_hits: list[str] = []
    for relative in ["memory/USER.md", "memory/MEMORY.md"]:
        summary_hits.extend(
            _strip_entry_marker(entry)
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
