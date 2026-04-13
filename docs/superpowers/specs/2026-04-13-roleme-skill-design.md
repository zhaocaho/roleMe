# roleMe Skill Design

Date: 2026-04-13
Status: Confirmed, ready for implementation planning

## Overview

`roleMe` is a portable user-role bundle skill for agent workflows.

Its core purpose is not to turn the model into a role. Its purpose is to let the user load a role as their own active identity context for the current conversation. After `/roleMe <role-name>`, the assistant remains an assistant, but it should interpret the user through the loaded role's identity, preferences, decision patterns, expression style, and progressively disclosed knowledge.

This design keeps the existing layered architecture of `brain/`, `memory/`, `projects/`, and the former `self-model/` concept, but renames `self-model/` to `persona/` to avoid the common misunderstanding that this folder defines the model's selfhood. In v1, `persona/` defines the loaded user's role identity.

The design also preserves progressive disclosure as a first-class architecture principle:

- load only the smallest stable role core by default
- retrieve deeper role knowledge only when the conversation needs it
- keep memory, topic knowledge, and project overlays discoverable through stepwise lookup rather than full eager injection

This direction is informed by Hermes concepts around persistent memory, context files, and personality separation, while adapting them to a portable user-role bundle model rather than copying Hermes surface structure directly.

References:

- https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/
- https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files/
- https://hermes-agent.nousresearch.com/docs/user-guide/features/personality/

## Goals

- Make `/roleMe <role-name>` mean "load the user's role context", not "switch the assistant's persona"
- Preserve the layered structure of `persona/`, `memory/`, `brain/`, and `projects/`
- Keep progressive disclosure as the default runtime behavior
- Support deeper first-time initialization through guided interview instead of shallow template-only setup
- Allow the assistant to stepwise discover relevant role knowledge during later conversations
- Keep role bundles portable as plain files under `~/.roleMe/<role-name>/`
- Support packaging, validation, migration, and export without coupling to a single machine

## Non-Goals

- Do not implement host-wide assistant persona replacement in v1
- Do not flatten all role identity into `memory/`
- Do not eagerly inject the full role bundle into every conversation
- Do not build a full autonomous retrieval engine beyond deterministic file operations and skill-guided lookup in v1
- Do not introduce destructive role deletion commands in v1

## Core Mental Model

### What `/roleMe` means

`/roleMe <role-name>` loads a user-side role bundle into the current conversation.

After loading:

- the assistant should continue acting as an assistant
- the user should be interpreted as the loaded role
- the assistant should prefer the loaded role's identity, decision habits, style, and memory when interpreting the user's intent
- the role bundle should shape understanding first, and wording or naming second

In short:

- `roleMe` manages user role context
- `roleMe` does not manage assistant persona switching

### Why `persona/` exists

`memory/` is not enough on its own.

`memory/` stores durable preferences, facts, summaries, and promoted history. It answers "what should be remembered".

`persona/` stores identity definition, voice, decision tendencies, and disclosure boundaries. It answers "who this role is" and "how this user-role should be interpreted".

This separation is important because:

- identity should remain structured and explicit
- memory should stay concise and retrieval-friendly
- not all identity belongs in persistent summary memory
- merging both into `memory/` would blur stable role definition and accumulated recall

## Role Bundle Structure

```text
~/.roleMe/
  self/
    AGENT.md
    role.json
    persona/
      narrative.md
      communication-style.md
      decision-rules.md
      disclosure-layers.md
    brain/
      index.md
      topics/
    memory/
      USER.md
      MEMORY.md
      episodes/
    projects/
      index.md
      <project-name>/
        overlay.md
        context.md
        memory.md
  <other-role>/
    ...
```

## Directory Responsibilities

### `persona/`

This is the role's identity layer.

It stores:

- first-person narrative self-description
- communication tendencies
- decision rules and tradeoff habits
- disclosure boundaries and retrieval hints

Recommended files:

- `persona/narrative.md`
- `persona/communication-style.md`
- `persona/decision-rules.md`
- `persona/disclosure-layers.md`

### `memory/`

This is the durable recall layer.

It stores:

- stable preferences
- long-term facts
- high-value summaries
- promoted insights from conversation history
- episodic records when detail must be preserved before summarization

Recommended files:

- `memory/USER.md`
- `memory/MEMORY.md`
- `memory/episodes/*`

### `brain/`

This is the role's topic and knowledge map.

It stores:

- major domains this role thinks about
- indexes to deeper topic notes
- knowledge entry points for stepwise retrieval

It should not be a full eager dump. `brain/index.md` is an index, and `brain/topics/*` holds deeper material.

### `projects/`

This is the overlay layer for concrete contexts.

It stores:

- project-specific constraints
- project-specific memory
- project-level behavior adjustments

