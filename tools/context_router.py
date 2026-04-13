from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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


@dataclass(frozen=True)
class ContextRoute:
    primary_path: str
    fallback_paths: list[str]


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
