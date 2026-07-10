# Plan: Mapper-Style Documentation Workflow

## Objective
Make Gin Workflow produce and consume durable mapper-style documentation artifacts, with technical documentation written as a concrete split file set instead of an underspecified combined document.

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
- Problem statement: Current technical documentation guidance permits either one combined document or loosely named split documents, which makes downstream planning and research less predictable.
- Success criteria: `technical-documentation` defines a canonical split documentation structure, `/tech-doc` defaults to it, researcher and reviewer prompts align with durable evidence artifacts, and the codebase mapper contract points downstream agents at the same structure.
- Constraints: Preserve Beads as execution state owner; keep `.planning/*` artifacts as planning evidence, not runtime status; do not commit or push.
- Non-goals: Implement a new CLI command, generate documentation for this repository now, or change installed plugin packaging.

## Approach Options
### Option 1: Minimal Technical Documentation Update
- Summary: Update only `technical-documentation` and `/tech-doc`.
- Pros: Smallest change.
- Cons: Other agents still lack a shared artifact contract.

### Option 2: Shared Artifact Contract Across Agents
- Summary: Update `technical-documentation`, `/tech-doc`, `codebase-mapper`, `agent-researcher`, and `code-reviewer` to use the mapper-style context layer.
- Pros: Aligns planning, research, documentation, and review around the same evidence files.
- Cons: More prompt surface to keep consistent.

### Option 3: Full Command Pipeline Rewrite
- Summary: Add new command behavior for map/research/plan/review orchestration.
- Pros: Strongest automation.
- Cons: Too much blast radius for the current request.

### Recommended Approach
- Selected option: Option 2.
- Reasoning: It implements the requested documentation structure and the recommended durable context layer without replacing the existing Beads-first lifecycle.

## Scope
- In scope: Prompt/documentation changes under `plugins/gin-workflow/src/skills`, `plugins/gin-workflow/src/commands`, and `plugins/gin-workflow/src/agents`.
- Out of scope: Runtime command implementation, generated docs, commits, pushes, and package release steps.

## Tasks
### Track 1: Canonical Split Documentation Structure
- **Dependencies**: none
- **Files**:
  - `plugins/gin-workflow/src/skills/technical-documentation/SKILL.md`
  - `plugins/gin-workflow/src/commands/tech-doc.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**: Technical documentation defaults to `.planning/codebase/` split files based on `draft-codebase-mapper.md`; combined docs are explicitly exceptional.
- **Estimated complexity**: low

### Track 2: Agent Artifact Contract Alignment
- **Dependencies**: Track 1
- **Files**:
  - `plugins/gin-workflow/src/agents/codebase-mapper.md`
  - `plugins/gin-workflow/src/agents/agent-researcher.md`
  - `plugins/gin-workflow/src/agents/code-reviewer.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**: Mapper, researcher, and reviewer prompts describe how `.planning/codebase/` and `.planning/research/` artifacts feed planning and review.
- **Estimated complexity**: medium

## Integration
- **Branch**: current workspace branch
- **Merge strategy**: sequential

## Validation
- [ ] Review modified Markdown for internal consistency.
- [ ] Run `git diff --check`.
- [ ] Run `git status`.

## Notes
- Beads remains the durable execution state.
- `.planning/codebase/` and `.planning/research/` are durable evidence inputs, not task status.
