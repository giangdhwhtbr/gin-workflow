# Plan: docs-wide style and grounding pass

Epic: gin-workflow-9pl2
Spec: `.planning/specs/2026-10-29-docs-style-grounding-pass-design.md`

## Objective

`README.md` and the 29 pages under `docs/` state only what the code does and follow the `docs` rule pack. `reference/troubleshooting.md`, `upgrade-2.0.md` and `upgrade-2.1.md` have runbook structure. A test in `tests/workflow_core/test_docs_coverage.py` fails on dashes, bold-label list items, emoji, and numbered headings.

## Goal

Apply the rules of epic `gin-workflow-46ns` (the `docs` pack, `references/docs-style.md`, the `/tech-doc` regrounding steps) to every user documentation page.

## Architecture

- Five page groups (T1 to T5) with disjoint files, each in its own worktree and branch, merged into the integration branch `docs/style-grounding-pass`.
- Every page goes through the page procedure below. Results go into the track report, not the repository.
- T6 adds `style_violations(text)` and two tests to `test_docs_coverage.py`, after the cross-page link fixes that T1 to T5 report.

## Tech Stack

Markdown, Python 3 stdlib (`re`, `pathlib`), unittest.

## Global Constraints

Copied from the spec:
- Out of scope: new pages, moved or renamed pages, changes to the `docs/` folder structure; code changes; the decks (`docs/presentations/*.html`, `*.pptx`) and `build_brownfield_pptx.py`.
- A claim that the docs get right and the code gets wrong becomes a bug bead in this repository; the page is left as it is and the bead is named in the track report.
- `docs/presentations/brownfield-modernization-script.md` keeps its slide-numbered headings and title; its claims are regrounded.
- Each track edits only its own pages. A fix another page needs goes into the track report, and the coordinator applies it after the tracks close.
- Pages are not moved, and `cli.md` keeps its `` ## `gin-workflow <command>` `` headings.

Plan-level rules:
- No commits on `master`. Workers commit on their track branch and do not push; the coordinator merges and pushes.
- Workers cannot create beads: a code bug goes into the report with `file:line` evidence, and the coordinator creates the bead (`gin-workflow task create "<title>" -t bug --description "<evidence>"`).
- The coordinator reruns the style scan on each track's pages; a worker's own check is not evidence.

## Page procedure

Applied to each page of a track, in this order:

1. Read the page, `plugins/gin-workflow/src/references/docs-style.md`, and the rules checklist passed with the track (`gin-workflow rules --files <pages>`).
2. Reground (`/tech-doc` "Regrounding existing docs"):
   1. List the page's factual claims: commands, flags, paths, defaults, and behavior.
   2. Check each claim against the code at HEAD (`plugins/*/src/`, `install.sh`, `install.ps1`, `tests/`), and note the evidence as `file:line`, or that nothing backs it.
   3. Fix a wrong claim, remove a claim nothing backs, or call it a convention when it describes team practice. When the code is wrong and the page is right, leave the page and report the bug.
3. Restyle, keeping the meaning:
   - remove em and en dashes (use a comma, colon, semicolon, or two sentences);
   - turn a list item that opens with a bold label into a plain item (`- **Reinstall** gin-workflow` becomes `- Reinstall gin-workflow`; `- **Note:** text` becomes `- text` or a sentence);
   - remove emoji;
   - remove numbers from headings and write them in sentence case, without questions outside a FAQ;
   - split sentences over 35 words; cut promotional and filler words; use one term per concept.
   Do not add sections (except the runbook structure of T1), move content to another page, or restate a fact another page owns; link to it.
4. For each heading whose text changed, find links to its old anchor (GitHub slug: lowercase, spaces to `-`, punctuation other than `-` and `_` dropped): `grep -rn "#<old-slug>" README.md AGENTS.md docs plugins/gin-workflow/src plugins/gin-orchestrator/src plugins/gin-qa/src`. Fix links inside the track's pages; report the others.
5. Run the style scan on the track's pages (below). Expected: no output.
6. Report per page: claims checked, fixed, removed (each with `file:line` evidence or "nothing backs it"); code bugs found; links outside the track to fix; open questions.

