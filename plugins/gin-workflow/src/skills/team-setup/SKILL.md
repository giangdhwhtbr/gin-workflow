---
name: team-setup
description: Set up or join gin-workflow team mode — members, roles, areas, approvals, generated conventions, hooks, and optional shared Beads.
---

# Team Setup

Requires `.agent-workflow/config.yaml`; if it is missing, tell the user to run `/setup` once and stop. Ask one question per message. Ask whether the user is the lead enabling team mode or a member joining.

## Lead: enable team mode
1. Collect: host (`github` or `gitlab`); commit convention (`conventional` or `none`); each member's git email, roles, and host login; areas (name, path globs that include the area's tests, `lead` role, optional `roles` allowed to own tracks); approvals (`requirement_confirmed` roles, `plan_approved: area_lead` or roles, `ship` roles, `roadmap` roles (who approves the `/roadmap` PR), `[]` for none). Optional shared Beads: a separate repository that already has one commit (for example created with a README), used as `beads_sync.remote` such as `git+ssh://git@github.com/<org>/<project>-beads.git`.
2. Show the resulting `team:` YAML and get confirmation. Write it with `gin-workflow setup configure --approve --set 'team=<json>'`, adding `--set 'artifacts.spec_review="pr"'` when `requirement_confirmed` lists roles. Exit 2 lists every rule the config breaks; fix them and retry.
3. `gin-workflow team init` (`--ci` adds a CI job); report the files it skipped. Commit on a branch, push, and offer to open a PR.
4. With `beads_sync`: `bd dolt remote add origin <remote>`, then `gin-workflow team sync`.
5. Tell the lead what to enable on the host: branch protection on the base branch requiring a PR with one approval and code-owner review (GitHub "Require review from Code Owners"; GitLab Premium "Code owner approval"). The CI spec and CODEOWNERS step runs only when the repository variable `GIN_WORKFLOW_INSTALL` holds a command that installs gin-workflow; on GitLab also add the `include` for `.gitlab/ci/gin-workflow.yml` (see the CI section of docs/guides/team.md).

## Member: join
1. `gin-workflow team whoami` must print your entry; otherwise fix `git config user.email` or ask the lead to add you.
2. `gin-workflow team hooks` (installs the commit-msg hook without replacing Beads hooks).
3. Log in to the host CLI: `gh auth login` or `glab auth login`.
4. With `beads_sync` and no `.beads/` yet: `bd init --remote <remote>`. With an existing `.beads/`, ask before replacing it.
5. `gin-workflow setup doctor --format json`: every check in `checks_details.team` must be true; follow its `team:` actions otherwise.
