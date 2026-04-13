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
        content = content[:content_budget]
        chunks.append(f"{header}{content}")
    return "\n\n".join(chunks)[:max_chars]


def write_memory(role_path: Path, target: str, content: str):
    if target == "episode":
        episodes_dir = role_path / "memory" / "episodes"
        episode_path = episodes_dir / f"episode-{len(list(episodes_dir.glob('*.md'))) + 1:03d}.md"
        episode_path.write_text(content, encoding="utf-8")
        return episode_path

    store_name = "MEMORY.md" if target == "memory" else "USER.md"
    store_path = role_path / "memory" / store_name
    bullet = f"- {content.strip()}"
    if _is_safe(bullet):
        entries = _read_entries(store_path)
        if bullet not in entries:
            _replace_entries(store_path, entries + [bullet])
    return None


def summarize_and_write(role_path: Path, target: str, source_text: str) -> None:
    store_name = "MEMORY.md" if target == "memory" else "USER.md"
    store_path = role_path / "memory" / store_name
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
    store_name = "MEMORY.md" if target == "memory" else "USER.md"
    store_path = role_path / "memory" / store_name
    entries = _read_entries(store_path)
    _replace_entries(store_path, entries[:max_entries])
