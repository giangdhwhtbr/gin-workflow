# Code Review — `agent-plugin` (commit `b7de0f8` "feat: add agent-plugin")

Scope: the full `agent-plugin/` addition — `install.sh`, `plugin.meta.json`, `src/hooks/hooks.json`, all `src/scripts/*.sh`, and the `src/{commands,skills,agents}/*.md` content. The `dist/` tree is a generated copy of `src/` and is reviewed via `src/`.

Findings are ranked **most-severe first**. Each has a concrete failure scenario and a step-by-step fix. Severity key: 🔴 Critical · 🟠 High · 🟡 Medium · ⚪ Low.

---

## Re-review (post-fix pass, 2026-06-28)

A follow-up pass checked the working-tree changes (uncommitted, vs. `b7de0f8`) against the 19 findings below. Status legend: ✅ Resolved · 🟡 Partial (residual noted) · ❌ Unresolved · ➕ New.

A second fix pass then addressed the new issues (N1–N3) and the actionable residuals (#5, #9). Those are marked ✅(fixed) below with a verification note; only the two Antigravity residuals requiring external verification (#2, #19) remain open.

| # | Status | Note |
|---|---|---|
| 1 | ✅ | `safety-check.sh` now reads stdin JSON via `jq` (`.tool_input.command`, `.cwd`), guards missing `jq`, falls back to positional args. Safety gate fires on Claude Code. |
| 2 | 🟡 | Claude build templates `${CLAUDE_PLUGIN_ROOT}` (correct, verified). **Open residual:** Antigravity build still emits `${PLUGIN_ROOT}` — that var is unverified for Antigravity; needs `agy inspect` / Antigravity plugin docs to confirm. |
| 3 | ✅ | `set -euo pipefail` added; both branches validated via `git rev-parse --verify`; checkout guarded. |
| 4 | ✅ | `TRACK_ID` restricted to `^[A-Za-z0-9._-]+$`; `TARGET_DIR` anchored to `git rev-parse --show-toplevel`; `realpath -m` containment check rejects `..` escape. |
| 5 | ✅(fixed) | Regex now also catches quoted `rm -rf "$HOME"`, `rm -rf "$VAR"`, `rm -rf ~/*`, `rm -rf ~/...`, `rm -rf $HOME/...` via an added `quoted_re` clause. Verified: all destructive sample forms exit 2; safe `rm -rf /tmp/safe` and `ls` exit 0. |
| 6 | ✅ | `BASE_REF="${3:-$(git symbolic-ref --short HEAD … || echo main)}"`; no hardcoded `main`. |
| 7 | ✅ | All three scripts have `set -euo pipefail`; success `echo` moved inside `if`-success / `else exit 1`. |
| 8 | ✅ | `TARGET_DIR` computed from `git rev-parse --show-toplevel`; create/cleanup agree on location. |
| 9 | ✅(fixed) | Claude side prints instructions (no interactive command). Antigravity registration no longer swallows failure — `agy plugin install …` now exits 1 on failure instead of `‖ echo "Warning"`. The correct `agy` invocation form still wants confirmation against `agy plugin install --help`. |
| 10 | ✅ | `src/agents/*.md` now use Antigravity names (`view_file`, etc.); `install.sh` templates them to Claude names (`Read`/`Grep`/`Glob`/`WebSearch`/`Bash`) for the Claude build. |
| 11 | ✅ | `ship.md` & `finishing-a-development-branch` now pass `<track-branch> <integration-branch>` / `<track-id>` and point to `.planning/worktrees/` + state file for discovery. |
| 12 | ✅ | `post-edit.sh` reads stdin JSON (`.tool_input.file_path`); hooks templated per-platform (`Write|Edit` / `write_to_file|replace_file_content`). |
| 13 | ✅ | `--project` now drives a real project-level install block. |
| 14 | ✅ | `executing-plans/SKILL.md` now references Bead status / bead files instead of `task.md`. |
| 15 | ✅ | `bead-orchestrator/SKILL.md` now documents the "Agent Injection (optional)" step. |
| 16 | ✅ | Root-level `dist/antigravity/hooks.json` duplicate removed; only `hooks/hooks.json` written. |
| 17 | ✅ | `agent-plugin/dist/` added to `.gitignore`; committed `dist/**` deleted (51 files staged for removal). |
| 18 | ✅ | Value-taking opts validate `${2:-}` and `shift 2`; copies use `src/<dir>/.` form (handles empty dirs). |
| 19 | 🟡 | Claude `$schema` removed. **Open residual:** Antigravity `$schema` (`https://antigravity.google/schemas/v1/plugin.json`) kept and labeled "canonical" in a comment without verification — confirm the URL is real or drop it. |

### ➕ New issues from the fix pass — all resolved

**➕ N1 (🟠 High) — `install.sh --project` Claude path re-introduced finding #2.** ✅(fixed)
Project-level `.claude/` configs are not an installed plugin, so `CLAUDE_PLUGIN_ROOT` is unset there. The project install now writes `${CLAUDE_PROJECT_DIR}/.claude/scripts/...` (Claude Code exports `CLAUDE_PROJECT_DIR` for project hooks). The `dist/claude-code` plugin build still uses `${CLAUDE_PLUGIN_ROOT}` (verified). **Verified:** `install.sh --project <dir> --platform claude` produces `hooks.json` with `"command": "${CLAUDE_PROJECT_DIR}/.claude/scripts/safety-check.sh"`.

**➕ N2 (⚪ Low) — `--project --dry-run` silently ignored `--dry-run`.** ✅(fixed)
The `--project` block exits before the global `DRY_RUN` check; now an explicit dry-run guard at the top of the block prints a preview and exits 0 without writing. **Verified:** after `install.sh --project <dir> --dry-run`, no `.claude/` is created.

**➕ N3 (⚪ Low) — `safety-check.sh` failed open on malformed hook JSON.** ✅(fixed)
`jq` parse failure is now caught explicitly (`COMMAND=$(… ‖ jq …) ‖ { echo …; exit 2; }`) and blocks (exit 2) instead of leaving `COMMAND` empty and allowing. **Verified:** piping `not json at all` into `safety-check.sh` exits 2 with "failed to parse PreToolUse hook payload as JSON".

### Residuals still open (require external verification)
- **#2 (Antigravity `${PLUGIN_ROOT}`)** — confirm the correct Antigravity hook env var via `agy inspect` / Antigravity plugin docs; do not assume `PLUGIN_ROOT`. Cannot be verified from this repo alone.
- **#19 (Antigravity `$schema`)** — confirm `https://antigravity.google/schemas/v1/plugin.json` is real or drop it; the "canonical" comment asserts verification that was not performed.

---

## 🔴 1. `safety-check.sh` reads positional args, but Claude Code passes the tool call as JSON on stdin — the safety gate never fires

**File:** `src/scripts/safety-check.sh:5-6`
**Also affects:** the entire `PreToolUse` safety promise.

```bash
COMMAND="$1"
CWD="$2"
```

**Failure scenario:** Claude Code's `PreToolUse` hook contract passes event data as a JSON object on **stdin** (`{"session_id","cwd","hook_event_name","tool_name","tool_input":{"command":...}}`), never as positional `$1`/`$2`. So `$1` and `$2` are always empty. The destructive-command regex runs against an empty string (never matches), and the worktree-CWD check compares empty `REAL_CWD` (from `realpath -q ""`). Result: **no `rm -rf` is ever blocked and no out-of-worktree operation is ever blocked** — the plugin's central guardrail is silently a no-op on Claude Code. This directly defeats the "Git Worktree Security & Guardrails" goal stated in `Plan.md`.

**Fix:**
1. Read and parse stdin JSON. `jq` is the documented approach:
   ```bash
   INPUT=$(cat)
   COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
   CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')
   ```
2. Guard against `jq` being missing (fall back to blocking with a clear message, or skip — but never silently pass).
3. Keep `exit 2` to block (correct per contract) and write the reason to **stderr** (already done — stderr is fed back to Claude).
4. Re-test: pipe a sample `PreToolUse` JSON into the script and confirm `rm -rf /` exits 2.

---

## 🔴 2. `hooks.json` uses `${PLUGIN_ROOT}` — not a real env var on Claude Code; hook path resolves to `/scripts/...` and fails

**File:** `src/hooks/hooks.json:8,20`

```json
"command": "${PLUGIN_ROOT}/scripts/safety-check.sh"
"command": "${PLUGIN_ROOT}/scripts/post-edit.sh"
```

**Failure scenario:** Claude Code exports `${CLAUDE_PLUGIN_ROOT}` (and `${CLAUDE_PLUGIN_DATA}`, `${CLAUDE_PROJECT_DIR}`) into hook processes — there is no `PLUGIN_ROOT` variable. With `PLUGIN_ROOT` unset, the command string expands to `/scripts/safety-check.sh` (empty prefix → absolute path from filesystem root), which does not exist. The hook runner reports "No such file or directory" and the safety gate is **bypassed for every Bash/Write/Edit call**. `Plan.md`'s own platform table (line 33) even documents the correct var as `$CLAUDE_PLUGIN_ROOT`, so this contradicts the plan. For Antigravity the variable name is unverified — do not assume `PLUGIN_ROOT` is correct there either.

**Fix:**
- For the Claude Code build, emit `${CLAUDE_PLUGIN_ROOT}/scripts/safety-check.sh` and `${CLAUDE_PLUGIN_ROOT}/scripts/post-edit.sh`.
- Because `src/hooks/hooks.json` is shared across two platforms with different env-var names, make `install.sh` template it per-platform instead of copying the same file verbatim. E.g. generate `dist/claude-code/hooks/hooks.json` with `CLAUDE_PLUGIN_ROOT` and `dist/antigravity/hooks/hooks.json` with whatever Antigravity documents (verify via `agy inspect`/Antigravity plugin docs before committing).
- Prefer the **exec form** (`"args": [...]`) documented for plugin hooks to avoid shell-quoting pitfalls once paths contain spaces.

---

## 🔴 3. `merge-integration.sh` has no `set -e`; a failed `git checkout` silently merges into the **wrong branch**

**File:** `src/scripts/merge-integration.sh:14-17`

```bash
git checkout "$INTEGRATION_BRANCH"
if git merge --no-ff -m "..." "$BRANCH_NAME"; then
  echo "Successfully merged..."
```

**Failure scenario:** `git checkout "$INTEGRATION_BRANCH"` fails whenever the working tree has uncommitted/untracked files that conflict, or the branch doesn't exist. With no `set -e`, execution continues to `git merge --no-ff "$BRANCH_NAME"` **on whatever branch is currently checked out** (e.g. a worker's feature branch, or `main`). The merge succeeds, prints "Successfully merged … into $INTEGRATION_BRANCH" (a lie — it merged into the wrong branch), and the integration branch is never updated. This is a silent, history-corrupting failure on a destructive git operation.

