# Team Mode (Sub-project E) — Design

Date: 2026-10-03
Status: awaiting user confirmation
Depends on:
- F (`.planning/specs/2026-10-03-sdd-living-specs-design.md`, shipped as schema 2.6): `artifacts.spec_review: pr`, `specs status` PR lookup via `gh`, templates and `specs lint`.
- D (`.planning/specs/2026-10-01-best-practice-rules-design.md`, schema 2.5): `setup doctor` checks and suggestions.
Followed by: G (`gin-qa` add-on).
Supersedes: the 2026-10-01 `bd remember` note `v-next-sub-project-e-team-mode-discuss` (lead plan + per-member plans). E uses one plan with per-track `Area:`/`Owner:` instead.

## Goal

A team (for example BA, QE, BE/FE devs, BE/FE leads) can run the gin-workflow lifecycle on one repository: every member is identified by git email, gates that need another person's approval are proven by a merged (or approved) PR/MR reviewed by someone holding the configured role, tracks are assigned by area and owner, and conventions are generated once and enforced locally and in CI. A repository without a `team:` key behaves exactly as today.

## Decisions

| Topic | Decision |
|---|---|
| Opt-in | `team:` key in `.agent-workflow/config.yaml`. Absent ⇒ solo behavior unchanged: free `--actor`, no host calls, no new doctor section. |
| Shared truth | Git and the git host are the shared source of truth (PR/MR + CODEOWNERS). Beads and workflow events stay local per member. Sharing Beads through a Dolt remote is optional (`team.beads_sync`). |
| Beads remote | A separate repository chosen by the team, e.g. `git+ssh://git@github.com/<org>/<project>-beads.git`. gin-workflow never creates it; it only runs `bd dolt remote add` / `pull` / `push`. |
| Members and roles | Declared in tracked config: `team.members.<email>: {roles: [...], login: <host-username>}`. Roles are free strings. Identity is `git config user.email`. |
| Areas | `team.areas.<name>: {paths: [globs], lead: <role>, roles: [<role>...]}` (`roles` optional: who may own tracks there). CODEOWNERS is generated from members + areas. |
| Approvals | `team.approvals.<gate>: [roles] \| area_lead \| []`. A gate with a non-empty policy is recorded only with a PR/MR URL as evidence, verified through the host CLI. |
| Track assignment | One plan; each track gets `Area:` (required in team mode) and `Owner:` (optional member email). No per-member plans. |
| Conventions | `gin-workflow team init [--ci] [--force]` generates CODEOWNERS, PR/MR template, `commit-msg` hook, optional CI. Enforced locally (hook via `core.hooksPath`) and on the server (CI, branch protection). |
| Hosts | GitHub (`gh`) and GitLab (`glab`), behind one `fetch_pr(url) -> PrInfo` interface. |
| Unknown identity | In team mode, a git email not in `team.members` can run read commands (`state`, `specs`, `rules`, `doctor`) but `record`, `unblock`, and track claims exit 2. |
| Schema | 2.7, version-only migration from 2.6. |

## Design

### 1. Configuration (schema 2.7)

```yaml
team:
  host: github                      # github | gitlab
  commit_convention: conventional   # conventional | none
  members:
    an@corp.com:   {roles: [ba], login: an-ba}
    binh@corp.com: {roles: [be_lead, be_dev], login: binh-dev}
    chi@corp.com:  {roles: [fe_lead, fe_dev], login: chi-fe}
    dung@corp.com: {roles: [qe], login: dung-qe}
  areas:
    backend:  {paths: ["services/**", "db/**"], lead: be_lead, roles: [be_dev]}
    frontend: {paths: ["web/**"], lead: fe_lead}
  approvals:
    requirement_confirmed: [ba, be_lead, fe_lead]
    plan_approved: area_lead
    verification_passed: []
  beads_sync:                       # optional
    remote: git+ssh://git@github.com/org/proj-beads.git
```

