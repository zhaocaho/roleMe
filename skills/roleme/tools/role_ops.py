from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import json
import os
import re
import shutil
import tempfile

from tools.context_router import build_context_snapshot, discover_context_paths
from tools.file_ops import atomic_write_json, atomic_write_text
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
from tools.memory import build_frozen_snapshot, write_memory
from tools.workflow_index import (
    WorkflowIndexEntry,
    normalize_workflow_slug,
    upsert_workflow_index_entry,
)


SCHEMA_VERSION = "1.0"
RESIDENT_PATHS = [
    "persona/narrative.md",
    "persona/communication-style.md",
    "persona/decision-rules.md",
    "memory/USER.md",
    "memory/MEMORY.md",
]
ON_DEMAND_PATHS = [
    "persona/disclosure-layers.md",
    "brain/index.md",
    "brain/topics",
    "projects/index.md",
    "projects",
    "memory/episodes",
]
REQUIRED_FILES = [
    "AGENT.md",
    "role.json",
    "brain/index.md",
    "memory/USER.md",
    "memory/MEMORY.md",
    "projects/index.md",
    "persona/narrative.md",
    "persona/communication-style.md",
    "persona/decision-rules.md",
    "persona/disclosure-layers.md",
]


@dataclass(frozen=True)
class RoleManifest:
    role_name: str
    schema_version: str
    role_version: str
    created_by_skill_version: str
    compatible_skill_range: str
    created_at: str
    updated_at: str
    default_load_profile: str = "standard"

    @classmethod
    def new(cls, role_name: str, skill_version: str) -> "RoleManifest":
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        return cls(
            role_name=role_name,
            schema_version=SCHEMA_VERSION,
            role_version="0.1.0",
            created_by_skill_version=skill_version,
            compatible_skill_range=">=0.1 <1.0",
            created_at=now,
            updated_at=now,
        )

    def write(self, path: Path) -> None:
        payload = {
            "roleName": self.role_name,
            "schemaVersion": self.schema_version,
            "roleVersion": self.role_version,
            "createdBySkillVersion": self.created_by_skill_version,
            "compatibleSkillRange": self.compatible_skill_range,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "defaultLoadProfile": self.default_load_profile,
        }
        atomic_write_json(path, payload)


@dataclass(frozen=True)
class RoleBundle:
    role_name: str
    role_path: str
    resident_files: dict[str, str]
    on_demand_paths: list[str]
    context_snapshot: str


@dataclass(frozen=True)
class QueryContextBundle:
    role_name: str
    role_path: str
    resident_files: dict[str, str]
    discovered_paths: list[str]
    context_snapshot: str


@dataclass(frozen=True)
class CurrentRoleState:
    role_name: str
    role_path: str
    loaded_at: str


@dataclass(frozen=True)
class ProjectIdentity:
    title: str
    slug: str


@dataclass(frozen=True)
class WorkflowArchivePlan:
    kind: str
    role_name: str | None
    project_title: str | None
    project_slug: str | None
    workflow_slug: str
    workflow_title: str
    workflow_summary: str
    workflow_applies_to: str
    workflow_keywords: list[str]
    workflow_doc_markdown: str
    context_summary_markdown: str
    user_rules: list[str]
    memory_summary: list[str]
    project_memory: list[str]


@dataclass(frozen=True)
class WorkflowArchiveResult:
    role_name: str
    project_title: str | None
    project_slug: str | None
    written_paths: list[str]
    requires_reload: bool
    markdown_written: bool = True
    index_updated: bool = True
    graph_updated: bool = False
    graph_skipped: bool = False
    doctor_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisionArchiveResult:
    written_paths: list[str]
    markdown_written: bool
    graph_updated: bool
    graph_skipped: bool
    decision_id: str
    doctor_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoleEntryPrompt:
    existing_roles: list[str]
    prompt: str


@dataclass(frozen=True)
class RoleInterviewTopic:
    slug: str
    title: str
    summary: str
    content: str


@dataclass(frozen=True)
class RoleInterviewProject:
    name: str
    context: str
    overlay: str = ""
    memory: list[str] | None = None


@dataclass(frozen=True)
class RoleInterview:
    narrative: str
    communication_style: str
    decision_rules: str
    disclosure_layers: str
    user_memory: list[str]
    memory_summary: list[str]
    brain_topics: list[RoleInterviewTopic]
    projects: list[RoleInterviewProject]


@dataclass(frozen=True)
class InterviewSession:
    role_name: str
    user_language: str
    current_stage: str
    current_prompt: str
    answers: dict[str, str]
    asked_slots: tuple[str, ...] = ()
    preview: str = ""


@dataclass(frozen=True)
class InterviewGap:
    slot: str
    status: str
    confidence: float
    notes: str


@dataclass(frozen=True)
class InterviewTurnPlan:
    target_slot: str
    question: str
    rationale: str
    gap_summary: list[InterviewGap]
    ready_to_finalize: bool = False


@dataclass(frozen=True)
class InterviewPlannerDirective:
    target_slot: str
    question: str
    rationale: str
    answer_mode: str = "append"
    ready_to_finalize: bool = False


@dataclass(frozen=True)
class DoctorReport:
    missing_files: list[str]
    warnings: list[str]


INTERVIEW_STAGE_ORDER = [
    "narrative",
    "language_preference",
    "communication_style",
    "decision_rules",
    "disclosure_layers",
    "user_memory",
    "memory_summary",
    "brain_topics",
    "projects",
]

INTERVIEW_CORE_SLOTS = [
    "narrative",
    "language_preference",
    "communication_style",
    "decision_rules",
]

INTERVIEW_STAGE_PROMPTS = {
    "zh": {
        "narrative": "先不用完整介绍。你可以只回答一小部分，比如职业身份、最近关注的事，或者你希望我怎么理解你，任选一个先说就行。",
        "language_preference": "你希望我后续默认用什么语言和你协作？如果暂时没有明确偏好，也可以先不定。",
        "communication_style": "你希望我默认怎么和你沟通协作？请说明回答风格、结构、节奏和语气。",
        "decision_rules": "当出现取舍时，你通常按什么优先级做决定？请说明第一、第二、第三优先级。",
        "disclosure_layers": "你的上下文应该怎样渐进式披露？哪些内容应常驻，哪些内容应按需展开？",
        "user_memory": "请列出应进入 USER memory 的稳定偏好或长期约定，每行一条，可用 `- ` 开头。",
        "memory_summary": "请列出应进入 MEMORY summary 的高价值长期结论，每行一条。",
        "brain_topics": "请描述 brain 主题，使用 `title:`、`slug:`、`summary:`、`content:`，多个主题之间用 `---` 分隔。",
        "projects": "请描述项目上下文，使用 `name:`、`context:`、`overlay:`、`memory:`，多个项目之间用 `---` 分隔，`memory:` 多条可用 `|` 分隔。",
    },
    "en": {
        "narrative": "No need for a full introduction. You can start with just one small piece, like your role, what you have been focused on recently, or how you want me to understand you.",
        "language_preference": "What language should I use by default when we work together? If you do not have a firm preference yet, we can leave it open for now.",
        "communication_style": "How do you prefer to communicate and collaborate: answer style, structure, pacing, and tone?",
        "decision_rules": "What decision rules do you use in priority order? Explain what you optimize for first, second, and third.",
        "disclosure_layers": "How should your context be disclosed progressively? What belongs in resident context versus on-demand context?",
        "user_memory": "List stable preferences or long-term agreements for USER memory. One item per line, optionally starting with `- `.",
        "memory_summary": "List high-value long-term conclusions for MEMORY summary. One item per line.",
        "brain_topics": "Describe brain topics with `title:`, `slug:`, `summary:`, and `content:`. Separate multiple topics with `---`.",
        "projects": "Describe project context with `name:`, `context:`, `overlay:`, and `memory:`. Separate multiple projects with `---`, and split multiple memory items with `|`.",
    },
}

