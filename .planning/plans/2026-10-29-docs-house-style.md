# Plan: docs house style and grounding in gin-workflow core

Epic: gin-workflow-46ns
Spec: `.planning/specs/2026-10-29-docs-house-style-design.md`

## Objective

gin-workflow writes and reviews Markdown with its own rules: a default `docs` rule pack for `**/*.md`, one shared reference `references/docs-style.md` that `tech-doc`, `docs-writer` and `review` load, and a regrounding mode in `/tech-doc`. The technical-writer plugin can then be uninstalled.

## Goal

Move the useful parts of technical-writer (MIT, v1.8.4) into gin-workflow's existing mechanisms, truth-vs-code checks first, as epic `gin-workflow-tvf5` showed.

## Architecture

- `plugins/gin-workflow/src/rules/docs.md`: a `core`-tier pack, `applies_to: ["**/*.md"]`. `workflow_core/rules.py` adds it to `DEFAULT_PACKS`, so `select_packs` picks it whenever a file in scope is Markdown, and `rules.disabled: [docs]` turns it off. No selection logic changes.
- `plugins/gin-workflow/src/references/docs-style.md`: the explanation behind the pack plus runbook and review guidance. `skills/tech-doc/SKILL.md` and `skills/review/SKILL.md` link it with `../../references/docs-style.md`; `agents/docs-writer.md` names it as a plugin reference, like `developer.md` names `references/shape-*.md`.
- The `review` stage chain (`workflow_core/budget.py`) follows links into `references/`, so `docs-style.md` counts toward the 12,000-character review budget. Review is 7,944 characters today; the reference is 2,579 characters; the chain lands near 10,700.

## Tech Stack

Markdown, Python 3 stdlib, unittest.

## Global Constraints

Copied from the spec:
- Out of scope: a CLI command, git hook or test that checks Markdown style; a new agent or skill set; design-doc, issue, ADR, changelog and postmortem formats; PlantUML or ArchiMate diagrams; restyling existing pages (epic `gin-workflow-9pl2`).
- The `docs` pack body stays at most 1,500 characters. `docs-style.md` stays under 3,500 characters (review stage budget).
- Existing projects get the `docs` pack on tasks that touch Markdown; `rules.disabled: [docs]` restores the old behavior.

Plan-level rules:
- New and edited lines follow the `docs` pack: no em or en dashes, no bold-label list items, no emoji, sentence-case headings. Existing lines of plugin instruction files (for example the bold step labels in `tech-doc/SKILL.md`) keep their format; the reviewer flags only lines the track writes.
- Docs state only what the code does. No commits on `master`.
- Test command: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest <module>`; full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `standard_impl`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: docs written by agents drifted from the code and from house style; the checks lived in a third-party plugin.
- Success criteria: spec US-1 to US-3 acceptance criteria; full suite passes.
- Constraints: review stage budget 12,000 characters; pack body limit 1,500; `docs-writer` has no shell (tools `view_file`, `grep_search`, `list_dir`).
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: two tracks, pack then reference
- Summary: Track 1 adds the pack and its selection; Track 2 adds the reference, wires the writers and the reviewer, and adds the regrounding mode.
- Pros: each track has its own test cycle and can be rejected alone.
- Cons: both edit `tests/workflow_core/test_rule_packs.py` and `tests/gin_orchestrator/test_harness_packaging.py`, so they run in order.

### Option 2: one track
- Summary: everything in one change.
- Pros: one review.
- Cons: a reviewer cannot accept the pack and reject the reference.

### Recommended Approach
- Selected option: Option 1.
- Reasoning: the pack changes runtime selection for every project; the reference only changes instructions. They deserve separate reviews.

## Scope
- In scope: spec R1 to R5.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Two small tracks that edit shared test files, so they run one after the other.
```

## Tasks

### Track 1: `docs` rule pack loaded by default for Markdown
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/rules/docs.md`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/rules.py:19,173` (`DEFAULT_PACKS`; `select_packs` docstring)
  - Modify `plugins/gin-workflow/src/rules/README.md:12` (precedence line)
  - Modify `docs/guides/rules.md:9-11,18,25` (packs table row, pack summary and credit, Configure comment)
  - Modify `docs/reference/cli.md:114` (`rules --files` defaults)
  - Modify `docs/reference/config.md:136` (`rules` defaults)
  - Test `tests/workflow_core/test_rule_packs.py`
  - Test `tests/workflow_core/test_rules.py`
  - Test `tests/workflow_core/test_token_budget.py:87`
  - Test `tests/gin_orchestrator/test_harness_packaging.py:48-49`
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Acceptance criteria**: spec US-1; `gin-workflow rules --list` and `--files README.md` show `docs`; full suite passes.
- **Estimated complexity**: low

