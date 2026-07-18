---
name: beads-migration
description: Move a repository's local .beads directory to the centralized vault and establish a symlink.
---

# Beads Migration Skill

Use this skill when initializing or onboarding a project repository to use the concentrated Beads database structure in the Obsidian vault.

## Purpose

To ensure that the Dolt Beads task databases of all repositories are centralized under the vault (`/home/coder/workspace/brain/.beads/`), enabling the `agent-orchestration` HTTP MCP server and Telegram bot to query and modify tasks cross-project.

## Migration Steps

1. **Verify Existing Local Database**:
   Run the following command at the repository root to verify that a local database exists:
   ```bash
   bd where
   ```
   Note the database path (typically `<repo_root>/.beads/embeddeddolt`).

2. **Locate vault directory**:
   The target path in the Obsidian vault will be:
   ```
   /home/coder/workspace/brain/.beads/<project-name>
   ```
   (where `<project-name>` is the slug of the repository, e.g., `infra`, `gin-workflow`). Ensure the parent directory `/home/coder/workspace/brain/.beads/` exists.

3. **Move the `.beads` directory**:
   Run the following to move the local directory to the vault (replace `<project-name>` and `<repo_root>`):
   ```bash
   mv <repo_root>/.beads /home/coder/workspace/brain/.beads/<project-name>
   ```

4. **Create the Symlink**:
   Create a symbolic link at the repository root pointing to the new location in the vault:
   ```bash
   ln -s /home/coder/workspace/brain/.beads/<project-name> <repo_root>/.beads
   ```
   Verify that `.beads` is in `<repo_root>/.gitignore` so the symlink itself is not tracked by Git.

5. **Verify Database Health**:
   Run:
   ```bash
   bd doctor
   bd status
   ```
   Ensure the database is recognized and issue counts match the previous state.
