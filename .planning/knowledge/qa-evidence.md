# Bugs from automated runs, one epic per bug, and published report evidence

**Context**
Epic `gin-workflow-qa-evidence` (2026-11-12, spec `.planning/specs/2026-11-12-qa-evidence-design.md`). `gin-qa cases bug` accepted manual cases only, so e2e and API failures could not file bugs; a case whose REQs belong to several epics filed silently against the first; the report zip stayed on the tester's machine.

**Decision/Solution**
- `gin-qa cases bug` accepts every case type. `bugs.epic_of` returns a list: the distinct epics of the case's REQs in REQ order, or the one epic of a legacy `Source:` spec. With more than one and no `--discovered-from`, it exits 2 with `several epics for <TC-ID>: <a>, <b>; pass --discovered-from <bead>` before any `gin task` call or case-file write.
- `/gin-qa:e2e` and `/gin-qa:tests` list product defects, ask which to file, and call `cases bug` with the run folder; `/gin-qa:run`, `/gin-qa:e2e`, and `/gin-qa:tests` answer the `several epics` exit like `no epic` (offer the epics, rerun with `--discovered-from`). No skill files a bug the user did not choose.
- Publishing is documentation, not code: GitHub has no API to attach a file to a pull request comment, so the guide gives CI snippets (`actions/upload-artifact` with `if: always()`, GitLab `artifacts: when: always`) and a drag-and-drop fallback. The approval comment carries the artifact URL by team convention.

**Consequences**
- A skill must not name a path in this repository (such as `docs/guides/qa.md`): the skill runs in the user's project, where that file does not exist.
- A behaviour change in a gin-qa command also needs `docs/reference/cli.md`, not only the QA guide; review of `.2` caught the stale reference.
- With gin-orchestrator healthy, the `backend` role routes to antigravity by `by_tier`. Dispatch failed with `worker_routes_unavailable` because the track worktree was nested under `.claude/worktrees/<feature>/.planning/worktrees/`, not the main checkout's `.planning/worktrees/` (`worker.unavailable` reason `workspace_unavailable`; see [non-claude-dispatch](non-claude-dispatch.md)); antigravity itself was healthy. The tracks ran on the fallback.

**References**
- `plugins/gin-qa/src/scripts/gin_qa/bugs.py` (`epic_of`, `file_bug`), `plugins/gin-qa/src/skills/{report,e2e,tests,run}/SKILL.md`, `docs/guides/qa.md` (Publish the evidence), `docs/reference/cli.md` (`gin-qa cases bug`)
- Beads: `gin-workflow-qa-evidence.1`, `.2`
- Related: [gin-qa-utilities](gin-qa-utilities.md), [gin-qa-setup-and-types](gin-qa-setup-and-types.md)

**Scope**
gin-qa bug filing, its skills, and the QA guide.