**Interfaces**: produces pack id `docs` and `DEFAULT_PACKS == ("core", "lean", "docs")`. Selection order for Markdown in scope is `core`, `docs`, `lean` (same tier and depth, sorted by id); `--list` order is `core`, `lean`, `docs` (`DEFAULT_PACKS` order).

Steps:

1. Failing tests. In `tests/workflow_core/test_rule_packs.py`, import `DEFAULT_PACKS` (`from workflow_core.rules import DEFAULT_PACKS, IMPACTS, TIERS, load_plugin_packs`) and add to `TestRulePacks`:
   ```python
       def test_docs_pack_is_default_and_markdown_only(self):
           self.assertIn("docs", DEFAULT_PACKS)
           self.assertEqual(("**/*.md",), PACKS["docs"].applies_to)
           self.assertEqual("core", PACKS["docs"].tier)
           self.assertLessEqual(PACKS["docs"].body_chars, PACKS["docs"].body_limit)
   ```
   In `tests/workflow_core/test_rules.py`, add a class after `TestSelect` (the class with `test_lean_can_be_disabled`):
   ```python
   class TestPackagedDefaults(unittest.TestCase):
       plugin = load_plugin_packs(SCRIPTS.parent / "rules")

       def _ids(self, config, files):
           return [p.id for p in select_packs(self.plugin, [], config, files)[0]]

       def test_docs_pack_loads_for_markdown_only(self):
           self.assertEqual(["core", "docs", "lean"], self._ids({}, ["README.md"]))
           self.assertEqual(["core", "docs", "lean"], self._ids({}, ["src/app.py", "docs/guides/rules.md"]))
           self.assertEqual(["core", "lean"], self._ids({}, ["src/app.py"]))

       def test_docs_pack_can_be_disabled(self):
           self.assertEqual(["core", "lean"], self._ids({"rules": {"disabled": ["docs"]}}, ["README.md"]))
   ```
   In `TestCli`, add:
   ```python
       def test_files_adds_docs_pack_for_markdown(self):
           with tempfile.TemporaryDirectory() as tmp:
               result = self._run(Path(tmp), "--files", "README.md", "--format", "json")
               self.assertEqual(0, result.returncode, result.stderr)
               self.assertEqual(["core", "docs", "lean"], [p["id"] for p in json.loads(result.stdout)["packs"]])
   ```
   and in `test_list_reports_sizes_and_impact_counts` replace `core, lean = json.loads(result.stdout)["packs"]` with `core, lean, docs = json.loads(result.stdout)["packs"]` and add `self.assertEqual(("docs", "plugin", 1_500), (docs["id"], docs["source"], docs["limit"]))`.
   In `tests/workflow_core/test_token_budget.py:87` add `"docs"` to the expected pack set. In `tests/gin_orchestrator/test_harness_packaging.py` add `"rules/docs.md",` after `"rules/lean.md",`.
2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_rule_packs tests.workflow_core.test_rules tests.workflow_core.test_token_budget tests.gin_orchestrator.test_harness_packaging`. Expected: failures and errors naming `docs`.
3. Create `plugins/gin-workflow/src/rules/docs.md` with exactly:
   ```markdown
---
id: docs
tier: core
applies_to: ["**/*.md"]
---
- [critical] `true-to-code`: State only what the code, configuration, or tests show; check every command, path, flag, and default against them.
- [high] `label-conventions`: Call a team practice the code does not enforce a convention; never describe it as tool behavior.
- [high] `one-home`: Keep each fact on one page; other pages link to it instead of restating it.
- [high] `no-plan-wording`: Write the content a plan step or prompt asks for; never copy its wording into the page.
- `lead-with-conclusion`: Open each section with its conclusion; one claim per sentence, at most 35 words.
- `headings`: Write headings as sentence-case noun phrases, without numbers or questions.
- `plain-words`: Cut promotional, inflated, and filler words; replace an adjective with a number or a named property.
- `no-marks`: Use no em or en dashes, no list items that open with a bold label, and no emoji markers.
- `one-term`: Use one term for each concept throughout a page.