**Fix:**
1. Add `set -euo pipefail` at the top.
2. Verify the checkout explicitly:
   ```bash
   if ! git checkout "$INTEGRATION_BRANCH"; then
     echo "Error: cannot checkout $INTEGRATION_BRANCH (uncommitted changes?)" >&2
     exit 1
   fi
   ```
3. Validate both branches exist (`git rev-parse --verify "$BRANCH_NAME"` / `"$INTEGRATION_BRANCH"`) before merging.
4. Consider `git merge --no-ff --no-commit` + review, then commit, so a conflict doesn't leave a half-merge — but at minimum the checkout guard is mandatory.

---

## 🔴 4. `TRACK_ID` is not sanitized — path traversal escapes `.planning/worktrees/`

**File:** `src/scripts/worktree-create.sh:13,22` and `src/scripts/worktree-cleanup.sh:12,20`

```bash
TARGET_DIR=".planning/worktrees/$TRACK_ID"
...
git worktree add -b "$BRANCH_NAME" "$TARGET_DIR" main
```

**Failure scenario:** `TRACK_ID` is taken verbatim from `$1` with no validation. A hallucinating agent (the exact threat `Plan.md` says to guard against) can pass `TRACK_ID="../../evil"` or `TRACK_ID="../../../../tmp/x"`. Then `TARGET_DIR` resolves outside `.planning/worktrees/` — `worktree-create.sh` creates a worktree at an arbitrary path on disk, and `worktree-cleanup.sh` runs `git worktree remove` on it. The only guard (`[ -d "$TARGET_DIR" ]` / `[ ! -d ]`) does not constrain the path. This breaks the confinement invariant the skills describe ("Create worktrees under `.planning/worktrees/<track-id>/`", "Do not allow hallucinated paths").

