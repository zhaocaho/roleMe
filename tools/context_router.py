from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from tools.memory import build_frozen_snapshot
from tools.workflow_index import WorkflowIndexEntry, parse_workflow_index


PROJECT_HINTS = {
    "repo",
    "repository",
    "project",
    "workspace",
    "codebase",
    "roleme",
    "仓库",
    "项目",
    "重构",
}
DOMAIN_HINTS = {
    "ai",
    "strategy",
    "product",
    "architecture",
    "knowledge",
    "brain",
    "产品",
    "策略",
    "架构",
    "领域",
    "知识",
}
PATH_PATTERN = re.compile(r"([A-Za-z0-9_./-]+\.md)")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")
CJK_RUN_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


@dataclass(frozen=True)
class ContextRoute:
    primary_path: str
    fallback_paths: list[str]


def _tokenize(text: str) -> set[str]:
    return {match.group(0).casefold() for match in TOKEN_PATTERN.finditer(text)}


def _extract_markdown_paths(text: str) -> list[str]:
    paths: list[str] = []
    for match in PATH_PATTERN.finditer(text):
        path = match.group(1).replace("\\", "/")
        if path not in paths:
            paths.append(path)
    return paths


def _score_text(query_tokens: set[str], text: str) -> int:
    text_tokens = _tokenize(text)
    return len(query_tokens & text_tokens)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _find_git_repo_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _list_project_slugs(role_path: Path) -> list[str]:
    projects_dir = role_path / "projects"
    if not projects_dir.exists():
        return []
    return sorted(path.name for path in projects_dir.iterdir() if path.is_dir())


def _resolve_query_project_slug(role_path: Path, query: str) -> str | None:
    if not any(hint in query.casefold() for hint in PROJECT_HINTS):
        return None

    for path in discover_project_paths(role_path, query):
        if path.startswith("projects/") and path.endswith("/context.md"):
            parts = path.split("/")
            if len(parts) >= 3:
                return parts[1]
    return None


def _resolve_current_project_slug(role_path: Path, query: str) -> str | None:
    existing_slugs = _list_project_slugs(role_path)
    if not existing_slugs:
        return None

    repo_root = _find_git_repo_root()
    if repo_root is not None:
        workspace_slug = _slugify(repo_root.name)
        if workspace_slug in existing_slugs:
            return workspace_slug

    if len(existing_slugs) == 1:
        return existing_slugs[0]

    return _resolve_query_project_slug(role_path, query)


def _resolve_brain_path(role_path: Path, relative_path: str) -> tuple[str, Path]:
    normalized = relative_path.replace("\\", "/").lstrip("./")
    if normalized.startswith("brain/"):
        return normalized, role_path / normalized
    return f"brain/{normalized}", role_path / "brain" / normalized


def _resolve_project_path(role_path: Path, relative_path: str) -> tuple[str, Path]:
    normalized = relative_path.replace("\\", "/").lstrip("./")
    if normalized.startswith("projects/"):
        return normalized, role_path / normalized
    return f"projects/{normalized}", role_path / "projects" / normalized


def route_context_lookup(role_path: Path, query: str) -> ContextRoute:
    _ = role_path
    normalized = query.casefold()

    if any(hint in normalized for hint in PROJECT_HINTS):
        return ContextRoute(
            primary_path="projects/index.md",
            fallback_paths=["brain/index.md", "memory/episodes/*"],
        )

    if any(hint in normalized for hint in DOMAIN_HINTS):
        return ContextRoute(
            primary_path="brain/index.md",
            fallback_paths=["memory/episodes/*", "projects/index.md"],
        )

    return ContextRoute(
        primary_path="memory/MEMORY.md",
        fallback_paths=["memory/episodes/*", "brain/index.md", "projects/index.md"],
    )


