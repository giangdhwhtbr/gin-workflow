# Plan: Docs Rewrite

**Goal:** Replace the drifted documentation set with a layered one that matches the code on `master` (rules and lean pack, SDD living specs, team mode, gin-qa, `quick`, usage report), has exactly one copy of each document, explains the plugin architecture with Mermaid diagrams, and fails a test when a skill, CLI subcommand, or relative link goes undocumented or dead.

**Architecture:** `README.md` is a short entry page. `docs/` has four layers: `getting-started.md` (+ Vietnamese `huong-dan.md`), `concepts/` (architecture with diagrams, lifecycle, state model, providers), `guides/` (one page per opt-in feature), `reference/` (CLI, config, skills, troubleshooting), plus `contributing.md`. Concept pages replace the seven canonical docs and their copies in `plugins/gin-workflow/src/references/`. One stdlib test (`tests/workflow_core/test_docs_coverage.py`) guards coverage, links, and Mermaid block headers.

**Tech Stack:** Markdown, Mermaid (GitHub-rendered), Python 3.12 `unittest`, bash/PowerShell smoke tests, `npx @mermaid-js/mermaid-cli` for a manual render check.

**Spec:** `.planning/specs/2026-10-04-docs-rewrite-design.md` (workflow id `docs-rewrite`, `requirement_confirmed` recorded).

## Global Constraints

Copied verbatim from the spec:

- Docs are written in English. One Vietnamese quickstart (`docs/huong-dan.md`) mirrors `docs/getting-started.md` and links to the English pages for detail.
- Every statement is checked against the current code (`--help`, `SKILL.md`, config schema, `plugins/gin-workflow/src/examples/config.full.yaml`), never copied from an old doc without checking.
- Each page has one job; other pages link to it instead of repeating it. Diagrams live only in `docs/concepts/architecture.md`.
- Historical docs are deleted; git history keeps them.
- `docs/` is the only copy. The plugin bundle ships only references that skills read (`stage-contract.md`, `shape-*.md`).
- `AGENTS.md` and `CLAUDE.md` stay a pointer layer.
- No new runtime dependency; the docs test uses the Python standard library only.

