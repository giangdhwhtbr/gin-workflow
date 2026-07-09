# Plan: Superpowers Extension for Gin Workflow Writing Plans

## Objective
Make `gin-workflow:writing-plans` explicitly extend `superpowers:writing-plans` while preserving Gin Workflow's Beads-backed plan location, schema, and model guidance requirements.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: The Gin Workflow planning skill currently duplicates a smaller planning contract instead of explicitly reusing the more complete Superpowers planning skill declaration.
- Success criteria: `gin-workflow:writing-plans` names `superpowers:writing-plans` as its base skill, defines Gin-specific override rules, and remains installable through the existing smoke test.
- Constraints: Plugin skills cannot inherit behavior automatically from another plugin; delegation must be documented inside `SKILL.md`. Gin Workflow still owns `.planning/plans/`, `plan-schema.md`, Beads-oriented track structure, and model-class metadata.
- Non-goals: Rewriting every Gin Workflow skill in this task, changing the plugin packaging system, or changing Superpowers source files.

## Approach Options
### Option 1: Copy Superpowers Text Into Gin Workflow
- Summary: Replace Gin's planning skill with a mostly copied Superpowers declaration plus Gin-specific additions.
- Pros: Self-contained and visible in one file.
- Cons: Duplicates upstream text, drifts quickly, and obscures which parts are Gin-specific.

### Option 2: Explicit Base Skill Plus Gin Overlay
- Summary: Add a `Base Skill` section instructing agents to use `superpowers:writing-plans` first when available, then apply Gin-specific overrides.
- Pros: Minimal, clear extension model; avoids duplicating upstream; preserves Gin-specific plan schema and Beads workflow.
- Cons: Depends on skill-aware agents honoring the explicit delegation instruction.

### Option 3: Build Manifest-Level Skill Inheritance
- Summary: Extend plugin metadata or install tooling so Gin skills can declare inherited skills structurally.
- Pros: Could generalize across all overlapping skills.
- Cons: Larger design change, likely unsupported by current Codex/Claude/Antigravity plugin formats, and unnecessary for this immediate behavior.

### Recommended Approach
- Selected option: Option 2.
- Reasoning: It is the smallest accurate change that makes Gin Workflow an extension of Superpowers for planning without pretending the plugin runtime supports automatic inheritance.

## Scope
- In scope: Update `plugins/gin-workflow/src/skills/writing-plans/SKILL.md` and the smoke test assertion for the generated skill.
- Out of scope: Repository-wide skill inheritance, generated `dist/` edits by hand, commits, or push.

## Tasks
### Track 1: Update Planning Skill Declaration
- **Dependencies**: none
- **Files**: `plugins/gin-workflow/src/skills/writing-plans/SKILL.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**: The skill says it extends `superpowers:writing-plans`, instructs agents to use the Superpowers contract first when available, and documents Gin-specific overrides.
- **Estimated complexity**: low

### Track 2: Update Verification Coverage
- **Dependencies**: Track 1
- **Files**: `tests/install_smoke_test.sh`
- **Model class**: `standard_impl`
- **Acceptance criteria**: The smoke test verifies the built planning skill includes the explicit Superpowers delegation text.
- **Estimated complexity**: low

## Integration
- **Branch**: current workspace branch
- **Merge strategy**: sequential

## Validation
- [ ] `bash tests/install_smoke_test.sh`
- [ ] `git status`
- [ ] Confirm Beads task is closed only after validation and handoff evidence are available.

## Notes
- Plugin skills do not inherit Superpowers behavior automatically. The source skill must explicitly instruct delegation.
- Broader conversion of other overlapping skills can be filed separately after the writing-plans pattern is accepted.
