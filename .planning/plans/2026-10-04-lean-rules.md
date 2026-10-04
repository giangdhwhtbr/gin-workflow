# Plan: Lean Rule Pack

**Goal:** Agents write less code for the same result and reviewers catch over-engineering: reuse what exists, prefer the standard library, the platform, and installed dependencies, add nothing speculative, and never cut validation, error handling, security, accessibility, or required tests. Delivered through the existing rule-pack mechanism, so it reaches the `developer` agent, `/quick`, and the reviewer, and nothing else.

**Architecture:** One new packaged rule pack `plugins/gin-workflow/src/rules/lean.md` (tier `core`, applies everywhere). `workflow_core/rules.py` loads it by default next to `core` and gives it the 1,000-char `core` body limit. The review skill gets one sentence on grading `lean` findings. README gets a short "Rule Packs" section with the ponytail credit. Installers already copy the whole `rules/` directory, so they do not change.

**Tech Stack:** Python 3.12 stdlib; `unittest`; Markdown rule pack and skill.

**Spec:** `.planning/specs/2026-10-04-lean-rules-design.md` @ `feat/lean-rules` (workflow id `lean-rules`, `requirement_confirmed` recorded).

## Global Constraints

Copied verbatim from the spec:

- `discuss` and `plan` behavior is unchanged: they never receive the `lean` pack, and the design gate and test-first plan steps stay as they are.
- `lean` never overrides `core`, project rules, the plan, or tests the plan requires.
- No new runtime dependency.
- The pack's wording is written for gin-workflow, not copied from ponytail; the README credits ponytail.