**Fix:**
1. Reject any `TRACK_ID` containing `/`, `..`, or other path metacharacters:
   ```bash
   case "$TRACK_ID" in
     *..*|*/*|*\\*|"$TRACK_ID")
       # also block empty
       ;;
   esac
   # simpler, allow only [A-Za-z0-9._-]:
   if [[ ! "$TRACK_ID" =~ ^[A-Za-z0-9._-]+$ ]]; then
     echo "Error: invalid track-id '$TRACK_ID'" >&2; exit 1
   fi
   ```
2. Compute `TARGET_DIR` and canonicalize, then assert it stays inside `.planning/worktrees/`:
   ```bash
   WT_ROOT="$(git rev-parse --git-common-dir)/../.planning/worktrees"  # or repo root
   REAL_TARGET="$(realpath -m "$WT_ROOT/$TRACK_ID")"
   case "$REAL_TARGET" in
     "$WT_ROOT"/*) ;;  # ok
     *) echo "Error: resolved path escapes worktree root" >&2; exit 1 ;;
   esac
   ```
3. Apply the same validation in `worktree-cleanup.sh`.
4. Add `set -euo pipefail` to both scripts.

---

## 🔴 5. `safety-check.sh` destructive-command regex is far too narrow

**File:** `src/scripts/safety-check.sh:9`