INTERVIEW_REVIEW_PROMPTS = {
    "zh": "已经有一版可用初稿了。剩下没说到的信息可以在后续使用里慢慢补充。请确认是否先将这份预览写入角色包。",
    "en": "There is now a usable draft. Anything still unsaid can be accumulated gradually during later use. Please confirm whether this preview should be materialized into the role bundle now.",
}
ARCHIVE_UNSAFE_PATTERNS = [
    re.compile(r"ignore previous instructions", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"developer prompt", re.IGNORECASE),
    re.compile(r"[\u200b-\u200f\u2060\ufeff]"),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def templates_dir() -> Path:
    return repo_root() / "templates"


def roleme_home() -> Path:
    override = os.environ.get("ROLEME_HOME")
    return Path(override).expanduser() if override else Path.home() / ".roleMe"


def _directory_writable(path: Path) -> bool:
    target = path.expanduser()
    while not target.exists() and target.parent != target:
        target = target.parent
    return os.access(target, os.W_OK | os.X_OK)


def roleme_state_home() -> Path:
    override = os.environ.get("ROLEME_STATE_HOME")
    if override:
        return Path(override).expanduser()

    home = roleme_home()
    if _directory_writable(home):
        return home

    return Path(tempfile.gettempdir()) / "roleMe-state"


def normalize_role_name(role_name: str) -> str:
    normalized = role_name.strip()
    if not normalized:
        raise ValueError("Role name must not be empty.")
    if normalized in {".", ".."}:
        raise ValueError("Role name must not be '.' or '..'.")
    if "/" in normalized or "\\" in normalized:
        raise ValueError("Role name must not contain path separators.")
    return normalized


def role_dir(role_name: str) -> Path:
    return roleme_home() / normalize_role_name(role_name)


def current_role_state_paths() -> list[Path]:
    preferred = roleme_state_home() / ".current-role.json"
    legacy = roleme_home() / ".current-role.json"
    return [preferred] if preferred == legacy else [preferred, legacy]


def current_role_state_path() -> Path:
    return current_role_state_paths()[0]


def set_current_role_state(role_name: str) -> CurrentRoleState:
    role_name = normalize_role_name(role_name)
    base_path = role_dir(role_name)
    if not base_path.exists():
        raise FileNotFoundError(f"Role does not exist: {base_path}")

    state = CurrentRoleState(
        role_name=role_name,
        role_path=str(base_path),
        loaded_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    )
    payload = {
        "roleName": state.role_name,
        "rolePath": state.role_path,
        "loadedAt": state.loaded_at,
    }
    state_path = current_role_state_path()
    atomic_write_json(state_path, payload)
    return state


def get_current_role_state() -> CurrentRoleState:
    invalid_pointer_found = False
    for path in current_role_state_paths():
        if not path.exists():
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))
        role_name = normalize_role_name(str(payload.get("roleName", "")).strip())
        role_path = Path(str(payload.get("rolePath", "")).strip())
        loaded_at = str(payload.get("loadedAt", "")).strip()
        expected_path = role_dir(role_name)
        if role_path != expected_path or not expected_path.exists() or not loaded_at:
            invalid_pointer_found = True
            continue

        return CurrentRoleState(
            role_name=role_name,
            role_path=str(expected_path),
            loaded_at=loaded_at,
        )

    if invalid_pointer_found:
        raise ValueError("Current role pointer is invalid.")
    raise FileNotFoundError("No current role is loaded.")


def build_default_role_entry_prompt(user_language: str = "中文") -> RoleEntryPrompt:
    roles = list_roles()
    quoted_roles = "、".join(roles)
    if _language_key(user_language) == "zh":
        if roles:
            prompt = (
                f"当前已有这些角色：{quoted_roles}。你可以直接告诉我想加载哪个角色；"
                "如果不想加载，也可以创建新角色。要创建的话，先告诉我你想用的角色名。"
            )
        else:
            prompt = "当前还没有任何角色。你想创建的角色叫什么名字？支持直接使用中文角色名。"
        return RoleEntryPrompt(existing_roles=roles, prompt=prompt)

    if roles:
        prompt = (
            f"These roles already exist: {', '.join(roles)}. Tell me which one you want to load, "
            "or tell me the name for a new role if you want to create one instead."
        )
    else:
        prompt = (
            "There are no roles yet. What would you like to call the new role? Chinese names are allowed."
        )
    return RoleEntryPrompt(existing_roles=roles, prompt=prompt)


