# gin-qa e2e tester: a cheap subagent per Playwright case

Workflow: gin-qa-e2e-tester
Status: draft for user review.

## Goal and scope

`/gin-qa:e2e` stops spending the main session's model on each test case. Today step 4 of `plugins/gin-qa/src/skills/e2e/SKILL.md:15` says only "give each case to one subagent", so on Claude Code the main session spawns `general-purpose`, which inherits the session model (Opus in gin-console) at the default effort, once per case and up to `--parallel` at a time. Every other skill in this repository names a role and a tier when it spawns (`discuss/SKILL.md:20`, `plan/SKILL.md:22`, `tech-doc/SKILL.md:16-18`); gin-qa has no `agents/` directory at all.

In scope:
- A new agent `gin-qa:e2e-tester` that runs the procedure in `skills/e2e/references/explore-case.md` for one case.
- Step 4 of the `e2e` skill names that agent at the middle model and `low` effort.
- Documentation, smoke-test assertions, and the gin-qa version bump.

Out of scope:
- `/gin-qa:cases`: it spawns no subagents (`skills/cases/SKILL.md` has no parallel or subagent step).
- Changing `explore-case.md`, the fixture, the `gin-qa` CLI, or `install.sh`: `install.sh:289-294` already copies any plugin's `agents/` and `install.sh:376-382` maps the tool names for Claude.
- Automatic model escalation for a `blocked` case: it stays reported, not retried, as step 7 of the skill already says.

## Requirements

### R1. Agent file `plugins/gin-qa/src/agents/e2e-tester.md`
Frontmatter follows the gin-workflow agents (`plugins/gin-workflow/src/agents/qa-agent.md:1-5`): `name: e2e-tester`, a one-line `description`, and `tools: ["view_file", "grep_search", "list_dir", "run_command", "write_to_file", "replace_file_content"]`. No `model:` or `effort:` key: the route lives in the skill text, as for every other agent, and `install.sh` rewrites the tool names per harness.

The body is short and defers to `explore-case.md`:
- Inputs: one `plan` row (TC-ID, title, steps, expected, `spec` path), the guidelines path, and the path of `explore-case.md`. The agent reads those two files first; the guidelines override the reference.
- Work: the loop in `explore-case.md` (one step per run, locators from the ARIA snapshot, `pin`, screenshot review, at most 3 fix rounds after the spec is complete). All commands are `gin-qa e2e <command>`.
- Boundary: writes only the case's spec file. Never commits, never edits the fixture, the guidelines, the test cases, or another spec, and never changes the application to make a step pass.
- Output: exactly one line, `<TC-ID> done|app_defect|blocked <run folder> <reason>`, with the meanings defined in `explore-case.md`.

The file stays under the 4,000-token budget that `tests/workflow_core/test_token_budget.py:162` applies to gin-workflow agents, and contains no `telegram.sh` or `telegram-notify` (`test_docs_coverage.py:77` scans `plugins/*/src/agents/*.md`).

### R2. Step 4 of the `e2e` skill names the agent and its route
`skills/e2e/SKILL.md` step 4 replaces "give each case to one subagent" with: give each case to `gin-qa:e2e-tester` at the middle model and `low` effort, at most N at a time. The message to the agent is unchanged: the `plan` row, the guidelines path, and the path of `explore-case.md`, nothing else from the conversation. The fallback without subagents (work through the cases one by one) and "a failed or blocked case does not stop the others" stay. Tier words follow `docs/concepts/providers.md:28`; no concrete model name appears.

### R3. Documentation
`docs/reference/skills.md:63-66` gets one sentence under gin-qa naming `e2e-tester` as the agent the `e2e` skill spawns per case, at the middle model and `low` effort. `docs/guides/qa.md:46` ("Where the harness has subagents it works on several cases in parallel") names `gin-qa:e2e-tester` and its route in that sentence.

### R4. Smoke tests
`tests/install_smoke_test.sh` adds `assert_exists "plugins/gin-qa/dist/claude-code/agents/e2e-tester.md"` next to the gin-qa asserts at lines 191-196, and a check that the installed copy names `"Bash"` rather than `"run_command"` (the Claude tool mapping ran). `tests/install_smoke_test.ps1` adds the matching existence assert for its gin-qa platform.

### R5. Version
gin-qa goes to `0.5.0` in `plugins/gin-qa/plugin.meta.json`, `src/.claude-plugin/plugin.json`, and `src/.codex-plugin/plugin.json`. The launcher-version asserts (`tests/install_smoke_test.sh:190`, `tests/install_smoke_test.ps1:71`) stay at `0.4`: that string comes from `QA_LAUNCHER_VERSION` in the installers, which is independent of the manifest version and out of scope.

## User Stories

### US-1: Specs written by a cheap agent
As a gin-qa user running `/gin-qa:e2e <capability>` on Claude Code, I want each case written by `gin-qa:e2e-tester` at the middle model and `low` effort, so that a run of many cases no longer costs Opus tokens per case.

Acceptance criteria:
- `plugins/gin-qa/src/skills/e2e/SKILL.md` step 4 names `gin-qa:e2e-tester`, "middle model", and `low`.
- After `install.sh --platform claude --plugin gin-qa`, `plugins/gin-qa/dist/claude-code/agents/e2e-tester.md` exists and its `tools` list reads `"Read"`, `"Grep"`, `"Glob"`, `"Bash"`, `"Write"`, `"Edit"`.
- The agent's result line and the main session's steps 5 to 8 are unchanged, so a run produces the same report shape as before.

### US-2: Agent scope is bounded
As the owner of a QA folder, I want the tester to touch only its case's spec file, so that a parallel run cannot corrupt the fixture, the guidelines, or another case's spec.

Acceptance criteria:
- `e2e-tester.md` states the write boundary (one spec file) and the no-commit rule.
- Step 5 of the skill (git status comparison) still catches any other change.

## Errors and compatibility

- A harness without subagents is unaffected: the skill's fallback branch runs the cases in the main session as today.
- A harness that ignores the `tools` frontmatter gets the same agent with its default tools; the body's boundary still applies.
- A case that ends `blocked` is reported with its reason; the main session does not rerun it at a stronger model.
- Repositories installed before this change get the agent on the next `install.sh` run; until then the skill text names an agent the harness does not know, and Claude Code reports an unknown agent type, which the user fixes by reinstalling. The `e2e` skill's precondition step already tells the user to reinstall when `gin-qa` is missing, so no new message is needed.

## Testing

- `bash tests/install_smoke_test.sh` passes with the new asserts (R4, R5).
- `python3 -m pytest tests/workflow_core/test_docs_coverage.py tests/gin_qa -q` passes.
- Manual: in gin-console, run `/gin-qa:e2e <capability>` with two `missing` cases and confirm in the Claude Code task list that the spawned agents are `gin-qa:e2e-tester` at the middle model and `low` effort, and that both cases end `done`, `app_defect`, or `blocked` with the usual report.