## Why
- `true-to-code`: A page that contradicts the code misleads every reader who trusts it, and a diff-only review does not catch it.
   ```
   (body 964 characters, measured with `parse_pack`.)
4. In `rules.py` set `DEFAULT_PACKS = ("core", "lean", "docs")` and change the `select_packs` docstring to `"""Enabled packs matching `files` (+ the default packs, + requires), highest precedence first."""`.
5. Run the tests of step 2. Expected: OK.
6. Docs, each one sentence or row, no other edits:
   - `plugins/gin-workflow/src/rules/README.md:12`: `` `core`, `lean`, and `docs` load by default (`docs` only when a Markdown file is in scope); `rules.disabled` in `.agent-workflow/config.yaml` turns any of them off. ``
   - `docs/guides/rules.md`: after the `lean` row add `` | `docs` | core | `*.md` | always, unless disabled | ``; after the `lean` sentence that credits ponytail add `` `docs` checks Markdown: every statement matches the code, practices the code does not enforce are called conventions, each fact has one home, and the house style holds (sentence-case headings, short sentences, no dashes, bold-label list items, or emoji). Its ideas come from [technical-writer](https://github.com/riekelt/technical-writer) (MIT). ``; change the Configure comment to `# turn a pack off, including core, lean, or docs`.
   - `docs/reference/cli.md:114`: `` the `core` and `lean` packs `` becomes `` the `core` and `lean` packs, `docs` when a Markdown file is given ``.
   - `docs/reference/config.md:136`: `` `core`, `lean`, and `docs` are always enabled unless disabled; `docs` applies only to Markdown files. `` followed by the rest of the existing line.
7. Run the full suite. Expected: OK. Commit `feat(rules): docs pack for Markdown, on by default`.

### Track 2: docs-style reference, writer and reviewer wiring, regrounding mode
- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-workflow/src/references/docs-style.md`
  - Modify `plugins/gin-workflow/src/skills/tech-doc/SKILL.md:15,44` (step 4; new section at the end)
  - Modify `plugins/gin-workflow/src/agents/docs-writer.md:16-20` (new guideline 4, renumber 4-7 to 5-8)
  - Modify `plugins/gin-workflow/src/skills/review/SKILL.md:23` (reviewer step 3)
  - Modify `docs/reference/skills.md:49` (`tech-doc` row)
  - Test `tests/workflow_core/test_rule_packs.py`
  - Test `tests/gin_orchestrator/test_harness_packaging.py:35-37,295`
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Acceptance criteria**: spec US-2 and US-3; review stage chain within 12,000 characters; full suite passes.
- **Estimated complexity**: low

**Interfaces**: consumes pack id `docs` from Track 1. Produces the path `references/docs-style.md` (sections `Truth`, `Sentences and headings`, `Banned constructions`, `Runbooks`, `Reviewing docs`) and the `tech-doc` section heading `## Regrounding existing docs`.

Steps:

1. Failing tests. In `tests/workflow_core/test_rule_packs.py` add to `TestRulePacks`:
   ```python
       def test_docs_writers_and_reviewer_load_docs_style(self):
           src = ROOT / "plugins/gin-workflow/src"
           style = (src / "references/docs-style.md").read_text(encoding="utf-8")
           for heading in ("## Truth", "## Sentences and headings", "## Banned constructions", "## Runbooks", "## Reviewing docs"):
               self.assertIn(heading, style)
           for relative in ("skills/tech-doc/SKILL.md", "agents/docs-writer.md", "skills/review/SKILL.md"):
               with self.subTest(path=relative):
                   self.assertIn("references/docs-style.md", (src / relative).read_text(encoding="utf-8"))
           tech_doc = (src / "skills/tech-doc/SKILL.md").read_text(encoding="utf-8")
           self.assertIn("gin-workflow rules --files", tech_doc)
           self.assertIn("## Regrounding existing docs", tech_doc)
   ```
   In `tests/gin_orchestrator/test_harness_packaging.py` add `"references/docs-style.md",` after `"references/shape-backend.md",` in `REQUIRED_ARTIFACTS`, and change the expected list in `test_docs_have_a_single_copy_outside_the_bundle` to `["docs-style.md", "shape-backend.md", "shape-frontend.md", "stage-contract.md"]`.
2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_rule_packs tests.gin_orchestrator.test_harness_packaging`. Expected: failures naming `docs-style.md`.
3. Create `plugins/gin-workflow/src/references/docs-style.md` with exactly:
   ```markdown
# Docs style

