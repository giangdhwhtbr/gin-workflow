# Move the Beads databases into gin-harness

Workflow: beads-harness-migration
Status: confirmed 2026-10-21.

## Goal and scope

Keep the Beads databases of every child project in one place, `~/gin-harness`,
and add a harness database for the cross-project roadmap and epics. This is
step 3 of the split spec (`2026-10-20-split-orchestrator-design.md`), done
before step 2 so the step 2 epic can be tracked in the harness.

In scope:

- Move the `.beads` directories of gin-workflow and gin-console to
  `~/gin-harness/beads/<repo>/`, with a symlink at each repo root.
- Create the harness database at `~/gin-harness/.beads` (prefix `gin-harness`).
- Rework the `beads-migration` skill so it takes a target directory and covers
  backup, untracking, hooks and verification.
- Recreate the missing gin-workflow git hooks.
- Configure `external_projects` so beads of one repo can depend on another.
- Amend US-4 of the split spec to match this design.

Out of scope: one shared database for all repos, `scripts/sync.sh`,
`versions.lock`, any gin-console code change, making the ship skill run
`bd ship`, running `/setup` in the harness, and a gin-orchestrator database
(created with the reworked skill when that repo exists, in split step 2).

## Findings (2026-10-21)

| Repo | Issues | Database | `.beads` files tracked in git |
|---|---|---|---|
| gin-workflow | 293 | `gin_workflow` (embedded Dolt) | none (`.beads/` is gitignored) |
| gin-console | 31 | `gin_console` (embedded Dolt) | 10: `.gitignore`, `README.md`, `config.yaml`, `metadata.json`, `interactions.jsonl`, 5 hooks |

- Both repos set `core.hooksPath` to the absolute path `<repo>/.beads/hooks`.
- In gin-workflow that directory does not exist, so its `pre-commit` and
  `pre-push` hooks never run.
- gin-workflow's `.beads/config.yaml` sets
  `sync.remote: git+ssh://git@github.com/giangdhwhtbr/gin-workflow.git`.
- The current `beads-migration` skill targets a stale vault path,
  `/home/coder/workspace/brain/.beads/<project>`.

## Requirements

### Layout

```
~/gin-harness/.beads/                 harness database, prefix gin-harness
~/gin-harness/beads/gin-workflow/     was ~/gin-workflow/.beads
~/gin-harness/beads/gin-console/      was ~/gin-console/.beads
~/gin-workflow/.beads -> ~/gin-harness/beads/gin-workflow
~/gin-console/.beads  -> ~/gin-harness/beads/gin-console
```

- Each child database keeps its name, prefix, issue ids, project id and
  `sync.remote`.
- `~/gin-harness/.gitignore` ignores `beads/` and the Dolt data under `.beads/`.
  Each database is backed up by its own `sync.remote` or by the backup copy
  below, not by harness git.

### Cross-repo dependencies

- Each of the three databases sets `external_projects` to map `gin-workflow`,
  `gin-console` and `gin-harness` to their database directories under
  `~/gin-harness`.
- A bead that provides work to another repo carries the label
  `export:<capability>`. After it closes, `bd ship <capability>` adds
  `provides:<capability>`.
- A bead that needs it declares `bd dep add <id> external:<project>:<capability>`
  and stays blocked until the capability is shipped.

### Migration of one repo

1. Record `bd count` and `bd context` (database, project id).
2. Stop if a `bd` or `gin-workflow` process is running for the repo.
3. Copy `.beads` to `~/gin-harness/backup/<repo>-<YYYY-MM-DD>/` with `cp -a`.
4. Move `.beads` to `~/gin-harness/beads/<repo>/` and create the symlink
   `<repo>/.beads -> ~/gin-harness/beads/<repo>`.
5. If git tracks files under `.beads`: `git rm -r --cached .beads`, add `.beads`
   to `.gitignore`, and commit on a feature branch.
6. Check that `core.hooksPath` resolves to an existing directory. For
   gin-workflow, run `gin-workflow hooks install`.
7. Verify: `bd count` equals step 1, `bd context` reports the same database and
   project id, and `gin-workflow task ready` and `gin-workflow state` succeed.

### beads-migration skill

- `plugins/gin-workflow/src/skills/beads-migration/SKILL.md` describes the
  steps above. The target directory is an input with the default
  `~/gin-harness/beads/<repo>`. The vault path is removed.
- The skill stays user-invoked only.

