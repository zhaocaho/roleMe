from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from tools.memory import build_frozen_snapshot


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
    context_path = role_path / context_relative
    if not context_path.exists():
        return []

    discovered: list[str] = []
    for linked in _extract_markdown_paths(context_path.read_text(encoding="utf-8")):
        normalized = linked.replace("\\", "/").lstrip("./")
        if normalized.startswith("projects/"):
            relative, full_path = _resolve_project_path(role_path, normalized)
        else:
            full_path = context_path.parent / normalized
            try:
                relative = full_path.relative_to(role_path).as_posix()
            except ValueError:
                continue
        if (
            full_path.exists()
            and full_path.is_file()
            and full_path.parent == context_path.parent
            and relative not in discovered
        ):
            discovered.append(relative)
    return discovered


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