Style scan (pass the track's pages as arguments):

```bash
python3 - <page> [<page> ...] <<'EOF'
import re, sys
from pathlib import Path
RULES = (("dash", re.compile("[–—]")),
         ("bold-label item", re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\*\*")),
         ("emoji", re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⭕️]")),
         ("numbered heading", re.compile(r"^#{1,6}\s+\d")))
for page in sys.argv[1:]:
    fenced = False
    for number, line in enumerate(Path(page).read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            for name, pattern in RULES:
                if pattern.search(line):
                    print(f"{page}:{number}: {name}")
EOF
```

Track checks, run in the track's worktree:

```bash
PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage
PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all
```

Expected: `OK` for both. Then commit on the track branch.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `standard_impl`
- `override_rule`: Use `high_reasoning` for tracks whose pages hold many command, flag, and default claims (T1 to T3).

## Requirement Analysis
- Problem statement: pages drifted from the code and from the house style; 16 of 30 pages break a mechanical rule.
- Success criteria: spec US-1 to US-4.
- Constraints: disjoint page groups; no code changes; the presentation script keeps its headings.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: five page groups in parallel, then the test
- Summary: T1 to T5 each restyle and reground their pages in their own worktree; T6 adds the test.
- Pros: fastest; each group reviewed alone.
- Cons: five merges, and cross-page link fixes wait for T6.

### Option 2: the same groups in sequence
- Summary: one worktree, T1 to T5 one after another.
- Pros: no merges.
- Cons: about five times slower for no quality gain.

### Recommended Approach
- Selected option: Option 1 (the user chose it in discuss).
- Reasoning: the groups share no file, so parallel runs cannot conflict.

## Scope
- In scope: spec R1 to R5.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Five independent page groups with disjoint files run as parallel workers, each in its own worktree; the test track follows.
```

## Tasks

### Track 1: runbooks
- **Dependencies**: none
- **Files**:
  - Modify `docs/reference/troubleshooting.md`
  - Modify `docs/reference/upgrade-2.0.md`
  - Modify `docs/reference/upgrade-2.1.md`
- **Provider role**: `docs`
- **Reasoning**: `high`
- **Model guidance**: `high_reasoning`
- **Acceptance criteria**: page procedure applied to the 3 pages; spec US-3; style scan clean; track checks OK; review approved.
- **Estimated complexity**: medium

**Interfaces**: produces the page report (procedure step 6). The headings of `troubleshooting.md` change; links to them from other pages (for example `upgrade-2.0.md` step 3 links `troubleshooting.md#orchestrator-errors-and-warnings-orchestrator_missing-orchestrator_contract_mismatch-orchestrator_failed`) are fixed here when inside T1, reported otherwise.

Steps:
1. Apply the page procedure to `troubleshooting.md`. Each entry keeps the shape: `## <symptom>` (the verbatim error when one exists, in backticks), then a `Cause:` paragraph, then the fix as numbered steps or one command block. An entry that names no symptom (for example `## GitHub Copilot CLI`) gets a symptom heading from what the reader sees, checked against the code.
2. Apply the page procedure to `upgrade-2.0.md`. Add `## What changed` with a table `| Before (2.7) | After (2.8) |` covering each change step 2 lists (routing keys moved to `orchestrator:`, `provider_mode`, `providers.task_tracking`, `providers.local.yaml` renamed to `orchestrator.local.yaml`, versions), each checked against `plugins/gin-workflow/src/scripts/workflow_core/` (migration code). Add `## Rollback` with `gin-workflow setup rollback --backup <path>` and what it restores, checked against the `setup rollback` code; keep the steps list as numbered plain items.
3. Apply the page procedure to `upgrade-2.1.md`. Add `## What changed` with a table `| Before (2.0) | After (2.1) |` (Telegram default, Telegram skill and script replaced by `gin-workflow notify`, `gin-workflow goal`), and `## Rollback`: the schema stays at 2.8, so going back is reinstalling the earlier release (`git checkout <tag>` in the gin-workflow checkout, then `./install.sh --platform all`), checked against `install.sh`. Rename the heading `## 2.1.1` to `## Changes in 2.1.1`.
4. Style scan on the 3 pages; track checks; commit `docs(reference): troubleshooting and upgrade guides as runbooks, regrounded`.

### Track 2: reference
- **Dependencies**: none
- **Files**:
  - Modify `docs/reference/cli.md`
  - Modify `docs/reference/config.md`
  - Modify `docs/reference/skills.md`
  - Modify `docs/reference/orchestrator-contract.md`
- **Provider role**: `docs`
- **Reasoning**: `high`
- **Model guidance**: `high_reasoning`
- **Acceptance criteria**: page procedure applied to the 4 pages; `cli.md` keeps `` ## `gin-workflow <command>` `` headings (`test_every_cli_subcommand_has_a_heading`); `skills.md` keeps every skill name (`test_every_skill_is_in_the_skills_reference`); style scan clean; track checks OK; review approved.
- **Estimated complexity**: high

**Interfaces**: produces the page report. Every flag and default in `cli.md` is checked against the subcommand's `argparse` definition (`plugins/gin-workflow/src/scripts/workflow_core/*.py`, `main()` of each module); every key in `config.md` against `workflow_core/schemas.py` and `plugins/gin-workflow/src/examples/config.full.yaml`.

Steps:
1. Apply the page procedure to `cli.md`, one `## \`gin-workflow <command>\`` section at a time.
2. Apply the page procedure to `config.md`, `skills.md` (each row against the skill's `SKILL.md` description and body), and `orchestrator-contract.md` (against `plugins/gin-orchestrator/src/`).
3. Style scan on the 4 pages; track checks; commit `docs(reference): cli, config, skills, orchestrator contract regrounded`.

### Track 3: concepts
- **Dependencies**: none
- **Files**:
  - Modify `docs/concepts/architecture.md`
  - Modify `docs/concepts/lifecycle.md`
  - Modify `docs/concepts/providers.md`
  - Modify `docs/concepts/state-model.md`
  - Modify `docs/contributing.md`
- **Provider role**: `docs`
- **Reasoning**: `high`
- **Model guidance**: `high_reasoning`
- **Acceptance criteria**: page procedure applied to the 5 pages; Mermaid blocks keep a diagram type (`test_mermaid_blocks_name_a_diagram_type`); style scan clean; track checks OK; review approved.
- **Estimated complexity**: medium

**Interfaces**: produces the page report. Gate names and stage order in `lifecycle.md` are checked against `workflow_core/lifecycle_cli.py`, `workflow_core/router.py`, and the stage skills; the invariants listed in `contributing.md` against the tests that enforce them.

Steps:
1. Apply the page procedure to the 4 `concepts/` pages, including each Mermaid diagram's nodes and arrows.
2. Apply the page procedure to `contributing.md` (build, install, test commands, release steps).
3. Style scan on the 5 pages; track checks; commit `docs(concepts): concepts and contributing regrounded`.

### Track 4: guides
- **Dependencies**: none
- **Files**:
  - Modify `docs/guides/customizing-templates.md`
  - Modify `docs/guides/qa.md`
  - Modify `docs/guides/recommended-tools.md`
  - Modify `docs/guides/rules.md`
  - Modify `docs/guides/sdd.md`
  - Modify `docs/guides/team.md`
  - Modify `docs/guides/usage-report.md`
  - Modify `docs/guides/use-cases.md`
  - Modify `docs/guides/windows.md`
- **Provider role**: `docs`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Acceptance criteria**: page procedure applied to the 9 pages; `use-cases.md` keeps the four section names `test_harness_packaging` checks (`Small change`, `Bounded defect`, `Large multi-track change`, `Resume in-progress work`); `rules.md` keeps the ponytail link; style scan clean; track checks OK; review approved.
- **Estimated complexity**: medium

**Interfaces**: produces the page report. `recommended-tools.md` keeps its path and anchors (`setup_service.py` and the `setup` skill link its GitHub URL).

Steps:
1. Apply the page procedure to each of the 9 pages, `windows.md` first (7 dashes, 5 bold-label items, 7 numbered headings; check the Python version it states against `install.ps1` and `install.sh`).
2. Style scan on the 9 pages; track checks; commit `docs(guides): guides regrounded and restyled`.

### Track 5: entry points
- **Dependencies**: none
- **Files**:
  - Modify `README.md`
  - Modify `docs/getting-started.md`
  - Modify `docs/roles.md`
  - Modify `docs/starters/greenfield.md`
  - Modify `docs/starters/brownfield-walkthrough.md`
  - Modify `docs/starters/brownfield-modernize.md`
  - Modify `docs/orchestrator/README.md`
  - Modify `docs/orchestrator/routing.md`
  - Modify `docs/presentations/brownfield-modernization-script.md` (claims only)
- **Provider role**: `docs`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Acceptance criteria**: page procedure applied to the 8 pages; claims of the presentation script regrounded with its headings and title unchanged; the README docs map still links every `docs/**/*.md` page (`test_every_docs_page_is_in_the_readme_map`) and keeps `docs/guides/rules.md` (`test_review_skill_grades_lean_findings`); README Credits unchanged; style scan clean on the 8 pages; track checks OK; review approved.
- **Estimated complexity**: medium

**Interfaces**: produces the page report. `README.md` "Documentation" table keeps one link per page.

Steps:
1. Apply the page procedure to `README.md` (its `### 1. Dependencies` and `### 2. The plugin` become `### Dependencies` and `### The plugin`) and `getting-started.md` (5 numbered headings, 5 emoji items, 6 bold-label items).
2. Apply the page procedure to `roles.md`, the 3 `starters/` pages, and the 2 `orchestrator/` pages.
3. Apply procedure steps 1, 2 and 6 only to `presentations/brownfield-modernization-script.md`.
4. Style scan on the 8 pages (not the script); track checks; commit `docs: readme, getting started, roles, starters, orchestrator regrounded`.

### Track 6: style test
- **Dependencies**: Track 1, Track 2, Track 3, Track 4, Track 5
- **Files**:
  - Test `tests/workflow_core/test_docs_coverage.py`
  - Modify any `README.md` or `docs/**/*.md` page a T1 to T5 report lists for a cross-page link fix (link target only)
- **Provider role**: `general`
- **Reasoning**: `low`
- **Model guidance**: `cheap_simple`
- **Acceptance criteria**: spec US-4; full suite OK; review approved.
- **Estimated complexity**: low

**Interfaces**: produces `style_violations(text: str) -> list[str]` (entries `"<line>: <rule>"`) and `STYLE_EXEMPT` in `test_docs_coverage.py`.

Steps:
1. Apply the cross-page link fixes from the T1 to T5 reports on the integration branch; run `tests.workflow_core.test_docs_coverage` (expected OK); commit `docs: fix links to renamed headings`.
2. Add to `tests/workflow_core/test_docs_coverage.py`, after `TYPES`:
   ```python
   STYLE_RULES = (("dash", re.compile("[–—]")),
                  ("bold-label item", re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\*\*")),
                  ("emoji", re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⭕️]")),
                  ("numbered heading", re.compile(r"^#{1,6}\s+\d")))
   STYLE_EXEMPT = {"docs/presentations/brownfield-modernization-script.md"}  # headings map to slide numbers


   def style_violations(text: str) -> list[str]:
       """Mechanical docs-pack rules outside fenced code blocks, as '<line>: <rule>'."""
       found, fenced = [], False
       for number, line in enumerate(text.splitlines(), 1):
           if line.lstrip().startswith("```"):
               fenced = not fenced
               continue
           if not fenced:
               found += [f"{number}: {name}" for name, pattern in STYLE_RULES if pattern.search(line)]
       return found
   ```
   and to `DocsCoverageTests`:
   ```python
       def test_style_check_catches_each_rule(self):
           sample = ("# Title\n## 2. Step\n- **Label:** text\n1. **Bold** start\n"
                     "A — dash\nDone ✅\n```\n## 3. In code\n```\n")
           self.assertEqual(["2: numbered heading", "3: bold-label item", "4: bold-label item", "5: dash", "6: emoji"],
                            style_violations(sample))

       def test_pages_follow_the_mechanical_style_rules(self):
           problems = [f"{page.relative_to(ROOT).as_posix()}:{found}"
                       for page in [ROOT / "README.md", *sorted(DOCS.rglob("*.md"))]
                       if page.relative_to(ROOT).as_posix() not in STYLE_EXEMPT
                       for found in style_violations(page.read_text(encoding="utf-8"))]
           self.assertEqual(problems, [])
   ```
3. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage`. Expected: OK. If `test_pages_follow_the_mechanical_style_rules` lists a page, the owning track missed it: fix that line (style only) and note it in the report.
4. Full suite; commit `test(docs): enforce mechanical docs style rules on README and docs`.

## Integration
- **Branch**: `docs/style-grounding-pass`
- **Merge strategy**: parallel-then-merge (T1 to T5 merge into the integration branch in track order after each closes; T6 runs on the integration branch)

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes on the integration branch
- [ ] Style scan clean on `README.md` and `docs/**/*.md` except the presentation script
- [ ] Every T1 to T5 report has per-page counts; every reported code bug has a bead

## Notes
- Parent bead `gin-workflow-9pl2` stays open until a human-confirmed merge; track beads close after tests and review pass.
- Track reports are kept in the track bead notes (`gin-workflow task update <id> --notes`), not in the repository.
