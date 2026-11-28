# Fresh context per stage with a state card

Epic: gin-workflow-context-boundaries
Kind: capability
Points: 8 (one command reading four sources with a size cap, two hooks on two platforms, a session binding key, a handoff rule with two stage edits, one setup proposal, team host lines; larger than gin-workflow-upkeep = 5)
Status: draft for user review.

## Goal and scope

A stage starts in a small session and loses nothing, because the workflow state is shown again after every start, clear, resume, and compaction.

The main session holds 81% of prompt tokens at a median context of 293K and a peak of 967K (product brief, "Where the tokens go"). Running `/clear` between stages is a convention today (`docs/guides/claude-workflow.md`), and nothing restores the workflow state after it.

Platform check: Claude Code already re-injects the project CLAUDE.md, auto memory, and invoked skill bodies after compaction, and it adds a `SessionStart` hook's stdout to the context. It shows no workflow state of its own. Its `PreCompact` hook stdout becomes instructions for the compaction summary, and `autoCompactWindow` sets the compaction point. This epic writes the glue to those features.

In scope:
- `gin prime` prints a state card: workflow, stage, gates, spec and plan, ready tracks, open questions, review cycles used, the next command, and the Beads memories.
- A `SessionStart` hook prints the card on `startup`, `resume`, `clear`, and `compact`, on Linux, macOS, and Windows.
- A `PreCompact` hook tells the compaction summary what to keep.
- Each stage ends with one handoff line: clear, then the next command.
- `/gin:setup` proposes `autoCompactWindow: 200000`.
- In team mode the card shows the member, the claimed lane, and the pull requests waiting for approval.

Out of scope: the stage preflight and mode text (`gin-workflow-stage-brief`); moving to the next stage without a typed command (`gin-workflow-one-entry`); a status line or pane; hooks for the Codex, Copilot, Antigravity, and OpenCode builds.

Decisions made in discuss (2026-11-28):
- `gin prime` replaces `bd prime` at session start. The card carries the Beads memories, trimmed to fit the output cap, and one line that points to `bd prime --no-memories` for the Beads command reference. gin installs no Beads hook, and `bd setup claude` is not needed beside it. `bd prime` prints 13,961 characters in this repository (memories 8,246), above Claude Code's 10,000-character cap for hook output.
- A session that is not bound to a workflow gets the workflow bound most recently in the same folder (the git top level).
- In team mode the card asks the host for the waiting pull requests, within a time cap.
- The card is computed when asked, on a lean read path; it is not cached.

## Requirements

### `gin prime`

Usage: `gin prime [--workflow-id ID] [--hook] [--pre-compact]`.

1. In a folder without `.agent-workflow/config.yaml`, the command prints nothing and exits 0.
2. The workflow is the first that applies:
   1. `--workflow-id`.
   2. The workflow bound to the running session: the `session_id` of the hook input with `--hook`, else `CLAUDE_CODE_SESSION_ID`.
   3. The newest `session.bound` event whose `cwd` is this folder's git top level and whose workflow is not shipped.
   4. None: the card lists up to 5 open workflows, one line each, with their stage and next command. An open workflow has a gate event, is not shipped, and has an event in the last 14 days.

   A workflow is shipped when it has a `delivery.shipped` event or the epic of its `orchestration.ready` event is closed in Beads; an epic with tracks never gets the event, because closing it is what ships it (decided in plan, 2026-11-28).
3. The card names how the workflow was found (`flag`, `this session`, or `last session in this folder` with its time).
4. Lines, each left out when empty:
   - `Workflow:` the id, the epic, and the kind.
   - `Stage:` the stage the router returns, with remedies when it holds.
   - `Gates:` the five gates, the same values as `gin state`.
   - `Spec:` and `Plan:` the paths named by the workflow's gate events.
   - `Ready tracks:` the ready children of the epic, id and title.
   - `Open questions:` the `[gin question]` comments on the epic that have no matching `[gin answer]`, and the open `TQ-<n>` of the design doc.
   - `Review cycles:` cycles used against `max_cycles` per bead in review, only with `project.review_ledger: true`.
   - `Next:` the command that runs the next stage: `/gin:<stage> <workflow-id>`; for `execute`, `/gin:execute` with the ready track ids; for a held workflow, `/gin:workflow <workflow-id>`; no line for a complete workflow.
   - `Other open workflows:` the other open workflows, id and stage, on one line.
   - A `Beads memories` section, then the line `Beads command reference: bd prime --no-memories`.
