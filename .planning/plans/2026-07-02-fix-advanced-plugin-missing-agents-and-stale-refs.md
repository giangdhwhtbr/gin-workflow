# Plan: Fix gin-workflow-advanced Missing Agents and Stale Skill References

## Objective

After running `./install.sh`, the `gin-workflow-advanced` Antigravity plugin has an empty `agents/` directory, and several skill files contain stale `agent-plugin/src/...` path references from a previous monorepo layout. An agent invoking `agent-browser` will find no agents and follow dead paths.

Success looks like:
- `agy`-installed `gin-workflow-advanced` has all three specialist agents registered and discoverable.
- `agent-browser`, `requesting-code-review`, and `writing-skills` skill files reference only paths that actually exist.
- The dead cross-plugin `../writing-plans/SKILL.md` link in `agent-browser` is fixed.
- The `/gin-workflow:plan` command description distinguishes itself from the native `agy` planning mode.
- `./install.sh --platform antigravity --plugin advanced` produces a correct `dist/` and re-registers the plugin.

---

## Scope

- **In scope**:
  - Adding `plugins/gin-workflow-advanced/src/agents/` with the three specialist agent `.md` files (copied from core).
  - Fixing stale `agent-plugin/src/...` references in three skill files in `gin-workflow-advanced/src/skills/`.
  - Fixing the dead `../writing-plans/SKILL.md` cross-plugin link in `agent-browser`.
  - Updating the `/gin-workflow:plan` command description to clarify its relationship to native planning.
  - Re-running `install.sh` to rebuild `dist/` and re-register with `agy`.
