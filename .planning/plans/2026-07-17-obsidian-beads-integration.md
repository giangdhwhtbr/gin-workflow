# Plan: Integrating Obsidian Second Brain & Remote Beads with Gin Workflow

## Objective
Implement a compounding knowledge-execution loop where Beads manages active execution state and Obsidian Second Brain manages long-term memory. 

This includes:
1. **Centralizing Beads Databases**: Move `.beads` databases into the Obsidian vault under `projects/<repo>/.beads/` and symlink them back to the repository roots.
2. **Upgrading the Orchestrator to a Remote Beads MCP Server**: Enable remote agents on other machines to query and update task states via the Caddy reverse-proxy.
3. **Updating the Telegram Bot**: Support explicit commands (`/task`, `/brain`, `/context`).
4. **Creating New Agent Skills**: Write workflow skills (`beads-migration`, `context-retrieval`, `knowledge-capture`, `knowledge-reconciliation`).
5. **Conflict Resolution Policy**: If codebase and Obsidian contradict, fail verification and block the task.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- **Success criteria**:
  - The `agent-orchestration` server acts as an MCP server with `beads_` tools.
  - Existing local `.beads` directories are migrated to the vault and symlinked back.
  - Telegram bot handles `/task`, `/brain`, and `/context` correctly.
  - Lifecycle skills enforce the verification block-on-conflict policy.
- **Constraints**:
  - Dolt databases must remain intact and functional after migration.
  - MCP authentication tokens must be preserved.

---

## Proposed Changes

### [Component Name] Agent Orchestrator Backend (infra/agent-orchestration)

#### [MODIFY] [Dockerfile](file:///home/gin/infra/agent-orchestration/Dockerfile)
- Add commands to install `dolt` and the `bd` binary in the image.
- Configure path environment variables so the binaries are available to the python process.

#### [MODIFY] [mcp_server.py](file:///home/gin/infra/agent-orchestration/src/mcp_server.py)
- Expose new tools: `beads_list_ready`, `beads_show_task`, `beads_update_task`, `beads_create_task`, `beads_close_task`.
- Run subprocess calls to the local `bd` binary, specifying `--db /obsidian-vault/qwikfone/.beads/<project>/embeddeddolt`.

#### [MODIFY] [telegram_bot.py](file:///home/gin/infra/agent-orchestration/src/telegram_bot.py)
- Implement Command handlers:
  - `/task` -> delegates to beads MCP functions.
  - `/brain` -> searches Obsidian via local MCP vault path.
  - `/context` -> returns story content + active task state.

#### [MODIFY] [orchestrator.py](file:///home/gin/infra/agent-orchestration/src/orchestrator.py)
- Implement `fetch_obsidian_context` to scan the vault `/stories` and `/indexes` matching the project/submodule scope.

---

### [Component Name] Gin-Workflow Plugin Skills (gin-workflow)

#### [NEW] [beads-migration](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/beads-migration/SKILL.md)
- Step-by-step instructions for moving `.beads` to `/home/coder/workspace/brain/.beads/<repo>` and symlinking the repository root.

#### [NEW] [context-retrieval](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/context-retrieval/SKILL.md)
- Directs agents to query Obsidian at startup using the scoped project/submodule directories.

#### [NEW] [knowledge-capture](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/knowledge-capture/SKILL.md)
- Guides logging environment quirks and design decisions in `/decisions/` or `/lessons/`.

#### [NEW] [knowledge-reconciliation](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/knowledge-reconciliation/SKILL.md)
- Guides updating user story status and MOC indexes in Obsidian at task completion.

#### [MODIFY] Core lifecycle skills: [plan](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/plan/SKILL.md), [bead-worker](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/bead-worker/SKILL.md), [bead-orchestrator](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/bead-orchestrator/SKILL.md), [verify](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/verify/SKILL.md), [ship](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/ship/SKILL.md), [execute](file:///home/gin/gin-workflow/plugins/gin-workflow/src/skills/execute/SKILL.md)
- Hook context gathering, decisions logging, and index updates.
- Under `verify` and `execute`, add the verification standard: if codebase and Obsidian conflict, fail verification and block the task (Conflict Option A).

---

## Verification Plan

### Automated Tests
- Build `agent-orchestration` image and test executing `bd` internally.
- Build plugin with `./install.sh --platform antigravity` and check for errors.

### Manual Verification
- Move a `.beads` directory, symlink it, and verify that `bd ready` still outputs correctly.
- Call the updated MCP server with remote queries and verify that task lists match the Dolt database.
