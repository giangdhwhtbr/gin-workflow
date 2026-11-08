# Epic comments: ship and roadmap annotate affected epics, discuss and plan read them

Workflow: epic-comments
Status: draft for user review.

## Goal and scope

A roadmap epic is discussed and planned from its bead description. When a blocker epic ships, or the roadmap changes an epic that is already in progress, nothing tells the next `/discuss` or `/plan` of the affected epic, so its spec or plan can be built on stale assumptions.

Today:
- `/discuss <epic-id>` reads only `gin task show <id> --json` and the roadmap entry (`plugins/gin-workflow/src/skills/discuss/SKILL.md:14`). `bd show --json` returns `comment_count`, never the comment bodies.
- No skill reads or writes bead comments. Bead notes are the only annotation channel (`skills/learn/SKILL.md`, `skills/execute/SKILL.md`, `references/stage-contract.md`).
- `/ship` step 7 closes the parent epic without looking at the epics that depend on it (`skills/ship/SKILL.md:36`).
- `/roadmap` step 6 warns the PM about an `in_progress`, adopted, or closed epic whose roadmap entry changed, and leaves the bead untouched (`skills/roadmap/SKILL.md`).
- `gin task` forwards its arguments to `bd` unchanged (`scripts/workflow_core/tasks.py:204-211`), so `gin task comments <id> --json` and `gin task comment <id> "<text>"` already work with the Beads backend. The markdown backend has no comment command (`docs/reference/cli.md:334`).

This spec changes the skills only:
- `/ship` writes a comment on every open epic that depends on the epic it closes;
- `/roadmap` writes a comment on an epic it may not update but whose roadmap entry changed;
- `/discuss` and `/plan` read the epic's comments, summarise the description and the comments in time order into one current understanding, and ask the user to confirm that understanding before anything else.

Decisions confirmed with the user:
- The automatic comments come from `/ship` and `/roadmap`. `/discuss` and `/plan` do not write comments.
- Discuss and plan never ask which comments to keep. They read the description first, then the comments in time order, and present one summary for confirmation.
- Beads comments through the existing `gin task` passthrough. No new CLI command, no bead notes, no new config key.
- Automatic comments carry a fixed prefix (`[gin ship]`, `[gin roadmap]`) so a reader can tell them from comments people wrote.

Out of scope:
- Cross-repository `external:` dependencies (gin-harness epics): `bd` does not resolve them, so ship cannot find those dependents.
- Comment support for the markdown task backend.
- Whether discuss or plan covers technical content: another worktree changes that.
- A new gate, event, or notification for comments.

## Requirements

### R1. Discuss reads the epic's comments
- In `/discuss <epic-id>`, after `gin task show <id> --json`, run `gin task comments <id> --json`.
- With no comment, discuss continues as today.
- With comments, before any clarifying question: read the bead description, then each comment in `created_at` order (author, time, text); write a summary of the current understanding (goal, scope, what the comments changed, dependencies that shipped or changed); ask the user to confirm or correct that summary. This confirmation does not count against `project.max_questions`.
- The confirmed summary goes into the spec's `## Goal and scope`, followed by one line `Comments considered: <count>, latest <created_at of the newest comment>`. With no comment the line is omitted.
- Discuss never asks the user which comments to keep, drop, or resolve, and writes no comment.

### R2. Plan reads comments newer than the spec
- In `/plan` step 1, when the spec has an `Epic:` line, run `gin task comments <epic> --json` and take the comments with `created_at` later than the timestamp on the spec's `Comments considered:` line; with no such line, take all comments.
- With none, plan continues as today.
- With some, before anything else: summarise the description and these comments in time order the same way as R1 and ask the user whether to continue planning with that understanding or return to `/discuss <epic>`. Plan writes nothing to the spec about them and writes no comment.
- The addition to `skills/plan/SKILL.md` is at most two sentences: the plan chain has about 700 characters left under the 12,000-character budget (`tests/workflow_core/test_token_budget.py`).

