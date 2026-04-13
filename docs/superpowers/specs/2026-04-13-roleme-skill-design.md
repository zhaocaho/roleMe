# roleMe Skill Design

Date: 2026-04-13
Status: Approved for planning

## Summary

`roleMe` is a reusable role system that lets a user initialize, load, switch, optimize, and export a "digital twin" role package. Each role lives under `~/.roleMe/<role-name>/` and can be copied between machines or users as a portable folder.

The system has two layers:

- Runtime layer: a `roleMe` skill that loads and operates on role packages during conversation
- Build layer: this repository, which owns templates, scripts, references, and the versioned skill artifact

The target experience is:

- `/roleMe` loads `self` by default
- `/roleMe <role-name>` loads a named role
- If the role does not exist, the skill initializes it through a guided conversation
- Once loaded, the current session continues in that role until the user explicitly switches or exits

## Goals

- Make a role package portable, inspectable, and editable as plain files
- Support direct use of copied role folders without requiring the original author environment
- Keep always-loaded context small through progressive disclosure
- Separate stable identity, memory, knowledge, and project overlays
- Support future versioned skill builds and schema migrations
- Make initialization complete enough to produce a usable first version of a role in one conversation

## Non-Goals

- Global host-level persona override outside the current conversation
- Automatic deletion of roles in v1
- Full autonomous memory retrieval stack in v1 beyond file-based indexing, summarization, and promotion
- Role-specific cloud sync in v1

## Core Concepts

### Role Package

A role package is a folder under `~/.roleMe/<role-name>/` that contains all files needed to load that role.

### Entry File

`AGENT.md` is the LLM-facing entry point. It defines:

- which files are always loaded
- which files are loaded on demand
- how project overlays are discovered
- how memory and knowledge should be routed during a task

### Runtime Metadata

`role.json` is the tool-facing manifest. It defines schema and compatibility metadata so scripts and the skill can validate and migrate role packages safely.

## Role Package Structure