How gin-workflow writes and reviews Markdown. The `docs` rule pack is the checklist; this page explains it. Condensed from [technical-writer](https://github.com/riekelt/technical-writer) (MIT).

## Truth

- Every claim traces to code, configuration, tests, or a named source. Label inference as inference.
- A team practice the code does not enforce is a convention, and the page says so.
- Each fact has one home; other pages link to it.
- Each page has one class: normative (what must be), descriptive (what the code does at HEAD), historical (dated, never updated), runbook (steps someone runs), reference (complete over its scope).

## Sentences and headings

- Conclusion first. One claim per sentence, at most 35 words, active voice with a named actor.
- One term per concept. A number or a named property instead of an adjective. Plain verbs (use, not leverage).
- Headings are sentence-case noun phrases; an imperative above a procedure; the verbatim error above a troubleshooting entry. No numbers; no questions outside a FAQ.
- A table only when items share two or more properties. No heading above every paragraph.

## Banned constructions

| Pattern | Repair |
|---|---|
| Antithesis ("not X, but Y") | State Y |
| Importance or recap ("It is worth noting", "In summary") | Delete; state the fact |
| Throat clearing, filler ("basically", "simply") | Delete |
| Promotional or inflated words ("powerful", "seamless", "robust") | A number or a named property |
| Trailing participle ("..., ensuring reliability") | A separate sentence with evidence, or delete |
| Stacked hedges ("might possibly") | One hedge, or the fact |
| Vague attribution ("experts say") | Name the source |
| Em or en dashes, bold-label list items, emoji | Commas, colons, plain items |
| Assistant residue ("Let me", "I hope this helps") | Delete |
| Plan or prompt wording copied into the page | Write the content it asked for |

## Runbooks

- A procedure is numbered steps, each one action with its expected result.
- A troubleshooting entry starts from the verbatim symptom, then the cause, then the fix.
- A migration guide has a table mapping old to new, and a rollback section.

## Reviewing docs

- Check each claim against the code, not only the diff, and cite `file:line`.
- A claim the code contradicts, a practice written as tool behavior, or a missing required section: `IMPORTANT` or higher.
- A style rule: `MINOR`, unless it changes the meaning.
- Do not flag quoted material, code blocks, an example that shows a banned phrase, or a section a template requires.
   ```
4. `skills/tech-doc/SKILL.md` step 4 becomes: `` 4. **Write**: run `gin-workflow rules --files <pages to write>` and follow its output and [references/docs-style.md](../../references/docs-style.md). Clear prose with headings and short lists; Mermaid only where it clarifies architecture, data flow, or ownership; one topic per file, linking to siblings instead of repeating them. `` Append at the end of the file:
   ```markdown

## Regrounding existing docs

When the user asks to reground (re-check) pages or a docs folder, check those pages against the code instead of writing new ones. For each page:

1. List its factual claims: commands, flags, paths, defaults, and behavior.
2. Check each claim against the code at HEAD and note the evidence as `file:line`, or note that nothing backs it.
3. Fix a wrong claim, remove a claim nothing backs, or call it a convention when it describes team practice.
4. Report per page: claims checked, fixed, and removed, and open questions.

Write only the pages in scope and only the claims you fix; add sections or restyle a page only when the request says so.
   ```
5. `agents/docs-writer.md`: insert after guideline 3, renumbering the rest: `` 4. Follow the rules checklist passed in the handoff (`gin-workflow rules --files <pages>`) and the plugin reference `references/docs-style.md`; ask for the checklist when none was passed. ``
6. `skills/review/SKILL.md` reviewer step 3: append `` For a Markdown file, check each factual claim against the code and grade docs findings per [references/docs-style.md](../../references/docs-style.md). `` after the `simplified:` sentence and before the `project.layout: sdd` sentence.
7. `docs/reference/skills.md:49` `tech-doc` row: `` | `tech-doc` | Write technical documentation (features, API, stack, architecture, conventions, testing) from repository evidence, or reground existing pages against the code, on request only | ``
8. Run the tests of step 2, then `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_token_budget tests.workflow_core.test_docs_coverage`. Expected: OK. Check the chain size: `cd plugins/gin-workflow/src/scripts && python3 -c "from pathlib import Path; from workflow_core.budget import stage_chars; print(stage_chars(Path('..'), 'review'))"` prints a number at most 12,000 (about 10,700).
9. Run the full suite. Expected: OK. Commit `feat(docs): docs-style reference for writers and reviewers; tech-doc regrounding mode`.

## Integration
- **Branch**: `feat/docs-house-style`
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes
- [ ] `gin-workflow rules --files README.md` (after `./install.sh`) lists `docs`; `--files src/app.py` does not
- [ ] Review stage chain at most 12,000 characters

## Notes
- Parent bead `gin-workflow-46ns` stays open until a human-confirmed merge; track beads close after tests and review pass.
- After ship, uninstall the technical-writer plugin and run epic `gin-workflow-9pl2` with the regrounding mode.