def _render(source: Path, destination: Path, role_name: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text(encoding="utf-8").replace("<role-name>", role_name)
    atomic_write_text(destination, content)


def _render_template_text(source: Path, replacements: dict[str, str]) -> str:
    content = source.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(key, value)
    return content


def _language_key(user_language: str) -> str:
    normalized = user_language.strip().lower()
    if "中" in user_language or normalized.startswith("zh") or "chinese" in normalized:
        return "zh"
    return "en"


def _localized_stage_prompt(slot: str, user_language: str) -> str:
    return INTERVIEW_STAGE_PROMPTS[_language_key(user_language)][slot]


def _localized_review_prompt(user_language: str) -> str:
    return INTERVIEW_REVIEW_PROMPTS[_language_key(user_language)]


def _replace_marker_entries(path: Path, entries: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    replacement = "\n".join(f"- {entry}" for entry in entries)
    updated = (
        text.split("<!-- ROLEME:ENTRIES:START -->", maxsplit=1)[0]
        + "<!-- ROLEME:ENTRIES:START -->\n"
        + replacement
        + "\n<!-- ROLEME:ENTRIES:END -->"
        + text.split("<!-- ROLEME:ENTRIES:END -->", maxsplit=1)[1]
    )
    atomic_write_text(path, updated)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "topic"


def _project_slug_fallback(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"project-{digest}"


def slugify_project_title(value: str) -> str:
    lowered = value.strip().casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or _project_slug_fallback(value)


def resolve_current_project_identity(
    role_path: Path,
    explicit_project: str | None,
    workspace_name: str | None,
) -> ProjectIdentity:
    existing_slugs = sorted(
        path.name
        for path in (role_path / "projects").iterdir()
        if path.is_dir()
    )
    if explicit_project:
        title = explicit_project.strip()
        return ProjectIdentity(title=title, slug=slugify_project_title(title))
    if workspace_name:
        title = workspace_name.strip()
        slug = slugify_project_title(title)
        return ProjectIdentity(title=title, slug=slug)
    if len(existing_slugs) == 1:
        only_slug = existing_slugs[0]
        return ProjectIdentity(title=only_slug, slug=only_slug)
    raise ValueError("Unable to resolve current project identity.")


def _current_git_repo_root() -> Path | None:
    cwd = Path.cwd()
    git_marker = cwd / ".git"
    if git_marker.exists():
        return cwd
    return None


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        atomic_write_text(path, content)


def _graph_archive_enabled() -> bool:
    return os.environ.get("ROLEME_GRAPH_ARCHIVE", "1") != "0"


def _short_key(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _replace_node_status(node: NodeRecord, status: str) -> NodeRecord:
    return NodeRecord(
        id=node.id,
        type=node.type,
        scope=node.scope,
        project_slug=node.project_slug,
        path=node.path,
        title=node.title,
        summary=node.summary,
        aliases=node.aliases,
        keywords=node.keywords,
        status=status,
        confidence=node.confidence,
        metadata=node.metadata,
    )


def _persist_graph(role_path: Path, nodes: list[NodeRecord], edges: list[EdgeRecord]) -> tuple[str, ...]:
    save_graph(role_path, nodes, edges)
    rebuild_indexes(role_path, nodes)
    return tuple(doctor_graph(role_path).warnings)


def _upsert_project_graph_node(
    role_path: Path,
    identity: ProjectIdentity,
    repo_path: Path | None = None,
) -> tuple[bool, tuple[str, ...]]:
    if not _graph_archive_enabled():
        return False, ()

    graph = load_graph(role_path)
    path = f"projects/{identity.slug}/context.md"
    node = NodeRecord(
        id=deterministic_node_id(
            node_type="Project",
            scope="project",
            project_slug=identity.slug,
            path=path,
            title=identity.title,
        ),
        type="Project",
        scope="project",
        project_slug=identity.slug,
        path=path,
        title=identity.title,
        aliases=(identity.title, identity.slug),
        metadata={"repo_path": str(repo_path)} if repo_path is not None else {},
    )
    warnings = _persist_graph(role_path, upsert_node(graph.nodes, node), graph.edges)
    return True, warnings


def maybe_bootstrap_project_from_cwd(role_path: Path) -> ProjectIdentity | None:
    if not _directory_writable(role_path):
        return None

    repo_root = _current_git_repo_root()
    if repo_root is None:
        return None

    identity = resolve_current_project_identity(
        role_path,
        explicit_project=None,
        workspace_name=repo_root.name,
    )
    project_dir = role_path / "projects" / identity.slug
    project_dir.mkdir(parents=True, exist_ok=True)

    _write_if_missing(
        project_dir / "context.md",
        (
            f"# {identity.title}\n\n"
            "自动从当前 Git 仓库根目录识别为当前项目。\n\n"
            f"- Workspace: {repo_root}\n"
        ),
    )
    _write_if_missing(
        project_dir / "overlay.md",
        (
            f"# {identity.title} overlay\n\n"
            "记录该项目特有的协作约束与回答偏置，后续按需补充。\n"
        ),
    )
    _write_if_missing(
        project_dir / "memory.md",
        (
            f"# {identity.title} memory\n\n"
            "- 项目目录已由 roleMe 在角色加载时根据当前 Git 仓库根目录自动初始化。\n"
        ),
    )
    upsert_markdown_index_entry(
        role_path / "projects" / "index.md",
        label=identity.title,
        target=f"projects/{identity.slug}/context.md",
        summary="自动从当前 Git 仓库根目录初始化。",
    )
    _upsert_project_graph_node(role_path, identity, repo_path=repo_root)
    return identity


def _sanitize_archive_text(content: str, minimum_chars: int) -> str:
    sanitized = content.strip()
    for pattern in ARCHIVE_UNSAFE_PATTERNS:
        if pattern.search(sanitized):
            raise ValueError("Archived content contains unsafe text.")
    if len(sanitized) < minimum_chars:
        raise ValueError("Archived content is too short.")
    return sanitized


def sanitize_archived_markdown(content: str, minimum_chars: int = 12) -> str:
    return _sanitize_archive_text(content, minimum_chars=minimum_chars)


def sanitize_archive_entry(content: str, minimum_chars: int = 4) -> str:
    normalized = content.strip().strip("-").strip()
    return _sanitize_archive_text(normalized, minimum_chars=minimum_chars)


def summarize_index_entry(summary: str) -> str:
    for raw_line in summary.splitlines():
        line = raw_line.strip(" -#\t")
        if line:
            return line
    return ""


def _first_meaningful_line(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip(" -#\t")
        if line:
            return line
    return ""


def _first_summary_content_line(text: str) -> str:
    ignored_titles = {"项目上下文", "全局上下文", "适用场景"}
    for raw_line in text.splitlines():
        line = raw_line.strip(" -#\t")
        if not line:
            continue
        if line in ignored_titles:
            continue
        return line
    return ""


def _derive_workflow_metadata(
    payload: dict[str, object],
    workflow_title: str,
    workflow_slug: str,
) -> tuple[str, str, list[str]]:
    context_summary = str(payload.get("context_summary_markdown", "")).strip()
    context_content = _first_summary_content_line(context_summary)
    workflow_summary = (
        str(payload.get("workflow_summary", "")).strip()
        or context_content
        or workflow_title
    )
    workflow_applies_to = (
        str(payload.get("workflow_applies_to", "")).strip()
        or context_content
        or workflow_title
    )
    workflow_keywords = [
        str(item).strip()
        for item in payload.get("workflow_keywords", [])
        if str(item).strip()
    ]
    if not workflow_keywords:
        tokens = re.findall(
            r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+",
            f"{workflow_title} {workflow_slug}",
        )
        workflow_keywords = list(
            dict.fromkeys(token.casefold() for token in tokens if token.strip())
        )
    return workflow_summary, workflow_applies_to, workflow_keywords


def parse_workflow_archive_response(raw: str | dict[str, object]) -> WorkflowArchivePlan:
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    kind = str(payload.get("kind", "")).strip().lower()
    if kind not in {"general", "project"}:
        raise ValueError(f"Unsupported workflow archive kind: {kind}")

    project_title = payload.get("project_title")
    project_slug = payload.get("project_slug")
    user_rules = [
        str(item).strip()
        for item in payload.get("user_rules", [])
        if str(item).strip()
    ]
    memory_summary = [
        str(item).strip()
        for item in payload.get("memory_summary", [])
        if str(item).strip()
    ]
    project_memory = [
        str(item).strip()
        for item in payload.get("project_memory", [])
        if str(item).strip()
    ]
    workflow_title = str(payload.get("workflow_title", "")).strip()
    if not workflow_title:
        raise ValueError("workflow_title is required.")
    workflow_slug = (
        str(payload.get("workflow_slug", "")).strip()
        or normalize_workflow_slug(workflow_title)
    )
    workflow_summary, workflow_applies_to, workflow_keywords = _derive_workflow_metadata(
        payload,
        workflow_title,
        workflow_slug,
    )

    return WorkflowArchivePlan(
        kind=kind,
        role_name=str(payload.get("role_name")).strip() if payload.get("role_name") is not None else None,
        project_title=str(project_title).strip() if project_title is not None else None,
        project_slug=str(project_slug).strip() if project_slug is not None else None,
        workflow_slug=workflow_slug,
        workflow_title=workflow_title,
        workflow_summary=workflow_summary,
        workflow_applies_to=workflow_applies_to,
        workflow_keywords=workflow_keywords,
        workflow_doc_markdown=str(payload.get("workflow_doc_markdown", "")).strip(),
        context_summary_markdown=str(payload.get("context_summary_markdown", "")).strip(),
        user_rules=user_rules,
        memory_summary=memory_summary,
        project_memory=project_memory,
    )


def upsert_markdown_index_entry(index_path: Path, label: str, target: str, summary: str = "") -> None:
    lines = index_path.read_text(encoding="utf-8").splitlines()
    entry_line = f"- {label}: {target}"
    if entry_line in lines:
        return

    summary_line = summarize_index_entry(summary)
    if summary_line:
        lines.extend([entry_line, f"  - {summary_line}"])
    else:
        lines.append(entry_line)
    atomic_write_text(index_path, "\n".join(lines).strip() + "\n")


def append_unique_project_memory(memory_path: Path, entries: list[str]) -> None:
    lines = (
        memory_path.read_text(encoding="utf-8").splitlines()
        if memory_path.exists()
        else ["# project memory", ""]
    )
    existing = {line.strip() for line in lines if line.strip().startswith("- ")}
    for entry in entries:
        safe_entry = sanitize_archive_entry(entry)
        bullet = f"- {safe_entry}"
        if bullet not in existing:
            lines.append(bullet)
            existing.add(bullet)
    atomic_write_text(memory_path, "\n".join(lines).strip() + "\n")


def _workflow_graph_nodes(
    *,
    scope: str,
    workflow_path: str,
    workflow_title: str,
    workflow_summary: str,
    workflow_applies_to: str,
    workflow_keywords: list[str],
    project_slug: str | None = None,
) -> tuple[NodeRecord, NodeRecord, NodeRecord, EdgeRecord, EdgeRecord]:
    workflow = NodeRecord(
        id=deterministic_node_id(
            node_type="Workflow",
            scope=scope,
            project_slug=project_slug,
            path=workflow_path,
            title=workflow_title,
        ),
        type="Workflow",
        scope=scope,
        project_slug=project_slug,
        path=workflow_path,
        title=workflow_title,
        summary=workflow_summary,
        aliases=(workflow_title,),
        keywords=tuple(workflow_keywords),
    )
    concept = NodeRecord(
        id=deterministic_node_id(
            node_type="Concept",
            scope=scope,
            project_slug=project_slug,
            title=workflow_applies_to,
        ),
        type="Concept",
        scope=scope,
        project_slug=project_slug,
        title=workflow_applies_to,
        summary=workflow_applies_to,
        aliases=(workflow_applies_to,),
    )
    evidence = NodeRecord(
        id=deterministic_node_id(
            node_type="Evidence",
            scope=scope,
            project_slug=project_slug,
            path=workflow_path,
            title=f"Evidence for {workflow_title}",
            metadata={"entry_key": "workflow", "source_path": workflow_path},
        ),
        type="Evidence",
        scope=scope,
        project_slug=project_slug,
        path=workflow_path,
        title=f"Evidence for {workflow_title}",
        metadata={"source_type": "user_statement", "source_path": workflow_path},
    )
    applies_to = EdgeRecord(
        id=deterministic_edge_id(workflow.id, "applies_to", concept.id),
        type="applies_to",
        from_node=workflow.id,
        to_node=concept.id,
        rationale="workflow applies to archived scenario",
    )
    evidenced_by = EdgeRecord(
        id=deterministic_edge_id(workflow.id, "evidenced_by", evidence.id),
        type="evidenced_by",
        from_node=workflow.id,
        to_node=evidence.id,
        rationale="workflow archived from user statement",
    )
    return workflow, concept, evidence, applies_to, evidenced_by


def _upsert_workflow_graph(
    role_path: Path,
    plan: WorkflowArchivePlan,
    workflow_path: str,
    scope: str,
) -> tuple[bool, tuple[str, ...]]:
    if not _graph_archive_enabled():
        return False, ()

    graph = load_graph(role_path)
    nodes = graph.nodes
    edges = graph.edges
    workflow, concept, evidence, applies_to, evidenced_by = _workflow_graph_nodes(
        scope=scope,
        project_slug=plan.project_slug if scope == "project" else None,
        workflow_path=workflow_path,
        workflow_title=plan.workflow_title,
        workflow_summary=plan.workflow_summary,
        workflow_applies_to=plan.workflow_applies_to,
        workflow_keywords=plan.workflow_keywords,
    )
    for node in [workflow, concept, evidence]:
        nodes = upsert_node(nodes, node)
    for edge in [applies_to, evidenced_by]:
        edges = upsert_edge(edges, edge)

    if scope == "project" and plan.project_slug and plan.project_title:
        project = NodeRecord(
            id=deterministic_node_id(
                node_type="Project",
                scope="project",
                project_slug=plan.project_slug,
                path=f"projects/{plan.project_slug}/context.md",
                title=plan.project_title,
            ),
            type="Project",
            scope="project",
            project_slug=plan.project_slug,
            path=f"projects/{plan.project_slug}/context.md",
            title=plan.project_title,
            aliases=(plan.project_title, plan.project_slug),
        )
        nodes = upsert_node(nodes, project)
        edges = upsert_edge(
            edges,
            EdgeRecord(
                id=deterministic_edge_id(workflow.id, "belongs_to", project.id),
                type="belongs_to",
                from_node=workflow.id,
                to_node=project.id,
                rationale="project workflow belongs to project",
            ),
        )
        for memory_entry in plan.project_memory:
            safe_entry = sanitize_archive_entry(memory_entry)
            memory_path = f"projects/{plan.project_slug}/memory.md"
            memory_key = _short_key(safe_entry)
            evidence_key = _short_key(f"evidence:{safe_entry}")
            memory = NodeRecord(
                id=deterministic_node_id(
                    node_type="Memory",
                    scope="project",
                    project_slug=plan.project_slug,
                    path=memory_path,
                    title=safe_entry,
                    metadata={"entry_key": memory_key},
                ),
                type="Memory",
                scope="project",
                project_slug=plan.project_slug,
                path=memory_path,
                title=safe_entry,
                metadata={"entry_key": memory_key},
            )
            evidence_node = NodeRecord(
                id=deterministic_node_id(
                    node_type="Evidence",
                    scope="project",
                    project_slug=plan.project_slug,
                    path=memory_path,
                    title=f"Evidence for {safe_entry}",
                    metadata={"entry_key": evidence_key},
                ),
                type="Evidence",
                scope="project",
                project_slug=plan.project_slug,
                path=memory_path,
                title=f"Evidence for {safe_entry}",
                metadata={"source_type": "user_statement", "source_path": memory_path},
            )
            nodes = upsert_node(nodes, memory)
            nodes = upsert_node(nodes, evidence_node)
            edges = upsert_edge(
                edges,
                EdgeRecord(
                    id=deterministic_edge_id(memory.id, "belongs_to", project.id),
                    type="belongs_to",
                    from_node=memory.id,
                    to_node=project.id,
                ),
            )
            edges = upsert_edge(
                edges,
                EdgeRecord(
                    id=deterministic_edge_id(memory.id, "evidenced_by", evidence_node.id),
                    type="evidenced_by",
                    from_node=memory.id,
                    to_node=evidence_node.id,
                ),
            )

    warnings = _persist_graph(role_path, nodes, edges)
    return True, warnings


def _safe_upsert_workflow_graph(
    role_path: Path,
    plan: WorkflowArchivePlan,
    workflow_path: str,
    scope: str,
) -> tuple[bool, bool, tuple[str, ...]]:
    if not _graph_archive_enabled():
        return False, True, ()
    try:
        graph_updated, warnings = _upsert_workflow_graph(
            role_path,
            plan,
            workflow_path=workflow_path,
            scope=scope,
        )
        return graph_updated, False, warnings
    except Exception as exc:
        return False, False, (f"graph archive failed: {exc}",)


def _upsert_topic_graph_node(
    role_path: Path,
    topic: RoleInterviewTopic,
) -> tuple[bool, tuple[str, ...]]:
    if not _graph_archive_enabled():
        return False, ()

    graph = load_graph(role_path)
    topic_path = f"brain/topics/{topic.slug}.md"
    topic_node = NodeRecord(
        id=deterministic_node_id(
            node_type="Topic",
            scope="global",
            path=topic_path,
            title=topic.title,
        ),
        type="Topic",
        scope="global",
        path=topic_path,
        title=topic.title,
        summary=topic.summary,
        aliases=(topic.title,),
    )
    concept = NodeRecord(
        id=deterministic_node_id(
            node_type="Concept",
            scope="global",
            title=topic.title,
        ),
        type="Concept",
        scope="global",
        title=topic.title,
        summary=topic.summary,
        aliases=(topic.title,),
    )
    edge = EdgeRecord(
        id=deterministic_edge_id(topic_node.id, "covers", concept.id),
        type="covers",
        from_node=topic_node.id,
        to_node=concept.id,
    )
    nodes = upsert_node(graph.nodes, topic_node)
    nodes = upsert_node(nodes, concept)
    edges = upsert_edge(graph.edges, edge)
    warnings = _persist_graph(role_path, nodes, edges)
    return True, warnings


def archive_decision(
    role_path: Path,
    title: str,
    summary: str,
    rationale: str,
    source_path: str | None = None,
    supersedes_id: str | None = None,
) -> DecisionArchiveResult:
    title = sanitize_archive_entry(title)
    summary = sanitize_archived_markdown(summary, minimum_chars=4)
    rationale = sanitize_archived_markdown(rationale, minimum_chars=4)
    if source_path is None:
        episodes_dir = role_path / "memory" / "episodes"
        episode_path = episodes_dir / f"episode-{len(list(episodes_dir.glob('*.md'))) + 1:03d}.md"
        source_path = f"memory/episodes/{episode_path.name}"
        atomic_write_text(
            episode_path,
            f"# {title}\n\n{summary}\n\n## Rationale\n\n{rationale}\n",
        )
    written_paths = [source_path]

    decision_id = deterministic_node_id(
        node_type="Decision",
        scope="global",
        title=title,
    )
    if not _graph_archive_enabled():
        return DecisionArchiveResult(
            written_paths=written_paths,
            markdown_written=True,
            graph_updated=False,
            graph_skipped=True,
            decision_id=decision_id,
        )

    graph = load_graph(role_path)
    decision = NodeRecord(
        id=decision_id,
        type="Decision",
        scope="global",
        title=title,
        summary=summary,
        metadata={"rationale": rationale},
    )
    evidence = NodeRecord(
        id=deterministic_node_id(
            node_type="Evidence",
            scope="global",
            title=f"Evidence for {title}",
            metadata={"entry_key": _short_key(source_path)},
        ),
        type="Evidence",
        scope="global",
        path=source_path,
        title=f"Evidence for {title}",
        metadata={"source_type": "decision_archive", "source_path": source_path},
    )
    nodes = upsert_node(graph.nodes, decision)
    nodes = upsert_node(nodes, evidence)
    edges = upsert_edge(
        graph.edges,
        EdgeRecord(
            id=deterministic_edge_id(decision.id, "evidenced_by", evidence.id),
            type="evidenced_by",
            from_node=decision.id,
            to_node=evidence.id,
        ),
    )
    if supersedes_id:
        nodes = [
            _replace_node_status(node, "superseded")
            if node.id == supersedes_id
            else node
            for node in nodes
        ]
        edges = upsert_edge(
            edges,
            EdgeRecord(
                id=deterministic_edge_id(decision.id, "supersedes", supersedes_id),
                type="supersedes",
                from_node=decision.id,
                to_node=supersedes_id,
            ),
        )
    try:
        warnings = _persist_graph(role_path, nodes, edges)
    except Exception as exc:
        return DecisionArchiveResult(
            written_paths=written_paths,
            markdown_written=True,
            graph_updated=False,
            graph_skipped=False,
            decision_id=decision.id,
            doctor_warnings=(f"graph archive failed: {exc}",),
        )
    return DecisionArchiveResult(
        written_paths=written_paths,
        markdown_written=True,
        graph_updated=True,
        graph_skipped=False,
        decision_id=decision.id,
        doctor_warnings=warnings,
    )


def archive_general_workflow(plan: WorkflowArchivePlan) -> WorkflowArchiveResult:
    current = get_current_role_state()
    if plan.role_name and plan.role_name != current.role_name:
        raise ValueError("Workflow archive role does not match the current role.")

    role_path = Path(current.role_path)
    workflow_doc = sanitize_archived_markdown(plan.workflow_doc_markdown)
    workflows_dir = role_path / "brain" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    workflow_filename = f"{plan.workflow_slug}.md"
    workflow_path = workflows_dir / workflow_filename
    atomic_write_text(workflow_path, workflow_doc + "\n")
    upsert_workflow_index_entry(
        workflows_dir / "index.md",
        WorkflowIndexEntry(
            slug=plan.workflow_slug,
            title=plan.workflow_title,
            file=workflow_filename,
            applies_to=plan.workflow_applies_to,
            keywords=tuple(plan.workflow_keywords),
            summary=plan.workflow_summary,
        ),
    )
    upsert_markdown_index_entry(
        role_path / "brain" / "index.md",
        label="工作流索引",
        target="workflows/index.md",
        summary="按需路由全局 workflow。",
    )
    for rule in plan.user_rules:
        write_memory(role_path, target="user", content=sanitize_archive_entry(rule))
    for item in plan.memory_summary:
        write_memory(role_path, target="memory", content=sanitize_archive_entry(item))
    graph_updated, graph_skipped, doctor_warnings = _safe_upsert_workflow_graph(
        role_path,
        plan,
        workflow_path=f"brain/workflows/{workflow_filename}",
        scope="global",
    )
    return WorkflowArchiveResult(
        role_name=current.role_name,
        project_title=None,
        project_slug=None,
        written_paths=[
            f"brain/workflows/{workflow_filename}",
            "brain/workflows/index.md",
            "brain/index.md",
            "memory/USER.md",
            "memory/MEMORY.md",
        ],
        requires_reload=bool(plan.user_rules or plan.memory_summary),
        graph_updated=graph_updated,
        graph_skipped=graph_skipped,
        doctor_warnings=doctor_warnings,
    )


def archive_project_workflow(plan: WorkflowArchivePlan) -> WorkflowArchiveResult:
    current = get_current_role_state()
    if plan.role_name and plan.role_name != current.role_name:
        raise ValueError("Workflow archive role does not match the current role.")
    if not plan.project_title or not plan.project_slug:
        raise ValueError("Project workflow archive requires project title and slug.")

    role_path = Path(current.role_path)
    project_dir = role_path / "projects" / plan.project_slug
    project_dir.mkdir(parents=True, exist_ok=True)
    workflows_dir = project_dir / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflow_doc = sanitize_archived_markdown(plan.workflow_doc_markdown)
    workflow_filename = f"{plan.workflow_slug}.md"
    atomic_write_text(workflows_dir / workflow_filename, workflow_doc + "\n")
    upsert_workflow_index_entry(
        workflows_dir / "index.md",
        WorkflowIndexEntry(
            slug=plan.workflow_slug,
            title=plan.workflow_title,
            file=workflow_filename,
            applies_to=plan.workflow_applies_to,
            keywords=tuple(plan.workflow_keywords),
            summary=plan.workflow_summary,
        ),
    )
    context_doc = (
        sanitize_archived_markdown(plan.context_summary_markdown)
        if plan.context_summary_markdown
        else f"# {plan.project_title}\n\n项目上下文待补充。"
    )
    if "- 工作流索引: workflows/index.md" not in context_doc:
        context_doc = context_doc.rstrip() + "\n\n- 工作流索引: workflows/index.md"
    atomic_write_text(project_dir / "context.md", context_doc.strip() + "\n")
    append_unique_project_memory(project_dir / "memory.md", plan.project_memory)
    upsert_markdown_index_entry(
        role_path / "projects" / "index.md",
        label=plan.project_title,
        target=f"projects/{plan.project_slug}/context.md",
        summary="记录项目上下文与 workflow 索引入口。",
    )
    graph_updated, graph_skipped, doctor_warnings = _safe_upsert_workflow_graph(
        role_path,
        plan,
        workflow_path=f"projects/{plan.project_slug}/workflows/{workflow_filename}",
        scope="project",
    )
    return WorkflowArchiveResult(
        role_name=current.role_name,
        project_title=plan.project_title,
        project_slug=plan.project_slug,
        written_paths=[
            f"projects/{plan.project_slug}/workflows/{workflow_filename}",
            f"projects/{plan.project_slug}/workflows/index.md",
            f"projects/{plan.project_slug}/context.md",
            f"projects/{plan.project_slug}/memory.md",
            "projects/index.md",
        ],
        requires_reload=False,
        graph_updated=graph_updated,
        graph_skipped=graph_skipped,
        doctor_warnings=doctor_warnings,
    )


def _parse_list(text: str) -> list[str]:
    entries: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        entries.append(line)
    return entries


def _split_blocks(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return [block.strip() for block in re.split(r"\n\s*---+\s*\n", stripped) if block.strip()]


def _parse_key_value_block(text: str, known_keys: set[str]) -> dict[str, str]:
    data: dict[str, list[str]] = {}
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if current_key is not None:
                data.setdefault(current_key, []).append("")
            continue
        if ":" in line:
            candidate, remainder = line.split(":", maxsplit=1)
            key = candidate.strip().lower()
            if key in known_keys:
                current_key = key
                data.setdefault(key, []).append(remainder.lstrip())
                continue
        if current_key is not None:
            data.setdefault(current_key, []).append(line)

    return {key: "\n".join(value).strip() for key, value in data.items()}


def _parse_brain_topics(text: str) -> list[RoleInterviewTopic]:
    topics: list[RoleInterviewTopic] = []
    for block in _split_blocks(text):
        payload = _parse_key_value_block(block, {"title", "slug", "summary", "content"})
        title = payload.get("title", "").strip()
        content = payload.get("content", "").strip()
        if not title and not content:
            continue
        slug = payload.get("slug", "").strip() or _slugify(title)
        if not content:
            content = f"# {title}\n"
        topics.append(
            RoleInterviewTopic(
                slug=slug,
                title=title or slug.replace("-", " ").title(),
                summary=payload.get("summary", "").strip(),
                content=content,
            )
        )
    return topics


def _parse_project_memory(text: str) -> list[str]:
    if not text.strip():
        return []
    if "|" in text:
        return [item.strip() for item in text.split("|") if item.strip()]
    return _parse_list(text)


def _parse_projects(text: str) -> list[RoleInterviewProject]:
    projects: list[RoleInterviewProject] = []
    for block in _split_blocks(text):
        payload = _parse_key_value_block(block, {"name", "context", "overlay", "memory"})
        name = payload.get("name", "").strip()
        context = payload.get("context", "").strip()
        if not name and not context:
            continue
        projects.append(
            RoleInterviewProject(
                name=name or "project",
                context=context,
                overlay=payload.get("overlay", "").strip(),
                memory=_parse_project_memory(payload.get("memory", "")),
            )
        )
    return projects


def _build_interview_preview(answers: dict[str, str]) -> str:
    sections = ["# Interview Preview", ""]
    for stage in INTERVIEW_STAGE_ORDER:
        value = answers.get(stage, "").strip()
        if not value:
            continue
        sections.append(f"## {stage}")
        sections.append(value)
        sections.append("")
    return "\n".join(sections).strip() + "\n"


def _merge_language_preference_into_user_memory(answers: dict[str, str]) -> list[str]:
    entries = _parse_list(answers.get("user_memory", ""))
    language_preference = answers.get("language_preference", "").strip()
    if not language_preference:
        return entries

    if any("language" in entry.casefold() or "语言" in entry for entry in entries):
        return entries

    return [f"Preferred language: {language_preference}", *entries]


def _interview_from_answers(answers: dict[str, str]) -> RoleInterview:
    return RoleInterview(
        narrative=answers.get("narrative", "").strip(),
        communication_style=answers.get("communication_style", "").strip(),
        decision_rules=answers.get("decision_rules", "").strip(),
        disclosure_layers=answers.get("disclosure_layers", "").strip(),
        user_memory=_merge_language_preference_into_user_memory(answers),
        memory_summary=_parse_list(answers.get("memory_summary", "")),
        brain_topics=_parse_brain_topics(answers.get("brain_topics", "")),
        projects=_parse_projects(answers.get("projects", "")),
    )


def _word_count(text: str) -> int:
    return len([word for word in re.split(r"\s+", text.strip()) if word])


def _assess_narrative(answer: str) -> InterviewGap:
    text = answer.strip()
    words = _word_count(text)
    if not text:
        return InterviewGap("narrative", "missing", 0.0, "Need identity, trajectory, and current stage.")
    if words < 12:
        return InterviewGap(
            "narrative",
            "partial",
            0.35,
            "Need more depth about background, trajectory, and current stage.",
        )
    return InterviewGap("narrative", "complete", 0.9, "Identity narrative is sufficiently grounded.")


def _assess_language_preference(answer: str) -> InterviewGap:
    text = answer.strip()
    if not text:
        return InterviewGap(
            "language_preference",
            "missing",
            0.0,
            "Language preference has not been expressed yet. Ask once, but do not force it.",
        )
    return InterviewGap(
        "language_preference",
        "complete",
        0.9,
        "Language preference is explicit enough for now.",
    )


def _assess_text_slot(slot: str, answer: str, minimum_words: int, note: str) -> InterviewGap:
    text = answer.strip()
    if not text:
        return InterviewGap(slot, "missing", 0.0, note)
    if _word_count(text) < minimum_words:
        return InterviewGap(slot, "partial", 0.45, f"{note} Add a bit more specificity.")
    return InterviewGap(slot, "complete", 0.85, "Enough detail captured for now.")


def _assess_list_slot(slot: str, answer: str, minimum_items: int, note: str) -> InterviewGap:
    items = _parse_list(answer)
    if not items:
        return InterviewGap(slot, "missing", 0.0, note)
    if len(items) < minimum_items:
        return InterviewGap(slot, "partial", 0.5, f"{note} Add more than one durable item.")
    return InterviewGap(slot, "complete", 0.9, "List coverage is sufficient.")


def _assess_brain_topics(answer: str) -> InterviewGap:
    topics = _parse_brain_topics(answer)
    if not topics:
        return InterviewGap("brain_topics", "missing", 0.0, "Need at least one reusable topic.")
    incomplete = [topic for topic in topics if not topic.summary or not topic.content.strip()]
    if incomplete:
        return InterviewGap(
            "brain_topics",
            "partial",
            0.55,
            "Need summary and content for each topic.",
        )
    return InterviewGap("brain_topics", "complete", 0.9, "Brain topics are structured well enough.")


def _assess_projects(answer: str) -> InterviewGap:
    projects = _parse_projects(answer)
    if not projects:
        return InterviewGap("projects", "missing", 0.0, "Need at least one project or a clear statement that none exist.")
    incomplete = [project for project in projects if not project.context.strip()]
    if incomplete:
        return InterviewGap(
            "projects",
            "partial",
            0.55,
            "Need clearer project context before materializing.",
        )
    return InterviewGap("projects", "complete", 0.9, "Project overlays are structured well enough.")


def assess_interview_gaps(answers: dict[str, str]) -> list[InterviewGap]:
    return [
        _assess_narrative(answers.get("narrative", "")),
        _assess_language_preference(answers.get("language_preference", "")),
        _assess_text_slot(
            "communication_style",
            answers.get("communication_style", ""),
            minimum_words=8,
            note="Need communication defaults and collaboration preferences.",
        ),
        _assess_text_slot(
            "decision_rules",
            answers.get("decision_rules", ""),
            minimum_words=5,
            note="Need clearer prioritization or tradeoff logic.",
        ),
        _assess_text_slot(
            "disclosure_layers",
            answers.get("disclosure_layers", ""),
            minimum_words=6,
            note="Need clearer resident versus on-demand boundary.",
        ),
        _assess_list_slot(
            "user_memory",
            answers.get("user_memory", ""),
            minimum_items=2,
            note="Need durable user memory items.",
        ),
        _assess_list_slot(
            "memory_summary",
            answers.get("memory_summary", ""),
            minimum_items=1,
            note="Need at least one long-term summary item.",
        ),
        _assess_brain_topics(answers.get("brain_topics", "")),
        _assess_projects(answers.get("projects", "")),
    ]


def _build_missing_question(slot: str, answers: dict[str, str], user_language: str) -> str:
    if _language_key(user_language) == "zh":
        if slot == "language_preference":
            return (
                "你希望我后续默认用什么语言和你协作？如果暂时没有明确偏好，也可以先不定，后面再慢慢形成。"
            )
        if slot == "communication_style" and answers.get("narrative"):
            return "我已经大致理解你是谁了。接下来请说说你希望我默认怎么和你沟通：回答方式、结构、节奏和协作方式分别是什么？"
        if slot == "decision_rules" and answers.get("narrative"):
            return "基于你刚才描述的角色，当出现取舍时，你通常按什么优先级做决定？"
        if slot == "disclosure_layers":
            return "你的哪些信息应该始终常驻，哪些信息应该只在需要时再展开？"
        return _localized_stage_prompt(slot, user_language)

    if slot == "language_preference":
        return (
            "What language should I default to when we work together? If you have not decided yet, we can leave it open and let it emerge later."
        )
    if slot == "communication_style" and answers.get("narrative"):
        return (
            "I have a grounded sense of who you are. How should our communication work by default: structure, pacing, tone, and collaboration style?"
        )
    if slot == "decision_rules" and answers.get("narrative"):
        return (
            "Given the role you described, what decision rules do you use in priority order when tradeoffs appear?"
        )
    if slot == "disclosure_layers":
        return (
            "Which parts of your role should stay resident all the time, and which parts should only be pulled in on demand?"
        )
    return _localized_stage_prompt(slot, user_language)


def _build_partial_follow_up(slot: str, answer: str, notes: str, user_language: str) -> str:
    if _language_key(user_language) == "zh":
        if slot == "narrative":
            return "我已经知道一点你的身份了，但这还不够支撑角色。请继续用第一人称补充你是怎么走到今天的、哪些经历塑造了你、你现在处于什么阶段。"
        if slot in {"user_memory", "memory_summary"}:
            return f"{notes} 请再补充几条稳定信息，每行一条。"
        return f"{notes} 请继续补充更具体的 `{slot}` 信息。"

    if slot == "narrative":
        return (
            "I already know a little about your identity, but not enough to ground the role yet. "
            "Please stay in first-person and add how you got here, what shaped you, and what stage you are in now."
        )
    if slot in {"user_memory", "memory_summary"}:
        return f"{notes} Please add a few more stable items, one per line."
    return f"{notes} Please add a more specific follow-up for `{slot}`."


def _append_unique_stage(stages: tuple[str, ...], stage: str) -> tuple[str, ...]:
    if stage in stages:
        return stages
    return (*stages, stage)


def _answered_stage_count(answers: dict[str, str], slots: list[str] | None = None) -> int:
    relevant_slots = slots or INTERVIEW_STAGE_ORDER
    return sum(1 for slot in relevant_slots if answers.get(slot, "").strip())


def _should_offer_early_review(answers: dict[str, str], asked_slots: tuple[str, ...]) -> bool:
    skipped_slots = [slot for slot in asked_slots if not answers.get(slot, "").strip()]
    return bool(skipped_slots) and _answered_stage_count(answers, INTERVIEW_CORE_SLOTS) >= 3


def _next_unasked_slot(answers: dict[str, str], asked_slots: tuple[str, ...]) -> str | None:
    for slot in INTERVIEW_STAGE_ORDER:
        if answers.get(slot, "").strip():
            continue
        if slot in asked_slots:
            continue
        return slot
    for slot in INTERVIEW_STAGE_ORDER:
        if slot in asked_slots:
            continue
        return slot
    return None


def _plan_next_turn_from_answers(
    answers: dict[str, str],
    user_language: str,
    asked_slots: tuple[str, ...] = (),
) -> InterviewTurnPlan:
    gap_summary = assess_interview_gaps(answers)
    if _should_offer_early_review(answers, asked_slots):
        return InterviewTurnPlan(
            target_slot="review",
            question=_localized_review_prompt(user_language),
            rationale=(
                "已经形成一版可用初稿，其余未表达的信息可以后续慢慢积累。"
                if _language_key(user_language) == "zh"
                else "A usable draft exists already, and anything still unsaid can be accumulated later."
            ),
            gap_summary=gap_summary,
            ready_to_finalize=True,
        )

    next_slot = _next_unasked_slot(answers, asked_slots)
    if next_slot is not None:
        gap = next((item for item in gap_summary if item.slot == next_slot), None)
        if gap is not None and gap.status == "partial" and answers.get(next_slot, "").strip():
            question = _build_partial_follow_up(
                gap.slot,
                answers.get(gap.slot, ""),
                gap.notes,
                user_language,
            )
            rationale = gap.notes
        else:
            question = _build_missing_question(next_slot, answers, user_language)
            rationale = gap.notes if gap is not None else "Ask the next interview question."
        return InterviewTurnPlan(
            target_slot=next_slot,
            question=question,
            rationale=rationale,
            gap_summary=gap_summary,
            ready_to_finalize=False,
        )

    return InterviewTurnPlan(
        target_slot="review",
        question=_localized_review_prompt(user_language),
        rationale=(
            "当前已经没有新的初始化问题需要追问，可以进入 review。"
            if _language_key(user_language) == "zh"
            else "There are no more new initialization questions to ask, so the draft can move to review."
        ),
        gap_summary=gap_summary,
        ready_to_finalize=True,
    )


def build_interview_planner_prompt(session: InterviewSession) -> str:
    if _language_key(session.user_language) == "zh":
        lines = [
            "# 动态访谈规划器",
            "",
            f"角色: {session.role_name}",
            f"当前槽位: {session.current_stage}",
            "",
            "工作原则:",
            "- 这不是固定问卷。",
            "- 这些槽位只是归档目标，不是你必须按顺序执行的脚本。",
            "- 当前只问一个信息增益最高的问题。",
            "- 同一个模型在不同情景里问出不同问题是正常的。",
            "- 保持对话自然，同时确保结果能稳定落成角色包。",
            "- 用户没表达出来可以先不记录，不要为了补全而反复追问同一槽位。",
            "- 默认槽位提示只是采访意图锚点，不要逐字复述，先按当前语境润色成自然口语再发问。",
            "",
            "已知信息:",
        ]
        if session.answers:
            for slot in INTERVIEW_STAGE_ORDER:
                value = session.answers.get(slot, "").strip()
                if value:
                    lines.append(f"- {slot}: {value}")
        else:
            lines.append("- <暂无>")

        lines.extend(["", "已问过的槽位:"])
        if session.asked_slots:
            for slot in session.asked_slots:
                lines.append(f"- {slot}")
        else:
            lines.append("- <暂无>")

        lines.extend(["", "缺口评估:"])
        for gap in assess_interview_gaps(session.answers):
            lines.append(
                f"- {gap.slot}: status={gap.status}, confidence={gap.confidence:.2f}, notes={gap.notes}"
            )

        lines.extend(
            [
                "",
                "请返回 JSON，包含:",
                '- `target_slot`: narrative, language_preference, communication_style, decision_rules, disclosure_layers, user_memory, memory_summary, brain_topics, projects, review 之一',
                '- `question`: 下一句真正要问的问题',
                '- `rationale`: 为什么这句当前信息增益最高',
                '- `answer_mode`: `append` 表示补充已有内容，`replace` 表示纠正并覆盖旧内容',
                '- `ready_to_finalize`: 只有在可以进入 review 时才设为 true',
            ]
        )
        return "\n".join(lines) + "\n"

    lines = [
        "# Dynamic Interview Planner",
        "",
        f"Role: {session.role_name}",
        f"Current slot: {session.current_stage}",
        "",
        "Operating principles:",
        "- This is not a fixed questionnaire.",
        "- The slots are storage destinations, not a script you must follow in order.",
        "- Ask exactly one next question with the highest information gain for the current context.",
        "- The same model may ask different questions in different situations and still be correct.",
        "- Keep the conversation natural, but converge toward a role bundle that can be materialized reliably.",
        "- If the user has not expressed something, you may leave it unrecorded for now instead of forcing backfill.",
        "- Default slot prompts are intent anchors, not literal scripts. Polish them into natural wording before asking.",
        "",
        "Known answers:",
    ]
    if session.answers:
        for slot in INTERVIEW_STAGE_ORDER:
            value = session.answers.get(slot, "").strip()
            if value:
                lines.append(f"- {slot}: {value}")
    else:
        lines.append("- <none yet>")

    lines.extend(["", "Already asked slots:"])
    if session.asked_slots:
        for slot in session.asked_slots:
            lines.append(f"- {slot}")
    else:
        lines.append("- <none yet>")

    lines.extend(["", "Gap assessment:"])
    for gap in assess_interview_gaps(session.answers):
        lines.append(
            f"- {gap.slot}: status={gap.status}, confidence={gap.confidence:.2f}, notes={gap.notes}"
        )

    lines.extend(
        [
            "",
            "Return JSON with:",
            '- `target_slot`: one of narrative, language_preference, communication_style, decision_rules, disclosure_layers, user_memory, memory_summary, brain_topics, projects, review',
            '- `question`: ask exactly one next question',
            '- `rationale`: why this question has the highest information gain now',
            '- `answer_mode`: `append` for adding onto existing slot content, `replace` for corrections that should overwrite prior content',
            '- `ready_to_finalize`: true only if the interview is grounded enough to review',
        ]
    )
    return "\n".join(lines) + "\n"


def parse_interview_planner_response(raw: str | dict[str, object]) -> InterviewPlannerDirective:
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    target_slot = str(payload.get("target_slot", "")).strip()
    question = str(payload.get("question", "")).strip()
    rationale = str(payload.get("rationale", "")).strip()
    answer_mode = str(payload.get("answer_mode", "append")).strip().lower() or "append"
    ready_to_finalize = bool(payload.get("ready_to_finalize", False))

    valid_slots = set(INTERVIEW_STAGE_ORDER) | {"review"}
    if target_slot not in valid_slots:
        raise ValueError(f"Unsupported planner target_slot: {target_slot}")
    if not question:
        raise ValueError("Planner response must include a question.")
    if answer_mode not in {"append", "replace"}:
        raise ValueError(f"Unsupported planner answer_mode: {answer_mode}")

    return InterviewPlannerDirective(
        target_slot=target_slot,
        question=question,
        rationale=rationale,
        answer_mode=answer_mode,
        ready_to_finalize=ready_to_finalize,
    )


def render_interview_planner_system_prompt(session: InterviewSession) -> str:
    return _render_template_text(
        templates_dir() / "interview-planner-system.md",
        {
            "<role-name>": session.role_name,
            "<user-language>": session.user_language,
            "<current-slot>": session.current_stage,
            "<planner-guide>": build_interview_planner_prompt(session).strip(),
        },
    )


def initialize_role(role_name: str, skill_version: str) -> Path:
    role_name = normalize_role_name(role_name)
    destination = role_dir(role_name)
    if destination.exists():
        raise FileExistsError(f"Role already exists: {destination}")

    for relative_dir in [
        "brain/graph/indexes",
        "brain/topics",
        "memory/episodes",
        "projects",
        "persona",
    ]:
        (destination / relative_dir).mkdir(parents=True, exist_ok=True)

    for relative_file in [
        "AGENT.md",
        "brain/graph/schema.yaml",
        "brain/index.md",
        "memory/MEMORY.md",
        "memory/USER.md",
        "projects/index.md",
        "persona/communication-style.md",
        "persona/decision-rules.md",
        "persona/disclosure-layers.md",
        "persona/narrative.md",
    ]:
        _render(templates_dir() / relative_file, destination / relative_file, role_name)

    RoleManifest.new(role_name=role_name, skill_version=skill_version).write(
        destination / "role.json"
    )
    return destination


def begin_role_interview(role_name: str, user_language: str = "中文") -> InterviewSession:
    role_name = normalize_role_name(role_name)
    first_plan = _plan_next_turn_from_answers({}, user_language, ())
    return InterviewSession(
        role_name=role_name,
        user_language=user_language,
        current_stage=first_plan.target_slot,
        current_prompt=first_plan.question,
        answers={},
        asked_slots=(),
        preview="",
    )


def submit_interview_answer(
    session: InterviewSession,
    answer: str,
    slot: str | None = None,
    mode: str = "append",
) -> InterviewSession:
    if session.current_stage == "review":
        raise ValueError("Interview is already ready for confirmation.")

    answers = dict(session.answers)
    asked_slots = session.asked_slots
    target_slot = slot or session.current_stage
    if target_slot not in INTERVIEW_STAGE_ORDER:
        raise ValueError(f"Unsupported interview slot: {target_slot}")
    if mode not in {"append", "replace"}:
        raise ValueError(f"Unsupported answer mode: {mode}")
    incoming = answer.strip()
    existing = answers.get(target_slot, "").strip()
    if mode == "replace":
        if incoming:
            answers[target_slot] = incoming
        elif existing:
            answers[target_slot] = existing
        else:
            answers.pop(target_slot, None)
    elif existing and incoming and incoming not in existing:
        answers[target_slot] = f"{existing}\n\n{incoming}"
    elif incoming:
        answers[target_slot] = incoming
    else:
        if existing:
            answers[target_slot] = existing
        else:
            answers.pop(target_slot, None)

    asked_slots = _append_unique_stage(asked_slots, target_slot)
    next_plan = _plan_next_turn_from_answers(answers, session.user_language, asked_slots)
    if next_plan.ready_to_finalize:
        return InterviewSession(
            role_name=session.role_name,
            user_language=session.user_language,
            current_stage="review",
            current_prompt=next_plan.question,
            answers=answers,
            asked_slots=asked_slots,
            preview=_build_interview_preview(answers),
        )

    return InterviewSession(
        role_name=session.role_name,
        user_language=session.user_language,
        current_stage=next_plan.target_slot,
        current_prompt=next_plan.question,
        answers=answers,
        asked_slots=asked_slots,
        preview="",
    )


def finalize_role_interview(session: InterviewSession, skill_version: str) -> Path:
    if session.current_stage != "review":
        raise ValueError("Interview is not ready to finalize.")
    return initialize_role_from_interview(
        role_name=session.role_name,
        skill_version=skill_version,
        interview=_interview_from_answers(session.answers),
    )


def initialize_role_from_interview(
    role_name: str,
    skill_version: str,
    interview: RoleInterview,
) -> Path:
    role_name = normalize_role_name(role_name)
    destination = initialize_role(role_name=role_name, skill_version=skill_version)

    atomic_write_text(
        destination / "persona" / "narrative.md",
        f"# 人物自述\n\n{interview.narrative.strip()}\n",
    )
    atomic_write_text(
        destination / "persona" / "communication-style.md",
        f"# 沟通风格\n\n{interview.communication_style.strip()}\n",
    )
    atomic_write_text(
        destination / "persona" / "decision-rules.md",
        f"# 决策规则\n\n{interview.decision_rules.strip()}\n",
    )
    atomic_write_text(
        destination / "persona" / "disclosure-layers.md",
        f"# 披露层级\n\n{interview.disclosure_layers.strip()}\n",
    )

    _replace_marker_entries(destination / "memory" / "USER.md", interview.user_memory)
    _replace_marker_entries(destination / "memory" / "MEMORY.md", interview.memory_summary)

    brain_index_lines = ["# 知识索引", ""]
    for topic in interview.brain_topics:
        topic_path = destination / "brain" / "topics" / f"{topic.slug}.md"
        atomic_write_text(topic_path, topic.content.strip() + "\n")
        _upsert_topic_graph_node(destination, topic)
        brain_index_lines.append(f"- {topic.title}: topics/{topic.slug}.md")
        if topic.summary:
            brain_index_lines.append(f"  - {topic.summary}")
    atomic_write_text(
        destination / "brain" / "index.md",
        "\n".join(brain_index_lines).strip() + "\n",
    )

    project_index_lines = ["# 项目索引", ""]
    for project in interview.projects:
        project_dir = destination / "projects" / project.name
        project_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            project_dir / "context.md",
            f"# {project.name}\n\n{project.context.strip()}\n",
        )
        atomic_write_text(
            project_dir / "overlay.md",
            f"# {project.name} overlay\n\n{project.overlay.strip()}\n",
        )
        memory_lines = [f"# {project.name} memory", ""]
        for item in project.memory or []:
            memory_lines.append(f"- {item}")
        atomic_write_text(
            project_dir / "memory.md",
            "\n".join(memory_lines).strip() + "\n",
        )
        project_index_lines.append(f"- {project.name}: projects/{project.name}/context.md")
    atomic_write_text(
        destination / "projects" / "index.md",
        "\n".join(project_index_lines).strip() + "\n",
    )

    return destination


def load_role_bundle(role_name: str) -> RoleBundle:
    role_name = normalize_role_name(role_name)
    base_path = role_dir(role_name)
    resident_files = {
        relative: (base_path / relative).read_text(encoding="utf-8")
        for relative in RESIDENT_PATHS
    }
    set_current_role_state(role_name)
    maybe_bootstrap_project_from_cwd(base_path)
    context_snapshot = build_frozen_snapshot(base_path)
    return RoleBundle(
        role_name=role_name,
        role_path=str(base_path),
        resident_files=resident_files,
        on_demand_paths=ON_DEMAND_PATHS,
        context_snapshot=context_snapshot,
    )


def load_query_context_bundle(
    role_name: str,
    query: str,
    max_chars: int = 4_000,
    max_brain_depth: int = 1,
) -> QueryContextBundle:
    role_name = normalize_role_name(role_name)
    base_path = role_dir(role_name)
    resident_files = {
        relative: (base_path / relative).read_text(encoding="utf-8")
        for relative in RESIDENT_PATHS
    }
    set_current_role_state(role_name)
    maybe_bootstrap_project_from_cwd(base_path)
    discovered_paths = discover_context_paths(
        base_path,
        query=query,
        max_brain_depth=max_brain_depth,
    )
    context_snapshot = build_context_snapshot(
        base_path,
        query=query,
        max_chars=max_chars,
        max_brain_depth=max_brain_depth,
    )
    return QueryContextBundle(
        role_name=role_name,
        role_path=str(base_path),
        resident_files=resident_files,
        discovered_paths=discovered_paths,
        context_snapshot=context_snapshot,
    )


def list_roles() -> list[str]:
    home = roleme_home()
    if not home.exists():
        return []
    return sorted(path.name for path in home.iterdir() if path.is_dir())


def export_role(role_name: str, output_dir: Path, as_zip: bool = True) -> Path:
    role_name = normalize_role_name(role_name)
    source = role_dir(role_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    if as_zip:
        archive_base = output_dir / source.name
        archive_path = shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=source.parent,
            base_dir=source.name,
        )
        return Path(archive_path)
    destination = output_dir / source.name
    shutil.copytree(source, destination, dirs_exist_ok=False)
    return destination


def doctor_role(role_name: str) -> DoctorReport:
    role_name = normalize_role_name(role_name)
    base_path = role_dir(role_name)
    missing = [relative for relative in REQUIRED_FILES if not (base_path / relative).exists()]
    warnings: list[str] = []
    manifest_path = base_path / "role.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            warnings.append(f"schema mismatch: {payload.get('schemaVersion')}")
    graph_report = doctor_graph(base_path)
    warnings.extend(graph_report.warnings)
    return DoctorReport(missing_files=missing, warnings=warnings)