Defaults when `team:` exists: `host: github`, `commit_convention: conventional`, `approvals: {requirement_confirmed: [], plan_approved: area_lead, verification_passed: []}`, no `beads_sync`. `members` must be non-empty; `areas` may be empty (then `area_lead` requires nothing and `Area:` is not required).

Validation (at config resolution and in `doctor`), each failure listed, exit 2 on resolution:
- every role named in `approvals` or an area `lead` is held by at least one member;
- emails are unique case-insensitively and logins are unique;
- area path globs do not overlap (checked by matching each area's globs against the other areas' literal prefixes);
- `approvals` keys are only `requirement_confirmed`, `plan_approved`, `verification_passed`.

`gin-workflow state` adds `project.team: {enabled, host, me: {email, roles, areas} | null}`.

### 2. Modules

New files in `plugins/gin-workflow/src/scripts/workflow_core/`:
- `team.py` — `TeamConfig` (parsed `team:`), `current_member(repo) -> Member | None`, `required_approvers(gate, team, plan_tracks) -> list[Requirement]`, `check_approval(gate, pr, team, ...) -> list[str]` (empty = pass, otherwise reasons), `plan_tracks(path) -> list[Track]` with `Track(number, title, area, owner, files)`.
- `team_host.py` — `fetch_pr(url, host) -> PrInfo(url, state, merged, merge_commit, head_sha, author, approvers, files)`. GitHub: `gh pr view <url> --json state,mergeCommit,headRefOid,author,reviews,files`; approvers = logins whose latest review is `APPROVED`, with the commit each approval was made on. GitLab: `glab mr view <url> -F json` plus `glab api projects/:id/merge_requests/:iid/approvals` for `approved_by`; works with self-hosted instances through `glab` auth. `HostUnavailable` for a missing CLI, missing auth, or network failure.
- `team_init.py` — file generation for both hosts.
- `team_cli.py` — `gin-workflow team init | codeowners [--check] | whoami | check --gate G <url> | check-plan <plan> | ready | claim <bead> | deps | sync`.

`lifecycle_cli.py` calls `team.py` from `record` and `unblock` only when `team:` is present.

### 3. Gate recording and role checks

Identity: in team mode the actor is `current_member()`'s email. `--actor` becomes optional; if given it must equal that email (exit 2 otherwise). A non-member exits 2.

For a gate whose policy is non-empty, `--evidence` must be a PR/MR URL:
- `requirement_confirmed`: PR merged; at least one approver holds one of the listed roles; the PR author's own approval never counts.
- `plan_approved` with `area_lead`: PR merged; the plan file is located among the PR's `files` (first `.md` under the plans directory, or `--plan <path>` to choose); for every distinct `Area:` in `plan_tracks(plan)`, the area's `lead` role has an approver (author excluded). A list of roles behaves like `requirement_confirmed`.
- `verification_passed` with roles: the feature PR may be open or merged; an approval from a listed role exists on a commit equal to the PR `head_sha`, and `head_sha` equals the local feature branch `HEAD`, so code changed after approval is not counted.

Pass ⇒ the event payload adds `pr_url`, `merge_commit`, and `approvers: [{login, email, roles}]`. Fail ⇒ exit 1, no event, each reason on its own line (for example `missing approval from fe_lead for area frontend`). `HostUnavailable` ⇒ exit 2, no event, with the fix (`gh auth login`, `glab auth login`, install link).

Gates with an empty policy record as today, but the actor is still the member's email.

`gin-workflow team check --gate <gate> <url>` runs the same check without recording, so any member can re-verify a teammate's gate.

Waivers: in team mode `unblock --gate G` requires the actor to hold one of G's roles (for `area_lead`, any area lead). Safety gates still require `--follow-up`. `--clear-blocker` requires membership only.

