# Plan: Agent tool names for a marketplace install

Spec: `.planning/specs/2026-11-28-agent-tool-names-design.md`
Workflow: agent-tool-names (bug gin-workflow-d0ur)

## Objective

A Claude Code marketplace install can spawn every gin and gin-qa agent with its tools, every installer still gives Antigravity and Copilot their own tool names, and the source safety hook no longer blocks every Bash call when the plugin root is unknown.

**Goal:** the six source agents list Claude Code tool names; the installers map them back for Antigravity and on to Copilot; the source hook skips with a message when its script is missing.

**Architecture:** `plugins/*/src/agents/*.md` are the Claude Code form. `install.sh` and `install.ps1` stop converting them for Claude, convert them to Antigravity names after every Antigravity copy (a regular file replaces a `--link` symlink), and map Copilot names from Claude Code names. `plugins/gin-workflow/src/hooks/hooks.json` checks the script exists before running it.

**Tech Stack:** bash and sed (`install.sh`), PowerShell (`install.ps1`), JSON, Python unittest under pytest.

**Global Constraints** (from the spec):

| Claude Code | Antigravity | Copilot |
|---|---|---|
| `Read` | `view_file` | `view` |
| `Grep` | `grep_search` | `grep` |
| `Glob` | `list_dir` | `glob` |
| `WebSearch` | `search_web` | `web_fetch` |
| `Bash` | `run_command` | `bash` |
| `Edit` | `replace_file_content` | `edit` |
| `Write` | `write_to_file` | `edit` |

- Replacement matches the quoted name only (`"Read"`); in the agent files these names appear only in `tools:`.
- An installed Antigravity agent is byte for byte the agent it installs today; the source never changes during an install, `--link` included.
- Out of scope: Codex and OpenCode agents (both drop `tools:`), the hook matcher `Bash|run_command`, `docs/`.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: `.claude-plugin/marketplace.json` installs `plugins/<plugin>/src` as is; its agents list Antigravity tool names, and Claude Code 2.1.332 refuses to spawn them ("would be spawned with zero tools"). The source hook exits 2 on a missing script when neither `CLAUDE_PLUGIN_ROOT` nor `PLUGIN_ROOT` is set.
- Success criteria: every `plugins/*/src/agents/*.md` lists only Claude Code names; the Antigravity install output of each agent equals the pre-change source; the Copilot output is unchanged; the source hook exits 0 with `hook skipped` when the script is missing; the full suite and `bash tests/install_smoke_test.sh` pass.
- Constraints: both installers change the same way; `pwsh` is not available here, so `install.ps1` and `tests/install_smoke_test.ps1` are checked by the `windows` job of `test.yml`, started by hand before ship.
- Non-goals: Codex, OpenCode, the hook matcher, the bundle layout of other harnesses.

## Approach Options
### Option 1: Claude Code names in source, reverse mapping for Antigravity
- Summary: flip the six agents; replace the Claude conversion with an Antigravity conversion in both installers.
- Pros: the marketplace install works with no build step; the one-to-one mapping makes the Antigravity output provably unchanged.
- Cons: the Antigravity `--link` install gets converted files instead of symlinks.

### Option 2: keep the source, build a Claude bundle for the marketplace
- Summary: commit a generated Claude Code bundle and point `marketplace.json` at it.
- Pros: installers unchanged.
- Cons: a committed build output that drifts from the source.

### Option 3: list both name sets in `tools:`
- Summary: each agent lists Claude Code and Antigravity names.
- Pros: no installer change.
- Cons: neither harness is known to ignore unknown names; not verifiable on Antigravity.

### Recommended Approach
- Selected option: Option 1 (confirmed in /discuss).
- Rationale: matches Claude Code first; the round-trip test guards Antigravity.

## Scope
- In scope: the six source agents, `install.sh`, `install.ps1`, the source hook, `tests/workflow_core/test_agent_files.py`, `tests/workflow_core/test_harness_packaging.py`, `tests/install_smoke_test.sh`, `tests/install_smoke_test.ps1`.
- Out of scope: as in Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Track 1 (agents and installers) and Track 2 (source hook) touch disjoint files and neither consumes the other's output.
```

## Tasks
### Track 1: Claude Code tool names in source agents, installers map back
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/agents/agent-researcher.md:4` (tools line)
  - Modify `plugins/gin-workflow/src/agents/code-reviewer.md:4` (tools line)
  - Modify `plugins/gin-workflow/src/agents/developer.md:4` (tools line)
  - Modify `plugins/gin-workflow/src/agents/docs-writer.md:4` (tools line)
  - Modify `plugins/gin-workflow/src/agents/qa-agent.md:4` (tools line)
  - Modify `plugins/gin-qa/src/agents/e2e-tester.md:4` (tools line)
  - Modify `install.sh:254-288` (claude template becomes antigravity template; copilot keys) and `install.sh:524-532` (conversion call)
  - Modify `install.ps1:204-223` (Convert-ClaudeAgents becomes Convert-AntigravityAgents), `install.ps1:240-266` (copilot keys), `install.ps1:425-427` (conversion call)
  - Test `tests/workflow_core/test_agent_files.py:40-110`
  - Test `tests/install_smoke_test.sh` (antigravity dry-run block near line 279; new link block after line 413)
  - Test `tests/install_smoke_test.ps1:187-216` (link block)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change with an exact mapping table and an existing conversion pattern to mirror in each installer; no design judgement left.
