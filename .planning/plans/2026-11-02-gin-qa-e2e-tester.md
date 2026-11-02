# Plan: gin-qa e2e tester subagent

Spec: `.planning/specs/2026-11-02-gin-qa-e2e-tester-design.md`
Workflow: gin-qa-e2e-tester

## Objective

`/gin-qa:e2e` hands each `Type: e2e` case to a named, cheap agent, `gin-qa:e2e-tester`, at the middle model and `low` effort, instead of an unnamed subagent that inherits the main session's model. The agent file ships in the gin-qa plugin, the skill names it, the docs and smoke tests know it, and gin-qa moves to 0.5.0.

## Architecture

gin-qa is a plugin under `plugins/gin-qa/src/` with `skills/`, `scripts/`, and `templates/`. `install.sh` (`copy_src`, lines 268-330) and `install.ps1` (line 88) copy any plugin's `agents/` directory into `plugins/<plugin>/dist/<platform>/agents/`; for the `claude` platform both rewrite the harness-neutral tool names in the frontmatter (`install.sh:178-188`, `install.ps1:172`). Agents are markdown files with `name`, `description`, and `tools` frontmatter (`plugins/gin-workflow/src/agents/qa-agent.md:1-5`). The route (model tier and effort) is written in the skill that spawns the agent, never in the agent file (`docs/concepts/providers.md:28`).

## Tech Stack

Markdown skill and agent files, JSON plugin manifests, bash and PowerShell smoke tests, Python `unittest` (`tests/gin_qa/test_packaging.py`).

## Global Constraints

Copied from the spec:

- `/gin-qa:cases` is out of scope: it spawns no subagents.
- `explore-case.md`, the fixture, the `gin-qa` CLI, and `install.sh` do not change.
- No automatic model escalation for a `blocked` case: it stays reported, not retried.
- The agent file has no `model:` or `effort:` key; tier words follow `docs/concepts/providers.md:28`, and no concrete model name appears in the skill or agent.
- The agent writes only the case's spec file, never commits, never edits the fixture, the guidelines, the test cases, or another spec, and never changes the application.
- The agent's output is exactly one line: `<TC-ID> done|app_defect|blocked <run folder> <reason>`.

Found while planning (tests that gate this change):

- `tests/gin_qa/test_packaging.py:21-28`: the three gin-qa manifests must agree on `version`.
- `tests/gin_qa/test_packaging.py:32-43`: `skills/e2e/SKILL.md` stays at most 6,000 characters (3,212 today) and its markdown links stay exactly two `references/explore-case.md`; the summed `description:` of every skill and agent under `plugins/gin-qa/src` stays at most 1,000 characters (386 today).
- `tests/workflow_core/test_docs_coverage.py:77`: no `telegram.sh` or `telegram-notify` in `plugins/*/src/agents/*.md`.
- `tests/workflow_core/test_docs_coverage.py:93-98`: `docs/**/*.md` follow the style rules (no em or en dash, no bold-label list item, no emoji, no numbered heading).

## Route Rubric

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis

- Problem statement: `skills/e2e/SKILL.md:15` says "give each case to one subagent" with no agent, model, or effort, so Claude Code spawns `general-purpose` at the session model (Opus in gin-console) per case.
- Success criteria: the skill names `gin-qa:e2e-tester` at the middle model and `low` effort; the installed Claude copy of the agent exists with `"Read"`, `"Grep"`, `"Glob"`, `"Bash"`, `"Write"`, `"Edit"`; the run report shape is unchanged; packaging and smoke tests pass.
- Constraints: the Global Constraints above.
- Non-goals: `/gin-qa:cases`, `explore-case.md`, the CLI, the installers, escalation.

## Approach Options

### Option 1: agent file plus skill text (the spec's design)
- Summary: add `plugins/gin-qa/src/agents/e2e-tester.md`; step 4 of the skill names it with the route.
- Pros: a named role every harness can route; bounded tool set; no installer change; matches how every other skill spawns.
- Cons: one more file to keep under the description budget.

### Option 2: skill text only
- Summary: keep `general-purpose` and add "middle model, `low` effort" to step 4.
- Pros: one-line diff.
- Cons: no role prompt or write boundary; other harnesses have no named agent; the spec was confirmed with the agent.

### Recommended Approach
- Selected option: Option 1.
- Rationale: it is what the confirmed spec requires, and the cost over Option 2 is one 40-line file.

## Scope

