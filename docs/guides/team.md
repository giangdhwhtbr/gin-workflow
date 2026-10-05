# Team Mode

Solo use needs nothing here: without a `team:` section in `.agent-workflow/config.yaml`, every stage behaves as described in [Lifecycle](../concepts/lifecycle.md). Team mode is opt-in. It adds member identity, gates proven by approved pull requests (GitHub) or merge requests (GitLab), areas with owners, per-member claims, and optionally a shared Beads database.

## Enable it (lead)

Run `/team-setup` and answer as the lead. It asks for:

- **host**: `github` or `gitlab`, and the **commit convention**: `conventional` or `none`;
- **members**: git email, roles, and host login for each person;
- **areas**: a name, path globs (including the area's tests), the `lead` role, and optionally the `roles` allowed to own tracks;
- **approvals**: which roles approve `requirement_confirmed` and `verification_passed`, and `area_lead` or roles for `plan_approved` (`[]` for none);
- optionally **shared Beads**: a separate repository used as `team.beads_sync.remote`.

It writes the `team:` block with `gin-workflow setup configure`, then runs `gin-workflow team init` to generate CODEOWNERS, the pull request template, the commit-msg hook, and with `--ci` a CI workflow that checks commit messages against the convention and, when the repository variable `GIN_WORKFLOW_INSTALL` holds an install command, runs `team codeowners --check` and (SDD layout) `specs lint`. Commit those on a branch. On the host, protect the base branch: require a pull request with an approval and code-owner review.

```yaml
team:
  host: github
  commit_convention: conventional
  members:
    an@example.com: {roles: [ba], login: an-ba}
    binh@example.com: {roles: [be_lead, be_dev], login: binh-dev}
  areas:
    backend: {paths: ["services/**"], lead: be_lead, roles: [be_dev]}
  approvals:
    requirement_confirmed: [ba, be_lead]
    plan_approved: area_lead
    verification_passed: [qe]
```

## Join it (member)

Run `/team-setup` as a member: `gin-workflow team whoami` must find your `git config user.email`; `gin-workflow team hooks` installs the commit-msg hook; log in with `gh auth login` or `glab auth login`; with shared Beads, `bd init --remote <remote>`. `gin-workflow setup doctor` reports anything still missing.

## What changes in each stage

The `gin-team` skill carries the exact steps.

| Stage | In team mode |
|---|---|
| gates | `record` and `unblock` take the actor from your git email. A gate with roles in `team.approvals` takes `--evidence <PR url>`: `record` checks the pull request is merged (open is enough for `verification_passed`) and approved by a member with a listed role who is not its author. A rejection lists the missing approvals; it is never worked around with other evidence or a waiver. |
| `discuss` | When `requirement_confirmed` has roles, the spec goes through a pull request (`spec/<topic>`, or the SDD `pr` flow) and the gate is recorded after it merges. |
| `plan` | Each track adds `Area:` and optionally `Owner:`; a track's files stay inside its area. `team check-plan <plan>` must pass. With `plan_approved: area_lead`, the plan merges through a pull request approved by the area lead. |
| `orchestrate` | Track beads get `track:<N>` and `area:<area>` labels and the owner as assignee. With shared Beads the lead orchestrates once; otherwise each member creates beads for their own tracks, and a dependency on someone else's track becomes an `external: <plan>#<N>` placeholder. |
| `execute` | `team deps` closes placeholders whose track has merged; pick work from `team ready` and claim it with `team claim <bead>`. Branches are `feat/<epic>-<area>`; the pull request template's `Plan:` and `Tracks:` fields are read by other members' `team deps`. |
| `verify` | When `verification_passed` has roles, that role approves the latest commit of the pull request; a later push needs a new approval. |
| `ship` | Merging follows the host's rules (CODEOWNERS, branch protection). With shared Beads, `team sync` after closing beads. |

`gin-workflow team check --gate <gate> <url>` re-checks a teammate's gate without recording it.

## Commands

See [`gin-workflow team`](../reference/cli.md#gin-workflow-team) and the [`team` configuration keys](../reference/config.md#team).
