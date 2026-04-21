from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from tools.file_ops import atomic_write_text


@dataclass(frozen=True)
class WorkflowIndexEntry:
    slug: str
    title: str
    file: str
    applies_to: str
    keywords: tuple[str, ...]
    summary: str


SECTION_PATTERN = re.compile(r"^##\s+([A-Za-z0-9_-]+)\s*$", re.MULTILINE)
FIELD_PATTERN = re.compile(r"^- ([a-z_]+):\s*(.*)$")


def normalize_workflow_slug(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value.casefold()).strip("-_")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "workflow"


def parse_workflow_index(text: str) -> list[WorkflowIndexEntry]:
    entries: list[WorkflowIndexEntry] = []
    sections = list(SECTION_PATTERN.finditer(text))
    for index, match in enumerate(sections):
        slug = match.group(1).strip()
        start = match.end()
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        block = text[start:end].strip().splitlines()
        fields: dict[str, str] = {}
        for raw_line in block:
            line = raw_line.strip()
            field_match = FIELD_PATTERN.match(line)
            if field_match:
                fields[field_match.group(1)] = field_match.group(2).strip()
        required = {"title", "file", "applies_to", "keywords", "summary"}
        if not required.issubset(fields):
            continue
        entries.append(
            WorkflowIndexEntry(
                slug=slug,
                title=fields["title"],
                file=fields["file"],
                applies_to=fields["applies_to"],
                keywords=tuple(
                    item.strip() for item in fields["keywords"].split(",") if item.strip()
                ),
                summary=fields["summary"],
            )
        )
    return entries


def render_workflow_index(entries: list[WorkflowIndexEntry]) -> str:
    lines = ["# 工作流索引", ""]
    for entry in entries:
        lines.extend(
            [
                f"## {entry.slug}",
                f"- title: {entry.title}",
                f"- file: {entry.file}",
                f"- applies_to: {entry.applies_to}",
                f"- keywords: {', '.join(entry.keywords)}",
                f"- summary: {entry.summary}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def upsert_workflow_index_entry(index_path: Path, entry: WorkflowIndexEntry) -> None:
    existing = (
        parse_workflow_index(index_path.read_text(encoding="utf-8"))
        if index_path.exists()
        else []
    )
    updated: list[WorkflowIndexEntry] = []
    replaced = False
    for current in existing:
        if current.slug == entry.slug:
            updated.append(entry)
            replaced = True
        else:
            updated.append(current)
    if not replaced:
        updated.append(entry)
    atomic_write_text(index_path, render_workflow_index(updated))
