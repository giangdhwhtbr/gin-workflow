# Epic kinds: capability, technical, parity

**Context**
Epic `gin-workflow-3nwf` (workflow `epic-kinds`, 2026-11-12). In team mode, purely technical epics went through the business spec flow (user stories, use cases, activity diagrams) and needed BA and PM approval, so a slow BA slowed every epic. `team.approvals.requirement_confirmed` was one policy for the whole project, and spec lint required user stories and a spec delta for every epic.

**Decision/Solution**
- Kinds are `capability` (default), `technical`, `parity` (`workflow_core/epic_kind.py` `KINDS`, `DEFAULT`). No kind anywhere means `capability`, so existing epics, specs, and configs behave as before.
- The source of the kind is the epic bead's `kind:<kind>` label; the spec repeats it as a `Kind:` line (legacy design spec, or the SDD `01-proposal.md`). `/gin:roadmap` writes `Kind:` in each entry and the label on create; it swaps the label for an existing epic unless the epic is `in_progress` or adopted, which gets a `[gin roadmap]` comment instead.
- Lint per kind (`specs.py`): `technical` needs no user stories; `gin specs template technical-design.md` gives Goal and scope, Approach, Risks and rollback, Testing, Open Technical Questions. An SDD `technical` change may have an empty or missing `02-spec-delta.md` (`delta_blocks` returns `([], [])`); trace and archive succeed with nothing to merge. `parity` needs `Parity with:` naming backticked asset folders that exist, are `Kind: legacy`, and are confirmed (`parity_errors`).
- `requirement_confirmed` may be a map `{capability, technical, parity}` with `capability` required (schema `_KIND_MAP`); a missing kind key uses `capability`. `team.policy_for(team, gate, kind)` is the one place that picks the policy; `check_approval`, `gate_roles`, `can_waive`, `authorize_waiver` take `kind`; `needs_pr` decides the spec PR when any kind has a policy; CODEOWNERS uses the union of every kind's roles.
- `epic_kind.lookup(root, workflow_id, spec_path)` fails closed: the bead label wins, else the spec `Kind:`, else `capability`. Only bd's not-found counts as "no bead" (outside team mode, also bd's "no beads database found"); any other tracker failure refuses with `cannot read the kind of epic <id>: <cause>`. Two `kind:` labels, an invalid label, or a label and spec line that disagree are refusals naming the values. `gin record requirement-confirmed`, `gin team check --workflow-id`, and `gin unblock` use it.
- Skill rules per kind live in one shared reference, `plugins/gin-workflow/src/references/epic-kinds.md`, linked from `discuss`. The `team` and `sdd` skills were left unlinked to stay inside their 6,000-character budgets.

**Consequences**
- The map form needs gin-workflow 3.1 or later; older versions reject the config at schema validation.
- `tests/gin_orchestrator/test_harness_packaging.py` pins the list of packaged references; adding a file under `plugins/gin-workflow/src/references/` must update it. Track 3 missed it because its validation ran only the targeted tests; the full suite in Track 4 caught it.
- `roadmap/SKILL.md` is at 11,985 of 12,000 characters and `discuss/SKILL.md` at 5,990 of 6,000; new rules go in a reference.
- Execution: antigravity timed out at 900 s on Track 2 and the main harness (claude) took the fallback; `invalid_result_contract` results still need manual commit checks.
- Changing a kind after the spec is confirmed needs a new `/gin:discuss`. Showing the kind in `/gin:progress` or gin-console is out of scope.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{epic_kind,specs,team,team_init,team_cli,lifecycle_cli,schemas}.py`; `plugins/gin-workflow/src/templates/technical-design.md`; `plugins/gin-workflow/src/references/epic-kinds.md`; `plugins/gin-workflow/src/skills/roadmap/SKILL.md`
- Tests: `tests/workflow_core/test_epic_kind.py`, `test_specs.py`, `test_specs_archive_trace.py`, `test_team_gates.py`, `test_team_init.py`, `test_lifecycle_cli.py`
- Docs: `docs/concepts/lifecycle.md` (Epic kinds), `docs/guides/team.md` (Policy per epic kind), `docs/reference/config.md`, `docs/reference/cli.md`, `docs/guides/sdd.md`, `docs/roles.md`, `docs/guides/ba.md`, `docs/starters/brownfield.md`, and `.vi.md` pairs
- `.planning/specs/2026-11-12-epic-kinds-design.md`, `.planning/plans/2026-11-12-epic-kinds.md`
- Beads: `gin-workflow-3nwf`, `.1` to `.4`
- Related: [approval-policies](approval-policies.md), [epic-shape-and-contract](epic-shape-and-contract.md), [non-claude-dispatch](non-claude-dispatch.md)

**Scope**
How an epic's kind is set, checked, and used to choose spec content, lint rules, and the `requirement_confirmed` approval.