Repository constraints:
- Test command (repo root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`. Baseline on `master` `eb843c2`: `OK (skipped=3)`.
- Install smoke test: `bash tests/install_smoke_test.sh` exits 0 after every track. `pwsh` is not available here; keep `tests/install_smoke_test.ps1` consistent by reading.
- Git: commit/push on `docs/docs-rewrite` (worktree `.planning/worktrees/<epic>`); never commit to `master`.

## Deviations from the spec

- The docs test lives at `tests/workflow_core/test_docs_coverage.py`, not `tests/test_docs_coverage.py`: `tests/test_all.py` only loads `workflow_core`, `workflow_providers`, `review_ledger`, `gin_qa`.
- The CLI subcommand list is read from the usage line that `gin-workflow` prints with no arguments (`usage: gin-workflow {setup,...} <command>`), so no code change is needed in `cli.py`.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `standard_impl`
- `override_rule`: docs default to `standard_impl`, not `cheap_simple`, because every statement must be checked against code.

## Requirement Analysis
- Problem: canonical docs predate rules, SDD, team mode, gin-qa, quick, and usage; seven docs exist twice; historical snapshots mix with current docs; README is ~20 KB.
- Success: spec §Verification; the Validation list below.
- Constraints: Global Constraints above.
- Non-goals (spec): generated reference pages, a docs site, full Vietnamese translation, plugin behavior changes (only the `waivers.py` comment changes).

## Approach Options
### Option 1: layered docs (concepts / guides / reference) with a coverage test (selected in discuss)
- Pros: readers know where to look; the test catches undocumented skills, subcommands, and dead links.
- Cons: more files than a flat layout.
### Option 2: flat one page per feature
- Cons: mixes concepts, guides, and reference.
### Option 3: generated reference
- Cons: needs a generator; dry output; the coverage test gives most of the benefit.
### Recommended Approach
- Option 1, as confirmed.

## Scope
- In: `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/**`, `plugins/gin-workflow/src/references/` (deletions only), `plugins/gin-workflow/src/scripts/workflow_core/waivers.py` (comment only), `tests/workflow_core/test_docs_coverage.py`, `tests/workflow_core/test_assignments.py`, `tests/workflow_providers/test_harness_packaging.py`, `tests/install_smoke_test.sh`.
- Out: skills, agents, CLI behavior, config schema, version bump (done at ship).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Four tracks that link to each other's pages and share README/AGENTS pointers; sequential direct execution with an independent review per track.
```

## Shared rules for every docs track

- Before writing a page, read its sources (Content Map in the spec) and the code they describe; run the read-only commands it shows and paste only output you have seen.
- Every relative link must resolve; the docs test enforces it.
- No page repeats another page's content; link instead. No diagrams outside `docs/concepts/architecture.md`.
- Each track ends with: full unittest run `OK`, `bash tests/install_smoke_test.sh` exit 0, independent review approved, commit on `docs/docs-rewrite`.

## Tasks

### Track 1: Docs test and reference pages
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Create `tests/workflow_core/test_docs_coverage.py`
  - Create `docs/reference/cli.md`, `docs/reference/config.md`, `docs/reference/skills.md`, `docs/reference/troubleshooting.md`
  - Modify `README.md`: replace the Troubleshooting section (from `## Troubleshooting` to before `## Local Development & Compilation`) with one line linking `docs/reference/troubleshooting.md`
- **Interfaces produced**: page paths above; heading form `## \`gin-workflow <subcommand>\`` in `cli.md`; skill names in backticks in `skills.md`.
- **Steps**:
  1. Write the test (fails: pages missing):
     ```python
     """Docs stay in step with the code: every skill and CLI subcommand is documented, links resolve, Mermaid blocks are typed."""

     from __future__ import annotations

     from pathlib import Path
     import re
     import subprocess
     import sys
     import unittest

     ROOT = Path(__file__).resolve().parents[2]
     DOCS = ROOT / "docs"
     SCRIPTS = ROOT / "plugins/gin-workflow/src/scripts"
     LINK = re.compile(r"\]\(([^)\s]+)\)")
     MERMAID = re.compile(r"```mermaid\n(\S+)")
     TYPES = {"flowchart", "graph", "sequenceDiagram", "stateDiagram-v2", "stateDiagram", "classDiagram", "erDiagram"}


     def pages() -> list[Path]:
         return [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CLAUDE.md", *sorted(DOCS.rglob("*.md"))]


     class DocsCoverageTests(unittest.TestCase):
         def test_every_skill_is_in_the_skills_reference(self):
             text = (DOCS / "reference/skills.md").read_text(encoding="utf-8")
             skills = sorted(p.name for p in ROOT.glob("plugins/*/src/skills/*") if p.is_dir())
             self.assertTrue(skills)
             self.assertEqual([s for s in skills if f"`{s}`" not in text], [])

         def test_every_cli_subcommand_has_a_heading(self):
             done = subprocess.run([sys.executable, "-m", "workflow_core.cli"], cwd=SCRIPTS,
                                   capture_output=True, text=True)
             commands = re.search(r"\{([^}]+)\}", done.stderr).group(1).split(",")
             text = (DOCS / "reference/cli.md").read_text(encoding="utf-8")
             self.assertEqual([c for c in commands if f"## `gin-workflow {c}" not in text], [])

         def test_relative_links_resolve(self):
             dead = []
             for page in pages():
                 for target in LINK.findall(page.read_text(encoding="utf-8")):
                     path = target.split("#", 1)[0]
                     if not path or re.match(r"[a-z]+:", path):
                         continue
                     if not (page.parent / path).exists():
                         dead.append(f"{page.relative_to(ROOT)} -> {target}")
             self.assertEqual(dead, [])

         def test_mermaid_blocks_name_a_diagram_type(self):
             bad = [f"{p.relative_to(ROOT)}: {kind}" for p in pages()
                    for kind in MERMAID.findall(p.read_text(encoding="utf-8")) if kind not in TYPES]
             self.assertEqual(bad, [])


     if __name__ == "__main__":
         unittest.main()
     ```
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_docs_coverage.py` → expect failures/errors for missing `skills.md` and `cli.md` (links and Mermaid already pass).
  3. Write `docs/reference/cli.md`: intro (install puts `gin-workflow` on PATH; `--version`; exit 2 on unknown command), then one `## \`gin-workflow <name>\`` section per subcommand `setup, state, unblock, record, quick-check, rules, specs, team, usage`, each with synopsis, options (from the module's argparse parser: `cli.py`, `state`/`record`/`unblock` modules, `quick_check`, `rules.py`, `specs_cli.py`, `team_cli.py`, `usage_cli.py`), exit codes, one example. Then `## review-ledger.py` listing its subcommands from `scripts/review-ledger.py` grouped as lifecycle (`init`, `checkpoint`, `start-review`, `approve`, `reject`, `render`, `validate`, `status`, `cleanup`, ...) and findings (`add-finding`, `fix-finding`, ...), one line each from their `help=`.
  4. Write `docs/reference/skills.md`: one table per plugin (`gin-workflow`, `gin-qa`) with columns Skill, Slash command, Purpose, When to use; one row per directory in `plugins/*/src/skills/` (gin-workflow: 24; gin-qa: `cases`, `e2e`), purpose taken from each `SKILL.md` frontmatter `description`.
  5. Write `docs/reference/config.md` from `docs/setup-system.md`, `plugins/gin-workflow/src/examples/config.full.yaml`, and the config schema/validation code (`workflow_core/configuration.py`, `project.py`, `migrations.py`): files (`.agent-workflow/config.yaml`, `generated/effective-config.yaml`, `local` provider config, `usage-prices.yaml`), setup actions (`COMMANDS` in `setup_service.py`), versioning and migration (`CURRENT_VERSION`), and a key table covering `project` (stage, shape, rigor, layout, team, verify_commands), `rules`, providers/roles, review.
  6. Write `docs/reference/troubleshooting.md`: move the four README Troubleshooting entries verbatim-checked, and add "Codex marketplace install has no `gin-workflow` launcher on PATH" with the fix (run the local installer, see `docs/contributing.md` once it exists — until Track 4, link `../../README.md#local-development--compilation`).
  7. Apply the README Troubleshooting replacement.
  8. Run the docs test → `OK`; full suite → `OK (skipped=3)`; smoke → exit 0. Commit `docs(reference): CLI, config, skills, troubleshooting reference and docs coverage test`.
- **Acceptance criteria**: docs test passes; every option in `cli.md` exists in the parser it names; every skill row matches its `SKILL.md`; review approved.

### Track 2: Concept pages, architecture diagrams, single copy
- **Dependencies**: Track 1
- **Provider role**: `docs`
- **Reasoning**: `high`
- **Estimated complexity**: high
- **Files**:
  - Create `docs/concepts/architecture.md`, `docs/concepts/lifecycle.md`, `docs/concepts/state-model.md`, `docs/concepts/providers.md`
  - Delete `docs/agent-task-lifecycle.md`, `docs/orchestration-state-model.md`, `docs/verification-and-handoff-workflow.md`, `docs/setup-system.md`, `docs/capability-provider-contracts.md`, `docs/context-and-evidence-policy.md`, `docs/provider-routing.md`
  - Delete `plugins/gin-workflow/src/references/{agent-task-lifecycle,orchestration-state-model,verification-and-handoff-workflow,setup-system,capability-provider-contracts,context-and-evidence-policy,provider-routing}.md`
  - Modify `tests/workflow_providers/test_harness_packaging.py` (`REQUIRED_ARTIFACTS` lines 53–59: drop the seven), `tests/install_smoke_test.sh` (lines 86–88, 161–162, 211–212: drop those assertions), `tests/workflow_core/test_assignments.py` (`test_parent_deliverable_vs_track_bead_and_handoff_contracts`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/waivers.py:29` comment, `AGENTS.md`, `CLAUDE.md`, `README.md` (the docs link list at lines ~102–108 → concept/reference pages)
- **Interfaces consumed**: Track 1 reference pages (concept pages link to them).
- **Interfaces produced**: `docs/concepts/*.md` section anchors used by Tracks 3–4.
- **Steps**:
  1. Change the test first. In `test_assignments.py` replace the `handoff_doc`/`handoff_ref` reads and the four handoff asserts with:
     ```python
             # Handoff contracts and PR merge claim prohibition live in the execute skill
             self.assertIn("waiting for PR merge", execute)
             self.assertIn("Xin lệnh tạo PR từ nhánh feature đã push", execute)
     ```
     and remove the now-unused `root` variable if nothing else uses it. Run it → `OK` (both strings are in `skills/execute/SKILL.md`).
  2. Delete the seven reference copies; update `REQUIRED_ARTIFACTS` and `install_smoke_test.sh` (`install_smoke_test.ps1` asserts none of these files; no change). Run `test_harness_packaging.py` and the smoke test → pass.
  3. Write `lifecycle.md` from `agent-task-lifecycle.md` + `verification-and-handoff-workflow.md`, checked against the stage skills and `references/stage-contract.md`: stages and gates table (gate, recorded by, evidence), `record`/`state`/`unblock`, workflow ids and epics, waivers (`waivers.py`), quick path (`quick-check` outcomes), rigor, verification checklist and handoff rules (no "waiting for PR merge" without a PR link), usage collect at bead and epic close. Note where SDD and team mode change a step and link the guides (plain path links to `../guides/sdd.md` and `../guides/team.md` are added in Track 3; until then mention them without links).
  4. Write `state-model.md` from `orchestration-state-model.md`: who owns what (Beads: status/ownership/deps; plan files; runtime events; review ledger; worktrees), parent vs track beads, review ledger states and `cleanup`, `.planning/` layout (`specs/`, `plans/`, `worktrees/`), `.agent-workflow/` layout.
  5. Write `providers.md` from the three provider docs, checked against `workflow_core/assignments.py`, `provider_config.py`, `executable_resolver.py`: capabilities and contracts, roles and reasoning tiers, model classes, preferred/fallback routing, circuit/health/capacity, `main_harness` override, worker context and result contract, evidence policy, CLI names (`claude`, `codex`, `agy`).
  6. Write `architecture.md` with the six diagrams from the spec (components `flowchart`, lifecycle `stateDiagram-v2`, track execution `sequenceDiagram`, routing `flowchart`, build and install `flowchart`, usage collection `flowchart`), each with 2–4 sentences and a link to its detail page. Every node name is a real file, function, or command; check each with `grep`.
  7. Render check: extract each block to `$CLAUDE_JOB_DIR/tmp/mermaid/N.mmd` and run `npx -y @mermaid-js/mermaid-cli -i N.mmd -o N.svg` → six SVGs, exit 0.
  8. Update `waivers.py:29` comment path to `docs/concepts/lifecycle.md`; rewrite the canonical list in `AGENTS.md` and `CLAUDE.md` to `docs/concepts/{architecture,lifecycle,state-model,providers}.md` and `docs/reference/{config,cli}.md` (AGENTS: replace `docs/verification-and-handoff-workflow.md` in Required Defaults with `docs/concepts/lifecycle.md#verification-and-handoff`); update README's docs link list.
  9. Delete the seven old `docs/*.md`. Run `grep -rn "agent-task-lifecycle\|orchestration-state-model\|verification-and-handoff-workflow\|setup-system.md\|capability-provider-contracts\|context-and-evidence-policy\|provider-routing.md" --exclude-dir=.git --exclude-dir=dist --exclude-dir=.planning .` → no hits.
  10. Docs test, full suite, smoke → pass. Commit `docs(concepts): architecture diagrams and concept pages; single copy of docs`.
- **Acceptance criteria**: no content lost that is still true of the code (reviewer compares the old seven docs with the new pages); every diagram renders; every diagram name exists in code; tests and smoke pass; review approved.

### Track 3: Feature guides
- **Dependencies**: Track 2
- **Provider role**: `docs`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Create `docs/guides/rules.md`, `docs/guides/sdd.md`, `docs/guides/team.md`, `docs/guides/qa.md`, `docs/guides/usage-report.md`, `docs/guides/use-cases.md`
  - Delete `docs/use-cases/` (README.md, large-task.md, quick-debug.md, resume-in-progress.md)
  - Modify `README.md`: Rule Packs, gin-qa, usage, and Common Use Cases sections shrink to one line each linking their guide; `docs/concepts/lifecycle.md`: add links to `../guides/sdd.md` and `../guides/team.md`
- **Steps**:
  1. `rules.md` from README Rule Packs, `.planning/specs/2026-10-01-best-practice-rules-design.md`, `2026-10-04-lean-rules-design.md`, `workflow_core/rules.py`, the rule pack files, and the review skill: packs (core, lean on by default), config keys, `gin-workflow rules --files ...` with real output, how review grades lean findings, disabling a pack.
  2. `sdd.md` from `skills/gin-sdd`, `skills/migrate-specs`, `specs*.py`, `2026-10-03-sdd-living-specs-design.md`: `project.layout: sdd`, change folders, living specs, REQ-IDs, `specs lint`/`trace`/archive, migration.
  3. `team.md` from `skills/gin-team`, `skills/team-setup`, `team_*.py`, `2026-10-03-team-mode-design.md`: opt-in, setup, `team ready`/`claim`, labels/assignees, PR-based gates; solo unchanged.
  4. `qa.md` from the README gin-qa section and `plugins/gin-qa/src/skills/{cases,e2e}`: install, cases, e2e, how it relates to `verify`.
  5. `usage-report.md` from the README usage paragraph and `2026-10-04-ai-usage-report-design.md`: what is measured, `usage collect`/`report`, `/report`, `usage-prices.yaml` example, attribution summary, limits (agy not measured, parallel root sessions, review interval includes waiting time).
  6. `use-cases.md`: merge the three use cases, updated to current skills (quick, progress, workflow).
  7. Delete `docs/use-cases/`; shrink the README sections; add the lifecycle guide links. Docs test, full suite, smoke → pass. Commit `docs(guides): rules, SDD, team, QA, usage report, use cases`.
- **Acceptance criteria**: each guide's commands and config keys exist in code; no content duplicated from concepts/reference; review approved.

### Track 4: README, getting started, contributing, cleanup
- **Dependencies**: Track 3
- **Provider role**: `docs`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Rewrite `README.md`
  - Create `docs/getting-started.md`, `docs/huong-dan.md`, `docs/contributing.md`
  - Delete `docs/huong-dan-workflow-v2.1.md`, `docs/workflow-audit-2026-07-08.md`, `docs/workflow-validation-simulation-2026-07-09.md`, `docs/model-class-planning-metadata-design-2026-07-09.md`, `docs/simulated-workflow-smoke-task.md`, `docs/superpowers/`, `docs/benchmarks/`
  - Modify `docs/reference/troubleshooting.md` (Codex launcher entry links `../contributing.md`)
- **Steps**:
  1. `contributing.md` from README Local Development & Compilation and Repository Structure plus `docs/benchmarks/README.md`: layout, build, local install on Linux/macOS and Windows (installer options), tests and smoke tests, release (version bump in `plugin.meta.json`/manifests, reinstall snapshots per harness), benchmark protocol.
  2. `getting-started.md`: prerequisites (`bd`, Python 3, a harness), install link, `/setup`, then one small worked feature through discuss → plan → orchestrate → execute → verify → ship with what each stage produces, then `/quick` and `/report`; links to concepts and reference.
  3. `huong-dan.md`: Vietnamese version of getting-started with the same headings and commands; links to the English pages for detail.
  4. Rewrite `README.md` (≤ ~6 KB): one-paragraph pitch, docs map (getting started, architecture, concepts, guides, reference, contributing), install (Claude Code, Antigravity, Codex, gin-qa — commands checked against the manifests and `install.sh`), 10-line quickstart, primary skills table (name + one line, linking `docs/reference/skills.md`).
  5. Delete the historical files and directories; update the troubleshooting link.
  6. `wc -c README.md` ≤ ~6200; docs test, full suite, smoke → pass. Commit `docs: rewrite README, getting started, contributing; drop historical docs`.
- **Acceptance criteria**: README size; install commands correct; `huong-dan.md` matches getting-started commands; no file under `docs/` outside the spec structure; review approved.

## Integration
- **Branch**: `docs/docs-rewrite`
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` → `OK`
- [ ] `bash tests/install_smoke_test.sh` → exit 0
- [ ] `tests/workflow_core/test_docs_coverage.py` → `OK`
- [ ] Six Mermaid diagrams render with `npx @mermaid-js/mermaid-cli`
- [ ] Read-only commands shown in docs (`gin-workflow --version`, `state`, `usage report`, `rules --files ...`) run and match the docs
- [ ] `wc -c README.md` ≤ ~6200
- [ ] `find docs -type f` matches the spec structure exactly
- [ ] Independent review per track approved with no open finding of severity important or higher

## Notes
- Parent Bead (epic) stays open until the human-confirmed merge; track beads close after tests and review pass.
- Provider roles and reasoning are portable; concrete providers resolve at orchestration.
