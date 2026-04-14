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


def begin_role_interview(role_name: str, user_language: str = "中文") -> InterviewSession:
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