5. Size: the whole output is at most 9,500 characters. Each list shows at most 10 items, then `+N more`. The memories fill the room the card leaves, then `+N more: bd memories`.
6. Speed: the Beads calls run concurrently, each with its own timeout. A call that fails or times out turns only its line into `unknown (<cause>)`. The knowledge and learn-comment warnings of `gin state` do not run.
7. With `--hook`, the command reads the hook input JSON from stdin and always exits 0. When the `.ginrc` version pin refuses, it prints nothing, because the `gin version --hook` hook already warns.
8. With `--pre-compact`, the command makes no Beads call and prints at most 1,500 characters: keep the workflow id and the stage; keep, word for word, the decisions and answers given in the chat that are not yet in the spec, the plan, or a bead; keep the question waiting for the user; keep the files being changed and why; drop tool output and file contents; the state card returns after compaction by itself.
9. The command is never a gate and writes nothing. In particular it never binds the session.

### Session binding

10. The `session.bound` payload gets a `cwd` key: the git top level of the folder the command ran in. The change only adds a key; older events without it are skipped by requirement 2.3.

### Hooks (Claude Code build only)

11. The Claude Code hooks file, written by `template_hooks_for_claude` in `install.sh` and `New-HooksFile` in `install.ps1`, gets:
    - A `SessionStart` entry with the matcher `startup|resume|clear|compact` and a 15-second timeout. On Linux and macOS: `if command -v gin >/dev/null 2>&1; then gin prime --hook; fi; exit 0`. On Windows, with `shell: powershell`: `if (Get-Command gin.cmd -ErrorAction SilentlyContinue) { gin.cmd prime --hook }; exit 0`.
    - A `PreCompact` entry that runs `gin prime --pre-compact` the same way.
12. The existing `gin version --hook` and safety hooks stay as they are. The other harness builds get no `SessionStart` or `PreCompact` hook.

### Handoff line

13. `references/stage-contract.md` gets a `## Handoff` rule: a stage ends its last message with one line, `Next: /clear, then <command>`, where `<command>` runs the next stage of the workflow and matches the card's `Next:`. A stage with nothing after it ends with `Next: /clear`.
14. The `Next commands:` lines of `orchestrate` and `ship` take the same form (`Next: /clear, then /gin:execute <id-1> <id-2>`). The `gin goal` text that orchestrate prints stays.
15. Every stage chain stays within its character cap; the caps and their tests do not change.

### Setup

16. When `~/.claude/settings.json` has no `autoCompactWindow`, `/gin:setup` proposes `200000` with one sentence of reason, and writes the key only after the user says yes. It never overwrites an existing value and never writes project settings.

### Docs

17. `docs/reference/cli.md` documents `gin prime`. `docs/guides/claude-workflow.md` and `claude-workflow.vi.md` describe the card, the handoff line, `autoCompactWindow`, and why `bd setup claude` is not needed. The `session.bound` docs name the `cwd` key. `docs/changelog.md` has the entry. The `bd prime` line of this repository's `AGENTS.md` says the card carries the Beads memories and points to `bd prime --no-memories`.

### Team mode

18. With `project.team.enabled`, the card adds:
    - `Member:` the login and roles of `team.require_member`.
    - `Claimed lane:` the lane and branch of the `gin team ready` rows assigned to the member.
    - `Pull requests waiting:` the rows of `gin team pending`, asked of the host within 4 seconds in total. On a timeout or a host failure the line reads `not checked (<cause>); run gin team pending`.
19. In team mode the gates come from the same shared-gate read as `gin state`, so the card and `gin state` agree.
20. Team behaviour is checked on the team's project before the release that carries it, and the ship note records the result.

## User Stories

### US-1: State after a clear
As a developer, I want the workflow state shown right after `/clear`, so that I start the next stage in a small session without retyping where I am.