- **Out of scope**:
  - Moving agents out of `gin-workflow/src/agents/` (they stay there; advanced gets its own copies).
  - Resolving the two open residuals from `review.md` (#2 `${PLUGIN_ROOT}`, #19 `$schema`) — those require external `agy` docs verification.
  - Changes to the core `gin-workflow` plugin's skills or commands (other than `plan.md` description).
  - Codex or Claude Code platform changes.

---

## Tasks

### Track 1: Add agents to gin-workflow-advanced/src/agents/

- **Dependencies**: none
- **Files**:
  - `plugins/gin-workflow-advanced/src/agents/agent-researcher.md` (NEW — copy from core)
  - `plugins/gin-workflow-advanced/src/agents/code-reviewer.md` (NEW — copy from core)
  - `plugins/gin-workflow-advanced/src/agents/codebase-mapper.md` (NEW — copy from core)
- **What to do**: Create `plugins/gin-workflow-advanced/src/agents/` and copy the three `.md` files from `plugins/gin-workflow/src/agents/`. The content stays identical; the core plugin retains its own copies (no duplication removal — both plugins ship agents independently).
- **Acceptance criteria**:
  - `ls plugins/gin-workflow-advanced/src/agents/` shows all three files.
  - File content is identical to the source in `plugins/gin-workflow/src/agents/`.
- **Estimated complexity**: low

---

### Track 2: Fix stale path references in gin-workflow-advanced skills

- **Dependencies**: none (can run in parallel with Track 1)
- **Files**:
  - `plugins/gin-workflow-advanced/src/skills/agent-browser/SKILL.md`
  - `plugins/gin-workflow-advanced/src/skills/requesting-code-review/SKILL.md`
  - `plugins/gin-workflow-advanced/src/skills/writing-skills/SKILL.md`
- **What to do**:

  **`agent-browser/SKILL.md`** — Four stale references to `agent-plugin/src/agents/` and `agent-plugin/src/skills/`:
  - Line 12: Replace `agent-plugin/src/agents/` → `the plugin's installed `agents/` directory`
  - Line 14: Replace the hardcoded path with a runtime instruction: "List the `agents/` directory within the plugin's installed location"
  - Line 49: Replace `agent-plugin/src/skills/` → `the plugin's installed `skills/` directory`
  - Line 51: Replace the hardcoded path with a runtime instruction: "List the `skills/` directory within the plugin's installed location"

  Also fix the dead cross-plugin link on line 52:
  - Replace `[writing-plans](file://../writing-plans/SKILL.md)` → plain text reference: `` `writing-plans` (from the `gin-workflow` core plugin) ``

  **`requesting-code-review/SKILL.md`** — One stale reference:
  - Replace `agent-plugin/src/agents/code-reviewer.md` → `the `code-reviewer` agent defined in this plugin's `agents/` directory`

  **`writing-skills/SKILL.md`** — Two stale references:
  - Line 14: Replace `agent-plugin/src/skills/writing-skills/SKILL.md` → `<skill-name>/SKILL.md` within the installed plugin's `skills/` directory
  - Line 62: Replace `agent-plugin/src/skills/` → `the plugin's installed `skills/` directory`

- **Acceptance criteria**:
  - `grep -r "agent-plugin" plugins/gin-workflow-advanced/src/skills/` returns no results.
  - `grep "writing-plans" plugins/gin-workflow-advanced/src/skills/agent-browser/SKILL.md` contains no dead `file://` link.
- **Estimated complexity**: low

---

### Track 3: Clarify /gin-workflow:plan command description

- **Dependencies**: none
- **Files**:
  - `plugins/gin-workflow/src/commands/plan.md`
- **What to do**: Update the command description and body to clarify that this command writes a **project-committed, git-tracked plan** to `.planning/plans/` for use by `/gin-workflow:orchestrate`. Distinguish it from the native `agy` session-local planning mode.

  Suggested updated content:
  ```markdown
  ---
  name: plan
  description: Write a project-committed implementation plan to `.planning/plans/` for use by `/orchestrate`. Distinct from the native session-local planning mode.
  ---

  # /gin-workflow:plan Command

  Writes a durable, git-tracked plan to `.planning/plans/` using the `writing-plans` skill.
  This is **not** the same as the native Antigravity session planning mode — it produces a
  persistent file that `/gin-workflow:orchestrate` reads to create beads and parallel workers.

  ## Instructions

  1. Use the `writing-plans` skill to draft a plan per [plan-schema.md](file://../skills/writing-plans/plan-schema.md).
  2. Ask the user for details if objectives, scope, or tasks are ambiguous.
  3. Save the resulting plan to `.planning/plans/<timestamp>-<description>.md`.
  ```

- **Acceptance criteria**:
  - `plan.md` description field distinguishes it from native planning mode.
  - Body explains the `.planning/plans/` → `/orchestrate` pipeline.
- **Estimated complexity**: low

---

### Track 4: Rebuild dist and re-register with agy

- **Dependencies**: Track 1, Track 2, Track 3 (all must complete first)
- **Files**: `plugins/gin-workflow-advanced/dist/` (generated)
- **What to do**:
  ```bash
  # Rebuild advanced plugin dist
  ./install.sh --platform antigravity --plugin advanced

  # Verify agents are present in dist
  ls plugins/gin-workflow-advanced/dist/antigravity/agents/

  # Verify no stale agent-plugin refs survive in dist
  grep -r "agent-plugin" plugins/gin-workflow-advanced/dist/antigravity/skills/ || echo "CLEAN"

  # Verify installed plugin (agy copies to ~/.gemini/config/plugins/)
  ls ~/.gemini/config/plugins/gin-workflow-advanced/agents/
  ```
- **Acceptance criteria**:
  - `dist/antigravity/agents/` contains all three agent `.md` files.
  - `~/.gemini/config/plugins/gin-workflow-advanced/agents/` is no longer empty.
  - No `agent-plugin` references survive in the installed skills.
- **Estimated complexity**: low

---

## Integration

- **Branch**: `fix/advanced-plugin-missing-agents`
- **Merge strategy**: sequential (all tracks → single PR)

---

## Validation

- [ ] `ls plugins/gin-workflow-advanced/src/agents/` shows 3 files
- [ ] `grep -r "agent-plugin" plugins/gin-workflow-advanced/src/` returns no results
- [ ] No dead `file://` links in `agent-browser/SKILL.md` for cross-plugin resources
- [ ] `plugins/gin-workflow/src/commands/plan.md` description updated
- [ ] `./install.sh --platform antigravity --plugin advanced` exits 0
- [ ] `ls ~/.gemini/config/plugins/gin-workflow-advanced/agents/` shows 3 files
- [ ] Manually verify: in a new `agy` session, the `agent-browser` skill correctly describes all three agents
