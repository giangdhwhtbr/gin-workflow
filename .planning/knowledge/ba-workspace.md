# BA during build: question, answer, and accept comments; sign-off lines on confirmed assets

**Context**
Epic `gin-workflow-ba-workspace` (2026-11-12), process review clusters "Capture and mockups in a workspace" and "BA during build" (BA-7, BA-10, BA-14, BA-15, FE-LEAD-15). A BA session runs in the workspace parent, so `/gin-ba:mockup` never read the frontend child's UI; `assets confirm` recorded no person; a developer's business question ended as a bead note; the BA had no acceptance point after the spec.

**Decision/Solution**
- `gin specs assets confirm <cap> --date D [--agreed-with TEXT]` writes `Confirmed by: <git user.email>` (via `team.git_email`) and, when given, `Agreed with:` with whitespace collapsed to one line; no git email is an exit-2 refusal before any write. Lint still parses only `Confirmed:`, so older folders stay valid.
- `/gin-ba:mockup` in a workspace takes the cloned `shape: frontend` child as the existing UI, writes nothing for a 1-1 copy of the legacy screens (that rule sits before the folder step, which runs `assets add`), and in team mode asks for the agreement of the lead of the `team.areas` entry whose `paths` cover that child before confirm. Both gin-ba skills ask who else agreed and pass `--agreed-with`.
- Epic comments gain three kinds (home: `docs/concepts/lifecycle.md`): execute posts `[gin question] <track>: <question>` when the spec and plan do not answer and resumes on a newer `[gin answer] <track>:`; `/gin:progress` lists unanswered questions; the BA posts `[gin accept] <epic>: ...` once per epic after the QA report, and ship warns (never stops) when `team.members` has a `ba` member and no `[gin accept]` exists.
- Acceptance is a team convention plus a ship warning, not a gate (a gate would need router, state model, and gin-console changes).

**Consequences**
- Stage chains after the change: execute 11,445, progress 4,754, ship 10,755 of 12,000 characters (master's removal of `gin notify` freed about 680 in execute).
- The antigravity worker (`gemini-3.8-flash-medium`) returned `invalid_result_contract` twice (a status outside completed/failed/cancelled, then `tests` not a list of objects) after committing correct work; the main session verified the diff and tests instead of re-dispatching. Check the commits of a failed dispatch before rerunning it.
- `tests/workflow_core/test_walkthrough_docs.py` treats `gin accept` in `docs/starters/brownfield.md` as an undocumented CLI command, so the starter says "an acceptance comment" and links the BA guide.
- A catalog change mid-epic (schema 2.10 lists `claude-sonnet-5-5` and no efforts) made `routes resolve` reject the approved plan's `sonnet`/effort routes; routes were rewritten with user approval.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/{specs_assets.py,specs_cli.py}`, `plugins/gin-workflow/src/templates/iteration.md`
- `plugins/gin-workflow/src/skills/{execute,progress,ship}/SKILL.md`, `plugins/gin-ba/src/skills/{mockup,capture}/SKILL.md`, `plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md`
- Tests: `tests/workflow_core/test_specs_assets.py`
- Docs: `docs/concepts/lifecycle.md`, `docs/guides/{ba,git-flow,workspace}.md`, `docs/roles.md`, `docs/starters/brownfield.md`, `docs/reference/cli.md`, and `.vi.md` pairs
- `.planning/specs/2026-11-12-ba-workspace-design.md`, `.planning/plans/2026-11-12-ba-workspace.md`
- Beads: `gin-workflow-ba-workspace`, `.1` to `.4`
- Related: [epic-comments](epic-comments.md), [ba-plugin](ba-plugin.md), [sdd-team-flow](sdd-team-flow.md), [spec-asset-iterations](spec-asset-iterations.md)

**Scope**
The BA's asset sign-off, mockups in a workspace, and the BA's questions and acceptance during build.