```text
~/.roleMe/
  self/
    AGENT.md
    role.json
    self-model/
      identity.md
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

## Loading Contract

### Default Resolution

- `/roleMe`:
  - load `~/.roleMe/self` when it exists
  - otherwise initialize `self`
- `/roleMe <role-name>`:
  - load `~/.roleMe/<role-name>` when it exists
  - otherwise initialize that role

### Session Activation

Role activation is conversation-scoped:

- the skill reads `AGENT.md` and the always-loaded files
- it emits an internal role activation summary for the current conversation
- future turns continue in that role until the user switches or exits

This design avoids hard dependency on host-global persona state while preserving the desired "load once, talk as that person" experience.

## Progressive Disclosure Model

### Always-Loaded Layer

These files are loaded during activation and remain the stable base:

- `self-model/identity.md`
- `self-model/communication-style.md`
- `self-model/decision-rules.md`
- `memory/USER.md`
- `memory/MEMORY.md`

### On-Demand Layer

These files are loaded only when the task needs them:

- `brain/index.md`
- `brain/topics/*`
- `projects/index.md`
- `projects/<project-name>/*`
- `memory/episodes/*`

### Disclosure Rules

`self-model/disclosure-layers.md` defines what belongs in the default layer, conditional layer, and deep layer so the role remains usable without overloading context.

## Initialization Flow

When a role folder does not exist, the skill enters `init` mode and completes a guided modeling conversation.

### Initialization Principles

- initialization should create a usable role in one conversation
- initialization should still write structured files, not a single large prompt
- the user can refine any section before the files are finalized
- partial progress should be staged in memory during the conversation and written only after confirmation

### Initialization Stages

1. Identity capture
2. Communication style capture
3. Decision rules capture
4. Brain and knowledge capture
5. Memory seed capture
6. Summary preview and targeted revision
7. Final write to role package
8. Immediate activation

### Initialization Outputs

The first initialization must produce:

- `AGENT.md`
- full `self-model/`
- `brain/index.md`
- `memory/USER.md`
- `memory/MEMORY.md`
- `projects/index.md`
- `role.json`

## Memory Design

The memory model is inspired by Hermes Agent's split between stable personality, user memory, and persistent summaries, while adapting it to a portable role package layout.

Reference materials:

- https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/
- https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files/
- https://hermes-agent.nousresearch.com/docs/user-guide/features/personality/

### Memory Layers

#### `memory/USER.md`

Stores stable preferences and long-term agreements such as:

- language preference
- response structure preference
- collaboration rules
- repeated workflow preferences

#### `memory/MEMORY.md`

Stores compressed, high-value persistent memory such as:

- stable facts worth carrying across sessions
- concise summaries of learned preferences
- memory topic index
- pointers to deeper files

#### `memory/episodes/`

Stores episodic or detailed records that are not always loaded:

- session-specific notes
- longer contextual records
- detailed evidence before summarization

### v1 Memory Operations

The first version should support:

- append new episodic memory
- summarize and promote high-value memory into `MEMORY.md`
- deduplicate repeated entries
- retrieve from summary first, then episodic files when needed
- keep always-loaded memory within a bounded size budget

### Memory Safety

Before promoting content into always-loaded files, the system should perform a basic prompt-injection and instruction-conflict scan, because these files directly affect future role behavior.

## Knowledge Design

`brain/` is the role's knowledge reserve.

### `brain/index.md`

This file is an index, not a knowledge dump. It should:

- summarize major knowledge domains
- link to topic files or external references
- help the skill decide what deeper material to load

### Topic Files

Detailed knowledge should live under `brain/topics/` or as referenced documents. The package must support both local files and curated links.

## Project Overlay Design

`projects/` lets one role adapt to different working contexts without changing the base identity.

Each project overlay may contain:

- `overlay.md`: project-specific role adjustments
- `context.md`: project facts and constraints
- `memory.md`: project-specific memory

Overlays adjust the base role but do not replace it.

## Command Surface

The runtime skill should support the following first-version commands:

- `/roleMe`
- `/roleMe <role-name>`
- `/roleMe list`
- `/roleMe current`
- `/roleMe optimize [role-name]`
- `/roleMe export [role-name]`
- `/roleMe doctor [role-name]`

### Scope Notes

- Delete is intentionally excluded from v1 to reduce accidental destructive actions
- `optimize` focuses on memory compression, index cleanup, and prompt budget hygiene
- `doctor` focuses on schema validation, missing files, and migration guidance

## Versioning and Compatibility

Three version concepts must remain separate:

- `skillVersion`: version of the `roleMe` skill itself
- `schemaVersion`: version of the role package contract
- `roleVersion`: version of a specific role's content

### `role.json`

Each role package must contain a machine-readable manifest similar to:

```json
{
  "roleName": "赵超",
  "schemaVersion": "1.0",
  "roleVersion": "0.1.0",
  "createdBySkillVersion": "0.1.0",
  "compatibleSkillRange": ">=0.1 <1.0",
  "createdAt": "2026-04-13T00:00:00+08:00",
  "updatedAt": "2026-04-13T00:00:00+08:00",
  "defaultLoadProfile": "standard"
}
```

### Compatibility Rules

- compatible schema versions should load directly
- older schema versions should be migrated by tooling when possible
- incompatible future schema versions should fail safely with guidance

## Repository Responsibilities

This repository is the source for the system, not the long-term store for user roles.

It should own:

- templates
- the skill source
- validation and migration scripts
- references and examples
- build outputs

It should not be the default storage location for personal role data.

## Skill Artifact Layout

The built artifact should be versioned and distributable, for example:

```text
dist/roleme-v0.1.0/
  SKILL.md
  agents/openai.yaml
  scripts/
  references/
  assets/templates/
```

Suggested first build scripts:

- `scripts/build_skill.py`
- `scripts/validate_role.py`
- `scripts/upgrade_role.py`

## Security and Portability

### Portability

- a copied role folder should be directly usable if `schemaVersion` is compatible
- the package should avoid machine-specific absolute paths in core files
- external links are allowed, but the role should remain usable without them

### Safety

- role loading should treat package files as trusted-by-user but still validate structure
- memory promotion should scan for instruction-conflicting content
- export should only include role-local data unless the user explicitly chooses extra assets

## Success Criteria

The design succeeds when:

- a missing `self` role can be initialized from conversation and used immediately
- a copied role package can be dropped into `~/.roleMe/` and loaded without manual edits
- activation keeps the role stable across the current conversation
- always-loaded files remain small and focused
- memory can grow without turning `AGENT.md` into a monolith
- the repository can build a versioned skill artifact and support future migrations

## Implementation Direction

Recommended implementation order:

1. Finalize role package schema and manifest
2. Implement the runtime loading and initialization flow
3. Implement file generation from templates
4. Implement memory optimize and doctor flows
5. Implement build, validate, and upgrade scripts
6. Add export and compatibility tests

## Open Decisions Resolved In This Spec

- Initialization is conversation-driven and should complete the first role definition in one pass
- The default unnamed command resolves to `self`
- Role data lives under `~/.roleMe/`, not this repository
- The first version supports progressive disclosure instead of full eager loading
- Memory uses summary plus episodic layers instead of one flat file
