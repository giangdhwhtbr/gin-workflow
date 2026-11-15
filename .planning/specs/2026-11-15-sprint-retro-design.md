# Sprint retro before the milestone close

Epic: gin-workflow-sprint-retro
Kind: capability
Status: draft for user review.

## Goal and scope

Before a milestone closes, each member records what went well, what slowed the work, and what to change. The milestone close (`gin-workflow-milestone-close`) later reads these answers, combines them with the results of the milestone, and turns them into actions. This epic only collects the answers.

In scope:

- A new skill `/gin:retro` that shows the member their part of the milestone, asks three questions, and records the answers as one comment on the milestone bead.
- Documentation of the skill in `docs/reference/skills.md` and `docs/reference/skills.vi.md`.

Out of scope:

- Summaries, actions, process changes, and reminders to members who have not run a retro (`gin-workflow-milestone-close`).
- Scores or ratings; a later change can add them without breaking existing comments.
- Anonymous answers.
- A `gin` CLI command or a Beads field for retros.
- Showing retros in gin-console.

Assumptions:

- The answers carry the member's name: Beads records the author of every comment, and the close needs to know who answered.
- A member may run the retro again; the newest `[gin retro]` comment of that member counts.
- The epic's acceptance line written on 2026-11-14 ("the next milestone planning shows a summary") predates the decision that the close reads the retros; this spec replaces it.

## Requirements

### Command and milestone

- `/gin:retro [--milestone <id>]`. Without an id, the skill uses the only milestone whose `status` is `active` in `gin milestone list --json`; with none or several, it lists the open milestones and asks which one.
- `gin milestone show <id> --json` must succeed. A closed milestone is refused with a message that its close already read the retros.
- The milestone needs the Beads task backend (milestones need `providers.task_tracking: beads`); with another backend the skill stops and says so.

### Member

- With `project.team.enabled`, the member is `project.team.me` from `gin state --format json`. When it is null (the git user is not a member), the skill stops and names the git email it found.
- Without team mode, the member is the git user name, and one retro covers the project.

### What the member sees first

- The epics of the milestone from `gin milestone show <id> --json`, each with `status`, `estimate_days`, and the count of its `open_bugs` warning, plus the working days (Monday to Friday) from the epic's `started_at` to its `closed_at`, or to today when open, read with `gin task show <epic> --json`; an epic not started shows `not started`.
- In team mode, only the epics with a track assigned to the member (`gin task list --parent <epic> --all --json`, `assignee` equal to the member's email), plus a count of the other epics. Without team mode, every epic.
- The view helps the member remember; it is not written into the comment.

### Questions

- Three questions, one per message, in this order: what went well; what slowed the work; what to change in the next milestone.
- The member may skip a question; a skipped answer is written as `-`.
- The skill asks no other question and does not suggest answers.

### Record

- Before writing, the skill shows the exact comment and writes it only after the member confirms; the member may edit the text first.
- The comment, written with `gin task comment <milestone-id> "<text>"`:

  ```
  [gin retro] <milestone-id> <member>
  Went well: <answer>
  Slowed us: <answer>
  Change next: <answer>
  ```

  `<member>` is the member's git email in team mode, else the git user name. Each answer stays on its line; line breaks inside an answer are replaced by `; `.
- In team mode, after the comment the skill runs `gin team sync` so other members see it.
- A failed `gin task comment` is reported with its error, and the skill shows the comment text so the member can retry; nothing else is written.

## User Stories

### US-1: Record my retro
As a member at the end of a milestone, I want to answer three retro questions in one guided run, so that my view is recorded where the milestone close will read it.

Acceptance criteria:
- `/gin:retro` with one active milestone asks the three questions in order, one per message.
- After the member confirms, the milestone bead has a new comment whose first line is `[gin retro] <milestone-id> <member>` followed by the `Went well:`, `Slowed us:`, and `Change next:` lines.
- A skipped question appears as `-` on its line.
- Nothing is written when the member does not confirm.

### US-2: See my part of the milestone first
As a member, I want to see my epics of the milestone with their estimates and actual days before answering, so that my answers rest on what happened.

Acceptance criteria:
- Before the first question, the skill lists the member's epics of the milestone with status, estimate, days taken, and open bugs.
- In team mode the list holds only epics with a track assigned to the member, and names how many other epics the milestone has.
- The listed numbers do not appear in the comment.

### US-3: Only open milestones and known members
As a team lead, I want retros only on open milestones and only from team members, so that the close reads answers that belong to the milestone and the team.

Acceptance criteria:
- `/gin:retro --milestone <id>` on a closed milestone writes nothing and says the close already read the retros.
- In team mode, a git user who is not a member gets a message naming the git email, and nothing is written.
- With no active milestone or several, the skill lists the open milestones and asks which one.

### US-4: Run it again
As a member, I want to run the retro again when I change my mind, so that the close reads my latest view.

Acceptance criteria:
- A second run adds a second `[gin retro]` comment for the same member; the skill states that the newest one counts.

## Errors and compatibility

- Comments are free text in Beads; the fixed first line and the three labels are the contract the milestone close parses. The labels are English and never translated, whatever language the answers use.
- Existing milestones, beads, and skills do not change. gin-console ignores the comments until `gin-console-workflow-catchup` decides otherwise.
- With the markdown task backend there are no milestones and no comments; the skill stops with one sentence.

## Testing

- A skill test reads `plugins/gin-workflow/src/skills/retro/SKILL.md` and asserts: the `[gin retro] <milestone-id> <member>` first line and the `Went well:`, `Slowed us:`, `Change next:` labels; the refusal of a closed milestone; the confirmation before writing; `gin team sync` after the comment in team mode; the active-milestone default; and that the skill names no concrete model.
- The packaging test lists `skills/retro/SKILL.md` in every harness build.
- The docs tests pass with the new row in `docs/reference/skills.md` and `docs/reference/skills.vi.md`.
- The token budget tests pass.

## Open Technical Questions
