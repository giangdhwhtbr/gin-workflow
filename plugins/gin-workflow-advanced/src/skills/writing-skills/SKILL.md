---
name: writing-skills
description: Meta-skill for authoring new SKILL.md files — frontmatter contract, prose style, when to split into a reference doc, naming, and composability.
---

# Writing Skills Skill

This is the meta-skill for authoring new `SKILL.md` files in the `gin-workflow` plugin. It defines the contract every skill follows so the catalog stays consistent, composable, and easy to browse.

## Frontmatter Contract

Every `SKILL.md` begins with YAML frontmatter containing exactly two required fields:

- `name` — the kebab-case skill identifier. Must match the skill's directory name (e.g. `writing-skills` lives at `<skill-name>/SKILL.md` within the installed plugin's `skills/` directory).
- `description` — a single sentence describing what the skill teaches. Used by the catalog/browser to summarize the skill; keep it specific and action-oriented ("How to …", "Guidance on …").

Do not add other frontmatter fields unless an existing skill already uses them and you are matching that convention. Keep the frontmatter minimal.

## Heading Convention

- First line after frontmatter is a single H1: `# <Name> Skill` (e.g. `# Writing Skills Skill`). The name is Title Case, matching the skill's display name.
- The H1 is followed by one short prose paragraph introducing what the skill is for.
- Use H2 (`##`) for major sections and H3 (`###`) only when a section genuinely needs sub-sections.

## Prose Style

Skills are guidance, not executable code. Match the voice of existing skills:

- Short, directive sentences. Imperative mood for rules ("Browse agents before assuming none fit.").
- Use numbered lists for ordered procedures (steps the reader follows in sequence).
- Use bullet lists for unordered guidance or enumerations.
- Lead with the rule, then explain the why only if it is not obvious. Avoid filler.
- Prefer concrete examples over abstraction ("Save plans in `.planning/plans/`", not "Save plans in an appropriate location").

Look at [bead-worker](file://../bead-worker/SKILL.md) and [writing-plans](file://../writing-plans/SKILL.md) as reference styles before authoring.

## When to Split Into a Reference Doc

Keep `SKILL.md` focused on guidance — the rules and workflow. Extract reference material into a sibling Markdown file when:

- The content is a schema or template that the skill references but is too large or structured to inline (the model for this is [plan-schema.md](file://../writing-plans/plan-schema.md) sitting beside [writing-plans](file://../writing-plans/SKILL.md)).
- The same structure is reused across multiple skills and centralizing it avoids drift.
- The reference would dominate the skill file and bury the guidance.

When you split, reference the sibling doc from the skill with a relative link (e.g. `See [plan-schema.md](file://plan-schema.md)`), and keep the `SKILL.md` as the entry point — the reference doc is supporting material, not a skill on its own.

Do not split for short examples or one-off lists; inlining keeps the skill self-contained and readable in one pass.

## Naming Conventions

- Skill directory and `name` frontmatter: kebab-case, verb or gerund form describing the activity (`writing-plans`, `agent-browser`, `using-claude-draft`, `bead-worker`).
- Filename inside the directory is always `SKILL.md` (uppercase). Reference docs use lowercase descriptive names (`plan-schema.md`).
- Name should describe what the skill does, not the feature it relates to — `writing-skills` (what) over `skills-meta` (topic).

## Composability

Skills should reference siblings rather than duplicate them. This keeps guidance DRY and the catalog browsable:

- Link to a sibling skill by relative path: `[writing-plans](file://../writing-plans/SKILL.md)`.
- Link to a reference doc beside the current skill: `[plan-schema.md](file://plan-schema.md)`.
- If you find yourself restating another skill's rules, stop and link to it instead.
- New skills should fit the existing catalog: check the plugin's `skills/` directory before naming a new skill to avoid overlapping scope with an existing one.

## Authoring Checklist

1. Frontmatter has `name` (matches directory) and `description` (one sentence).
2. First heading is `# <Name> Skill`.
3. One intro paragraph, then sections with directive prose.
4. Reference material too large to inline is split into a sibling doc and linked.
5. Sibling skills are cross-referenced by relative link rather than restated.
6. Directory and `name` match; filename is `SKILL.md`.