Acceptance criteria:
- After `/clear` in the worktree of a workflow, the first context of the new session holds the card of that workflow.
- The card's `Next:` line names the command for the stage the router returns.
- In a folder whose last bound workflow is shipped, the card lists the open workflows instead.
- In a repository without gin configuration, the hook adds nothing to the context.

### US-2: State after compaction
As a developer, I want a compacted session to keep the workflow state and the decisions made in chat, so that a long stage goes on without losing what we agreed.

Acceptance criteria:
- `gin prime --pre-compact` prints at most 1,500 characters and tells the summary to keep chat-only decisions word for word.
- After a compaction the card of the session's workflow is in the context again.
- `gin prime --pre-compact` makes no Beads call.

### US-3: One handoff line per stage
As a developer, I want each stage to end with one line that says to clear and what to type next, so that I never guess the next command.

Acceptance criteria:
- The stage contract holds the `## Handoff` rule with the line `Next: /clear, then <command>`.
- `orchestrate` and `ship` end with that line form.
- Every stage chain stays within its character cap.

### US-4: Beads memories at session start
As a developer, I want the Beads memories in the card, so that I do not need `bd prime` at session start.

Acceptance criteria:
- The card shows the Beads memories, and the whole output stays at or under 9,500 characters.
- When the memories do not fit, the card ends them with `+N more: bd memories`.
- The card ends with `Beads command reference: bd prime --no-memories`.

### US-5: A smaller compaction point
As a developer, I want `/gin:setup` to offer `autoCompactWindow: 200000`, so that a session compacts before it grows to near 1M tokens.

Acceptance criteria:
- Setup proposes the value only when `~/.claude/settings.json` has no `autoCompactWindow`.
- The key is written only after a yes, and an existing value is never changed.

### US-6: Team state on the card
As a team member, I want the card to show who I am, my claimed lane, and the pull requests waiting for approval, so that I know what is mine after a clear.

Acceptance criteria:
- With team mode on, the card shows `Member:` and `Claimed lane:` from local data.
- The pull request line lists the waiting pull requests when the host answers within 4 seconds.
- When the host times out or fails, the line reads `not checked (<cause>); run gin team pending` and the card still prints.

### US-7: Hooks on Windows
As a developer on Windows, I want the same hooks to run in PowerShell, so that the card works without Git Bash.

Acceptance criteria:
- The Windows Claude Code hooks file runs `gin.cmd prime --hook` and `gin.cmd prime --pre-compact` with `shell: powershell`.
- Without `gin.cmd` on the PATH, both hooks exit 0 and print nothing.

## Errors and compatibility

- A failed or timed-out Beads call marks only its line `unknown (<cause>)`; the hook still exits 0.
- A missing `gin`, a version pin refusal, or a folder without gin configuration prints nothing.
- If Claude Code drops a hook that runs past its timeout, the session starts without a card; nothing else changes.
- `gin state --format json` keeps every key; gin-console reads nothing new.
- The `cwd` key on `session.bound` is additive; an older gin reads the event log unchanged.
- Team mode, workspaces, and the SDD layout keep working; no mode is frozen or removed.

## Testing

- `gin prime` unit tests:
  - the workflow order (flag, session, folder, list);
  - silence outside a gin project;
  - the `Next:` line for each stage, a held workflow, and a complete one;
  - the 9,500-character cap and `+N more`;
  - an `unknown` line for a failed or timed-out Beads call;
  - a team host timeout (mocked);
  - the `--pre-compact` text and its 1,500-character cap;
  - parsing the hook input.
- Binding tests: the `cwd` key is written; an event log with and without it reads back.
- Packaging and smoke tests on Linux and Windows assert the two new Claude Code hook entries and that the other builds have neither.
- The docs coverage test finds `## \`gin prime\`` in `docs/reference/cli.md`; the budget tests stay green.
- Measured and written in the ship note: the card size and the `gin prime --hook` time on this repository before and after (target: under 3 seconds), and the median main-session context from a transcript scan of the first sessions with the hooks against the 293K baseline. The phase gate of 120K belongs to the whole phase, not to this epic alone.

## Open Technical Questions
