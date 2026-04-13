from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import shutil

from tools.context_router import build_context_snapshot, discover_context_paths


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
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


@dataclass(frozen=True)
class RoleBundle:
    role_name: str
    role_path: str
    resident_files: dict[str, str]
    on_demand_paths: list[str]


@dataclass(frozen=True)
class QueryContextBundle:
    role_name: str
    role_path: str
    resident_files: dict[str, str]
    discovered_paths: list[str]
    context_snapshot: str


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
    current_stage: str
    current_prompt: str
    answers: dict[str, str]
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
class DoctorReport:
    missing_files: list[str]
    warnings: list[str]


INTERVIEW_STAGE_ORDER = [
    "narrative",
    "communication_style",
    "decision_rules",
    "disclosure_layers",
    "user_memory",
    "memory_summary",
    "brain_topics",
    "projects",
]

INTERVIEW_STAGE_PROMPTS = {
    "narrative": (
        "Please answer in first-person. Who are you, how did you get here, and what stage are you in now?"
    ),
    "communication_style": (
        "How do you prefer to communicate and collaborate: default language, answer style, pacing, and tone?"
    ),
    "decision_rules": (
        "What decision rules do you use in priority order? Explain what you optimize for first, second, and third."
    ),
    "disclosure_layers": (
        "How should your context be disclosed progressively? What belongs in resident context versus on-demand context?"
    ),
    "user_memory": (
        "List stable preferences or long-term agreements for USER memory. One item per line, optionally starting with `- `."
    ),
    "memory_summary": (
        "List high-value long-term conclusions for MEMORY summary. One item per line."
    ),
    "brain_topics": (
        "Describe brain topics with `title:`, `slug:`, `summary:`, and `content:`. Separate multiple topics with `---`."
    ),
    "projects": (
        "Describe project context with `name:`, `context:`, `overlay:`, and `memory:`. Separate multiple projects with `---`, and split multiple memory items with `|`."
    ),
}

