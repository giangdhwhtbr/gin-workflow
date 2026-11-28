# Agent tool names for a marketplace install

Workflow: agent-tool-names
Kind: technical
Points: 3 (6 agent files, 2 installers including Windows, 1 hook line, 4 test files; low: the name mapping is one to one)
Status: draft for user review.

## Goal and scope

Bug gin-workflow-d0ur, split from gin-workflow-6ujv. `.claude-plugin/marketplace.json` installs `plugins/gin-workflow/src` and `plugins/gin-qa/src` as they are. Their agents list Antigravity tool names in `tools:` (`view_file`, `grep_search`, `list_dir`, `search_web`, `run_command`, `replace_file_content`, `write_to_file`); only `install.sh` and `install.ps1` rewrite them to Claude Code names. Claude Code 2.1.332 refuses such an agent: "would be spawned with zero tools". A marketplace install therefore cannot run `gin:developer`, `gin:code-reviewer`, `gin:agent-researcher`, `gin:docs-writer`, `gin:qa-agent`, or `gin-qa:e2e-tester`.

Second, from the review of gin-workflow-6ujv: `src/hooks/hooks.json` runs `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/scripts/safety_check.py`. With neither variable set, python exits 2 on a missing file and every Bash call is blocked; the Copilot hook skips with a message instead.

In scope:

- The six source agents list Claude Code tool names.
- Both installers map them back to Antigravity names for Antigravity, including `--link`, and map Copilot names from Claude Code names.
- The source hook skips with a message when the script is missing.

Out of scope: the Codex and OpenCode agents (both drop `tools:`), the hook matcher `Bash|run_command`, the bundle layout of the other harnesses (deferred with gin-workflow-harness-convergence), `docs/` (no page names these tools).

## Approach

The two name sets map one to one:

| Claude Code | Antigravity | Copilot |
|---|---|---|
| `Read` | `view_file` | `view` |
| `Grep` | `grep_search` | `grep` |
| `Glob` | `list_dir` | `glob` |
| `WebSearch` | `search_web` | `web_fetch` |
| `Bash` | `run_command` | `bash` |
| `Edit` | `replace_file_content` | `edit` |
| `Write` | `write_to_file` | `edit` |

1. **Source agents.** `plugins/gin-workflow/src/agents/{agent-researcher,code-reviewer,developer,docs-writer,qa-agent}.md` and `plugins/gin-qa/src/agents/e2e-tester.md` list Claude Code names in `tools:`, in the same order.
2. **Claude.** `template_agents_for_claude` (`install.sh`) and `Convert-ClaudeAgents` (`install.ps1`) are removed with their calls. A `--link` Claude install links the agents like the skills.
3. **Antigravity.** New `template_agents_for_antigravity` (`install.sh`) and `Convert-AntigravityAgents` (`install.ps1`) replace each quoted Claude Code name with its Antigravity name. They run after the copy in every Antigravity install. Under `--link` they write a regular file in place of the symlink, as the Claude conversion does today (`mv` over the link in `install.sh`; remove the link first in `install.ps1`), so the source never changes. Because the mapping is one to one, an installed Antigravity agent is byte for byte the agent it installs today.
4. **Copilot.** `template_agents_for_copilot` and `Convert-CopilotAgents` read Claude Code names; the merge of duplicate `"edit"` stays.
5. **Hook.** The `src/hooks/hooks.json` command checks the script exists; when it does not, it prints `gin: <path> not found, hook skipped` to stderr and exits 0, like the Copilot hook. When it exists, the hook runs as today.

Replacement matches the quoted name only (`"Read"`); in the agent files these names appear only in `tools:`.

## Risks and rollback

- A missing-script hook now lets a Bash call through unchecked instead of blocking it. That state only arises when the plugin root is unknown, where blocking every call made the plugin unusable; the message keeps it visible.
- An earlier `--link` Claude install holds regular agent files; the next install replaces them with links, as for skills.
- Antigravity behaviour rests on the reverse mapping; the round-trip test guards it, and Antigravity itself is not run here.
- Rollback: revert the merge commit and re-run the installer.

## Testing

- `tests/workflow_core/test_agent_files.py`: every agent under `plugins/*/src/agents/` lists only Claude Code names; the existing per-agent assertions use Claude Code names; the `install.sh` Antigravity expressions, run through `sed`, turn each source agent into Antigravity names with no Claude Code name left, and applying the inverse yields the source again.
- `tests/workflow_core/test_harness_packaging.py`: with neither `CLAUDE_PLUGIN_ROOT` nor `PLUGIN_ROOT` set, the source hook exits 0 and prints `hook skipped`; the existing test for both variables still passes.
- `tests/install_smoke_test.sh` and `tests/install_smoke_test.ps1`: the Claude agents contain `"Bash"` and no `"run_command"`; the Antigravity agents contain `"run_command"` and no `"Bash"`; the Copilot assertions hold unchanged; under `--link` the Antigravity agent is a regular file and the source agents are unchanged.
- Full suite `python3 -m pytest -n auto` at push.

## Open Technical Questions