- In scope: the agent file, step 4 of the `e2e` skill, one sentence in `docs/reference/skills.md`, one sentence in `docs/guides/qa.md`, the version bump in three manifests, and the smoke-test asserts.
- Out of scope: everything under Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One track; every file changes together and is proven by one test cycle.
```

## Tasks

### Track 1: e2e-tester agent, skill route, docs, version, smoke tests
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-qa/src/agents/e2e-tester.md`
  - Modify `plugins/gin-qa/src/skills/e2e/SKILL.md:15` (step 4 names the agent and route)
  - Modify `docs/reference/skills.md:66` (one sentence after the gin-qa table)
  - Modify `docs/guides/qa.md:46` (the parallel sentence names the agent and route)
  - Modify `plugins/gin-qa/plugin.meta.json:3`, `plugins/gin-qa/src/.claude-plugin/plugin.json:3`, `plugins/gin-qa/src/.codex-plugin/plugin.json:3` (version 0.5.0)
  - Test `tests/install_smoke_test.sh:194` (agent asserts)
  - Test `tests/install_smoke_test.ps1:74` (agent assert)
  - Test `tests/gin_qa/test_packaging.py` (unchanged; proves manifests and budgets)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** every edit is spelled out below, so no design judgement is left; the middle model rather than the weakest because the agent body is a prompt another model will follow and its wording must stay exact; `low` because there is no intricate logic.
- **Acceptance criteria**:
  - `plugins/gin-qa/src/skills/e2e/SKILL.md` step 4 contains `gin-qa:e2e-tester`, `middle model`, and `` `low` ``.
  - `plugins/gin-qa/dist/claude-code/agents/e2e-tester.md` exists after `./install.sh --platform claude --plugin gin-qa --dry-run` and contains `"Bash"` and not `"run_command"`.
  - `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.gin_qa.test_packaging tests.workflow_core.test_docs_coverage` prints `OK`.
  - `bash tests/install_smoke_test.sh` exits 0.
- **Estimated complexity**: low

#### Steps