def discover_brain_paths(role_path: Path, query: str, max_depth: int = 1) -> list[str]:
    index_relative = "brain/index.md"
    index_path = role_path / index_relative
    if not index_path.exists():
        return []

    query_tokens = _tokenize(query)
    discovered: list[str] = [index_relative]
    visited: set[str] = {index_relative}

    index_text = index_path.read_text(encoding="utf-8")
    candidate_paths = _extract_markdown_paths(index_text)
    if not candidate_paths:
        return discovered

    scored_candidates: list[tuple[int, str, Path]] = []
    for candidate in candidate_paths:
        relative, full_path = _resolve_brain_path(role_path, candidate)
        if not full_path.exists():
            continue
        candidate_text = full_path.read_text(encoding="utf-8")
        score = _score_text(query_tokens, relative) + _score_text(query_tokens, candidate_text)
        scored_candidates.append((score, relative, full_path))

    if not scored_candidates:
        return discovered

    scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, top_relative, top_path = scored_candidates[0]
    discovered.append(top_relative)
    visited.add(top_relative)

    current_paths = [(top_relative, top_path)]
    for _ in range(max_depth - 1):
        next_paths: list[tuple[str, Path, int]] = []
        for _, current_path in current_paths:
            current_text = current_path.read_text(encoding="utf-8")
            for linked in _extract_markdown_paths(current_text):
                relative, full_path = _resolve_brain_path(role_path, linked)
                if relative in visited or not full_path.exists():
                    continue
                score = _score_text(query_tokens, relative) + _score_text(
                    query_tokens, full_path.read_text(encoding="utf-8")
                )
                next_paths.append((relative, full_path, score))
        if not next_paths:
            break
        next_paths.sort(key=lambda item: (item[2], item[0]), reverse=True)
        best_relative, best_path, _ = next_paths[0]
        discovered.append(best_relative)
        visited.add(best_relative)
        current_paths = [(best_relative, best_path)]

    return discovered


def _follow_project_context_links(role_path: Path, context_relative: str) -> list[str]:
    return _follow_same_directory_markdown_links(role_path, context_relative)


def _follow_same_directory_markdown_links(role_path: Path, relative_path: str) -> list[str]:
    source_path = role_path / relative_path
    if not source_path.exists():
        return []

    discovered: list[str] = []
    for linked in _extract_markdown_paths(source_path.read_text(encoding="utf-8")):
        normalized = linked.replace("\\", "/").lstrip("./")
        if normalized.startswith("projects/"):
            relative, full_path = _resolve_project_path(role_path, normalized)
        elif normalized.startswith("brain/"):
            relative, full_path = _resolve_brain_path(role_path, normalized)
        else:
            full_path = source_path.parent / normalized
            try:
                relative = full_path.relative_to(role_path).as_posix()
            except ValueError:
                continue
        if (
            full_path.exists()
            and full_path.is_file()
            and full_path.parent == source_path.parent
            and relative not in discovered
        ):
            discovered.append(relative)
    return discovered


def _is_nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def _workflow_signal_terms(text: str) -> set[str]:
    normalized = text.casefold()
    terms = {token for token in ASCII_TOKEN_PATTERN.findall(normalized) if token}
    for run in CJK_RUN_PATTERN.findall(normalized):
        if len(run) == 1:
            terms.add(run)
            continue
        for index in range(len(run) - 1):
            terms.add(run[index : index + 2])
    return terms


def _score_workflow_entry(query_terms: set[str], entry: WorkflowIndexEntry) -> int:
    keyword_terms: set[str] = set()
    for keyword in entry.keywords:
        keyword_terms.update(_workflow_signal_terms(keyword))

    score = 2 * len(query_terms & _workflow_signal_terms(entry.applies_to))
    score += len(query_terms & keyword_terms)
    score += len(query_terms & _workflow_signal_terms(entry.title))
    score += len(query_terms & _workflow_signal_terms(Path(entry.file).stem.replace("-", " ")))
    return score


def _select_workflow_entry(query: str, entries: list[WorkflowIndexEntry]) -> WorkflowIndexEntry | None:
    query_terms = _workflow_signal_terms(query)
    if not query_terms:
        return None

    ranked = sorted(
        ((entry, _score_workflow_entry(query_terms, entry)) for entry in entries),
        key=lambda item: item[1],
        reverse=True,
    )
    if not ranked or ranked[0][1] < 4:
        return None
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 5:
        return None
    return ranked[0][0]


def _discover_workflow_paths_from_index(role_path: Path, index_relative: str, query: str) -> list[str]:
    index_path = role_path / index_relative
    if not _is_nonempty_file(index_path):
        return []

    entry = _select_workflow_entry(
        query,
        parse_workflow_index(index_path.read_text(encoding="utf-8")),
    )
    if entry is None:
        return []

    workflow_relative = f"{Path(index_relative).parent.as_posix()}/{entry.file}"
    if not _is_nonempty_file(role_path / workflow_relative):
        return []
    return [index_relative, workflow_relative]


def _discover_project_workflow_paths(role_path: Path, project_slug: str, query: str) -> list[str]:
    workflow_bundle = _discover_workflow_paths_from_index(
        role_path,
        f"projects/{project_slug}/workflows/index.md",
        query,
    )
    if not workflow_bundle:
        return []

    discovered: list[str] = []
    if _is_nonempty_file(role_path / "projects/index.md"):
        discovered.append("projects/index.md")
    context_relative = f"projects/{project_slug}/context.md"
    if _is_nonempty_file(role_path / context_relative):
        discovered.append(context_relative)
    discovered.extend(workflow_bundle)
    return discovered