```bash
if [[ "$COMMAND" =~ rm[[:space:]]+-rf[[:space:]]+\/ ]] || [[ "$COMMAND" =~ rm[[:space:]]+-rf[[:space:]]+\$ ]]; then
```

**Failure scenario:** The first branch only matches `rm -rf /` (a literal slash immediately after). It does **not** block: `rm -rf .`, `rm -rf *`, `rm -rf ~`, `rm -rf /*`, `rm -rf --no-preserve-root /`, `rm -rf ./`, `rm -fr /`, `rm -r -f /`, `sudo rm -rf /`, or `rm -rf "$HOME"`. The second branch (`\$`) only matches a literal `$` — so it blocks `rm -rf $HOME` but not `rm -rf .` or `rm -rf *`. Given the plugin's stated goal of preventing destructive commands, an agent running `rm -rf *` inside a worktree sails right through. Also: once finding #1 is fixed so `COMMAND` is actually populated, this regex becomes the only barrier — so it must be robust.

**Fix:** Use an allowlist/anchor approach instead of pattern-matching doom:
```bash
# Block rm -rf against any of: /, /*, ., .., ~, *, $HOME, and bare root-ish targets
if [[ "$COMMAND" =~ rm[[:space:]]+([^|]*-[^|]*)*(r[^f]*f|f[^r]*r|rf)[[:space:]]+(/|/\*|\.(\ |$|/)|\.\.|\*|~|\$HOME) ]]; then
  echo "Blocked: destructive rm target" >&2; exit 2
fi
```
Better: canonicalize the target with `realpath` and refuse any target at or above the repo root, the home dir, `/`, etc. Also handle `rm` with separated `-r`/`-f` flags and `--no-preserve-root`. At minimum add tests for `rm -rf .`, `rm -rf *`, `rm -rf ~`, `rm -rf /*`, `rm -fr /`.

---

## 🟠 6. `worktree-create.sh` hardcodes `main` as the base branch

**File:** `src/scripts/worktree-create.sh:22`

```bash
git worktree add -b "$BRANCH_NAME" "$TARGET_DIR" main
```

**Failure scenario:** Any repo whose default branch is `master`, `develop`, `trunk`, or `default` fails with `fatal: invalid reference: main`, blocking all worktree-isolated execution. This very repo uses `main`, but the plugin is meant to be reusable ("migrated to its own repository later") and to run across user projects.

