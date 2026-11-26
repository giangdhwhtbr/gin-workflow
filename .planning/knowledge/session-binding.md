# Session binding: which Claude Code session worked on which workflow

**Context**
Epic `gin-workflow-cost-binding` (2026-11-26, spec `.planning/specs/2026-11-26-cost-binding-design.md`), the first epic of the roadmap on the cost and friction of the common path. gin 3.4.0 removed usage tracking because it attributed transcript usage to a bead by time span, took about a minute per epic, and missed most of the work ([retire-ai-usage](retire-ai-usage.md)). A cost view needs only the link between a session and a workflow: the transcripts already hold the usage of every request, the skill of every turn, and the type and model of every subagent. The PM decided on 2026-11-26 that reading transcripts and showing cost belong to gin-console.

**Decision/Solution**
- `workflow_core/session_binding.py` holds the rules: `binding_event`, `bind_session`, `bound_sessions`.
- The session id comes from `CLAUDE_CODE_SESSION_ID`, which Claude Code sets in the subprocesses of its Bash and PowerShell tools and of its hooks. Checked on 2026-11-26 with Claude Code 2.1.322: it equals the transcript file name, a subagent's shell sees the parent's id, and the id changes after `/clear`. No skill text changes.
- `gin state`, `gin record`, `gin unblock`, and `gin routes dispatch` append one `session.bound` event per session and workflow (`workflow_id` the command's workflow, `payload` `{"session_id"}`, `idempotency_key` `session:<id>`). The event id is a hash of those fields, so the store's duplicate check makes a repeat a no-op.
- Nothing is bound for `default-workflow`, without the variable, or for a value outside `[A-Za-z0-9_.-]{1,128}`.
- The binding never changes a command's result: a store it cannot read or write prints `gin: session not bound: <cause>` on stderr. `gin state` binds only after it read the log, passes the events it read so an existing binding costs no lock, and never writes to a log it could not read.
- `gin record` binds after its transaction has released the store's lock, because the lock is not re-entrant.
- `gin state --format json` adds `sessions` (`session_id`, `bound_at`) for the requested workflow, oldest first.

**Consequences**
- `gin state` is no longer read-only: the first call of a session for a workflow rewrites `.agent-workflow/runtime/events.jsonl` once, as every append does.
- Every command run from a Claude Code session inherits the variable, the local pre-push hook included. Tests that read the last event of the log (`test_team_gates.py`, `test_hosts_gitea.py`, `test_hosts_codecommit.py`) failed there and not on CI. `tests/conftest.py` clears the variable for the whole pytest run; a test that needs it sets it with `mock.patch.dict`. A plain `python -m unittest` run does not load the conftest.
- A tool started inside a Claude Code session, such as a gin-console backend, binds that session to every epic it polls with `gin state --workflow-id`. Such a caller must drop the variable from the environment it gives `gin`.
- Bindings are local to a machine, like the transcripts, so a team's cost is per member.
- An older gin reads a log with the new event: the event schema accepts any non-empty type and readers select the types they know.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{session_binding,lifecycle_cli,routes}.py`, `tests/conftest.py`
- Tests: `tests/workflow_core/test_session_binding.py`, `tests/workflow_core/test_routes_cli.py`
- Docs: `docs/concepts/state-model.md` (Event store), `docs/reference/cli.md` (`gin state`)
- Spec and plan: `.planning/specs/2026-11-26-cost-binding-design.md`, `.planning/plans/2026-11-26-cost-binding.md`
- Beads: `gin-workflow-cost-binding`, `gin-workflow-cost-binding.1`

**Scope**
The event log, the four commands that bind a session, the `sessions` key of `gin state`, and how the test suite treats the session variable.
