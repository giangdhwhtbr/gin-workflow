---
name: beads-migration
description: Move a repository's .beads directory into ~/gin-harness/beads/<repo> and symlink it back.
---

# Beads Migration

Load only when the user explicitly invokes it.

## Inputs

- `<root>`: the absolute path of the repository root.
- `<name>`: the repository's directory name (`basename <root>`).
- `<target>`: the target directory, default `~/gin-harness/beads/<repo>` with `<repo>` = `<name>`.

## Steps

1. Record the current database state in `<root>`. Note the issue count, database name and project id.
   ```bash
   bd count
   bd context
   ```

2. Stop if any process holds files in the database; never move a database in use. No output means it is free.
   ```bash
   lsof +D <root>/.beads
   ```

3. Stop if `<target>` or today's backup path already exists (`mv` and `cp -a` would nest into it). Otherwise back up:
   ```bash
   mkdir -p ~/gin-harness/backup && cp -a <root>/.beads ~/gin-harness/backup/<name>-$(date +%F)
   ```

4. Move and link.
   ```bash
   mkdir -p ~/gin-harness/beads && mv <root>/.beads <target> && ln -s <target> <root>/.beads
   ```
   Until step 5, `git status` may show tracked `.beads` files as deleted and `.beads` as untracked.

5. If `git ls-files .beads` lists files, untrack them and ignore the symlink. Use a `.beads` line with no trailing slash; `.beads/` does not match a symlink.
   ```bash
   git rm -r --cached .beads
   ```
   Add the `.gitignore` line in the same change, and commit on a feature branch only after step 8 passes, never on main/master.

6. Hooks: `git config core.hooksPath` often points into `.beads/hooks`. If that directory does not exist, `mkdir -p` it. Then run `gin-workflow hooks install`.

7. Cross-repo dependencies: add an `external_projects` map to `<target>/config.yaml` naming the other databases. Write absolute paths; YAML does not expand `~`.
   ```yaml
   external_projects:
     gin-workflow: /home/<user>/gin-harness/beads/gin-workflow
     gin-harness: /home/<user>/gin-harness/.beads
   ```
   A providing bead carries the label `export:<capability>`; after it closes, `bd ship <capability>` marks it shipped. A needing bead declares `bd dep add <id> external:<project>:<capability>` and stays out of `bd ready` until then. Probe this once with two throwaway beads; if the path form does not resolve, try the repo root instead and record which works here.

8. Verify: `bd count` and `bd context` match step 1, and `gin-workflow task ready` and `gin-workflow state` run in the main checkout and in a new worktree. If anything differs, run Rollback and stop.

The harness repository ignores `beads/`, `backup/` and the Dolt data under `.beads/` in its own `.gitignore`.

## Rollback

```bash
rm <root>/.beads && mv <target> <root>/.beads
```

Or restore the backup copy. Then undo step 5 (`git restore --staged .beads` and the `.gitignore` line) and step 6 if they ran.
