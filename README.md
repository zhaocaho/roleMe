# roleMe

`roleMe` is a portable role-bundle skill for agent workflows.

It helps an agent initialize, switch, inspect, optimize, export, and diagnose role bundles through `/roleMe`.

## Install

Install from GitHub with the Skills CLI:

```bash
npx skills add https://github.com/<owner>/roleme --skill roleme
```

Replace `<owner>` with your GitHub user or organization name.

## Published Skill

The publishable skill package lives at:

```text
skills/roleme/
```

Key files:

- `skills/roleme/SKILL.md`
- `skills/roleme/agents/openai.yaml`
- `skills/roleme/references/usage.md`

## Development

Source content is maintained in:

- `skill/`
- `tools/`
- `templates/`

Publish the current skill package into `skills/roleme/` with:

```bash
python -c "from scripts.build_skill import publish_skill; print(publish_skill())"
```

Run tests with:

```bash
python -m pytest -q
```
