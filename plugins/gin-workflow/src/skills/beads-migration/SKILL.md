---
name: beads-migration
description: Move a repository's .beads directory into ~/gin-harness/beads/<repo> and symlink it back.
---

# Beads Migration

Load only when the user explicitly invokes it.

## Inputs

- `<repo>`: the repository root.
- `<target>`: the target directory, default `~/gin-harness/beads/<repo>`, where `<repo>` is the repo's directory name.

## Steps

1. Record the current database state in the repo. Note the database name and project id.
   ```bash
   bd count
   bd context
   ```

2. Stop if a process is working in that repo; never move a database in use.
   ```bash
   pgrep -af "bd |gin-workflow"
   ```

3. Back up the database.
   ```bash
   mkdir -p ~/gin-harness/backup && cp -a <repo>/.beads ~/gin-harness/backup/<repo>-$(date +%F)
   ```

4. Move and link.
   ```bash
   mkdir -p ~/gin-harness/beads && mv <repo>/.beads <target> && ln -s <target> <repo>/.beads
   ```

5. If `git ls-files .beads` lists files:
   ```bash
   git rm -r --cached .beads
   ```
   Add a `.beads` line (no trailing slash; `.beads/` does not match a symlink) to `.gitignore`, and commit on a feature branch, never on main/master.

6. Hooks: `git config core.hooksPath` often points into `.beads/hooks`. If that directory does not exist, `mkdir -p` it. Then run `gin-workflow hooks install`.

7. Cross-repo dependencies: add an `external_projects` map to `<target>/config.yaml` naming the other databases.
   ```yaml
   external_projects:
     gin-workflow: ~/gin-harness/beads/gin-workflow
     gin-harness: ~/gin-harness/.beads
   ```
   A providing bead carries the label `export:<capability>`; after it closes, `bd ship <capability>` marks it shipped. A needing bead declares `bd dep add <id> external:<project>:<capability>`.

8. Verify: `bd count` and `bd context` match step 1, and `gin-workflow task ready` and `gin-workflow state` run.

## Rollback

```bash
rm <repo>/.beads && mv <target> <repo>/.beads
```

Or restore the backup copy.