### R3. Ship comments the dependent epics
- In `/ship` step 7, after the parent epic is closed: run `gin task show <epic> --json --include-dependents`, keep the dependents with `issue_type: epic` and status `open` or `in_progress` (`--include-dependents` also lists the epic's own tracks and bugs, which are skipped), and for each run:
  `gin task comment <dependent> "[gin ship] <epic-id> <epic title> shipped (merge <sha>). Spec: <design doc path>. Its outcome may change what this epic needs; the next /discuss <dependent> reads this comment."`
- `<sha>` is the merge commit from the handoff; `<design doc path>` is the closed epic's design doc (the legacy spec with `Epic: <id>`, or the SDD change folder), or `none` when there is none.
- The handoff lists the dependents that received a comment. A dependent with no open status, or a bead that is not an epic, receives nothing.
- A standalone bead (its own epic) is covered the same way: it may have dependents too.

### R4. Roadmap comments the epics it leaves unchanged
- In `/roadmap` step 6, for an epic that is `in_progress`, or `open` and adopted into a milestone, whose title, description, or `Depends on:` list differs from the roadmap file: keep the warning and the unchanged bead, and run:
  `gin task comment <epic> "[gin roadmap] <roadmap path> now says: <one line per difference: title, description, dependencies added or removed>. Bead left unchanged; the next /discuss <epic> reads this comment."`
- A closed epic receives no comment.
- A re-run is idempotent: skip the comment when the epic's most recent `[gin roadmap]` comment has the same body.
- Step 7 (the report) lists the epics that received a comment.

### R5. Backends and failures
- With the markdown task backend (`gin task` without Beads), `gin task comments` and `gin task comment` do not exist: discuss, plan, ship, and roadmap skip the comment steps and say so in one sentence.
- A failing `gin task comment` never blocks closing the epic (ship) or the Beads sync (roadmap): the skill reports which epics were commented and which failed, and continues.
- A failing `gin task comments` in discuss or plan stops the stage with the error, as a failing `gin task show` does today.

### R6. Documentation
- `docs/concepts/lifecycle.md` gets a short paragraph: which stages write epic comments, which read them, and that comments are advisory (no gate reads them).
- `docs/reference/cli.md` notes under `gin task` that `comments` and `comment` reach `bd` with the Beads backend and are absent on the markdown backend.

## User Stories

### US-1: Discussing an epic after its blocker shipped
As a developer running `/discuss <epic-id>`, I want the agent to read the epic's comments after its description and present one summary of what the epic now needs, so that my spec reflects what the blocker actually delivered.

Acceptance criteria:
- With comments on the epic, the first thing discuss asks is to confirm or correct the summary, before any clarifying question.
- The summary names the goal, the scope, what each comment changed, and the dependencies that shipped or changed, in time order.
- Discuss never asks which comments to keep.
- The written spec contains the confirmed summary and a `Comments considered:` line with the count and the newest timestamp.
- With no comment, discuss behaves exactly as before and writes no `Comments considered:` line.

### US-2: Planning an epic whose comments are newer than its spec
As a developer running `/plan` for an epic, I want the agent to show me the comments added since the spec was written, so that I can return to discuss before a plan is built on a stale spec.

Acceptance criteria:
- Only comments newer than the spec's `Comments considered:` timestamp (or all, when the line is absent) are summarised.
- Plan asks whether to continue or return to `/discuss <epic>`; it writes nothing to the spec or the bead.
- With no newer comment, plan behaves as before.

### US-3: Shipping an epic others depend on
As a developer running `/ship`, I want every open epic that depends on the shipped epic to receive a comment with the merge commit and the design doc path, so that whoever discusses those epics next sees what changed.

Acceptance criteria:
- After the parent epic closes, each open or in-progress dependent epic has a new `[gin ship]` comment naming the shipped epic, the merge commit, and the design doc path.
- Tracks, bugs, and closed beads among the dependents receive nothing.
- The handoff lists the commented epics, and a failed comment is reported without blocking the close.

### US-4: Re-running the roadmap after requirements changed
As a PM re-running `/roadmap`, I want an epic that is already in progress to receive a comment with the differences between the roadmap and its bead, so that the team sees the change without the bead being rewritten under them.

Acceptance criteria:
- An `in_progress` or adopted epic with a changed title, description, or dependency gets one `[gin roadmap]` comment listing each difference; its bead fields stay unchanged.
- Running `/roadmap` again with the same file adds no second identical comment.
- A closed epic gets no comment.
- The report lists the commented epics.

## Errors and compatibility

- The Beads backend is required for comments; the markdown backend skips the steps with one sentence (R5).
- `gin task comment` failures are reported and never block the stage; `gin task comments` failures stop discuss and plan (R5).
- Existing epics without comments see no change in discuss, plan, ship, or roadmap.
- gin-console reads `bd ... --json` per project; it never reads comments, so its parsing is unaffected.
- The stage chains stay within the 12,000-character budget: discuss has about 3,600 characters free, ship about 2,700, plan about 700.

## Testing

- `tests/workflow_core/test_epic_comments.py` (new), in the style of `test_role_aware_skills.py`: the discuss and plan skills name `gin task comments`, the `Comments considered:` line, and the time-ordered summary; the ship and roadmap skills name `gin task comment` with their prefixes, the `issue_type: epic` filter (ship), and the idempotent re-run (roadmap); every skill names the markdown-backend skip.
- `tests/workflow_core/test_token_budget.py` stays green for every stage.
- Manual check on the Beads backend: add a comment to an open epic, run `/discuss <epic>`, and confirm the summary is asked first and the spec gets the `Comments considered:` line.

## Open Technical Questions