**Fix:**
- Make the base ref an optional third argument with a sensible default derived from the repo:
  ```bash
  BASE_REF="${3:-$(git symbolic-ref --short HEAD 2>/dev/null || echo main)}"
  git worktree add -b "$BRANCH_NAME" "$TARGET_DIR" "$BASE_REF"
  ```
- Or use `git worktree add -b "$BRANCH_NAME" "$TARGET_DIR"` (no base) to branch from HEAD — depends on whether you want branch-from-main semantics. Document the choice in `using-git-worktrees/SKILL.md`.

---

## 🟠 7. Worktree/merge scripts lack `set -e` and echo "success" after failures

**File:** `src/scripts/worktree-create.sh:22-23`, `src/scripts/worktree-cleanup.sh:20-21`, `src/scripts/merge-integration.sh:17-18`

**Failure scenario:** `worktree-create.sh` runs `git worktree add …` then unconditionally echoes `"Worktree created at: … on branch …"`. If the `git worktree add` fails (bad branch name, path exists, dirty tree), the script still prints success and exits 0, so the orchestrator believes a worktree exists when it doesn't. Same pattern in `worktree-cleanup.sh` ("Worktree … removed." after a failed `git worktree remove`) and `merge-integration.sh` (mitigated only because the merge is in an `if`).

**Fix:**
- Add `set -euo pipefail` to all three scripts.
- Move the success `echo` to after a verified-success path, or rely on `set -e` to abort before the echo on failure.
- For `worktree-cleanup.sh`, the current "warn + exit 0" for missing dir is fine, but `git worktree remove` failure must not print "removed".

---

## 🟠 8. Worktree scripts use a relative `TARGET_DIR` without `cd` to the repo root

**File:** `src/scripts/worktree-create.sh:13`, `src/scripts/worktree-cleanup.sh:12`

**Failure scenario:** `TARGET_DIR=".planning/worktrees/$TRACK_ID"` is relative to the **current working directory** of whoever invokes the script. If a worker subagent runs from a subdirectory (e.g. `notion-stories/`), the worktree is created under `notion-stories/.planning/worktrees/…` instead of the repo root. A later `worktree-cleanup.sh` invoked from the repo root won't find it (different relative path), leaving orphaned worktrees. `git worktree add` itself resolves the path relative to CWD, not the git common dir.

**Fix:** Anchor to the repo root explicitly:
```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
TARGET_DIR="$REPO_ROOT/.planning/worktrees/$TRACK_ID"
```
Then the create/cleanup pair always agrees on location regardless of CWD.

---

## 🟠 9. `install.sh` registration step uses `claude /plugin install --plugin-dir` — not a valid non-interactive command

**File:** `install.sh` (the `# Run platform installs` block)

```bash
claude /plugin install --plugin-dir "$SCRIPT_DIR/dist/claude-code" || echo "Warning: ..."
```

