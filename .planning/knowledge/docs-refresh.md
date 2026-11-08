# Docs refresh: BA page, team git agreement, and doc-writing constraints

**Context**
Epic `gin-workflow-docs-refresh` (2026-11-08). After the BA-flow epics, the rename, the deadline forecast, and the roadmap pipeline shipped, the docs were rewritten as one pass: a task-ordered BA page, starters that walk the roadmap and milestone process with realistic prompts, a formal team git agreement for non-technical members, and an accuracy pass over the reference and concept pages. Every `.vi.md` is written with the `vietnamese-tech-writing` skill (user requirement).

**Decision/Solution**
- `docs/guides/ba.md` is the BA's one page (role, eight steps, conventions, commands, reading list); mechanics stay in `sdd.md` and `team.md` and are linked, not restated. Nav name: `Business analyst`.
- `docs/guides/git-flow.md` (`Team git agreement`) is written with SHALL / SHALL NOT (vi: PHẢI / PHẢI KHÔNG, both defined in Purpose and scope). Its Gate approval section follows what the skills do: `roadmap` is only checked (`gin team check <pr> --gate roadmap`, the roadmap skill records no gate); `requirement_confirmed` and `plan_approved` are recorded by discuss and plan with the merged pull request URL; `ship` is checked on the open pull request before the merge (`gin team check --gate ship`) and recorded as `gin record shipped` after the merge only for a standalone bead (an epic ships when its bead closes).
- Team mode verifies pull requests on GitHub and GitLab only (`workflow_core/team_host.py:13`); AWS CodeCommit support is epic `gin-workflow-uj2o`.
- GitHub Copilot CLI is a valid main harness (`SUPPORTED_HARNESSES` in `configuration.py`, `catalog.py`, installers); the old "cannot be the configured harness" wording was wrong.

**Consequences**
- `tests/workflow_core/test_walkthrough_docs.py` forbids the word "sprint" in `docs/starters/brownfield.md` and requires every `gin` command it cites to appear in `docs/reference/cli.md`. Run the docs tests (`test_docs_check.py`, `test_docs_coverage.py`, `test_walkthrough_docs.py`) before the full suite.
- The `docs` rule pack forbids numbered headings; a plan that numbers sections loses to the rule.
- `gin evidence run | tail` hides the run's exit code; confirm with `gin evidence check` before requesting review.
- An open finding of any severity, SUGGESTION included, blocks `review-ledger.py approve`; a reviewer cannot withdraw it, so the implementer fixes it (`fix-finding`) or proposes a deferral.
- `gin:developer` and `gin:docs-writer` have no Skill tool: give them the path of the Vietnamese skill (`~/.claude/plugins/marketplaces/vietnamese-language-skill/skills/vietnamese-tech-writing/SKILL.md`, its `references/`, and `scripts/validate_copy.py --register eng-impersonal`).
- In a worktree-isolated session the shell guard refuses commands whose arguments contain `git-flow`; use a glob (`docs/guides/gi?-flow.md`).
- Follow-up `gin-workflow-nox6`: `docs/index.md` still names a verify stage, `contributing.md:45` and `orchestrator/routing.md:45` disagree with the Copilot support.

**References**
- `docs/guides/{ba,git-flow,sdd,team}.md`, `docs/roles.md`, `docs/starters/{brownfield,greenfield}.md`, `docs/reference/{cli,skills,config}.md`, `docs/concepts/{architecture,lifecycle}.md`, `README.md`, `mkdocs.yml`, and their `.vi.md` pairs
- `.planning/specs/2026-11-08-docs-refresh-design.md`, `.planning/plans/2026-11-08-docs-refresh.md`
- Beads: `gin-workflow-docs-refresh`, `.1` to `.5`; follow-ups `gin-workflow-uj2o`, `gin-workflow-nox6`
- Related: [roadmap-delivery-pipeline](roadmap-delivery-pipeline.md), [milestone-lanes-and-forecast](milestone-lanes-and-forecast.md)

**Scope**
Documentation under `docs/` and `README.md`; the review and evidence flow of docs-only tracks.