INTERVIEW_REVIEW_PROMPT = (
    "Interview draft is ready. Please confirm whether this preview should be materialized into the role bundle."
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def templates_dir() -> Path:
    return repo_root() / "templates"


def roleme_home() -> Path:
    override = os.environ.get("ROLEME_HOME")
    return Path(override).expanduser() if override else Path.home() / ".roleMe"


def role_dir(role_name: str) -> Path:
    return roleme_home() / role_name


def _render(source: Path, destination: Path, role_name: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text(encoding="utf-8").replace("<role-name>", role_name)
    destination.write_text(content, encoding="utf-8")


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
    path.write_text(updated, encoding="utf-8")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "topic"


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


def _interview_from_answers(answers: dict[str, str]) -> RoleInterview:
    return RoleInterview(
        narrative=answers.get("narrative", "").strip(),
        communication_style=answers.get("communication_style", "").strip(),
        decision_rules=answers.get("decision_rules", "").strip(),
        disclosure_layers=answers.get("disclosure_layers", "").strip(),
        user_memory=_parse_list(answers.get("user_memory", "")),
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


def _build_missing_question(slot: str, answers: dict[str, str]) -> str:
    if slot == "communication_style" and answers.get("narrative"):
        return (
            "I have a grounded sense of who you are. How should our communication work by default: language, structure, pacing, and collaboration style?"
        )
    if slot == "decision_rules" and answers.get("narrative"):
        return (
            "Given the role you described, what decision rules do you use in priority order when tradeoffs appear?"
        )
    if slot == "disclosure_layers":
        return (
            "Which parts of your role should stay resident all the time, and which parts should only be pulled in on demand?"
        )
    return INTERVIEW_STAGE_PROMPTS[slot]


def _build_partial_follow_up(slot: str, answer: str, notes: str) -> str:
    if slot == "narrative":
        return (
            "I already know a little about your identity, but not enough to ground the role yet. "
            "Please stay in first-person and add how you got here, what shaped you, and what stage you are in now."
        )
    if slot in {"user_memory", "memory_summary"}:
        return f"{notes} Please add a few more stable items, one per line."
    return f"{notes} Please add a more specific follow-up for `{slot}`."


def _plan_next_turn_from_answers(answers: dict[str, str]) -> InterviewTurnPlan:
    gap_summary = assess_interview_gaps(answers)
    for gap in gap_summary:
        if gap.status == "complete":
            continue
        if gap.status == "partial":
            question = _build_partial_follow_up(gap.slot, answers.get(gap.slot, ""), gap.notes)
        else:
            question = _build_missing_question(gap.slot, answers)
        return InterviewTurnPlan(
            target_slot=gap.slot,
            question=question,
            rationale=gap.notes,
            gap_summary=gap_summary,
            ready_to_finalize=False,
        )

    return InterviewTurnPlan(
        target_slot="review",
        question=INTERVIEW_REVIEW_PROMPT,
        rationale="All required slots are covered well enough to materialize the role bundle.",
        gap_summary=gap_summary,
        ready_to_finalize=True,
    )


def build_interview_planner_prompt(session: InterviewSession) -> str:
    lines = [
        "# Dynamic Interview Planner",
        "",
        f"Role: {session.role_name}",
        f"Current slot: {session.current_stage}",
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

    lines.extend(["", "Gap assessment:"])
    for gap in assess_interview_gaps(session.answers):
        lines.append(
            f"- {gap.slot}: status={gap.status}, confidence={gap.confidence:.2f}, notes={gap.notes}"
        )

    lines.extend(
        [
            "",
            "Return JSON with:",
            '- `target_slot`: one of narrative, communication_style, decision_rules, disclosure_layers, user_memory, memory_summary, brain_topics, projects, review',
            '- `question`: ask exactly one next question',
            '- `rationale`: why this question has the highest information gain now',
            '- `ready_to_finalize`: true only if the interview is grounded enough to review',
        ]
    )
    return "\n".join(lines) + "\n"


def initialize_role(role_name: str, skill_version: str) -> Path:
    destination = role_dir(role_name)
    if destination.exists():
        raise FileExistsError(f"Role already exists: {destination}")

    for relative_dir in ["brain/topics", "memory/episodes", "projects", "persona"]:
        (destination / relative_dir).mkdir(parents=True, exist_ok=True)

    for relative_file in [
        "AGENT.md",
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


def begin_role_interview(role_name: str) -> InterviewSession:
    first_plan = _plan_next_turn_from_answers({})
    return InterviewSession(
        role_name=role_name,
        current_stage=first_plan.target_slot,
        current_prompt=first_plan.question,
        answers={},
        preview="",
    )


def submit_interview_answer(session: InterviewSession, answer: str) -> InterviewSession:
    if session.current_stage == "review":
        raise ValueError("Interview is already ready for confirmation.")

    answers = dict(session.answers)
    incoming = answer.strip()
    existing = answers.get(session.current_stage, "").strip()
    if existing and incoming and incoming not in existing:
        answers[session.current_stage] = f"{existing}\n\n{incoming}"
    else:
        answers[session.current_stage] = incoming or existing

    next_plan = _plan_next_turn_from_answers(answers)
    if next_plan.ready_to_finalize:
        return InterviewSession(
            role_name=session.role_name,
            current_stage="review",
            current_prompt=next_plan.question,
            answers=answers,
            preview=_build_interview_preview(answers),
        )

    return InterviewSession(
        role_name=session.role_name,
        current_stage=next_plan.target_slot,
        current_prompt=next_plan.question,
        answers=answers,
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
    destination = initialize_role(role_name=role_name, skill_version=skill_version)

    (destination / "persona" / "narrative.md").write_text(
        f"# 人物自述\n\n{interview.narrative.strip()}\n",
        encoding="utf-8",
    )
    (destination / "persona" / "communication-style.md").write_text(
        f"# 沟通风格\n\n{interview.communication_style.strip()}\n",
        encoding="utf-8",
    )
    (destination / "persona" / "decision-rules.md").write_text(
        f"# 决策规则\n\n{interview.decision_rules.strip()}\n",
        encoding="utf-8",
    )
    (destination / "persona" / "disclosure-layers.md").write_text(
        f"# 披露层级\n\n{interview.disclosure_layers.strip()}\n",
        encoding="utf-8",
    )

    _replace_marker_entries(destination / "memory" / "USER.md", interview.user_memory)
    _replace_marker_entries(destination / "memory" / "MEMORY.md", interview.memory_summary)

    brain_index_lines = ["# 知识索引", ""]
    for topic in interview.brain_topics:
        topic_path = destination / "brain" / "topics" / f"{topic.slug}.md"
        topic_path.write_text(topic.content.strip() + "\n", encoding="utf-8")
        brain_index_lines.append(f"- {topic.title}: topics/{topic.slug}.md")
        if topic.summary:
            brain_index_lines.append(f"  - {topic.summary}")
    (destination / "brain" / "index.md").write_text(
        "\n".join(brain_index_lines).strip() + "\n",
        encoding="utf-8",
    )

    project_index_lines = ["# 项目索引", ""]
    for project in interview.projects:
        project_dir = destination / "projects" / project.name
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "context.md").write_text(
            f"# {project.name}\n\n{project.context.strip()}\n",
            encoding="utf-8",
        )
        (project_dir / "overlay.md").write_text(
            f"# {project.name} overlay\n\n{project.overlay.strip()}\n",
            encoding="utf-8",
        )
        memory_lines = [f"# {project.name} memory", ""]
        for item in project.memory or []:
            memory_lines.append(f"- {item}")
        (project_dir / "memory.md").write_text(
            "\n".join(memory_lines).strip() + "\n",
            encoding="utf-8",
        )
        project_index_lines.append(f"- {project.name}: projects/{project.name}/context.md")
    (destination / "projects" / "index.md").write_text(
        "\n".join(project_index_lines).strip() + "\n",
        encoding="utf-8",
    )

    return destination


def load_role_bundle(role_name: str) -> RoleBundle:
    base_path = role_dir(role_name)
    resident_files = {
        relative: (base_path / relative).read_text(encoding="utf-8")
        for relative in RESIDENT_PATHS
    }
    return RoleBundle(
        role_name=role_name,
        role_path=str(base_path),
        resident_files=resident_files,
        on_demand_paths=ON_DEMAND_PATHS,
    )


def load_query_context_bundle(
    role_name: str,
    query: str,
    max_chars: int = 4_000,
    max_brain_depth: int = 1,
) -> QueryContextBundle:
    base_path = role_dir(role_name)
    resident_files = {
        relative: (base_path / relative).read_text(encoding="utf-8")
        for relative in RESIDENT_PATHS
    }
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
    base_path = role_dir(role_name)
    missing = [relative for relative in REQUIRED_FILES if not (base_path / relative).exists()]
    warnings: list[str] = []
    manifest_path = base_path / "role.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            warnings.append(f"schema mismatch: {payload.get('schemaVersion')}")
    return DoctorReport(missing_files=missing, warnings=warnings)