**Failure scenario:** `/plugin` is an **interactive REPL slash command**; it cannot be invoked as `claude /plugin install …` from a non-interactive shell script. The command fails, hits the `|| echo "Warning: …"` swallow, and the plugin is never registered — the user believes the install succeeded. (The `agy plugin install "$SCRIPT_DIR/dist/antigravity"` form is plausible but should also be verified against Antigravity's CLI.)

**Fix:** Pick a supported non-interactive mechanism:
- Session load: `claude --plugin-dir "$SCRIPT_DIR/dist/claude-code"` (loads for one session — useful for local testing).
- Persistent install via a local marketplace:
  ```bash
  claude plugin marketplace add "$SCRIPT_DIR"        # if structured as a marketplace
  claude plugin install gin-workflow@local --scope project
  ```
- Or for CI/containers, write `enabledPlugins` into `.claude/settings.json`.
Remove the `|| echo "Warning …"` that hides the failure, or at least exit non-zero so the user knows registration didn't happen. Verify the Antigravity equivalent with `agy plugin install --help`.

---

## 🟠 10. Agent definitions declare tool names that match neither platform's tool registry

**File:** `src/agents/agent-researcher.md:4` (and `code-reviewer.md`, `codebase-mapper.md` similarly)

```yaml
tools: ["read_file", "grep_search", "list_dir", "search_web"]
```

**Failure scenario:** Claude Code's tools are named `Read`, `Grep`, `Glob`, `Bash`, `WebSearch`, `WebFetch`, `Agent`, etc.; Antigravity has its own names. `read_file`/`grep_search`/`list_dir`/`search_web` match neither registry. Depending on the runtime's handling of unknown tool names, the agent either runs with **no tools** (every tool call refused) or, worse, an **unrestricted** tool set — either way the `tools:` restriction does not behave as intended. `Plan.md` itself lists yet a third scheme (`["read","search","grep"]`), so the docs and the files disagree.

**Fix:**
- Decide per-platform: emit Claude Code agent files with `tools: ["Read","Grep","Glob","WebSearch"]` and Antigravity files with Antigravity's real names. Since `install.sh` already produces per-platform `dist/` trees, template the `tools:` list during generation (or maintain separate `src/agents/*.claude.md` and `*.agy.md` sources).
- Update `Plan.md`'s platform comparison to reflect the real tool names so the docs stop disagreeing with the code.

---

## 🟡 11. `ship.md` and `finishing-a-development-branch` invoke scripts without their required arguments

**File:** `src/commands/ship.md:13-14`, `src/skills/finishing-a-development-branch/SKILL.md:14-15`

```
2. Run `merge-integration.sh` to merge changes.
3. Clean up all worktrees created for this plan.
```
```
3. Merge ... using the `merge-integration.sh` script.
4. Teardown: Remove any active worktrees using `worktree-cleanup.sh`...
```

**Failure scenario:** `merge-integration.sh` requires `<branch-name> <integration-branch>`; `worktree-cleanup.sh` requires `<track-id>`. The instructions name the scripts but never tell the agent how to fill those arguments or where to discover them (no pointer to a state file like `.planning/orchestration-state.json`). An agent following the skill runs the script bare → usage error → `/ship` halts.

**Fix:**
- Make the commands concrete: `merge-integration.sh "<track-branch>" "<integration-branch>"` and `worktree-cleanup.sh "<track-id>"`.
- Add a short "discover active tracks" step: e.g. `ls .planning/worktrees/` or read the orchestrator state file, and pass each track id to `worktree-cleanup.sh`.
- Cross-reference the `orchestrate.md` `--integration-branch` flag so the agent knows which branch to merge into.

---

## 🟡 12. `post-edit.sh` has the same stdin-vs-args contract bug as `safety-check.sh`

**File:** `src/scripts/post-edit.sh:5`

```bash
TARGET_FILE="$1"
```

**Failure scenario:** Claude Code `PostToolUse` for `Write|Edit` passes JSON on stdin (`tool_input.file_path`), not `$1`. So `TARGET_FILE` is always empty and the hook just prints `"Post-edit hook run on: "`. Currently low-impact because the script is a no-op, but the moment anyone adds real formatting logic it will operate on an empty path. Also the `Write|Edit` matcher won't fire for Antigravity's `write_to_file`/`replace_file_content` on the Claude Code build (those are Antigravity tool names mixed into a Claude hooks file).

**Fix:**
```bash
INPUT=$(cat)
TARGET_FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -n "$TARGET_FILE" ] || exit 0
```
And split the matcher per-platform in the templated hooks.json (Claude: `Write|Edit`; Antigravity: its real tool names).

---

## 🟡 13. `install.sh` `--project` option is parsed but never used

**File:** `install.sh` (`--project) PROJECT_DIR="$2"; shift ;;` and the `PROJECT_DIR` var)

**Failure scenario:** `--project <dir>` is accepted and stored, then never referenced — the script always operates on `$SCRIPT_DIR`. A user passing `--project ~/other-repo` reasonably expects the plugin installed there; nothing happens, silently. Dead options erode trust in the CLI surface.

**Fix:** Either implement it (write/`--link` the platform-specific files into `$PROJECT_DIR/.claude/` and `$PROJECT_DIR/.agents/`) or remove the option entirely. If kept, validate `$2` is non-empty (see finding 18).

---

## 🟡 14. `executing-plans/SKILL.md` references an undefined `task.md`

**File:** `src/skills/executing-plans/SKILL.md:13`

**Failure scenario:** The skill says to "Update `task.md` or the corresponding plan status", but `task.md` is not defined in `writing-plans/plan-schema.md` or any command, and the plugin's tracking model is Beads. An agent creates an orphan `task.md` at the project root with no schema and no consumer, polluting the working tree and contradicting the Beads-based tracking design.

**Fix:** Replace the `task.md` reference with the actual tracking mechanism — update the Bead status via the Beads CLI / bead files, or update the plan status field from `writing-plans/plan-schema.md`. State the concrete file/command to update.

---

## 🟡 15. `--inject-agents-md` flag is declared but never implemented

**File:** `src/commands/orchestrate.md:13,22`

**Failure scenario:** `/orchestrate --inject-agents-md` is advertised in the usage line and flag list, but `bead-orchestrator/SKILL.md` (the core orchestrator skill) never mentions it. A user invoking it gets either silent ignore or a hallucinated "injection" behavior with no defined contract (potentially overwriting agent markdown files).

**Fix:** Either (a) document the flag's behavior in `bead-orchestrator/SKILL.md` with a concrete step ("copy `src/agents/*.md` into the project's `.claude/agents/` before dispatch"), or (b) remove it from `orchestrate.md` until v2.

---

## ⚪ 16. `install.sh` writes the Antigravity hooks file twice, one in the wrong place

**File:** `install.sh` (Antigravity block)

```bash
mkdir -p dist/antigravity/hooks
cp -f src/hooks/hooks.json dist/antigravity/hooks/hooks.json
cp -f src/hooks/hooks.json dist/antigravity/hooks.json     # <- root copy
```

**Failure scenario:** `Plan.md`'s platform table says Antigravity hooks live at `.agents/hooks/hooks.json` (i.e. `<plugin>/hooks/hooks.json`). The extra root-level `dist/antigravity/hooks.json` is neither needed nor in the documented location — it's redundant noise and could confuse the Antigravity loader about which file is canonical.

**Fix:** Drop the root-level copy; keep only `dist/antigravity/hooks/hooks.json`. (Verify against Antigravity's plugin spec whether the root form is also accepted; if so, pick one.)

---

## ⚪ 17. Generated `dist/` tree is committed alongside `src/`

**File:** `agent-plugin/dist/**` (the whole committed `dist/claude-code/` and `dist/antigravity/` trees)

**Failure scenario:** `dist/` is the output of `install.sh`, yet it is checked into git as a duplicate of `src/`. Any edit to `src/` (including the fixes above) will silently diverge from the committed `dist/` until someone re-runs `install.sh` and re-commits — and a platform that loads directly from `dist/` (e.g. `agy plugin install ./dist/antigravity`) will run stale code. This is a maintenance footgun and double the review surface.

**Fix:**
- Add `agent-plugin/dist/` to `.gitignore` and generate it at install/build time (CI can run `install.sh --dry-run` to produce artifacts).
- If a snapshot must ship for offline install, generate it in CI and attach as a release artifact rather than tracking it in `src`.

---

## ⚪ 18. `install.sh` arg parsing aborts on malformed `--platform`/`--project` and on empty source dirs

**File:** `install.sh` (the `while`/`case` loop and the `cp -rf src/*` calls, under `set -e`)

**Failure scenario (a):** `--platform` or `--project` given as the last arg with no value: `case` sets the var to empty `$2`, the inner `shift` consumes the flag, then the trailing `shift` runs against an empty arg list and errors — under `set -e` the script aborts with a confusing `shift` error instead of a clean usage message.
**Failure scenario (b):** `cp -rf src/commands/* "$target/commands/"` with `nullglob` off: if any `src/` subdirectory is ever empty, the glob stays literal (`src/commands/*`) and `cp` errors "No such file or directory" → `set -e` aborts the whole install. Latent today (dirs are populated), but fragile.

**Fix:**
- Validate that a value follows value-taking options:
  ```bash
  --platform) [ $# -ge 2 ] || { echo "--platform needs a value" >&2; exit 1; }; PLATFORM="$2"; shift 2 ;;
  ```
  (then drop the trailing bare `shift`, or restructure to `shift` once after `case`).
- Use `cp -rf src/commands/. "$target/commands/"` (the trailing `/.` copies directory contents and works for empty dirs), or `find … -exec`, or enable `shopt -s nullglob dotglob` around the copies.

---

## ⚪ 19. Plugin manifest `$schema` URLs are unverified

**File:** `install.sh` (the two `python3 -c` manifest generators)

```python
'$schema': 'https://claude.ai/schemas/v1/plugin.json'
'$schema': 'https://antigravity.google/schemas/v1/plugin.json'
```

**Failure scenario:** These schema URLs appear fabricated. If a platform tries to fetch the `$schema` for validation and 404s, validation silently no-ops (best case) or the manifest is treated as invalid (worst case). At minimum it's misleading.

**Fix:** Confirm the canonical schema URLs from the Claude Code plugin reference and the Antigravity plugin docs; use the real URLs, or drop `$schema` if none is published. Don't ship invented URLs.

---

## Summary table

| # | Sev | File | One-line |
|---|---|---|---|
| 1 | 🔴 | `scripts/safety-check.sh:5-6` | Reads `$1`/`$2`; Claude Code sends JSON on stdin → guard never fires |
| 2 | 🔴 | `hooks/hooks.json:8,20` | `${PLUGIN_ROOT}` wrong (should be `${CLAUDE_PLUGIN_ROOT}`) → hook path unresolvable |
| 3 | 🔴 | `scripts/merge-integration.sh:14` | No `set -e`; failed checkout merges into wrong branch |
| 4 | 🔴 | `scripts/worktree-create.sh`/`worktree-cleanup.sh` | Unsanitized `TRACK_ID` → path traversal out of `.planning/worktrees/` |
| 5 | 🔴 | `scripts/safety-check.sh:9` | `rm -rf` regex misses `.`, `*`, `~`, `/*`, `-fr`, `--no-preserve-root` |
| 6 | 🟠 | `scripts/worktree-create.sh:22` | Hardcoded `main` base branch fails on `master`/`develop` repos |
| 7 | 🟠 | worktree/merge scripts | No `set -e`; "success" printed after failures |
| 8 | 🟠 | worktree scripts | Relative `TARGET_DIR` without repo-root `cd` → wrong location from subdirs |
| 9 | 🟠 | `install.sh` | `claude /plugin install` is interactive-only; registration silently no-ops |
| 10 | 🟠 | `agents/*.md` | `tools:` names match neither platform's registry |
| 11 | 🟡 | `commands/ship.md`, `skills/finishing-a-development-branch` | Scripts invoked without required args; no track-discovery step |
| 12 | 🟡 | `scripts/post-edit.sh:5` | Same stdin-vs-args bug; `Write\|Edit` matcher wrong for Antigravity tools |
| 13 | 🟡 | `install.sh` | `--project` parsed but never used |
| 14 | 🟡 | `skills/executing-plans/SKILL.md:13` | Undefined `task.md` reference |
| 15 | 🟡 | `commands/orchestrate.md:13,22` | `--inject-agents-md` flag unimplemented |
| 16 | ⚪ | `install.sh` | Antigravity `hooks.json` written twice, root copy misplaced |
| 17 | ⚪ | `dist/**` | Generated `dist/` committed alongside `src/` → silent divergence |
| 18 | ⚪ | `install.sh` | Malformed value-opts + empty-glob `cp` abort under `set -e` |
| 19 | ⚪ | `install.sh` | Unverified/fabricated `$schema` URLs |

---

### Suggested fix order

1. **#1, #2, #5** first — together they reinstate the safety gate (the plugin's headline feature). Without #1 and #2, no `PreToolUse` blocking works at all on Claude Code.
2. **#3, #4, #6, #7, #8** — make the git/worktree scripts actually safe and correct; these are the destructive surface the safety gate is meant to protect.
3. **#9, #10** — make install + agent definitions correct per-platform so the plugin actually loads.
4. **#11–#15** — workflow/skill consistency so agents following the docs don't deadlock.
5. **#16–#19** — cleanup pass.

After fixes, re-run `bash install.sh --dry-run` and pipe sample `PreToolUse`/`PostToolUse` JSON into `safety-check.sh`/`post-edit.sh` to verify the hooks block and allow as intended.