1. **Failing smoke test first.** Edit `tests/install_smoke_test.sh`. Line 190 (`launcher version 0.4`) stays: that string comes from `QA_LAUNCHER_VERSION` in `install.sh:13` and `install.ps1:18`, which is independent of the plugin manifest version (gin-workflow's launcher is 2.9 while its manifest is 2.1.1) and out of scope. After line 194 (`assert_exists "plugins/gin-qa/dist/claude-code/skills/e2e/references/explore-case.md"`) insert:

   ```bash
   assert_exists "plugins/gin-qa/dist/claude-code/agents/e2e-tester.md"
   assert_contains "plugins/gin-qa/dist/claude-code/agents/e2e-tester.md" '"Bash"'
   assert_not_contains "plugins/gin-qa/dist/claude-code/agents/e2e-tester.md" '"run_command"'
   ```

   Edit `tests/install_smoke_test.ps1`. Line 71 (`launcher version 0.4`) stays for the same reason. After line 74 (`Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/skills/e2e/references/explore-case.md')`) insert:

   ```powershell
       Assert-Exists (Join-Path $Root 'plugins/gin-qa/dist/codex/agents/e2e-tester.md')
   ```

   Run `bash tests/install_smoke_test.sh`. Expected: exit 1 with `Expected path to exist: plugins/gin-qa/dist/claude-code/agents/e2e-tester.md` on stderr. `pwsh` is not installed on this machine and there is no Windows CI yet, so the `.ps1` change is proven by review only.

2. **Version bump.** In `plugins/gin-qa/plugin.meta.json`, `plugins/gin-qa/src/.claude-plugin/plugin.json`, and `plugins/gin-qa/src/.codex-plugin/plugin.json`, change `"version": "0.4.0"` to `"version": "0.5.0"`. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.gin_qa.test_packaging`. Expected: `OK`. Run `bash tests/install_smoke_test.sh`. Expected: exit 1 with `Expected path to exist: plugins/gin-qa/dist/claude-code/agents/e2e-tester.md`.

3. **Agent file.** Create `plugins/gin-qa/src/agents/e2e-tester.md` with this content:

   ````markdown
   ---
   name: e2e-tester
   description: Builds and verifies one Playwright spec for a `Type: e2e` test case against the running application.
   tools: ["view_file", "grep_search", "list_dir", "run_command", "write_to_file", "replace_file_content"]
   ---

   # E2E Tester

   You turn one `Type: e2e` test case into a passing Playwright spec with per-step evidence. The `e2e` skill dispatches you with one case; the main session plans the work, reruns the final check, and reports.

   ## Inputs

   The dispatcher sends you three things and nothing else:

   1. The case's `plan` row: TC-ID, title, steps, expected, and the `spec` path.
   2. The path of the guidelines file.
   3. The path of `explore-case.md`.

   Read the guidelines and `explore-case.md` before anything else. The guidelines (locators, sign-in, test data) override the reference.

   ## Work

   Follow the loop in `explore-case.md` exactly: write step 1 only, run `gin-qa e2e run <TC-ID> --format json`, read `result.json` and the last step's `NN.aria.yml` and `url`, take the next step's locator from that snapshot and confirm it in the UI source, add the `Expected` assertions, run again until every case step is in the spec, `gin-qa e2e pin <TC-ID>`, run once more, then open every `NN.png` and confirm it shows what its step title says. Spec defects (locator, timing, navigation, wrong screen) get at most 3 fix rounds after the spec is complete. All commands are `gin-qa e2e <command>`.

   ## Boundary

   - Write only the case's spec file, at its `spec` path.
   - Never commit. Never edit the fixture (`evidence.ts`), the guidelines, the test cases, another spec, or the application.
   - Never bend the spec to pass: when the application does not do what `Expected` says, the outcome is `app_defect`.
   - Never wait with `waitForTimeout`; assert with auto-waiting `expect(...)`.

   ## Output

   Return exactly one line and nothing after it:

   `<TC-ID> done|app_defect|blocked <run folder> <reason>`

   - `done`: the last run passed and the screenshot review found nothing.
   - `app_defect`: name the step, its error, and the screenshot and snapshot paths.
   - `blocked`: the reason (the `baseURL` cannot be reached, no access, 3 rounds used up, or a step the UI cannot perform).
   ````

   Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -c "from workflow_core.budget import description_chars; print(description_chars('plugins/gin-qa/src'))"`. Expected: `486` (386 plus 100; any value at most 1000 passes). Run `bash tests/install_smoke_test.sh`. Expected: exit 0.

4. **Skill step 4.** In `plugins/gin-qa/src/skills/e2e/SKILL.md` line 15, replace

   ```
      - When the platform has subagents, give each case to one subagent, at most N at a time. Send it the `plan` row, the guidelines path, and the path of `explore-case.md`; nothing else from this conversation. Otherwise work through the cases one by one yourself.
   ```

   with

   ```
      - When the platform has subagents, give each case to `gin-qa:e2e-tester` at the middle model and `low` effort, at most N at a time. Send it the `plan` row, the guidelines path, and the path of `explore-case.md`; nothing else from this conversation. Otherwise work through the cases one by one yourself.
   ```

   No markdown link is added (the packaging test counts links). Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.gin_qa.test_packaging`. Expected: `OK`.

5. **Docs.** In `docs/reference/skills.md`, after the gin-qa table (line 66, the `e2e` row) and before `## gin-orchestrator (optional add-on)`, insert a blank line and:

   ```markdown
   Where the harness has subagents, `e2e` gives each case to the add-on's `e2e-tester` agent at the middle model and `low` effort.
   ```

   In `docs/guides/qa.md` line 46, replace the sentence `Where the harness has subagents it works on several cases in parallel (`--parallel N`, default 3).` with:

   ```markdown
   Where the harness has subagents it gives each case to the `gin-qa:e2e-tester` agent at the middle model and `low` effort, several cases at a time (`--parallel N`, default 3).
   ```

   Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage`. Expected: `OK`.

6. **Full check and commit.** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` (the configured `verify.checks.test`). Expected: `OK` with no failures. Run `bash tests/install_smoke_test.sh`. Expected: exit 0. Commit on the track branch:

   ```
   feat(gin-qa): e2e-tester agent runs each case at the middle model, low effort
   ```

## Integration

- **Branch**: `feat/gin-qa-e2e-tester`
- **Merge strategy**: sequential

## Validation

- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` prints `OK`
- [ ] `bash tests/install_smoke_test.sh` exits 0
- [ ] `plugins/gin-qa/dist/claude-code/agents/e2e-tester.md` lists `"Read"`, `"Grep"`, `"Glob"`, `"Bash"`, `"Write"`, `"Edit"`
- [ ] Manual, after `./install.sh --plugin gin-qa` in gin-console: `/gin-qa:e2e <capability>` with two `missing` cases spawns `gin-qa:e2e-tester` at the middle model and `low` effort, and each case ends `done`, `app_defect`, or `blocked` with the usual report

## Notes

- `Model:` and `Effort:` come from the Claude catalog (`haiku`, `sonnet`, `opus`; `low` to `max`).
- The parent bead stays open until the user confirms the merge; the track bead closes when its tests and review pass.
- The `.ps1` smoke test cannot run here (no `pwsh`) and there is no Windows CI yet; its two-line change is reviewed, not run.