- **Interfaces**:
  - Produces bash `template_agents_for_antigravity <src> <dest>` (sed, writes `<dest>`), replacing `template_agents_for_claude`.
  - Produces PowerShell `Convert-AntigravityAgents -AgentsDirectory <path>`, replacing `Convert-ClaudeAgents`.
  - `template_agents_for_copilot` and `Convert-CopilotAgents` keep their signatures; their input is Claude Code names.
- **Acceptance criteria**:
  - Every `plugins/*/src/agents/*.md` `tools:` line holds only Claude Code names, in the order of the old line.
  - `template_agents_for_antigravity` turns each source agent into exactly its pre-change content (`git show master:<path>`).
  - `dist/claude-code` agents contain `"Bash"`; `dist/antigravity` agents contain `"run_command"` and no `"Bash"`; `dist/copilot` agents keep `"view", "grep", "glob", "bash", "edit"`.
  - A `--platform both --project <dir> --link` install leaves `.claude/agents/developer.md` a symlink, makes `.agents/agents/developer.md` a regular file with Antigravity names, and leaves every source agent unchanged.
- **Estimated complexity**: medium

Steps:

1. Write the failing unit tests. In `tests/workflow_core/test_agent_files.py`, replace `test_agent_tools_declared` and `test_claude_template_agents_maps_tools_for_developer` with:

   ```python
   CLAUDE_TO_ANTIGRAVITY = {
       "Read": "view_file",
       "Grep": "grep_search",
       "Glob": "list_dir",
       "WebSearch": "search_web",
       "Bash": "run_command",
       "Edit": "replace_file_content",
       "Write": "write_to_file",
   }

   def _tools(path: Path) -> list[str]:
       m = re.search(r"^tools:\s*(\[[^\]]+\])", path.read_text(encoding="utf-8"), re.MULTILINE)
       assert m, f"{path} missing tools declaration"
       return re.findall(r'"([^"]+)"', m.group(1))

   def _sed_args(function: str) -> list[str]:
       body = re.search(function + r"\(\)\s*\{([\s\S]*?)\n\}", (ROOT / "install.sh").read_text(encoding="utf-8"))
       assert body, f"{function} not found in install.sh"
       args = []
       for flag in re.findall(r"-e\s+('[^']+'|\"[^\"]+\")", body.group(1)):
           args.extend(["-e", flag[1:-1]])
       return args
   ```

   (module level, after `ROOT`), and in the test class:

   ```python
   def test_source_agents_list_claude_code_tool_names(self):
       agents = sorted(ROOT.glob("plugins/*/src/agents/*.md"))
       self.assertTrue(agents)
       for path in agents:
           with self.subTest(agent=path.relative_to(ROOT).as_posix()):
               tools = _tools(path)
               self.assertTrue(tools)
               self.assertLessEqual(set(tools), set(CLAUDE_TO_ANTIGRAVITY))

   def test_agent_tools_declared(self):
       agents = ROOT / "plugins/gin-workflow/src/agents"
       self.assertLessEqual({"Edit", "Write"}, set(_tools(agents / "developer.md")))
       self.assertIn("Bash", _tools(agents / "agent-researcher.md"))
       self.assertLessEqual({"Bash", "Edit", "Write"}, set(_tools(agents / "docs-writer.md")))
       self.assertIn("Glob", _tools(agents / "code-reviewer.md"))

   @unittest.skipIf(os.name == "nt", "runs the install.sh expressions through sed, a POSIX tool")
   def test_antigravity_template_round_trips_every_source_agent(self):
       forward = _sed_args("template_agents_for_antigravity")
       self.assertEqual(len(CLAUDE_TO_ANTIGRAVITY), len(forward) // 2)
       inverse = []
       for claude, antigravity in CLAUDE_TO_ANTIGRAVITY.items():
           inverse.extend(["-e", f's/"{antigravity}"/"{claude}"/g'])
       for path in sorted(ROOT.glob("plugins/*/src/agents/*.md")):
           source = path.read_text(encoding="utf-8")
           with self.subTest(agent=path.relative_to(ROOT).as_posix()):
               converted = subprocess.run(["sed", *forward], input=source, text=True,
                                          capture_output=True, check=True).stdout
               for claude, antigravity in CLAUDE_TO_ANTIGRAVITY.items():
                   self.assertNotIn(f'"{claude}"', converted)
               self.assertIn('"run_command"', converted)
               back = subprocess.run(["sed", *inverse], input=converted, text=True,
                                     capture_output=True, check=True).stdout
               self.assertEqual(source, back)

   @unittest.skipIf(os.name == "nt", "runs the install.sh expressions through sed, a POSIX tool")
   def test_copilot_template_maps_claude_code_names(self):
       source = (ROOT / "plugins/gin-workflow/src/agents/developer.md").read_text(encoding="utf-8")
       converted = subprocess.run(["sed", *_sed_args("template_agents_for_copilot")], input=source, text=True,
                                  capture_output=True, check=True).stdout
       self.assertIn('tools: ["view", "grep", "glob", "bash", "edit"]', converted)
   ```

   Keep the other tests of the file.