Repository constraints:
- Test command (worktree root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`. Baseline on `feat/lean-rules` (`967e07c` + spec commits): `Ran 777 tests … OK (skipped=3)`.
- Install smoke test: `bash tests/install_smoke_test.sh` (exit 0). The PowerShell smoke test cannot run here; it needs no change.
- Git: commit on `feat/lean-rules` (worktree `.claude/worktrees/lean-rules`); never commit to `master`.

## Deviations from the spec (decided while planning; each keeps the spec's intent)

1. **README has no rules section today.** Track 2 adds a short `## Rule Packs` section before `## Notifications (Optional)`.
2. **The 1,000-char limit is keyed by pack id** in `rules.py` (`BODY_LIMITS`), not by tier, so `lean` is added to `BODY_LIMITS` explicitly.
3. **`plugins/gin-workflow/src/rules/README.md`** (the pack policy) is updated in Track 1 to say `core` and `lean` load by default and share the 1,000-char limit.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `cheap_simple`
- `override_rule`: none; no track has unresolved boundaries.

## Requirement Analysis
- Problem: nothing in the rules the developer agent and the reviewer receive pushes toward the shortest correct solution or flags over-engineering.
- Success: spec §Success criteria; Validation below.
- Constraints: Global Constraints above.
- Non-goals (spec): hooks, intensity levels, per-turn injection, debt collection, audits, benchmarks, changes to `discuss`, `plan`, or `core`.

## Approach Options
### Option 1: Own `lean` rule pack in the existing mechanism (selected in discuss)
- Pros: every harness, no Node, reaches only execute/quick/review, graded through the existing review ledger.
- Cons: wording maintained by us.
### Option 2: Install or vendor the ponytail plugin
- Cons: always-on injection conflicts with the discuss gate and TDD plan steps; Node hooks; upstream sync.
### Recommended Approach
- Option 1, as confirmed.

## Scope
- In: `plugins/gin-workflow/src/rules/lean.md` (new), `plugins/gin-workflow/src/rules/README.md`, `plugins/gin-workflow/src/scripts/workflow_core/rules.py`, `plugins/gin-workflow/src/skills/review/SKILL.md`, `README.md`, tests under `tests/workflow_core/` and `tests/workflow_providers/test_harness_packaging.py`.
- Out: installers, `core.md`, `discuss`/`plan` skills, config schema, version bumps (done at release).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Two small dependent tracks touching shared rule-pack tests; one agent in order.
```

## Tasks

### Track 1: `lean` pack loaded by default

- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: low
- **Acceptance criteria**: `lean.md` parses and stays within 1,000 body chars; `select_packs` and `--list` include `lean` by default after `core`; `rules.disabled: [lean]` removes it; `rules.packs: [lean]` adds it once; full suite and smoke test pass; independent review approved.

**Files**
- Create: `plugins/gin-workflow/src/rules/lean.md`
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/rules.py` (lines 17–19 constants; 170–176 `select_packs`; 202–205 `list_packs`)
- Modify: `plugins/gin-workflow/src/rules/README.md` (Format and Precedence lines)
- Test: `tests/workflow_core/test_rules.py` (class with `_ids`, lines 85–118; CLI tests lines 172–185), `tests/workflow_core/test_rule_packs.py` (lines 47–49), `tests/workflow_core/test_token_budget.py` (line 87), `tests/workflow_providers/test_harness_packaging.py` (rules list, lines 93–100)

**Interfaces**
- Produces: `workflow_core.rules.DEFAULT_PACKS: tuple[str, ...] = ("core", "lean")`; `BODY_LIMITS == {"core": 1_000, "lean": 1_000}`. `select_packs` and `list_packs` signatures unchanged.
- Consumed by: Track 2 (review sentence cites `lean`), `gin-workflow rules --files` callers (unchanged).

**Steps**

1. Failing selection tests. In `tests/workflow_core/test_rules.py`, in the class that defines `_ids` (after `test_unknown_pack_is_warned_not_fatal`), add:
   ```python
       def _with_lean(self):
           _pack(self.root / "rules", "lean", "id: lean\ntier: core\napplies_to: ['**/*']",
                 "- [high] `reuse-existing`: Reuse what exists.\n")
           self.plugin = load_plugin_packs(self.root / "rules")

       def test_lean_is_on_by_default_after_core(self):
           self._with_lean()
           self.assertEqual(["core", "lean"], self._ids({}, ["app/page.tsx"]))
           self.assertEqual(["python", "core", "lean"], self._ids({"rules": {"packs": ["python"]}}, ["a.py"]))
           self.assertEqual(["core", "lean"], self._ids({"rules": {"packs": ["lean"]}}, ["a.py"]))

       def test_lean_can_be_disabled(self):
           self._with_lean()
           self.assertEqual(["core"], self._ids({"rules": {"disabled": ["lean"]}}, ["a.py"]))
   ```
   Replace the two CLI tests that read the packaged packs:
   ```python
       def test_files_uses_packaged_packs_and_core_by_default(self):
           with tempfile.TemporaryDirectory() as tmp:
               result = self._run(Path(tmp), "--files", "src/a.py", "--format", "json")
               self.assertEqual(0, result.returncode, result.stderr)
               payload = json.loads(result.stdout)
               self.assertEqual(["core", "lean"], [p["id"] for p in payload["packs"]])

       def test_list_reports_sizes_and_impact_counts(self):
           with tempfile.TemporaryDirectory() as tmp:
               result = self._run(Path(tmp), "--list", "--format", "json")
               self.assertEqual(0, result.returncode, result.stderr)
               core, lean = json.loads(result.stdout)["packs"]
               self.assertEqual(("core", "plugin"), (core["id"], core["source"]))
               self.assertEqual(("lean", "plugin", 1_000), (lean["id"], lean["source"], lean["limit"]))
               self.assertFalse(lean["over_limit"])
               self.assertEqual({"critical", "high", "medium"}, set(core["impacts"]))
   ```
   In `tests/workflow_core/test_rule_packs.py` replace `test_core_applies_everywhere_and_others_are_scoped` with:
   ```python
       def test_core_and_lean_apply_everywhere_and_others_are_scoped(self):
           for name in ("core", "lean"):
               self.assertEqual(("**/*",), PACKS[name].applies_to)
               self.assertEqual("core", PACKS[name].tier)
           self.assertNotIn("**/*", [p for pack in PACKS.values() if pack.id not in ("core", "lean")
                                     for p in pack.applies_to])
   ```
   In `tests/workflow_core/test_token_budget.py` line 87 add `"lean"` to the expected pack set. In `tests/workflow_providers/test_harness_packaging.py` add `"rules/lean.md",` after `"rules/core.md",`.

2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_rules tests.workflow_core.test_rule_packs tests.workflow_core.test_token_budget tests.workflow_providers.test_harness_packaging` → expect failures: `KeyError: 'lean'` in `test_rule_packs`, `['core'] != ['core', 'lean']` in the selection and CLI tests, the pack-set mismatch, and the missing `rules/lean.md` in packaging.

3. Create `plugins/gin-workflow/src/rules/lean.md`:
   ```markdown
   ---
   id: lean
   tier: core
   applies_to: ["**/*"]
   ---
   - [high] `reuse-existing`: Reuse an existing helper, type, or pattern from the repository before writing a new one.
   - [high] `no-new-dependency`: Add no dependency for what the standard library, the platform, an installed dependency, or a few lines already do.
   - `ladder`: Prefer, in order: not building it, existing code, the standard library, a platform feature, an installed dependency, one line, then minimal new code.
   - `no-speculative`: Add no abstraction, option, or extension point without a second real use; no scaffolding for later.
   - `delete-first`: Prefer deleting or shrinking code to adding it; shortest correct diff.
   - `root-cause`: Fix a bug once in the shared code every caller goes through, not in each caller.
   - `simplified-marker`: Mark a deliberate simplification with a `simplified:` comment naming its limit and upgrade path.
   - `never-cut`: Never trim validation at trust boundaries, error handling, security, accessibility, tests the plan requires, or anything requested.

   ## Why
   - `reuse-existing`: A second copy of existing logic drifts from the first and doubles every fix.
   - `no-new-dependency`: Each dependency adds supply-chain, upgrade, and licence cost for the life of the project.
   ```

4. In `plugins/gin-workflow/src/scripts/workflow_core/rules.py`:
   - Replace `BODY_LIMITS = {"core": 1_000}` with:
     ```python
     DEFAULT_PACKS = ("core", "lean")
     BODY_LIMITS = {"core": 1_000, "lean": 1_000}
     ```
   - In `select_packs`, change the docstring to `"""Enabled packs matching `files` (+ core and lean, + requires), highest precedence first."""` and the `enabled` line to:
     ```python
         enabled = {name for name in (*DEFAULT_PACKS, *packs) if name in plugin and name not in disabled}
     ```
   - In `list_packs`, change the `enabled` line to:
     ```python
         enabled = [plugin[name] for name in dict.fromkeys((*DEFAULT_PACKS, *packs)) if name in plugin and name not in disabled]
     ```

5. In `plugins/gin-workflow/src/rules/README.md`: change `- Body ≤ 1,500 chars (\`core\` ≤ 1,000).` to `- Body ≤ 1,500 chars (\`core\` and \`lean\` ≤ 1,000).`, and add under `## Precedence` as its first line: `` `core` and `lean` load by default; `rules.disabled` in `.agent-workflow/config.yaml` turns either off. ``

6. Run the four modules from step 2 → `OK`. Then `PYTHONPATH=plugins/gin-workflow/src/scripts python3 plugins/gin-workflow/src/scripts/gin-workflow rules --list` → shows `lean (plugin, core): <n>/1000 chars; critical=0 high=2 medium=6` with no `OVER LIMIT`.

7. Full suite → `Ran 779 tests … OK (skipped=3)` (777 + 2 new selection tests; replaced and updated tests keep their count). `bash tests/install_smoke_test.sh` → exit 0. Commit: `feat(rules): add lean rule pack, on by default next to core`.

### Track 2: Review grading and README

- **Dependencies**: Track 1
- **Provider role**: `docs`
- **Reasoning**: `low`
- **Estimated complexity**: low
- **Acceptance criteria**: the review skill tells the reviewer to grade `lean` findings by impact, name the cut and its replacement, and skip `simplified:` code; README has a `## Rule Packs` section naming `lean`, how to disable it, and crediting ponytail; stage chain budgets still pass; full suite and smoke pass; independent review approved.

**Files**
- Modify: `plugins/gin-workflow/src/skills/review/SKILL.md` (Reviewing step 3, line 23)
- Modify: `README.md` (insert before `## Notifications (Optional)`, line ~109)
- Test: `tests/workflow_core/test_rule_packs.py` (new test at end of class)

**Interfaces**
- Consumes: pack id `lean` and its `high` anchors from Track 1.
- Produces: no code interface.

**Steps**

1. Failing test. Append to `TestRulePacks` in `tests/workflow_core/test_rule_packs.py`:
   ```python
       def test_review_skill_grades_lean_findings(self):
           text = (ROOT / "plugins/gin-workflow/src/skills/review/SKILL.md").read_text(encoding="utf-8")
           for phrase in ("`lean`", "`IMPORTANT`", "`MINOR`", "`simplified:`"):
               self.assertIn(phrase, text)
           readme = (ROOT / "README.md").read_text(encoding="utf-8")
           self.assertIn("## Rule Packs", readme)
           self.assertIn("https://github.com/dietrichgebert/ponytail", readme)
   ```
2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_rule_packs` → fails on `` `lean` `` not in the review skill.
3. In `plugins/gin-workflow/src/skills/review/SKILL.md`, Reviewing step 3, after `and record a \`critical\` violation at severity \`IMPORTANT\` or higher.` insert:
   ```
   Grade `lean` findings by impact: a `high` bullet at `IMPORTANT`, any other at `MINOR`; name what to cut and what replaces it, and do not flag a simplification marked `simplified:`.
   ```
4. In `README.md`, before `## Notifications (Optional)`, insert:
   ```markdown
   ## Rule Packs

   `gin-workflow rules --files <paths>` gives the `developer` agent, `/quick`, and the reviewer the best-practice rules for the files in scope. `core` and `lean` load by default; language and framework packs come from `rules.packs` in `.agent-workflow/config.yaml`, and `rules.disabled: [lean]` turns a pack off. `lean` asks for the shortest correct solution: reuse what exists, prefer the standard library, the platform, and installed dependencies, and add nothing speculative, without cutting validation, error handling, security, accessibility, or required tests. Its ideas come from [ponytail](https://github.com/dietrichgebert/ponytail) (MIT).

   ---

   ```
5. Run `tests.workflow_core.test_rule_packs` and `tests.workflow_core.test_token_budget` → `OK` (stage chain budgets hold).
6. Full suite → previous Track 1 count + 1, `OK (skipped=3)`. `bash tests/install_smoke_test.sh` → exit 0. Commit: `docs(rules): grade lean findings in review and document rule packs`.

## Integration
- **Branch**: `feat/lean-rules`
- **Merge strategy**: sequential

## Validation
- [ ] Full suite OK (Track 1 count + 1 after Track 2), smoke test exit 0.
- [ ] `gin-workflow rules --files src/a.py` in a repository with default config prints `## core (plugin)` then `## lean (plugin)`.
- [ ] With `rules: {disabled: [lean]}` in `.agent-workflow/config.yaml`, the `lean` block is gone.
- [ ] `gin-workflow rules --list` shows `lean` within 1,000 chars.
- [ ] `discuss`, `plan`, `orchestrate`, `verify`, `ship` skills still never call `gin-workflow rules` (`test_rules_injected_only_into_implement_and_review_paths`).

## Notes
- Parent Bead (epic) stays open until the human-confirmed merge; each track closes after its tests and review pass.
- Provider-neutral roles and model classes only.
