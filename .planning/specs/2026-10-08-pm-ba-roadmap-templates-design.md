# PM/BA roadmap, artifact templates, and brownfield onboarding

Status: draft for user review.

## Goal and scope

Give PMs and BAs first-class support in gin-workflow, so a brownfield team can go from a documented as-is system to a long-term plan and then into per-sprint delivery without manual Beads work:

1. A `roadmap` skill that reads the whole tech-doc set (or a product brief), proposes epics with dependencies, and after confirmation writes a roadmap file and creates the epics in Beads.
2. `/discuss <epic-id>` reuses a roadmap epic instead of creating one; sprints are Beads labels with `progress` and `report` filters.
3. Project-overridable templates for every PM/BA artifact (roadmap, epic, user story, legacy design spec).
4. A brownfield end-to-end walkthrough with example prompts per role.
5. An HTML onboarding presentation for teams starting a brownfield project.

Everything lives inside the `gin-workflow` plugin. No `gin-pm` plugin: PM/BA work has no checker CLI of its own yet (unlike `gin-qa`).

Non-goals: sprints as objects with dates or capacity; an `artifacts.roadmap` config key; schema validation of template fields; a CLI checker for user stories; CODEOWNERS generation for the roadmap file; changes to `docs/interactive/`.

## Requirements

### 1. `roadmap` skill (`plugins/gin-workflow/src/skills/roadmap/SKILL.md`)

Outside the lifecycle state machine (like `tech-doc` and `progress`); it records no gate.

**Preconditions.** `effective-config.yaml` exists in the main checkout. With `project.stage` `brownfield` or `legacy`, the tech-doc folder (`.planning/codebase/`, or `artifacts.codebase` with the SDD layout) must exist; otherwise stop and recommend `/tech-doc`. With `greenfield`, a product brief is required (a file path or text in chat).

**Roadmap file.** `.planning/roadmap.md` with the legacy layout, `docs/roadmap.md` with SDD. Built from `gin-workflow specs template roadmap.md`.

**Steps.**
1. Read every tech-doc file, including subsystem subfolders, plus living specs (or `.planning/specs/`), the existing roadmap file, and `bd list --label roadmap`. No subagent summarization: dependencies need cross-file reading. Verify load-bearing claims with `codegraph explore` when `.codegraph/` exists.
2. Ask the PM one question per message: business goals, milestones, team capacity, operational constraints (for example no downtime), exclusions.
3. Propose 2–3 epic-splitting strategies (for example by bounded context, by risk, by business value) with trade-offs and a recommendation.
4. Present the roadmap for edits and explicit confirmation. Each epic: title, `Epic: <planned id>`, `Goal:`, `Scope:`, `Out of scope:`, `Depends on:`, `Evidence:` (tech-doc file and section), `Risks:`. The dependency graph must be acyclic; the skill checks before presenting.
5. Write the file on branch `roadmap/<topic>` and commit.
   - Without a `team.approvals.roadmap` policy: continue to step 6 after the chat confirmation.
   - With a policy: push, ask approval to open the PR, and return `awaiting_roadmap_review`. A later run calls `gin-workflow team check <pr-url> --gate roadmap`; exit 0 continues to step 6, exit 1 shows the reasons and stops. Never worked around with other evidence.
6. Sync Beads per roadmap entry: missing → `bd create --id <id> --type epic --labels roadmap -d <epic.md rendering>`; existing → update title and description. Then add `bd dep add` edges from `Depends on:` and remove edges no longer listed.

**Epic IDs.** Chosen when the roadmap is written, so the file carries them before any Beads write and team mode needs a single PR. The exact `--id` format accepted by Beads (prefix, allowed characters) is verified as the first plan step.

**Re-run.** Compare the file with Beads and present only the differences. An epic labelled `roadmap` but absent from the file is reported and the PM is asked; the skill never closes or deletes an epic. An epic that is `in_progress` or closed gets a warning and its scope is not changed.

**Errors.** A failed `bd` call stops the sync and reports which entries were synced; a re-run continues (sync is idempotent).

### 2. Team-mode roadmap approval

```yaml
team:
  approvals:
    roadmap: [pm]   # optional; absent = chat confirmation only
```

- `schemas.py`: add `roadmap` (`_ROLES`) to `team.approvals.properties`; `additionalProperties` stays `false`.
- `team.py`: add `"roadmap"` to `GATES` so `team check --gate roadmap` accepts it. `gin-workflow record` keeps its own lifecycle-gate list, so `roadmap` never reaches `authorize_record`; it is not waivable.
- `team.py` `_is_artifact` / `resolve_artifact`: a `roadmap` branch accepting only the roadmap file path of the current layout. `check_approval` is reused unchanged: merged, same repository, changes the roadmap file, approved by a listed role who is not the author.
- The existing role check (`team.py:89`) already reports a `roadmap` role held by no member.
- `team-setup` asks who approves the roadmap (default: nobody).

### 3. `/discuss <epic-id>` and epic reuse

