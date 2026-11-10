# Team mode

Solo use needs nothing here: without a `team:` section in `.agent-workflow/config.yaml`, every stage behaves as described in [Lifecycle](../concepts/lifecycle.md). Team mode is opt-in. It adds member identity, gates proven by approved pull requests (GitHub, Gitea, AWS CodeCommit) or merge requests (GitLab), areas with owners, per-member claims, and optionally a shared Beads database. For how a PM, a BA, developers, and testers split the work, see [Team roles](../roles.md). The rules for branches, pull requests, review, and merge are in the [team git agreement](git-flow.md).

```mermaid
flowchart TD
  L["Lead: /gin:team-setup"] --> C["team block, CODEOWNERS, hooks"]
  C --> PR["Pull request merged"]
  PR --> M["Member: /gin:team-setup"]
  M --> W["Work on a track"]
  W --> G["Gate pull request approved by a listed role"]
```

## Enable it (lead)

Run `/team-setup` and answer as the lead. It asks for:

- the host (`github`, `gitlab`, `gitea`, or `codecommit`) and the commit convention (`conventional` or `none`);
- members: git email, roles, and host login for each person (on `codecommit`, the `aws_identity` instead);
- areas: a name, path globs (including the area's tests), the `lead` role, and optionally the `roles` allowed to own tracks;
- approvals: which roles approve `requirement_confirmed`, `ship`, and the `/roadmap` pull request (`roadmap`), and `area_lead` or roles for `plan_approved` (`[]` for none);
- optionally shared Beads: a separate repository used as `team.beads_sync.remote`.

It writes the `team:` block with `gin setup configure`, then runs `gin team init` to generate CODEOWNERS, the pull request template, the commit-msg hook, and with `--ci` a CI workflow that checks commit messages against the convention and, when the repository variable `GIN_WORKFLOW_INSTALL` holds an install command, runs `team codeowners --check` and (SDD layout) `specs lint`. Commit those on a branch. On the host, protect the base branch: require a pull request with an approval and code-owner review.

```yaml
team:
  host: github
  commit_convention: conventional
  members:
    an@example.com: {roles: [ba], login: an-ba}
    lan@example.com: {roles: [pm], login: lan-pm}
    binh@example.com: {roles: [be_lead, be_dev], login: binh-dev}
  areas:
    backend: {paths: ["services/**"], lead: be_lead, roles: [be_dev]}
  approvals:
    requirement_confirmed: [ba, be_lead]
    plan_approved: area_lead
    ship: [qe]
    roadmap: [pm]
```

## Join it (member)

Install the [prerequisites](../getting-started.md#prerequisites) first, and do not run `/gin:setup`: the lead has already configured the repository.

Run `/team-setup` as a member: `gin team whoami` must find your `git config user.email`; `gin team hooks` installs the commit-msg hook; log in with `gh auth login`, `glab auth login`, `gt auth login --host <instance URL>`, or `aws configure` or `aws sso login`, as your host needs; with shared Beads, `bd init --remote <remote>`. `gin setup doctor` reports anything still missing.

## What changes in each stage

The `team` skill carries the exact steps.

| Stage | In team mode |
|---|---|
| gates | `record` and `unblock` take the actor from your git email. A gate with roles in `team.approvals` takes `--evidence <PR url>`: `record` checks the pull request is merged (open is enough for `ship`) and approved by a member with a listed role who is not its author. The pull request must belong to this repository, or for `ship` to a `workspace.repos` child, and change the gate's artifact (`--plan`/`--spec` pick one when it changes several); the plan gate also runs `check-plan`. A rejection lists the missing approvals; it is never worked around with other evidence or a waiver. |
| `discuss` | When `requirement_confirmed` has roles, the spec goes through a pull request (`spec/<topic>`, or the SDD `pr` flow) and the gate is recorded after it merges. A member has no technical role when they are no area's `lead` and hold no role in any area's `roles`; `gin team whoami` then shows `technical: no`. That member gets business questions only, and the `team` skill has `discuss` write each technical point as `- TQ-<n>: <question>` under the design doc's `## Open Technical Questions`. |
| `plan` | Each track adds `Area:` and `Owner:` (optional only with shared Beads; reassigning a track means a new plan PR); a track's files stay inside its area. `team check-plan <plan>` must pass. With `plan_approved: area_lead`, the plan merges through a pull request approved by the area lead. `plan` first settles each open `TQ-<n>` with the member running it and writes `Decision:` under it. The plan pull request carries those lines and, with the SDD layout, the filled `03-design.md` sections. |
| `orchestrate` | Track beads get `track:<N>` and `area:<area>` labels and the owner as assignee. With shared Beads the lead orchestrates once; otherwise each member creates beads only for the tracks they own, and a dependency on someone else's track becomes an `external: <plan>#<N>` placeholder. |
| `execute` | `team deps` closes placeholders whose track has merged; pick work from `team ready`, claim it with `team claim <bead>` (a lease of `team.claim_ttl_hours`, renewed by claiming again; an expired lease lets another member take the bead; so does a bead assigned without a lease or with unreadable `claim` metadata), and in the track worktree `team deps --bead <bead>` must pass before implementation. The `team` skill names track branches `feat/<topic>-t<N>`; the pull request template's `Plan:` and `Tracks:` fields are read by other members' `team deps`. The [brownfield starter](../starters/brownfield.md#execute) shows claims, leases, and handing a track over. |
| `ship` | When `ship` has roles in `team.approvals`, only the pull request and keep options are offered, and that role approves the latest commit of the pull request before merge (`team check --gate ship <url>`); a later push needs a new approval. In team mode `record` also writes the gate's PR proof to the epic bead's `gates` metadata (see the [brownfield starter](../starters/brownfield.md#ship)). GitLab needs "Reset approvals on push", Gitea "Dismiss stale approvals", and CodeCommit binds approvals to the revision (see [Host settings](#host-settings)). Merging follows the host's rules (CODEOWNERS, branch protection). With shared Beads, `team sync` after closing beads. The old key `verification_passed` is deprecated and maps to `ship`. |

Milestone writes follow `team.permissions.milestone`, and with shared Beads they pull first and push after. Details are in the [milestone command](../reference/cli.md#gin-milestone).

To hand a track over (a member runs out of quota or is away), the current assignee or the area lead runs `gin team handoff <bead> <email>` from the main checkout. It refuses when the track worktree has uncommitted or untracked files. Otherwise it pushes the track branch and the review ref, records the branch on the bead, and reassigns it with a fresh lease. `gin team handoff <bead> --release` instead returns the bead to the pool: it loses its assignee and lease, reopens, and gets the label `released`. Any member then sees it in `gin team ready` and may claim it whatever their areas. The new owner runs `gin team takeover <bead>` in the main checkout of their clone: it fetches the branch, checks it out at `.planning/worktrees/<bead>`, fetches the review ref, and claims. The plan's `Owner:` field is not changed.

`gin team check --gate <gate> <url>` re-checks a teammate's gate without recording it.

A member's ship covers only their own tracks. The lead declares the feature complete once every track pull request has merged (the `team` skill's rule).

## Host settings

Each host needs a logged-in CLI and branch protection on the integration branch. The login commands are `gh auth login`, `glab auth login`, `gt auth login --host <instance URL>`, and `aws configure` or `aws sso login`. The `team` skill's `references/hosts.md` lists them with the open-pull-request command and settings per host. `gin setup doctor` reports a missing CLI or login with the fix to run.

- GitHub: branch protection on the integration branch and CODEOWNERS per area (`team init`). Recommended: "Dismiss stale pull request approvals when new commits are pushed". The `ship` gate counts only approvals made on the latest commit either way.
- GitLab: "Reset approvals on push" (`reset_approvals_on_push`), required for `ship`; without it the gate rejects the approval.

### Gitea

Set `team.host: gitea`. `team init` writes `.gitea/CODEOWNERS` and `.gitea/PULL_REQUEST_TEMPLATE.md`. Protect the integration branch with required approvals and turn on "Dismiss stale approvals". The `ship` gate counts only approvals made on the head commit either way.

`gt` is Gitea's CLI and needs Gitea 28 or later. Log in once per instance, and include any subpath in the URL:

```bash
gt auth login --host https://example.com/gitea --oauth
gt auth login --host https://example.com/gitea --with-token < token.txt
```

For an instance behind an access proxy, `gt auth login` also takes `--header` and `--client-cert`. A self-signed certificate must be trusted by the system, because gin passes no certificate option to `gt`.

`gin setup doctor` runs these Gitea checks:

- `gt` on `PATH` is Gitea's CLI. Graphite also names its CLI `gt`, and the check tells them apart by the output of `gt --version`.
- `gt` is logged in to the instance of `origin`. An https remote names the instance. For an SSH remote, gin looks for the logged-in instance with the same host name; with several matches, log in to one only or use an https remote.
- The instance runs Gitea 28 or later.

Two limits apply. gin identifies a Gitea repository by host, owner, and repository name, so do not run two Gitea instances on one host with the same repository paths. `gin team deps` and `gin specs trace` scan the newest 500 pull requests and at most 100 search hits.

### AWS CodeCommit

Set `team.host: codecommit`. CodeCommit has no CODEOWNERS file, pull request template, or CI workflow, so `team init` writes only the commit-msg hook, and `team init --ci` is refused with exit 2: use CodeBuild or CodePipeline for CI.

Each member who holds an approving role needs `aws_identity`, which gin matches against the approver. It is the IAM user name, or `<role>/<session>` for an assumed role (`arn:aws:sts::<account>:assumed-role/Dev/alice` matches `Dev/alice`). gin matches the role too, so a session named `alice` under another role is not alice. Anyone who may assume the same role can still pick any session name: use AWS SSO, which sets the session name, or an `sts:RoleSessionName` condition in the role trust policy. A bare session name such as `alice` matches no assumed role, so prefix it with the role. `gin team check` reports an approver without it as an error.

```yaml
team:
  host: codecommit
  members:
    alice@example.com: {roles: [be_lead], aws_identity: Dev/alice}
```

gin calls `aws` with your environment, so it needs credentials (`aws configure` or `aws sso login`) and a region. The region comes from the `origin` remote (`codecommit::<region>://<repo>` or the https form `git-codecommit.<region>.amazonaws.com`), else from `AWS_REGION`, else from `AWS_DEFAULT_REGION`. When the remote is `codecommit://<profile>@<repo>`, set `AWS_PROFILE` to that profile, because gin does not read the profile from the remote.

CodeCommit does not enforce code owners. Create an approval rule template and associate it with the repository, so a pull request needs approvals before merge:

```bash
aws codecommit create-approval-rule-template \
  --approval-rule-template-name team-approvals \
  --approval-rule-template-content '{"Version":"2018-11-08","DestinationReferences":["refs/heads/main"],"Statements":[{"Type":"Approvers","NumberOfApprovalsNeeded":1,"ApprovalPoolMembers":["arn:aws:sts::<account>:assumed-role/Dev/*"]}]}'
aws codecommit associate-approval-rule-template-with-repository \
  --approval-rule-template-name team-approvals --repository-name <repo>
```

Approvals belong to one revision of the pull request. The `ship` gate counts only approvals of the current revision whose source commit equals your local `HEAD`.

## CI (optional)

`gin team init --ci` writes a CI job for the host. Commit it with the rest of `team init`'s files.

| Host | File | Runs on |
|---|---|---|
| GitHub Actions | `.github/workflows/gin-workflow.yml` (job `conventions`) | every pull request |
| GitLab CI | `.gitlab/ci/gin-workflow.yml` (job `gin-workflow-conventions`, stage `test`) | every merge request |
| Gitea Actions | `.gitea/workflows/gin-workflow.yml` (job `conventions`) | every pull request |

CodeCommit has no CI file. GitLab does not pick the file up by itself: add `include: { local: .gitlab/ci/gin-workflow.yml }` to the root `.gitlab-ci.yml`.

The job always checks commit messages against `team.commit_convention` (skipped for `none`). It also runs `gin team codeowners --check` and, with the SDD layout, `gin specs lint`, but only when the variable `GIN_WORKFLOW_INSTALL` holds a shell command that installs `gin` on the CI runner; without it those two checks are skipped and the job still passes.

- GitHub: Settings, Secrets and variables, Actions, tab **Variables** (a Variable, not a Secret).
- GitLab: Settings, CI/CD, Variables.
- Gitea: the repository's Settings, Actions, Variables.
- Example value: `curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --platform claude`.

## Commands

See [`gin team`](../reference/cli.md#gin-team) and the [`team` configuration keys](../reference/config.md#team).