Interaction with F: in team mode, when `approvals.requirement_confirmed` is non-empty, the effective `spec_review` is `pr`; `doctor` reports a config that still says `chat`. The `discuss` ending from F (push `spec/<epic>-<slug>`, wait for merge, record) is unchanged; only the record step now checks roles. Under `layout: legacy` the spec PR carries the `.planning/specs/` file instead of the change folder.

### 4. Plans, tracks, and execution

Plan metadata per track gains:
```
- Area: backend
- Owner: binh@corp.com
```
`gin-workflow team check-plan <plan>` (exit 1 on findings) checks: every track has `Area:` naming a configured area (when areas exist); every file in the track's Files section matches that area's paths; `Owner:`, when present, is a member eligible for that area. The `plan` skill runs it before asking for approval.

Owner eligibility: an area may list `roles: [be_dev, be_lead]`; a member is eligible when they hold one of those roles or the area's `lead` role. When `roles` is absent, any member is eligible.

Stable track identity across machines: `<plan-path>#<N>`. Track beads carry labels `track:<N>` and `area:<area>`; the PR/MR template carries `Plan: <path>` and `Tracks: <N,...>`.

Orchestrate:
- With `beads_sync`: the lead orchestrates once (beads created with `--assignee <owner>` when set, labels as above, deps via `bd dep add`), then `gin-workflow team sync` (`bd dolt pull`, then `bd dolt push`).
- Without sync: each member orchestrates locally and creates beads only for tracks they own or unowned tracks in an area they may own. A dependency on another member's track becomes a local placeholder bead titled `external: <plan>#<N>`. `gin-workflow team deps` finds merged PRs/MRs whose `Tracks:` line contains N (`gh pr list --state merged --search "<plan-path> in:body"` / `glab mr list --merged --search`) and closes matching placeholders.

Execute:
- `gin-workflow team ready` filters `bd ready --json` to beads assigned to me, plus unassigned beads whose `area:` label is an area I may own.
- `gin-workflow team claim <bead>` runs `BD_ACTOR=<email> bd update <bead> --claim`. With sync: pull → claim → push; a rejected push pulls again; if the bead is then assigned to someone else, the claim is released and the command exits 1 naming the holder.
- Branch: `feat/<epic>-<area>`, one worktree per member. One feature PR per track or per group of tracks, using the generated template.

Sync errors: a Dolt merge conflict exits 1 listing the conflicting beads and never uses `--force`; an unreachable remote leaves local commands working, makes `team sync` exit 2, and `doctor` warns.

Sync spike first: the first step of the sync track proves `bd dolt push`/`pull` against a git remote with two clones. If it fails, the git-remote option is dropped from E (a `file://` or DoltHub remote is still accepted) and the result is reported to the user before continuing.

### 5. `team init` and conventions

`gin-workflow team init [--ci] [--force]` writes, by host:

| File | GitHub | GitLab |
|---|---|---|
| CODEOWNERS | `.github/CODEOWNERS` | `.gitlab/CODEOWNERS` |
| PR/MR template | `.github/pull_request_template.md` | `.gitlab/merge_request_templates/Default.md` |
| commit-msg hook | `.githooks/commit-msg` | `.githooks/commit-msg` |
| CI (`--ci`) | `.github/workflows/gin-workflow.yml` | `.gitlab/ci/gin-workflow.yml` (the user adds `include:` to `.gitlab-ci.yml`; never edited by gin-workflow) |

- Every generated file contains the marker `generated by gin-workflow team init`. A file with the marker is regenerated; a file without it is user-owned and skipped (listed in the output) unless `--force`.
- CODEOWNERS: one line per area, `<glob> @<login of each member holding the area lead role>`, plus the plans and specs directories owned by the logins holding roles in `approvals.requirement_confirmed` and the area leads. `team codeowners --check` exits 1 on drift.
- PR/MR template: `Plan:`, `Tracks:`, `Spec:` / REQ-IDs, bead ids, tests run, checklist.
- `commit-msg` hook (POSIX sh): with `conventional`, requires `^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?!?: .+`; skips merge commits, `fixup!`/`squash!`, and `Revert "`; `none` makes it a no-op. Activated per clone with `git config core.hooksPath .githooks`.
- CI: runs the same commit regex over the PR's commits with plain shell (no gin-workflow install needed); runs `gin-workflow specs lint` and `team codeowners --check` only when the job can install gin-workflow (documented step, skipped otherwise).

