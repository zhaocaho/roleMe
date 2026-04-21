from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from tools.file_ops import atomic_rewrite_jsonl, atomic_write_json
from tools.workflow_index import parse_workflow_index


GRAPH_DIR = Path("brain") / "graph"
REQUIRED_SCHEMA_SECTIONS = (
    "graph_schema_version",
    "node_types",
    "edge_types",
    "statuses",
    "confidences",
)
PATH_BACKED_TYPES = {"File", "Project", "Topic", "Workflow"}
ENTRY_BACKED_TYPES = {"Memory", "Preference", "Principle"}
STRONG_TYPES = {"Project", "Workflow", "Rule", "Preference", "Principle", "Concept"}
WEAK_TYPES = {"Memory", "Episode", "Decision", "Topic", "File"}
INACTIVE_STATUSES = {"invalidated", "deprecated", "superseded"}
WEAK_QUERY_HINTS = {
    "history",
    "source",
    "evidence",
    "conflict",
    "past",
    "episode",
    "历史",
    "来源",
    "证据",
    "冲突",
    "以前",
    "记录",
}
EVIDENCE_REQUIRED_EDGE_TYPES = {
    "supersedes",
    "invalidated_by",
    "promoted_to",
    "generalizes",
}


@dataclass(frozen=True)
class NodeRecord:
    id: str
    type: str
    scope: str
    project_slug: str | None = None
    path: str | None = None
    title: str = ""
    summary: str = ""
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    status: str = "active"
    confidence: str = "high"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "scope": self.scope,
            "status": self.status,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }
        if self.project_slug is not None:
            payload["project_slug"] = self.project_slug
        if self.path is not None:
            payload["path"] = _normalize_path(self.path)
        if self.title:
            payload["title"] = self.title
        if self.summary:
            payload["summary"] = self.summary
        if self.aliases:
            payload["aliases"] = list(self.aliases)
        if self.keywords:
            payload["keywords"] = list(self.keywords)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NodeRecord":
        return cls(
            id=str(payload["id"]),
            type=str(payload["type"]),
            scope=str(payload["scope"]),
            project_slug=(
                str(payload["project_slug"])
                if payload.get("project_slug") is not None
                else None
            ),
            path=str(payload["path"]) if payload.get("path") is not None else None,
            title=str(payload.get("title", "")),
            summary=str(payload.get("summary", "")),
            aliases=tuple(str(item) for item in payload.get("aliases", [])),
            keywords=tuple(str(item) for item in payload.get("keywords", [])),
            status=str(payload.get("status", "active")),
            confidence=str(payload.get("confidence", "high")),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class EdgeRecord:
    id: str
    type: str
    from_node: str
    to_node: str
    weight: float = 1.0
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "from": self.from_node,
            "to": self.to_node,
            "weight": self.weight,
            "metadata": self.metadata,
        }
        if self.rationale:
            payload["rationale"] = self.rationale
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EdgeRecord":
        return cls(
            id=str(payload["id"]),
            type=str(payload["type"]),
            from_node=str(payload["from"]),
            to_node=str(payload["to"]),
            weight=float(payload.get("weight", 1.0)),
            rationale=str(payload.get("rationale", "")),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(frozen=True)
class GraphData:
    nodes: list[NodeRecord]
    edges: list[EdgeRecord]


@dataclass(frozen=True)
class GraphDoctorReport:
    warnings: list[str]


@dataclass(frozen=True)
class GraphOptimizeResult:
    repairs: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ContextCandidate:
    node_id: str
    path: str | None
    score: float
    recall_strength: str
    status: str
    confidence: str
    reasons: tuple[str, ...]
    trust_flags: tuple[str, ...]


@dataclass(frozen=True)
class GraphRecallResult:
    candidates: list[ContextCandidate]
    fallback_required: bool
    warnings: list[str]


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def _normalize_text(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.casefold()).strip()
    return normalized


def _digest(parts: list[str]) -> str:
    raw = "\x1f".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def deterministic_node_id(
    node_type: str,
    scope: str,
    project_slug: str | None = None,
    path: str | None = None,
    title: str = "",
    metadata: dict[str, Any] | None = None,
) -> str:
    metadata = metadata or {}
    base = [node_type, scope, project_slug or ""]
    if node_type in ENTRY_BACKED_TYPES:
        entry_key = str(metadata.get("entry_key", "")).strip()
        base.extend([_normalize_path(path or ""), entry_key])
    elif node_type in PATH_BACKED_TYPES and path:
        base.append(_normalize_path(path))
    else:
        base.append(_normalize_text(title))
    return f"{node_type.lower()}-{_digest(base)}"


def deterministic_edge_id(from_node: str, edge_type: str, to_node: str) -> str:
    return f"edge-{_digest([from_node, edge_type, to_node])}"


def upsert_node(nodes: list[NodeRecord], node: NodeRecord) -> list[NodeRecord]:
    if any(current.id == node.id for current in nodes):
        return [node if current.id == node.id else current for current in nodes]
    return [*nodes, node]


def upsert_edge(edges: list[EdgeRecord], edge: EdgeRecord) -> list[EdgeRecord]:
    if any(current.id == edge.id for current in edges):
        return [edge if current.id == edge.id else current for current in edges]
    return [*edges, edge]


def _graph_path(role_path: Path, filename: str) -> Path:
    return role_path / GRAPH_DIR / filename


def load_schema_text(role_path: Path) -> str:
    return _graph_path(role_path, "schema.yaml").read_text(encoding="utf-8")


def validate_schema_text(text: str) -> None:
    missing = [
        section
        for section in REQUIRED_SCHEMA_SECTIONS
        if not re.search(rf"^{section}\s*:", text, re.MULTILINE)
    ]
    if missing:
        raise ValueError(f"Graph schema missing required sections: {', '.join(missing)}")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise TypeError("JSONL records must be objects")
        records.append(payload)
    return records


def load_graph(role_path: Path) -> GraphData:
    nodes = [
        NodeRecord.from_dict(payload)
        for payload in _load_jsonl(_graph_path(role_path, "nodes.jsonl"))
    ]
    edges = [
        EdgeRecord.from_dict(payload)
        for payload in _load_jsonl(_graph_path(role_path, "edges.jsonl"))
    ]
    return GraphData(nodes=nodes, edges=edges)


def save_graph(role_path: Path, nodes: list[NodeRecord], edges: list[EdgeRecord]) -> None:
    atomic_rewrite_jsonl(
        _graph_path(role_path, "nodes.jsonl"),
        [node.to_dict() for node in nodes],
    )
    atomic_rewrite_jsonl(
        _graph_path(role_path, "edges.jsonl"),
        [edge.to_dict() for edge in edges],
    )


def _append_index(index: dict[str, list[str]], key: str | None, node_id: str) -> None:
    if not key:
        return
    normalized_key = _normalize_text(key)
    if not normalized_key:
        return
    index.setdefault(normalized_key, [])
    if node_id not in index[normalized_key]:
        index[normalized_key].append(node_id)


def rebuild_indexes(
    role_path: Path,
    nodes: list[NodeRecord],
    index_version: str = "1.0",
) -> None:
    _ = index_version
    by_type: dict[str, list[str]] = {}
    by_path: dict[str, list[str]] = {}
    by_alias: dict[str, list[str]] = {}
    by_project: dict[str, list[str]] = {}

    for node in nodes:
        by_type.setdefault(node.type, []).append(node.id)
        if node.path:
            by_path.setdefault(_normalize_path(node.path), []).append(node.id)
        _append_index(by_alias, node.title, node.id)
        for alias in node.aliases:
            _append_index(by_alias, alias, node.id)
        for keyword in node.keywords:
            _append_index(by_alias, keyword, node.id)
        if node.project_slug:
            by_project.setdefault(node.project_slug, []).append(node.id)

    indexes_dir = role_path / GRAPH_DIR / "indexes"
    atomic_write_json(indexes_dir / "by-type.json", by_type)
    atomic_write_json(indexes_dir / "by-path.json", by_path)
    atomic_write_json(indexes_dir / "by-alias.json", by_alias)
    atomic_write_json(indexes_dir / "by-project.json", by_project)


def _duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _workflow_index_paths(role_path: Path) -> set[str]:
    paths: set[str] = set()
    global_index = role_path / "brain" / "workflows" / "index.md"
    if global_index.exists():
        for entry in parse_workflow_index(global_index.read_text(encoding="utf-8")):
            paths.add(_normalize_path(f"brain/workflows/{entry.file}"))

    projects_dir = role_path / "projects"
    if projects_dir.exists():
        for index_path in projects_dir.glob("*/workflows/index.md"):
            project_slug = index_path.parents[1].name
            for entry in parse_workflow_index(index_path.read_text(encoding="utf-8")):
                paths.add(_normalize_path(f"projects/{project_slug}/workflows/{entry.file}"))
    return paths


def _node_paths(nodes: list[NodeRecord], node_type: str) -> set[str]:
    return {
        _normalize_path(node.path)
        for node in nodes
        if node.type == node_type and node.path and node.status == "active"
    }


def _evidence_backed_edge_ids(nodes: list[NodeRecord], edges: list[EdgeRecord]) -> set[str]:
    evidence_like = {
        node.id
        for node in nodes
        if node.type in {"Evidence", "Episode"}
    }
    backed_sources = {
        edge.from_node
        for edge in edges
        if edge.type in {"evidenced_by", "derived_from", "records"}
        and edge.to_node in evidence_like
    }
    backed_targets = {
        edge.to_node
        for edge in edges
        if edge.type in {"evidenced_by", "derived_from", "records"}
        and edge.from_node in evidence_like
    }
    return backed_sources | backed_targets


def doctor_graph(role_path: Path) -> GraphDoctorReport:
    graph = load_graph(role_path)
    warnings: list[str] = []

    node_ids = [node.id for node in graph.nodes]
    edge_ids = [edge.id for edge in graph.edges]
    for duplicate_id in _duplicate_values(node_ids):
        warnings.append(f"duplicate node id: {duplicate_id}")
    for duplicate_id in _duplicate_values(edge_ids):
        warnings.append(f"duplicate edge id: {duplicate_id}")

    node_id_set = set(node_ids)
    for edge in graph.edges:
        if edge.from_node not in node_id_set:
            warnings.append(f"orphan edge source: {edge.id} -> {edge.from_node}")
        if edge.to_node not in node_id_set:
            warnings.append(f"orphan edge target: {edge.id} -> {edge.to_node}")

    for node in graph.nodes:
        if node.scope == "project" and not node.project_slug:
            warnings.append(f"project scope node missing project_slug: {node.id}")
        if node.type in PATH_BACKED_TYPES and not node.path:
            warnings.append(f"path-backed node missing path: {node.id}")
        if node.type in ENTRY_BACKED_TYPES and not node.metadata.get("entry_key"):
            warnings.append(f"entry-backed node missing metadata.entry_key: {node.id}")
        if node.type in STRONG_TYPES and node.confidence == "low":
            warnings.append(f"low confidence strong node: {node.id}")

    workflow_index_paths = _workflow_index_paths(role_path)
    graph_workflow_paths = _node_paths(graph.nodes, "Workflow")
    for path in sorted(workflow_index_paths - graph_workflow_paths):
        warnings.append(f"workflow index entry missing graph node: {path}")
    for path in sorted(graph_workflow_paths - workflow_index_paths):
        warnings.append(f"active workflow graph node missing index entry: {path}")

    connected_nodes = {
        endpoint
        for edge in graph.edges
        for endpoint in (edge.from_node, edge.to_node)
    }
    for node in graph.nodes:
        if node.type == "Evidence" and node.id not in connected_nodes:
            warnings.append(f"orphan evidence node: {node.id}")

    backed_nodes = _evidence_backed_edge_ids(graph.nodes, graph.edges)
    for edge in graph.edges:
        if edge.type in EVIDENCE_REQUIRED_EDGE_TYPES and edge.from_node not in backed_nodes:
            warnings.append(f"relationship missing evidence or episode source: {edge.id}")

    return GraphDoctorReport(warnings=warnings)


def _workflow_node_from_index(
    path: str,
    title: str,
    summary: str,
    applies_to: str,
    keywords: tuple[str, ...],
) -> NodeRecord:
    project_slug = None
    scope = "global"
    parts = path.split("/")
    if len(parts) >= 4 and parts[0] == "projects":
        scope = "project"
        project_slug = parts[1]
    node_id = deterministic_node_id(
        node_type="Workflow",
        scope=scope,
        project_slug=project_slug,
        path=path,
        title=title,
    )
    return NodeRecord(
        id=node_id,
        type="Workflow",
        scope=scope,
        project_slug=project_slug,
        path=path,
        title=title,
        summary=summary or applies_to,
        aliases=(title,),
        keywords=keywords,
    )


def _backfill_workflow_nodes(role_path: Path, nodes: list[NodeRecord]) -> tuple[list[NodeRecord], list[str]]:
    existing_paths = _node_paths(nodes, "Workflow")
    updated = list(nodes)
    repairs: list[str] = []

    global_index = role_path / "brain" / "workflows" / "index.md"
    if global_index.exists():
        for entry in parse_workflow_index(global_index.read_text(encoding="utf-8")):
            path = _normalize_path(f"brain/workflows/{entry.file}")
            if path in existing_paths:
                continue
            updated.append(
                _workflow_node_from_index(
                    path,
                    title=entry.title,
                    summary=entry.summary,
                    applies_to=entry.applies_to,
                    keywords=entry.keywords,
                )
            )
            existing_paths.add(path)
            repairs.append(f"backfilled workflow node: {path}")

    projects_dir = role_path / "projects"
    if projects_dir.exists():
        for index_path in projects_dir.glob("*/workflows/index.md"):
            project_slug = index_path.parents[1].name
            for entry in parse_workflow_index(index_path.read_text(encoding="utf-8")):
                path = _normalize_path(f"projects/{project_slug}/workflows/{entry.file}")
                if path in existing_paths:
                    continue
                updated.append(
                    _workflow_node_from_index(
                        path,
                        title=entry.title,
                        summary=entry.summary,
                        applies_to=entry.applies_to,
                        keywords=entry.keywords,
                    )
                )
                existing_paths.add(path)
                repairs.append(f"backfilled workflow node: {path}")
    return updated, repairs


def optimize_graph(role_path: Path) -> GraphOptimizeResult:
    graph = load_graph(role_path)
    node_ids = {node.id for node in graph.nodes}
    kept_edges = [
        edge
        for edge in graph.edges
        if edge.from_node in node_ids and edge.to_node in node_ids
    ]
    repairs: list[str] = []
    removed_count = len(graph.edges) - len(kept_edges)
    if removed_count:
        repairs.append(f"removed orphan edges: {removed_count}")

    nodes, backfill_repairs = _backfill_workflow_nodes(role_path, graph.nodes)
    repairs.extend(backfill_repairs)

    save_graph(role_path, nodes, kept_edges)
    rebuild_indexes(role_path, nodes)
    warnings = doctor_graph(role_path).warnings
    return GraphOptimizeResult(repairs=repairs, warnings=warnings)


def _recall_terms(text: str) -> set[str]:
    normalized = text.casefold()
    terms = {token for token in re.findall(r"[a-z0-9_]+", normalized)}
    for run in re.findall(r"[\u4e00-\u9fff]+", normalized):
        terms.add(run)
        if len(run) == 1:
            continue
        for index in range(len(run) - 1):
            terms.add(run[index : index + 2])
    return {term for term in terms if term}


def _node_terms(node: NodeRecord) -> dict[str, set[str]]:
    return {
        "title": _recall_terms(node.title),
        "summary": _recall_terms(node.summary),
        "aliases": set().union(*(_recall_terms(alias) for alias in node.aliases))
        if node.aliases
        else set(),
        "keywords": set().union(*(_recall_terms(keyword) for keyword in node.keywords))
        if node.keywords
        else set(),
        "path": _recall_terms(node.path or ""),
    }


def _score_node(
    node: NodeRecord,
    query_terms: set[str],
    current_project_slug: str | None,
) -> tuple[float, list[str], list[str]]:
    term_groups = _node_terms(node)
    score = 0.0
    reasons: list[str] = []
    trust_flags: list[str] = []

    weights = {
        "aliases": 4.0,
        "keywords": 3.0,
        "title": 2.0,
        "summary": 1.0,
        "path": 1.0,
    }
    for group, terms in term_groups.items():
        matches = query_terms & terms
        if not matches:
            continue
        score += weights[group] * len(matches)
        reasons.append(f"{group}: {', '.join(sorted(matches))}")

    if current_project_slug and node.project_slug == current_project_slug:
        score += 2.0
        reasons.append("current project")

    if node.confidence == "low":
        score *= 0.5
        trust_flags.append("low-confidence")
    elif node.confidence == "medium":
        score *= 0.8
        trust_flags.append("medium-confidence")

    if node.status == "stale":
        score *= 0.6
        trust_flags.append("stale")

    return score, reasons, trust_flags


def _include_weak_candidates(query: str, strong_candidates: list[ContextCandidate]) -> bool:
    _ = strong_candidates
    normalized = query.casefold()
    return any(hint in normalized for hint in WEAK_QUERY_HINTS)


def recall_graph(
    role_path: Path,
    query: str,
    current_project_slug: str | None = None,
) -> GraphRecallResult:
    if os.environ.get("ROLEME_GRAPH_ROUTING") == "0":
        return GraphRecallResult(candidates=[], fallback_required=True, warnings=["graph routing disabled"])
    if os.environ.get("ROLEME_GRAPH_ARCHIVE") == "0":
        return GraphRecallResult(candidates=[], fallback_required=True, warnings=["graph archive disabled"])

    warnings: list[str] = []
    try:
        validate_schema_text(load_schema_text(role_path))
        graph = load_graph(role_path)
    except Exception as exc:
        return GraphRecallResult(candidates=[], fallback_required=True, warnings=[str(exc)])

    query_terms = _recall_terms(query)
    if not query_terms:
        return GraphRecallResult(candidates=[], fallback_required=True, warnings=[])

    strong_candidates: list[ContextCandidate] = []
    weak_candidates: list[ContextCandidate] = []
    for node in graph.nodes:
        if node.status in INACTIVE_STATUSES or not node.path:
            continue
        if not (role_path / _normalize_path(node.path)).exists():
            continue

        if node.type in STRONG_TYPES:
            recall_strength = "strong"
        elif node.type in WEAK_TYPES:
            recall_strength = "weak"
        else:
            continue

        score, reasons, trust_flags = _score_node(node, query_terms, current_project_slug)
        if score < 4.0:
            continue
        candidate = ContextCandidate(
            node_id=node.id,
            path=_normalize_path(node.path),
            score=score,
            recall_strength=recall_strength,
            status=node.status,
            confidence=node.confidence,
            reasons=tuple(reasons),
            trust_flags=tuple(trust_flags),
        )
        if recall_strength == "strong":
            strong_candidates.append(candidate)
        else:
            weak_candidates.append(candidate)

    candidates = list(strong_candidates)
    if _include_weak_candidates(query, strong_candidates):
        candidates.extend(weak_candidates)
    candidates.sort(key=lambda candidate: (candidate.score, candidate.path or ""), reverse=True)

    if len(candidates) > 1 and candidates[0].score - candidates[1].score < 2.0:
        warnings.append("ambiguous graph recall candidates")
        return GraphRecallResult(candidates=[], fallback_required=True, warnings=warnings)

    return GraphRecallResult(candidates=candidates, fallback_required=False, warnings=warnings)
