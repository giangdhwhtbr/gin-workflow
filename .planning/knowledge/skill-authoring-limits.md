# Skill authoring limits: description budget, size caps, strict frontmatter

**Context**
Epics `gin-workflow-legacy-inventory`, `gin-workflow-sprint-retro`, and `gin-workflow-milestone-close` (2026-11-14 and 2026-11-15) each added skill text and ran into limits that tests enforce. A planned skill description failed only at test time because of its punctuation.

**Decision/Solution**
- The frontmatter of every `SKILL.md` must parse as strict YAML (`test_every_skill_frontmatter_is_strict_yaml`). A colon followed by a space inside the `description:` value breaks it; write the description without `: `.
- The sum of all frontmatter descriptions is capped by `test_descriptions_within_budget` in `tests/workflow_core/test_token_budget.py`. It was raised from 4,000 to 4,500 characters for `/milestone-close` (4,104 used after it). Every description is loaded into each session, so a raise is a deliberate choice recorded in the spec.
- `skills/roadmap/SKILL.md` is capped at 12,000 characters and had 4 left after the legacy inventory epic; new roadmap rules go into `skills/roadmap/references/` files (each capped at 4,000 by the same test file: `manager-view.md`, `milestone-plan.md`).
- Before planning a new skill, measure: `cd plugins/gin-workflow/src/scripts && python3 -c "from pathlib import Path; from workflow_core.budget import description_chars; print(description_chars(Path('..')))"`.

**Consequences**
- A plan that quotes exact skill text should check its description for `: ` and its length against the remaining budget.
- Large rule additions to a capped skill move text into references, which the reviewer must check for lost rules.

**References**
- `tests/workflow_core/test_token_budget.py` (`test_descriptions_within_budget`, `test_roadmap_skill_within_12000`); `plugins/gin-workflow/src/scripts/workflow_core/budget.py`
- `plugins/gin-workflow/src/skills/milestone-close/SKILL.md`, `plugins/gin-workflow/src/skills/roadmap/references/`
- Beads: `gin-workflow-milestone-close.1` (the `[gin learn]` comment on `gin-workflow-milestone-close`), `gin-workflow-legacy-inventory.2`, `gin-workflow-4p75`

**Scope**
Writing or changing plugin skills, their descriptions, and their references.