### Split spec amendment

US-4 in `2026-10-20-split-orchestrator-design.md` changes from "one Beads
database in gin-harness" to "each repo's database kept in gin-harness, plus a
harness database for cross-project epics". The release-sequence step 3 is
narrowed to `sync.sh` and `versions.lock`.

### Working across repos

- Implementation sessions start in the child repo. The gin-workflow lifecycle
  (gates, `.planning/`, worktrees, review ledger, tests, hooks) stays per repo.
- Roadmap and cross-repo planning sessions start in `~/gin-harness`, using its
  database.
- A cross-repo epic is a `gin-harness-` epic that names one epic per child repo.
  Each child epic runs discuss, plan, execute and ship in its own repo. Ordering
  between them uses the `export:`/`external:` dependencies above.

## User Stories

### US-1: Keep every project's Beads in the harness
As the maintainer, I want each child repo's Beads database stored under
`~/gin-harness/beads/<repo>`, so that all task data lives in one place I can
back up and inspect.

Acceptance criteria:
- `~/gin-workflow/.beads` and `~/gin-console/.beads` are symlinks into
  `~/gin-harness/beads/`.
- `bd count` in each repo reports the same number as before the move (293 and
  31 at the time of writing, or the current count when the migration runs).
- `bd context` in each repo reports the same database name and project id as
  before.
- `gin-workflow task ready` and `gin-workflow state` work in gin-workflow, in
  its main checkout and in a new worktree.
- gin-console's git no longer tracks files under `.beads`, and `.beads` is in
  its `.gitignore`.

### US-2: Plan cross-project work in the harness
As the maintainer, I want a Beads database in gin-harness, so that the roadmap
and epics that span repos have a home.

Acceptance criteria:
- `bd context` in `~/gin-harness` reports its own database with prefix
  `gin-harness`.
- `bd create` in `~/gin-harness` creates an issue whose id starts with
  `gin-harness-`.

### US-3: Repeat the migration for a new repo
As the maintainer, I want the `beads-migration` skill to move any repo's Beads
into the harness safely, so that gin-orchestrator can follow the same steps
later.

Acceptance criteria:
- The skill names the target directory as an input with default
  `~/gin-harness/beads/<repo>`, and contains no `/home/coder/workspace/brain`
  path.
- The skill covers backup, the tracked-files check, the hooks check, and
  verification by `bd count` and `bd context`.

### US-4: Git hooks run in gin-workflow
As the maintainer, I want gin-workflow's `pre-commit` and `pre-push` hooks to
run, so that pushes are checked by tests as the ship skill assumes.

Acceptance criteria:
- `git config core.hooksPath` in gin-workflow resolves to an existing
  directory that contains `pre-commit` and `pre-push`.
- A `git push` from gin-workflow runs the `pre-push` hook.

### US-5: Order work across repos
As the maintainer, I want a bead in one repo to wait for a capability shipped in
another, so that a cross-repo epic runs in the right order.

Acceptance criteria:
- A gin-console bead with `external:gin-workflow:<capability>` is absent from
  `bd ready` in gin-console while the capability is not shipped.
- After the gin-workflow bead labelled `export:<capability>` is closed and
  `bd ship <capability>` runs, that gin-console bead appears in `bd ready`.
- `gin-workflow task ready` in gin-console gives the same result before and
  after. If it does not, the gap is recorded as a follow-up bug, not fixed here.
- The probe beads are deleted after the check.

## Errors and compatibility

- **Count mismatch after the move:** remove the symlink, restore the backup
  copy to `<repo>/.beads`, and stop.
- **Running process holds the Dolt lock:** stop before copying; never move a
  database in use.
- **Worktrees:** worktrees find Beads through the main checkout, so they follow
  the symlink. US-1 verifies this.
- **gin-console:** it runs `bd` inside each project directory, so the symlink
  is transparent to it. No code change.
- **Other hosts or clones:** a fresh clone has no `.beads`. Setting one up uses
  the `beads-migration` skill, or `bd init` against the harness path.

## Testing

- The migration itself is verified by the US-1, US-2 and US-5 checks, run and
  recorded as evidence.
- `tests/workflow_core/test_token_budget.py` (or the existing skill tests)
  asserts that the `beads-migration` skill has no vault path and mentions
  `~/gin-harness/beads/<repo>`, `bd count` and `bd context`.
- The full suite passes, and runs from the `pre-push` hook on the next push.