Branch protection or GitLab approval rules are not configured by gin-workflow; `team-setup` prints the exact settings to enable. On GitLab Free, required code-owner approval is unavailable; the CLI check still applies.

### 6. Doctor

`checks_details.team` appears only when `team:` exists:
- config valid (section 1 rules);
- current git email is a member;
- `core.hooksPath` is `.githooks` when `commit_convention` is not `none`;
- host CLI present and authenticated (`gh auth status` / `glab auth status`);
- CODEOWNERS in sync;
- effective `spec_review` consistent with `approvals.requirement_confirmed`;
- with `beads_sync`: the remote is configured in `bd dolt remote list` and reachable;
- GitLab: an info note that enforced approvals need GitLab Premium.

Each failing check adds a `team:` action with the fix command.

### 7. Skills

- New `skills/gin-team/SKILL.md`: the team-mode procedure for each stage (identity, PR evidence, `check-plan`, `ready`/`claim`/`sync`, `deps`). Named conditionally by stage skills like `gin-sdd`, so it is not counted in any stage's token chain.
- New `skills/team-setup/SKILL.md` (`/gin-workflow:team-setup`): lead path — collect members, roles, logins, areas, approvals, write them with `gin-workflow setup configure`, run `team init`, print branch-protection settings; member path — `core.hooksPath`, `bd dolt remote add` + first `team sync` when `beads_sync` is set, `team whoami`, `doctor`.
- One added line each in `discuss`, `plan`, `orchestrate`, `execute`, `verify`, `ship`: "If `project.team.enabled`, follow the `gin-team` skill for this stage."
- `agents/developer.md`: commit messages follow `team.commit_convention` when team mode is on.

### 8. Migration and solo guarantee

`_migrate_2_6_to_2_7` bumps the version only. No `team:` is ever added automatically. With no `team:`, `record`, `unblock`, `state` (apart from `project.team: {enabled: false, ...}`), and `doctor` behave as in 2.6 and no host CLI is invoked.

## Testing

- Solo regression: without `team:`, `record`/`unblock` results and events match 2.6 behavior; a fake `gh`/`glab` on `PATH` that fails when called proves no host call happens.
- Config validation: each rule in section 1, with all findings reported.
- Policy matrix with fake `gh` and `glab` executables returning JSON fixtures: merged vs open; missing role; author self-approval; missing lead for one of two areas; QE approval on an older commit; non-member actor; `--actor` mismatch; `HostUnavailable` ⇒ exit 2 and no event.
- `plan_tracks` and `check-plan`: missing `Area:`, file outside area, ineligible owner.
- `team init`: both hosts; rerun is a no-op; a user-owned file is skipped; `--force` overwrites; `codeowners --check` detects drift.
- Hook: accepted and rejected sample messages, skipped merge/fixup/revert, `none`.
- `ready`/`claim`/`deps` against a temporary Beads database; sync with two clones and a `file://` Dolt remote, plus the git-remote spike; skipped when `dolt` is not installed.
- Migration 2.6 → 2.7, `state` `project.team`, doctor `checks_details.team`, token budget (`gin-team` loads on demand), installer packaging of the new skills.

## Non-goals

- Bitbucket or other hosts.
- Configuring branch protection or approval rules through host APIs.
- Several teams or sub-teams in one repository.
- Ownership per REQ-ID.
- Sharing workflow events between members.
- G (`gin-qa`).