Project overlays should modify the base role, not replace it.

## `AGENT.md` Contract

`AGENT.md` becomes the user-role loading protocol.

It should not tell the model to become the role. It should tell the assistant how to interpret the user after the role is loaded.

At minimum, `AGENT.md` must define:

1. Current role declaration
   The current user has loaded role `<role-name>`. Interpret the user's intent, style, and decision patterns through this role.

2. Resident context
   The stable files that should be loaded as the conversation's default role core.

3. On-demand context
   The deeper files that should only be read when the conversation needs them.

4. Retrieval routing
   How the assistant should decide whether to consult `memory`, `brain`, `projects`, or episodic details.

5. Memory writeback policy
   Which newly surfaced information belongs in `USER.md`, `MEMORY.md`, or `episodes/`.

6. Progressive disclosure boundaries
   Which knowledge should stay latent until triggered by topic, intent, or need.

### Recommended default resident files

- `persona/narrative.md`
- `persona/communication-style.md`
- `persona/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

### Recommended default on-demand paths

- `persona/disclosure-layers.md`
- `brain/index.md`
- `brain/topics/*`
- `projects/index.md`
- `projects/<project-name>/*`
- `memory/episodes/*`

## Progressive Disclosure Model

Progressive disclosure is a runtime rule, not only a folder naming convention.

The assistant should not inject everything at once. It should follow a staged lookup model.

### Stage 1: interpret from the resident role core

For each user turn, first interpret the request from:

- `persona/narrative.md`
- `persona/communication-style.md`
- `persona/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

This gives a stable first-pass understanding of who the user-role is.

### Stage 2: route to the right deeper layer

If the answer depends on deeper context, the assistant should decide which layer to inspect next:

- consult `brain/index.md` when the conversation touches a knowledge domain or conceptual area
- consult `projects/index.md` when the conversation appears project-specific
- consult `memory/episodes/*` when summary memory is insufficient and event-level detail matters
- consult `persona/disclosure-layers.md` when the assistant must decide whether deeper personal identity details should be surfaced

### Stage 3: stepwise expansion

When a domain is identified, the assistant should expand one step at a time rather than load the entire tree.

Example:

1. The user asks about a domain-related issue
2. The assistant checks `brain/index.md`
3. `brain/index.md` points to a relevant topic note
4. The assistant reads only that note or the next linked note
5. If needed, it continues one layer deeper

This supports the user's intended behavior:

- if a knowledge document is stored in the role's "brain"
- and the conversation enters that domain
- the assistant should be able to find it progressively and use it
- without preloading every knowledge file into the conversation

### Disclosure policy

The system should prefer:

- small stable resident context
- index-first retrieval
- topic-triggered deepening
- project-triggered overlays
- summary-first memory recall, then episodic fallback

The system should avoid:

- full eager role injection
- storing domain knowledge directly in resident memory
- mixing project overlays into the base identity layer

## Initialization Flow

If the target role does not exist, `/roleMe` should enter guided initialization mode.

Initialization should no longer be "create folders immediately and stop". It should first perform a substantial guided interview, then write the role bundle.

### Initialization goals

- produce a usable first version of the role in one guided flow
- collect enough identity depth to support later in-role conversations
- prioritize first-person narrative identity, not just shallow profile fields
- convert raw conversation into structured role files
- keep the user in control before final write

### Initialization stages

1. Narrative identity interview
   Collect a first-person self-description: who the user is in this role, how they got here, what stage they are in, what they care about, and why they work the way they do.

2. Communication shaping
   Extract how this role tends to speak, explain, react, and collaborate.

3. Decision modeling
   Extract how this role makes tradeoffs, what it values, when it becomes cautious, and what defaults it uses when information is incomplete.

4. Knowledge map seeding
   Identify recurring domains, topic clusters, and likely `brain/` entry points.

5. Durable memory seeding
   Extract stable preferences, long-term facts, and high-value summaries for `memory/`.

6. Preview and correction
   Show a draft role summary before final writing so the user can correct identity drift.

7. Write role bundle
   Persist the structured files.

8. Activate role
   Load the newly created role into the current conversation.

### Initialization output mapping

Interview output should map to files like this:

- narrative self-description -> `persona/narrative.md`
- communication habits -> `persona/communication-style.md`
- decision tendencies -> `persona/decision-rules.md`
- disclosure boundaries -> `persona/disclosure-layers.md`
- stable preferences and facts -> `memory/USER.md`
- high-value summaries and indexes -> `memory/MEMORY.md`
- domain map -> `brain/index.md`
- concrete topic files -> `brain/topics/*` only when enough detail exists
- project-specific material -> `projects/` only when clearly scoped

### Initialization writing principles

- `persona/` can preserve a human, first-person feel
- `memory/` should stay compressed and retrieval-friendly
- `brain/` should favor indexes over bulk content
- `projects/` should not be invented unless the interview clearly identifies them

## Memory Design

The memory layer adapts the Hermes-style separation between stable user memory and retrievable historical detail to a portable role bundle.

### `memory/USER.md`

Stores:

- stable preferences
- long-term agreements
- persistent facts about the user-role
- collaboration defaults

### `memory/MEMORY.md`

Stores:

- high-value compressed summaries
- durable conclusions worth reusing
- indexes into deeper memories
- promoted insights from repeated interaction

### `memory/episodes/`

Stores:

- conversation-level detail
- event records
- evidence preserved before summarization
- details too large or too transient for resident memory

### Frozen snapshot rule

At role activation time:

- read `USER.md` and `MEMORY.md`
- build a frozen resident snapshot for the current conversation
- persist new memory writes immediately to disk
- do not automatically rebuild the resident snapshot mid-conversation unless the role is explicitly reloaded

This preserves predictability and avoids prompt drift.

## Knowledge and Retrieval Design

`brain/` exists so the role can own knowledge without forcing that knowledge into the resident prompt.

### `brain/index.md`

This file should:

- list the role's major knowledge domains
- map domains to specific topic files
- help the assistant decide whether it should go deeper

### `brain/topics/*`

These files should hold:

- domain notes
- methods
- frameworks
- references
- linked knowledge documents

The skill should support both local content and referenced documents, as long as retrieval remains controlled and stepwise.

## Project Overlay Design

`projects/` allows the same role to behave differently across concrete working contexts without changing the base identity.

Each project overlay can include:

- `overlay.md` for project-specific behavioral adjustments
- `context.md` for constraints and facts
- `memory.md` for project-level durable memory

The assistant should consult `projects/index.md` first and only read a project directory when the current conversation clearly points there.

## Commands

The v1 runtime skill should support:

- `/roleMe`
- `/roleMe <role-name>`
- `/roleMe list`
- `/roleMe current`
- `/roleMe optimize [role-name]`
- `/roleMe export [role-name]`
- `/roleMe doctor [role-name]`

### Command semantics

- `/roleMe`
  - load `self` if it exists
  - otherwise initialize `self`

- `/roleMe <role-name>`
  - load the named role if it exists
  - otherwise initialize it

- `/roleMe current`
  - report which user-role is currently active in the conversation

- `/roleMe optimize`
  - focus on memory compaction, cleanup, and role bundle hygiene

- `/roleMe doctor`
  - validate required files, schema compatibility, and structural health

## Manifest and Compatibility

Each role bundle must include `role.json`.

Example:

```json
{
  "roleName": "self",
  "schemaVersion": "1.0",
  "roleVersion": "0.1.0",
  "createdBySkillVersion": "0.1.0",
  "compatibleSkillRange": ">=0.1 <1.0",
  "createdAt": "2026-04-13T00:00:00+08:00",
  "updatedAt": "2026-04-13T00:00:00+08:00",
  "defaultLoadProfile": "standard"
}
```

Compatibility rules:

- compatible schemas should load directly
- older schemas may be upgraded by tools when possible
- incompatible future schemas should fail safely with a clear message

## Repository Responsibilities

This repository is the source repository for the skill system, not the long-term storage location for user role data.

It should own:

- templates
- runtime tools
- packaging scripts
- validation and upgrade scripts
- tests
- references
- published skill artifacts

The user's real role bundles live under `~/.roleMe/`.

## Template Changes Required

To support this design, templates should be updated as follows:

- rename `templates/self-model/` to `templates/persona/`
- update `templates/AGENT.md` to describe user-role interpretation rather than assistant-role performance
- update resident and on-demand file lists to use `persona/*`
- update disclosure instructions to include retrieval routing
- keep `MEMORY.md` and `USER.md` as structured marker-block files for safe edits
- keep project templates explicitly on-demand

## Success Criteria

The design is successful when:

- `/roleMe <role-name>` clearly means the user becomes that role in the conversation
- the assistant still behaves as an assistant
- the role bundle structure preserves `persona`, `memory`, `brain`, and `projects`
- initialization produces a deeper and more convincing role foundation
- later conversations can retrieve relevant domain knowledge progressively from `brain/`
- resident context remains small and stable
- deeper knowledge stays discoverable without full eager injection
- role bundles remain portable and packageable

## Confirmed Decisions

- `roleMe` manages user-side role context, not assistant persona switching
- the current `self-model/` concept stays, but is renamed to `persona/`
- `memory/` does not replace `persona/`
- progressive disclosure remains a core architecture rule
- the assistant should be able to stepwise discover knowledge from `brain/` during later conversations
- initialization should use a deeper guided interview, with strong emphasis on first-person narrative identity