2. Run: `python3 -m pytest tests/workflow_core/test_agent_files.py -q`. Expected: the four new tests fail (Antigravity names in source; `template_agents_for_antigravity not found`; Copilot output still holds `"Read"`).

3. Flip the six `tools:` lines, keeping order:
   - `agent-researcher.md`: `tools: ["Read", "Grep", "Glob", "WebSearch", "Bash"]`
   - `code-reviewer.md`: `tools: ["Read", "Grep", "Glob", "Bash"]`
   - `developer.md`: `tools: ["Read", "Grep", "Glob", "Bash", "Edit", "Write"]`
   - `docs-writer.md`: `tools: ["Read", "Grep", "Glob", "Bash", "Edit", "Write"]`
   - `qa-agent.md`: `tools: ["Read", "Grep", "Bash"]`
   - `plugins/gin-qa/src/agents/e2e-tester.md`: `tools: ["Read", "Grep", "Glob", "Bash", "Write", "Edit"]`

4. `install.sh`: replace `template_agents_for_claude` with

   ```bash
   template_agents_for_antigravity() {
     local src="$1"
     local dest="$2"
     sed -e 's/"Read"/"view_file"/g' \
         -e 's/"Grep"/"grep_search"/g' \
         -e 's/"Glob"/"list_dir"/g' \
         -e 's/"WebSearch"/"search_web"/g' \
         -e 's/"Bash"/"run_command"/g' \
         -e 's/"Edit"/"replace_file_content"/g' \
         -e 's/"Write"/"write_to_file"/g' \
         "$src" > "$dest"
   }
   ```

   In `template_agents_for_copilot`, change the seven keys: `"Read"`→`"view"`, `"Grep"`→`"grep"`, `"Glob"`→`"glob"`, `"WebSearch"`→`"web_fetch"`, `"Bash"`→`"bash"`, `"Edit"`→`"edit"`, `"Write"`→`"edit"`; keep the `:a`/`ta` merge. In `install_platform`, replace the `if [ "$platform" = "claude" ]` agent loop with the same loop under `if [ "$platform" = "antigravity" ]` calling `template_agents_for_antigravity`, with `rm -f "$f"` before `mv "$tmp_file" "$f"` as in the Codex loop.

5. Run: `python3 -m pytest tests/workflow_core/test_agent_files.py -q`. Expected: all pass.

6. `install.ps1`: rename `Convert-ClaudeAgents` to `Convert-AntigravityAgents` and reverse its seven `Replace` calls (`'"Read"'`→`'"view_file"'`, `'"Grep"'`→`'"grep_search"'`, `'"Glob"'`→`'"list_dir"'`, `'"WebSearch"'`→`'"search_web"'`, `'"Bash"'`→`'"run_command"'`, `'"Edit"'`→`'"replace_file_content"'`, `'"Write"'`→`'"write_to_file"'`); keep its `$Link`/`LinkType` removal. In `Convert-CopilotAgents`, change the seven keys as in step 4. In `Install-PlatformLayout`, replace `if ($Harness -eq 'claude') { Convert-ClaudeAgents ... }` with `if ($Harness -eq 'antigravity') { Convert-AntigravityAgents -AgentsDirectory (Join-Path $Destination 'agents') }`. Then `grep -n 'Convert-ClaudeAgents\|view_file' install.ps1` must list only `Convert-AntigravityAgents` lines.

