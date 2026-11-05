# Codebase glossary: one `11-GLOSSARY.md` and the `glossary` rule pack

**Context**
Epic `gin-workflow-h27s` (2026-11-05) supports rebuilding a non-English legacy system (Korean first) as a new application in one monorepo, where every epic must use the same English term for a legacy concept. Tech-doc pages are not read by later stages, so a glossary needed both a producer and consumers.

**Decision/Solution**
- No separate `/glossary` skill: the tech-doc scouts already read the legacy code, so `/tech-doc` writes `11-GLOSSARY.md` (template `templates/codebase/11-GLOSSARY.md`).
- The glossary always lives at the root of the codebase docs folder, also for a subsystem run, so one file serves the whole monorepo.
- Merge rules live only in `skills/tech-doc/SKILL.md` text: a new row is `proposed`, only the user sets `confirmed`, a `confirmed` row's `English` never changes, and a different meaning goes to `Conflicts`. No code merges the file; tests assert the skill text.
- Consumers: the plugin pack `rules/glossary.md` (opt-in via `rules.packs: [glossary]`, proposed by setup through `detect.files_exist`), one sentence in `discuss` step 5, one clause in `plan` step 9.
- `glossary` is the only non-core pack with `applies_to: ["**/*"]`; `test_core_and_lean_apply_everywhere_and_others_are_scoped` exempts it by name, because it is opt-in and must cover every language of the new application.

**Consequences**
- A custom `artifacts.codebase` path is not detected by setup; the project adds the pack by hand.
- One Markdown file is the ceiling at a few thousand rows; beyond that, split by `Lang`. No YAML/CSV copy or i18n key generation yet.
- The discuss sentence sits at the end of step 5 after the `gin-team` sentence; it applies without team mode.

**References**
- `plugins/gin-workflow/src/skills/tech-doc/SKILL.md`, `plugins/gin-workflow/src/templates/codebase/11-GLOSSARY.md`
- `plugins/gin-workflow/src/rules/glossary.md`, `plugins/gin-workflow/src/skills/discuss/SKILL.md`, `plugins/gin-workflow/src/skills/plan/SKILL.md`
- `.planning/specs/2026-11-05-codebase-glossary-design.md`, `.planning/plans/2026-11-05-codebase-glossary.md`
- Beads: `gin-workflow-h27s`, `gin-workflow-h27s.1`, `gin-workflow-h27s.2`

**Scope**
The tech-doc set, the rule pack catalog, and the discuss and plan skills.
