# State card: `gin prime` and the Claude Code session hooks

**Context**
Epic `gin-workflow-context-boundaries` (2026-11-28, spec `.planning/specs/2026-11-28-context-boundaries-design.md`). The main session held 81% of prompt tokens at a median context of 293K. `/clear` between stages was only a convention, and nothing showed the workflow state again after a clear, a resume, or a compaction. Claude Code adds a `SessionStart` hook's stdout to the context (capped at 10,000 characters), turns `PreCompact` stdout into instructions for the summary, and sets the compaction point with `autoCompactWindow`.

**Decision/Solution**
- `workflow_core/prime.py` prints the card: workflow, stage, gates, spec and plan, ready tracks, open questions, review cycles, `Next:`, other open workflows, then the Beads memories and `Beads command reference: bd prime --no-memories`. `gin prime` replaces `bd prime` at session start; gin installs no Beads hook.
- The workflow is the first of: `--workflow-id`; the workflow bound to the hook's `session_id` (else `CLAUDE_CODE_SESSION_ID`); the newest `session.bound` whose `cwd` is this git top level and that is not shipped; else up to 5 open workflows. Shipped means a `delivery.shipped` event or the epic of `orchestration.ready` closed in Beads.
- Caps: `CARD_CAP` 9,500 characters, `PRE_COMPACT_CAP` 1,500, 10 items per list then `+N more`; memories fill the room left, then `+N more: bd memories`.
- Speed: the Beads calls run one after another on one daemon thread (`bounded`), in priority order (`state`, `ready`, `shipped`, `comments`, `cycles`, team member and lane, `memories`), within `ROUND_TIMEOUT` 9 s; a call that fails or runs out marks only its line `unknown (<cause>)`. The shipped check before the round has `CALL_TIMEOUT` 4 s; the team host call (`gin team pending`) runs beside the round with `TEAM_TIMEOUT` 4 s. The hook timeout is 15 s.
- `gin prime` is never a gate, writes nothing, and never binds the session. `--hook` reads the hook input on stdin, always exits 0, and prints nothing outside a gin project or when the `.ginrc` pin refuses. `--pre-compact` makes no Beads call.
- `install.sh` (`template_hooks_for_claude`) and `install.ps1` (`New-HooksFile`) add a `SessionStart` entry (matcher `startup|resume|clear|compact`) and a `PreCompact` entry, guarded by `command -v gin` / `Get-Command gin.cmd`; Windows uses `shell: powershell`. Other harness builds get neither.
- `references/stage-contract.md` `## Handoff`: a stage ends with `Next: /clear, then <command>`, matching the card's `Next:`. `/gin:setup` proposes `autoCompactWindow: 200000` in `~/.claude/settings.json` only when the key is absent, and writes it only on a yes.

**Consequences**
- The machine must run `install.sh` / `install.ps1` again to get the hooks; a `bd setup claude` hook is redundant beside them.
- Concurrent Beads calls are slower than calls in a row (see [beads-call-costs](beads-call-costs.md)), so new card lines join the one round, most important first, instead of starting threads.
- `gin state --format json` is unchanged; gin-console reads nothing new.
- Team behaviour of the card is checked on the team's project before the release that carries it.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{prime,session_binding,lifecycle_cli,cli}.py`, `install.sh`, `install.ps1`
- `plugins/gin-workflow/src/references/stage-contract.md`, `plugins/gin-workflow/src/skills/{setup,orchestrate,ship}/SKILL.md`
- Tests: `tests/workflow_core/test_prime.py`, `test_prime_team.py`, `test_harness_packaging.py`, `test_stage_handoff.py`, `tests/install_smoke_test.{sh,ps1}`
- Docs: `docs/reference/cli.md` (`gin prime`), `docs/guides/claude-workflow.md` and `.vi.md`
- Plan: `.planning/plans/2026-11-28-context-boundaries.md`; Beads: `gin-workflow-context-boundaries.1` to `.7`

**Scope**
The Claude Code build of gin-workflow: session start, clear, resume, and compaction, and the last line of every stage.