- `discuss`: given an epic id, `bd show <id>` and the matching roadmap entry are the starting context, and every `state`/`record` call uses `--workflow-id <epic-id>`. An id that does not exist, is not an epic, or is closed stops with an error. An epic still blocked by its dependencies gets a warning, not a stop. Without an id, behavior is unchanged.
- `gin-sdd` (discuss step 1): with an existing epic, skip `bd create --type epic` and run `specs new <slug> --epic <epic-id>`.
- Legacy layout: the spec header carries `Epic: <id>`.
- `orchestrate`: "reuse the epic as parent" becomes a general rule (today SDD only): when the workflow has an epic, tracks are `bd create --parent <epic>` and no new epic is created.
- `execute`: a bead labelled `roadmap` with no confirmed spec is refused as a standalone bead; recommend `/discuss <epic-id>`.

### 4. User stories

- The legacy design spec template and the SDD `proposal.md` template gain `## User Stories`. Each story comes from `user-story.md`: `US-<n>`, As a / I want / So that, acceptance criteria, and with SDD a `REQ: REQ-…` line.
- `discuss` self-review checks that every story points to at least one REQ (SDD) and every `ADDED` REQ has a story or a stated technical reason.

### 5. Sprints

- A sprint is the Beads label `sprint:<name>` on epics (`bd update <epic> --add-label sprint:<name>`). The `roadmap` skill applies it when asked.
- `progress`: a sprint scope listing `bd list --label sprint:<name>` and their tracks, grouped by epic.
- `gin-workflow usage report --sprint <name>`: in the same mutually exclusive group as `--bead`, `--epic`, `--since`; aggregates the labelled epics and their tracks. `report` skill documents it.

### 6. Templates

New defaults in `plugins/gin-workflow/src/templates/`, rendered with the existing `{{...}}` placeholders and writing rules in `<!-- ... -->` comments:

| File | Used by | Content |
|---|---|---|
| `roadmap.md` | `roadmap` | goals, constraints, chosen strategy, Mermaid epic order, one block per epic with the fields of Requirement 1 step 4 |
| `epic.md` | `roadmap` (bead description) | condensed roadmap entry plus the roadmap file path |
| `user-story.md` | `discuss` | the story block of Requirement 4 |
| `design-spec.md` | `discuss` (legacy layout) | goal and scope, requirements, user stories, errors and compatibility, testing |

- Projects override any of them with `.agent-workflow/templates/<name>`; skills fetch them through `gin-workflow specs template <name>`, which already honors overrides for every name and layout (`specs.py:94`, `specs_cli.py:57`).
- `stage-contract.md` gains one rule: a skill never invents an artifact structure when a template exists.
- QA keeps the `gin-qa` guidelines file; the `gin-qa` case format is unchanged.

### 7. Documentation

- New `docs/starters/brownfield-walkthrough.md`: one scenario (modernizing a legacy ordering system; PM, BA, Tech Lead, Dev, QE). Each stage gives the role, a copyable prompt, expected output, the gate or PR involved, and common mistakes: setup → `/tech-doc` → `/roadmap` → sprint label → `/discuss <epic-id>` → `/plan` → `/orchestrate` → `/gin-qa:cases` → `/execute` → `/gin-qa:e2e` → `/verify` → `/ship` → `/progress` and `/report --sprint`. Ends with a short solo variant and a template-customization section (override `user-story.md` example).
- `team-roles.md`: PM row in the matrix and a PM workflow section. `brownfield-modernize.md` and `greenfield.md` link to the walkthrough and `/roadmap`. `docs/reference/config.md` and `docs/guides/team.md`: `approvals.roadmap`. `docs/reference/cli.md`: `usage report --sprint`.

### 8. Onboarding presentation

Built last, from the walkthrough and the verified features, so no slide describes behavior that does not exist.

- Self-contained HTML deck at `docs/presentations/brownfield-onboarding.html` (no network dependencies), also published as a private claude.ai artifact for sharing.
- Audience: a team starting a brownfield project. Solo mode is not covered.
- Slides: overview and one-page lifecycle diagram; advantages, each backed by a real feature (evidence-backed gates, role-based PR approvals, story → REQ → test case → test traceability, isolated worktrees, independent review, sprint cost and quality reports, overridable templates); team map (who works at which stage, who approves which gate); one or two slides per role (PM, BA, Tech Lead, Dev, QE) with commands, example prompts, outputs, and owned gates; output customization (templates for PM/BA, `gin-qa` guidelines for QE, before/after examples); day-one checklist.
- Diagrams are simple inline SVG that read in light and dark themes. Slide language is asked when the deck is built.

## Errors and compatibility

- Repositories without a roadmap behave exactly as today; `/discuss` without an id is unchanged.
- `team.approvals` without `roadmap` validates as before; existing gates and ledgers are unaffected.
- New templates are additive; existing project overrides keep winning.

## Testing

- Unit (`tests/workflow_core/`): schema accepts `approvals.roadmap` and rejects a role no member holds; `_is_artifact`/`resolve_artifact` for a PR changing the roadmap, not changing it, and changing several candidates; `check_approval` for `roadmap` with a missing approval, an author self-approval, and an unmerged PR; `usage report --sprint` with matching epics, no match, and an epic with several tracks; `specs template` returns each new template and a project override.
- `tests/install_smoke_test.sh`: `skills/roadmap/SKILL.md` exists in every dist, and asserts the key rules (reads every tech-doc file, never deletes epics, the `execute` refusal of unspecced roadmap epics).
- Manual: `bd create --id` format check before the skill is written; one dry run of the walkthrough scenario in a scratch repository before the presentation is built.