7. `tests/install_smoke_test.sh`: after the `./install.sh --platform antigravity --dry-run` asserts add

   ```bash
   assert_contains "plugins/gin-workflow/dist/antigravity/agents/developer.md" '"run_command"'
   assert_not_contains "plugins/gin-workflow/dist/antigravity/agents/developer.md" '"Bash"'
   assert_contains "plugins/gin-workflow/dist/claude-code/agents/developer.md" '"Bash"'
   ```

   and after the OpenCode `--link` block (line ~413) add

   ```bash
   # A --link project install links Claude agents and converts Antigravity ones without touching source.
   link_project="$MOCK_HOME/link-project"
   mkdir -p "$link_project" "$MOCK_HOME/link-home"
   source_sum="$(cat plugins/*/src/agents/*.md | cksum)"
   HOME="$MOCK_HOME/link-home" ./install.sh --platform both --project "$link_project" --link >/dev/null
   [ -L "$link_project/.claude/agents/developer.md" ] || { echo "Claude agent is not a symlink" >&2; exit 1; }
   [ ! -L "$link_project/.agents/agents/developer.md" ] || { echo "Antigravity agent is still a symlink" >&2; exit 1; }
   assert_contains "$link_project/.agents/agents/developer.md" '"run_command"'
   assert_not_contains "$link_project/.agents/agents/developer.md" '"Bash"'
   [ "$source_sum" = "$(cat plugins/*/src/agents/*.md | cksum)" ] || { echo "Install changed a source agent" >&2; exit 1; }
   ```

8. `tests/install_smoke_test.ps1` link block: install with `Platform = 'both'`; drop the `'Templated Claude agent remained a source symlink'` assertion; keep `Assert-Contains $linkedContent '"Read"'` and replace the `'Claude agent was not templated'` check with one that `$linkedContent` has no `'"view_file"'`; add for `Join-Path $linkProject '.agents/agents/developer.md'`: `LinkType` is `$null`, content contains `'"view_file"'`, content has no `'"Read"'`. Keep the source snapshot asserts.

9. Run: `bash tests/install_smoke_test.sh`. Expected: exit 0. Run: `python3 -m pytest -n auto -q tests/workflow_core`. Expected: all pass.

10. Commit: `fix(agents): source agents use Claude Code tool names; installers map back (gin-workflow-d0ur)`.

### Track 2: Source hook skips when its script is missing
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/hooks/hooks.json:10` (command)
  - Test `tests/workflow_core/test_harness_packaging.py:228-242`
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** one shell line with a given replacement and one test that mirrors the existing one.
- **Interfaces**: the hook command reads the same variables; stdout/exit of `safety_check.py` unchanged when the script exists.
- **Acceptance criteria**:
  - With neither `CLAUDE_PLUGIN_ROOT` nor `PLUGIN_ROOT` set, the command exits 0 and stderr contains `hook skipped`.
  - With either variable set to `plugins/gin-workflow/src`, `ls` exits 0 and `rm -rf /` exits 2 (existing test).
- **Estimated complexity**: low

Steps:

1. In `test_marketplace_hook_finds_the_script_under_claude_code_and_codex`, after the loop add:

   ```python
           missing = subprocess.run(["bash", "-c", pre], input=json.dumps(danger), capture_output=True,
                                    text=True, env=base)
           self.assertEqual(0, missing.returncode, missing.stderr)
           self.assertIn("hook skipped", missing.stderr)
   ```

2. Run: `python3 -m pytest tests/workflow_core/test_harness_packaging.py -q -k marketplace_hook`. Expected: fails (exit 2).

3. Set the command in `plugins/gin-workflow/src/hooks/hooks.json` to (JSON-escaped):

   ```
   s="${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/scripts/safety_check.py"; if [ ! -f "$s" ]; then echo "gin: $s not found, hook skipped" >&2; exit 0; fi; if command -v python3 >/dev/null 2>&1; then exec python3 "$s"; fi; exec python "$s"
   ```

4. Run the step 2 command. Expected: pass. Run: `python3 -m pytest -n auto -q tests/workflow_core/test_harness_packaging.py`. Expected: all pass.

5. Commit: `fix(hooks): source hook skips with a message when its script is missing (gin-workflow-d0ur)`.

## Integration
- **Branch**: feat/agent-tool-names
- **Merge strategy**: parallel-then-merge

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `bash tests/install_smoke_test.sh` exits 0
- [ ] `test.yml` started by hand on the branch; its `windows` job (`tests/install_smoke_test.ps1`) passes
- [ ] Manual: `claude -p --plugin-dir <copy of plugins/gin-workflow/src>` spawns `developer` without the "zero tools" refusal

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- The Parent Bead stays open until the human-confirmed merge; track beads close after tests and review pass.
