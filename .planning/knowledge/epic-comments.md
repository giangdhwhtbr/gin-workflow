# Epic comments: ship and roadmap annotate affected epics, discuss and plan read them

**Context**
Epic `gin-workflow-sjow` (2026-11-07). A roadmap epic was discussed and planned from its bead description alone. When a blocker epic shipped, or a roadmap re-run changed an epic already in progress, nothing told the next `/discuss` or `/plan` of the affected epic. `bd show --json` returns only `comment_count`; no skill read or wrote bead comments, and bead notes were the only annotation channel.

**Decision/Solution**
- Beads comments are the cross-epic channel, through the existing `gin task` passthrough to `bd`: `gin task comments <id> --json` (list of `{id, issue_id, author, text, created_at}`) and `gin task comment <id> "<text>"`. No new CLI command, no bead notes, no config key, no gate or event. Automatic comments carry the prefix `[gin ship]` or `[gin roadmap]`.
- `ship` step 7, after the parent epic closes (also for a standalone bead): `gin task show <epic> --json --include-dependents`, keep dependents with `issue_type: epic` and status `open` or `in_progress` (the list also holds the epic's own tracks and bugs), and comment each with the merge commit and the design doc. The design doc is the `evidence` of the epic's latest `requirement.confirmed` event in `.agent-workflow/runtime/events.jsonl` of the main checkout (`gin state` does not expose it). The handoff lists the commented epics.
- `/roadmap` step 6: an `in_progress` or adopted `open` epic whose title, description, or `Depends on:` differs from the file keeps the warning and the unchanged bead and gets a `[gin roadmap]` comment listing the differences, skipped when its most recent `[gin roadmap]` comment has the same text; closed epics get none.
- `/discuss <epic-id>` reads the description, then the comments in `created_at` order, summarises the current understanding, and asks the user to confirm it before any clarifying question (not counted against `project.max_questions`); it never asks which comments to keep. The spec ends `## Goal and scope` with the summary and `Comments considered: <count>, latest <created_at>` when the epic had comments.
- `plan` step 1, with an `Epic:` line, summarises the comments newer than that timestamp (all without the line) right after the gate check and before the open technical questions, and asks whether to continue or return to discuss.
- Markdown task backend: no comment commands; every stage skips in one sentence. A failed `gin task comment` never blocks the close or the sync; a failed `gin task comments` stops discuss or plan like a failed `gin task show`.

**Consequences**
- Stage chains after the change: discuss 9,064, plan 11,731, ship 10,113 of 12,000 characters; roadmap is outside the chains. The next plan-skill addition has about 270 characters left.
- `tests/workflow_core/test_epic_comments.py` pins the skill text by substrings on single lines; a rewording of those lines must keep the needles.
- Cross-repository `external:` dependencies (gin-harness) get no comment: `bd` does not resolve them.
- Not run: a real `/discuss` on an epic with comments, and a real `/ship` with open dependents.
- Since `gin-workflow-ba-workspace`, execute, progress, and ship also use `[gin question]`, `[gin answer]`, and `[gin accept]` comments; see [ba-workspace](ba-workspace.md).

**References**
- `plugins/gin-workflow/src/skills/{discuss,plan,ship,roadmap}/SKILL.md`; `tests/workflow_core/test_epic_comments.py`
- Docs: `docs/concepts/lifecycle.md` (paragraph after `/roadmap`), `docs/reference/cli.md` (`gin task`)
- `.planning/specs/2026-11-07-epic-comments-design.md`, `.planning/plans/2026-11-07-epic-comments.md`
- Commits `ef01bed`, `6a88cce`, `9eb796e`, `76260bd`, `d42841b`, `f988e84`, `b83434a`
- Beads: `gin-workflow-sjow`, `gin-workflow-sjow.1` to `.5`
- Related: [role-aware-discuss](role-aware-discuss.md), [review-ledger-cycle-limit](review-ledger-cycle-limit.md)

**Scope**
Roadmap epics in `/discuss`, `/plan`, `/ship`, and `/roadmap` with the Beads task backend.
