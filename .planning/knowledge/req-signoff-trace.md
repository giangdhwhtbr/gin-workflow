# Requirement sign-off in git and `gin specs trace --all`

**Context**
Epic `gin-workflow-ch2v` (2026-11-22, capability `req-signoff-trace`). Spec sign-off was a per-epic `requirement.confirmed` event in the gitignored `.agent-workflow/runtime/events.jsonl` (mirrored into the epic bead's `gates` only in team mode), and `gin specs trace` covered one open change and test files only. gin-console's requirements view (`gin-console-rm-requirements`, `gin-console-rm-req-signoff`) needs sign-off per requirement and one join of requirement, beads, gin-qa cases, and tests.

**Decision/Solution**
- `workflow_core/signoff.py` is the one home of sign-off rules. With the SDD layout, `record requirement-confirmed` adds `requirements: [{id, hash8, op}]` from the open change whose proposal says `Epic: <workflow id>`; `hash8` is `block_hash[:8]`, and a REMOVED block pins its `<!-- base: -->` (the living block's hash). `_proof` carries the list into the bead `gates` mirror.
- Sources, in order: `06-signoff.md` (archived folders, `source: git`), the epic bead's `gates.requirement_confirmed` (`beads`), the newest local `requirement.confirmed` event of the epic (`events`), then a `requirement_confirmed` waiver (`waived: true`, reason in `evidence`). An old archived change finds its sign-off through the `Epic:` line its folder keeps.
- `gin specs archive` writes `06-signoff.md` after the move and stages it; no sign-off is a warning, never a failure. The file holds `Epic:`, `Signed off:`/`By:`/`Evidence:` (a waiver: `Waived:`/`By:`/`At:`), `Source:`, optional `Hashes: at archive`, and a `| Requirement | hash8 | op |` table.
- `gin specs trace --all` (`specs_trace_all.py`, schema 1) lists living, proposed, and removed requirements with `changes`, `signoff` (`current`), `beads` (`req:` labels from one `bd list --all`), `cases` (`gin-qa cases export`), and `tests`. A source that fails is null plus a `warnings` entry. The contract table lives only in `docs/reference/cli.md#requirement-trace`.
- `current` compares the signed hash with the requirement's living hash, so a living requirement whose last signed change is still open (MODIFIED) reads `false` until archive; gin-console can tell it apart by `changes[].archived: null`. Changing this needs a spec change.

**Consequences**
- `WorkflowEvent` freezes its payload: lists become tuples and dicts `mappingproxy`. Code that copies a read-back payload into JSON must `thaw` it (`models.thaw`); `_proof` failed this way at `orchestration-ready` until `3dcb85a5`.
- `specs.delta_blocks` returns blocks under a non-delta `##` heading together with an error; callers that need `op` must filter to `DELTA_SECTIONS` (`signoff.change_requirements`, `specs_trace_all.trace_all`).
- No skill text changed: `skills/sdd/SKILL.md` (5,990 of 6,000 characters) and `skills/team/SKILL.md` (5,991) have no room; sign-off moves into git at archive so no stage has to commit a new file.
- Tests patch `specs_trace_all._gin_qa` because an installed `gin-qa` on `PATH` would otherwise run against the temporary repository; `tests/gin_qa/test_trace_cases.py` runs the real CLI (POSIX only).

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{signoff,specs_trace_all,specs_archive,specs_cli,lifecycle_cli}.py`
- Tests: `tests/workflow_core/{test_signoff,test_specs_trace_all,test_specs_archive_trace,test_lifecycle_cli,test_team_gates}.py`, `tests/gin_qa/test_trace_cases.py`
- `docs/reference/cli.md` (Requirement trace), `docs/guides/sdd.md` (Sign-off)
- `.planning/specs/2026-11-22-req-signoff-trace-design.md`, `.planning/plans/2026-11-22-req-signoff-trace.md`; commits `8d202fb6`, `3dcb85a5`, `f8182377`, `4a7bade3`, `6cbb7a67`
- Beads: `gin-workflow-ch2v`, `.1` to `.3`; consumer `gin-console-rm-req-signoff`

**Scope**
SDD layout: requirement sign-off, `gin specs archive`, and `gin specs trace --all` with the Beads or markdown task backend and an optional gin-qa.