def _discover_global_workflow_paths(role_path: Path, query: str) -> list[str]:
    workflow_bundle = _discover_workflow_paths_from_index(role_path, "brain/workflows/index.md", query)
    if not workflow_bundle:
        return []

    discovered: list[str] = []
    if _is_nonempty_file(role_path / "brain/index.md"):
        discovered.append("brain/index.md")
    discovered.extend(workflow_bundle)
    return discovered


def discover_workflow_paths(role_path: Path, query: str) -> list[str]:
    project_slug = _resolve_current_project_slug(role_path, query)
    if project_slug:
        project_paths = _discover_project_workflow_paths(role_path, project_slug, query)
        if project_paths:
            return project_paths

    return _discover_global_workflow_paths(role_path, query)


def discover_project_paths(role_path: Path, query: str) -> list[str]:
    index_relative = "projects/index.md"
    index_path = role_path / index_relative
    if not index_path.exists():
        return []

    query_tokens = _tokenize(query)
    discovered: list[str] = [index_relative]
    index_text = index_path.read_text(encoding="utf-8")
    candidate_paths = _extract_markdown_paths(index_text)
    if not candidate_paths:
        return discovered

    scored_candidates: list[tuple[int, str, Path]] = []
    for candidate in candidate_paths:
        relative, full_path = _resolve_project_path(role_path, candidate)
        if not full_path.exists():
            continue
        candidate_text = full_path.read_text(encoding="utf-8")
        score = _score_text(query_tokens, relative) + _score_text(query_tokens, candidate_text)
        scored_candidates.append((score, relative, full_path))

    if not scored_candidates:
        return discovered

    scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, top_relative, _ = scored_candidates[0]
    discovered.append(top_relative)
    for linked_relative in _follow_project_context_links(role_path, top_relative):
        discovered.append(linked_relative)
    return discovered


def discover_context_paths(role_path: Path, query: str, max_brain_depth: int = 1) -> list[str]:
    workflow_paths = discover_workflow_paths(role_path, query)
    if workflow_paths:
        return workflow_paths

    route = route_context_lookup(role_path, query)
    discovered: list[str] = []
    seen: set[str] = set()

    def append_paths(paths: list[str]) -> None:
        for path in paths:
            if path not in seen:
                seen.add(path)
                discovered.append(path)

    if route.primary_path == "projects/index.md":
        project_paths = discover_project_paths(role_path, query)
        append_paths(project_paths)

        project_text = ""
        for project_path in project_paths[1:]:
            project_text += "\n" + (role_path / project_path).read_text(encoding="utf-8")

        if "brain/" in project_text or any(hint in query.casefold() for hint in DOMAIN_HINTS):
            append_paths(discover_brain_paths(role_path, query, max_depth=max_brain_depth))
        return discovered

    if route.primary_path == "brain/index.md":
        append_paths(discover_brain_paths(role_path, query, max_depth=max_brain_depth))
        return discovered

    append_paths([route.primary_path, *route.fallback_paths])
    return discovered


def build_context_snapshot(
    role_path: Path,
    query: str,
    max_chars: int = 4_000,
    max_brain_depth: int = 1,
) -> str:
    resident_budget = max(1, max_chars // 2)
    discovered_budget = max(1, max_chars - resident_budget)

    resident_snapshot = build_frozen_snapshot(role_path, max_chars=resident_budget)
    discovered_paths = discover_context_paths(
        role_path,
        query=query,
        max_brain_depth=max_brain_depth,
    )

    discovered_chunks: list[str] = []
    used_chars = 0
    for relative_path in discovered_paths:
        full_path = role_path / relative_path
        if not full_path.exists() or not full_path.is_file():
            continue
        header = f"## {relative_path}\n"
        remaining_budget = discovered_budget - used_chars - len(header) - 2
        if remaining_budget <= 0:
            break
        content = full_path.read_text(encoding="utf-8").strip()[:remaining_budget]
        chunk = f"{header}{content}"
        discovered_chunks.append(chunk)
        used_chars += len(chunk) + 2

    discovered_snapshot = "\n\n".join(discovered_chunks)
    combined = f"## resident\n{resident_snapshot}\n\n## discovered\n{discovered_snapshot}".strip()
    return combined[:max_chars]
