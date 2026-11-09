# Team mode hosts: Gitea and AWS CodeCommit

Epic: gin-workflow-uj2o
Workflow: gin-workflow-uj2o
Status: confirmed by the user on 2026-11-09.

## Goal and scope

Team mode accepts `team.host: gitea` and `team.host: codecommit` next to `github` and `gitlab`. On both new hosts a gate whose approving roles are set in `team.approvals` is recorded from a pull request URL, and `gin team init`, `gin team check`, `gin team deps`, and `gin setup doctor` work.

Confirmed understanding (2026-11-09):

- Today `team_host.py` has two adapters, `gh` and `glab` (`_EXECUTABLE`, `team_host.py:13`); host branches are also spread over `team_init.py:22-27,157-188`, `team.py:343-364`, `team_beads.py:362-370`, `schemas.py:19`, `executables.py:14`, and `specs_trace.py:61-68`, which calls `gh` whatever the host (a bug on GitLab today).
- Gitea fits the existing model: reviews carry `commit_id` and a `stale` flag, identities are logins, pull request URLs are `https://<host>/<owner>/<repo>/pulls/<n>`, and it has CODEOWNERS, pull request templates, and Actions.
- AWS CodeCommit differs: identities are IAM ARNs, approvals belong to a pull request `revisionId`, the console URL carries region and repository name instead of `owner/repo`, there is no CODEOWNERS, pull request template, or text search over pull requests. The service returned to general availability for new customers on 2025-11-24.
- User decisions (2026-11-09):
  - CodeCommit identity: an optional per-member `aws_identity`, matched against the IAM user name or the assumed-role session name of an approver or author (option A).
  - Gitea access: the official Gitea CLI `gt` (docs.gitea.com/cli), through `gt api` with the credentials of `gt auth login`; `gt` needs Gitea 28 or later, so older instances are not supported (option A, replacing an earlier choice of `tea`).
  - Gitea covers self-hosted instances (any domain, port, or subpath), not only gitea.com.
  - CodeCommit `team init`: no generated file replaces CODEOWNERS; doctor notes that the host does not enforce code owners, and the docs show how to create an approval rule template by hand (option A).
  - Approach: one adapter module per host behind one interface (approach 1).

Comments considered: 0.

In scope: the host adapter interface and four adapters, schema and config validation, `team init`, `team check`, `team deps`, gate recording, `setup doctor`, `specs trace`, the `team`, `team-setup`, `ship`, and `sdd` skills, tests, and docs in this repository.

Out of scope:
- CI for CodeCommit (CodeBuild, CodePipeline); `gin team init --ci` refuses on CodeCommit.
- Generating or applying a CodeCommit approval rule template.
- Forgejo: it may work through the Gitea adapter, but it is not tested or documented as supported.
- gin-console: it only displays the `host` string from `gin state`.

## Requirements

### R1. Host adapter interface

A package `workflow_core/hosts/` holds one module per host (`github`, `gitlab`, `gitea`, `codecommit`) and a registry `adapter(host) -> HostAdapter`. Each adapter provides:

- `executable` and `login_fix` (the CLI name and the command that fixes a missing or failed login);
- `auth_check_argv` (the command `setup doctor` runs to check the login);
- `fetch_pr(url, cwd) -> PrInfo` with the existing `PrInfo` fields;
- `merged_with_text(text, cwd) -> list[PrInfo]`;
- `repo_matches(pr_url, origin_url) -> bool`, replacing the `repo_slug` comparison in `team.check_approval`;
- `files`: the paths of CODEOWNERS, the pull request template, and the CI workflow with its template, each `None` when the host has none;
- `doctor_notes`: host-specific notes (the GitLab Free note moves here).

`team.py`, `team_init.py`, `team_beads.py`, and `specs_trace.py` call the registry and contain no host names. `team_host.py` keeps `fetch_pr`, `merged_with_text`, `PrInfo`, and `HostUnavailable` as thin entry points, so existing imports keep working. GitHub and GitLab behaviour does not change; their existing tests pass unchanged.

### R2. Gitea adapter

- CLI: `gt`, through `gt api --host <instance base URL> <path>` (paths relative to `/api/v1/`). `login_fix`: `gt auth login --host <instance base URL>` (with `--with-token` or `--oauth`). `auth_check_argv`: `gt auth status`. Exit code 4 from `gt` (authentication missing or rejected) becomes `HostUnavailable` with `login_fix`.
- Server version: `setup doctor` reads `version` from the API and reports an instance older than Gitea 28 as unsupported; `fetch_pr` does not check the version.
- `fetch_pr`: from `repos/{owner}/{repo}/pulls/{n}` (state, merged, merge commit, head SHA, author login, body), `.../pulls/{n}/reviews`, and `.../pulls/{n}/files`. Approvals: per reviewer, the latest review that is not dismissed; it counts when its state is `APPROVED`, and its commit is `commit_id`. A review with an empty `commit_id` gets `""` and the `approval_note` says it predates commit tracking.
- `merged_with_text`: the issue search for closed pull requests whose text matches, then `pulls/{n}` for each result to keep the merged ones, at most 100.
- `repo_matches`: `owner/repo` from the two URL path segments before `/pulls/`, compared with the origin remote, case-insensitive.
- Self-hosted Gitea is supported, not only gitea.com (user requirement 2026-11-09):
  - The instance is any scheme, host, and port, and may live under a subpath (`https://git.example.com/gitea/<owner>/<repo>/pulls/<n>`); the instance base URL is everything before `/<owner>/<repo>/pulls/`.
  - Origin remotes in every form match: `https://` or `http://` with a port or subpath, `ssh://git@host:2222/<owner>/<repo>.git`, and scp-style `git@host:<owner>/<repo>.git`. The host must match the pull request URL's host; the port and subpath are not compared for SSH remotes, because SSH and HTTP ports differ.
  - `gt` keeps credentials per instance; every `gt api` call passes `--host <instance base URL>` from the pull request URL, so the right instance is used when several are logged in. Without a login for that instance, `gt` exits 4 and gin reports `gt auth login --host <instance base URL>`.
  - TLS: gin adds no TLS option of its own. An instance behind an access proxy uses the `gt` login options (`--header`, `--client-cert`); a self-signed certificate must be trusted by the system, and the docs say so.
  - `setup doctor` checks the `gt` login for the instance of the origin remote (`gt auth status`), not only that `gt` is logged in somewhere.
- `files`: `.gitea/CODEOWNERS`, `.gitea/PULL_REQUEST_TEMPLATE.md`, `.gitea/workflows/gin-workflow.yml` from a new template `templates/team/gitea-ci.yml` that does not use `hashFiles`.

### R3. CodeCommit adapter

- CLI: `aws`. `login_fix`: `aws configure` or `aws sso login`. `auth_check_argv`: `aws sts get-caller-identity`.
- Accepted URL: the console URL `https://<region>.console.aws.amazon.com/codesuite/codecommit/repositories/<repo>/pull-requests/<id>`, with an optional query string. Any other form fails with `HostUnavailable` showing the expected form.
- `fetch_pr`: `aws codecommit get-pull-request --pull-request-id <id> --region <region>`: state (`OPEN` maps to `open`; `CLOSED` maps to `merged` when `mergeMetadata.isMerged`, else `closed`), merge commit, head SHA (`sourceCommit`), author, description, `revisionId`. Approvals: `get-pull-request-approval-states --revision-id <revisionId>`; each `APPROVE` counts with the commit `sourceCommit` of that revision. Changed files: `get-differences` between `mergeBase` (or `destinationCommit`) and `sourceCommit`, following `NextToken`.
- Identity: an ARN maps to a name: `arn:aws:iam::<acct>:user/<name>` gives `<name>`; `arn:aws:sts::<acct>:assumed-role/<role>/<session>` gives `<session>`. `PrInfo.author` and approval logins carry that name. `Team.by_login` falls back to matching a member's `aws_identity` (case-insensitive) on CodeCommit.
- `merged_with_text`: `list-pull-requests --repository-name <repo> --pull-request-status CLOSED`, then `get-pull-request` for each, keeping merged ones whose description contains the text, at most 100.
- `repo_matches`: region and repository name from the console URL against the origin remote, in either form `codecommit::<region>://<repo>` (also `codecommit://<profile>@<repo>` with the region from the AWS configuration) or `https://git-codecommit.<region>.amazonaws.com/v1/repos/<repo>`.
- `files`: no CODEOWNERS, no pull request template, no CI. `gin team init` writes only the commit-msg hook; `--ci` exits 2 with "CodeCommit has no CI workflow file; use CodeBuild or CodePipeline". `doctor_notes`: "CodeCommit does not enforce code owners; create an approval rule template (see docs/guides/team.md)".

### R4. Configuration

- `schemas.py`: `host` enum `["github", "gitlab", "gitea", "codecommit"]`; a member may have `aws_identity` (non-empty string).
- Validation: with `host: codecommit`, `gin team check` reports each member without `aws_identity` (an error for members holding a role listed in `team.approvals`, a warning otherwise); `aws_identity` values are unique across members.
- `executables.KNOWN_TOOLS` gains `gt` and `aws`.
- Widening the enum and adding an optional field keeps every existing configuration valid; no migration.

### R5. Gates and checks

- `gin record` with a pull request URL, `gin team check --gate <gate> <url>`, and `gin team deps` behave on Gitea and CodeCommit as on GitHub: same conditions (repository, artifact changed, approver role not the author, approval on the latest commit for `ship`) and the same rejection messages.
- `gin setup doctor` runs the adapter's `auth_check_argv` and prints its `login_fix` and `doctor_notes`.
- `gin specs trace` finds a change's spec pull request through the adapter instead of calling `gh`; on a host whose adapter cannot search by branch it reports the existing unavailable status with the host name.

### R6. Skills

- `team-setup`: host is one of the four; login commands per host; `aws_identity` asked for each member on CodeCommit; branch-protection advice per host (Gitea: protected branch with required approvals and "Dismiss stale approvals"; CodeCommit: an approval rule template).
- `ship` and `sdd`: the command that opens a pull request per host (`gh pr create --fill`, `glab mr create --fill`, `gt pr create`, `aws codecommit create-pull-request`; each command and flag checked against the CLI's `--help` when written), taken from one table in the `team` skill's references, not repeated per skill.
- `team`: the "Reset approvals on push" note stays GitLab-only; Gitea needs "Dismiss stale approvals" for the same reason; CodeCommit ties approvals to the revision.
- Skill files stay within their character budgets (`tests/workflow_core/test_token_budget.py`).

### R7. Docs

`docs/guides/team.md` (hosts, settings per host, logging `gt` in to a self-hosted Gitea (Gitea 28 or later, `gt auth login --host`, the proxy options, a self-signed certificate trusted by the system), the CodeCommit approval rule template), `docs/guides/git-flow.md` and `.vi.md` (Gitea and CodeCommit host procedures; the CodeCommit limitation sentence and its pointer replaced by the supported flow), `docs/reference/config.md` (`host`, `aws_identity`), `docs/reference/cli.md` (`team init --ci` on CodeCommit, doctor checks). Vietnamese text is written with the `vietnamese-tech-writing` skill.

## User Stories

### US-1: Run team mode on Gitea
As a team lead on a self-hosted Gitea, I want team mode to read our pull requests, so that gates are proven by approvals like on GitHub.

Acceptance criteria:
- `gin team init` writes `.gitea/CODEOWNERS`, `.gitea/PULL_REQUEST_TEMPLATE.md`, and with `--ci` `.gitea/workflows/gin-workflow.yml`.
- `gin record requirement-confirmed --evidence <gitea PR url>` succeeds for a merged pull request approved by a listed role and fails with the missing approvals otherwise.
- `gin team check --gate ship <url>` counts only approvals on the pull request's head commit.
- `gin setup doctor` reports a missing `gt`, a missing login for the instance (with `gt auth login --host <instance>`), or an instance older than Gitea 28.
- On a self-hosted instance under a subpath with an SSH remote on a custom port, the same gate succeeds, and `gt` is called with that instance's `--host` when several instances are logged in.

### US-2: Run team mode on CodeCommit
As a team lead on AWS CodeCommit, I want gates recorded from CodeCommit pull requests, with approvers matched to members by their AWS identity.

Acceptance criteria:
- An approval by `arn:aws:sts::<acct>:assumed-role/Dev/alice` counts for the member whose `aws_identity` is `alice`.
- The ship check counts only approvals of the current revision whose source commit equals local HEAD.
- A console URL of another repository or region is rejected as not this repository.
- `gin team init` writes only the commit-msg hook, `--ci` exits 2 with the CodeBuild/CodePipeline message, and doctor shows the approval rule template note.
- `gin team check` reports an approver without `aws_identity` as an error.

### US-3: Keep GitHub and GitLab unchanged
As an existing team, I want the refactor to change nothing on GitHub and GitLab, so that my configuration and gates keep working.

Acceptance criteria:
- Existing tests for GitHub and GitLab hosts pass without changes to their expectations.
- `gin specs trace` on GitLab uses `glab` instead of failing with `gh_unavailable`.

### US-4: Read how to set up each host
As a member who is not technical, I want the team docs and the team git agreement to show the steps on our host, so that I can follow them without knowing the CLI.

Acceptance criteria:
- `git-flow.md` and its `.vi.md` pair have Gitea and CodeCommit host procedures, and the old CodeCommit limitation sentence is gone.
- `team.md` shows the per-host settings and the CodeCommit approval rule template steps.

## Errors and compatibility

- A missing CLI, failed login, unreachable host, unexpected URL, or non-JSON output raises `HostUnavailable`: exit 2, nothing recorded, the message names the fix.
- CodeCommit pagination (`NextToken`) is followed for differences and the pull request list.
- `team_host` keeps its public names, so callers and tests that import them keep working.
- Existing configurations validate unchanged; no schema migration.

## Testing

- New tests per adapter with `fake_cli` fakes of `gt` and `aws` (`tests/workflow_core/team_fixtures.py` pattern): `fetch_pr` mapping, approvals on the head commit, stale or dismissed reviews (Gitea), revision approvals and ARN mapping (CodeCommit), `merged_with_text`, `repo_matches` for each URL and remote form, pagination; for Gitea also a self-hosted instance with a subpath, an SSH remote with a custom port, `--host` passed on every `gt api` call, `gt` exit 4 mapped to the login fix, and the doctor version check (Gitea 28 and older).
- Gate tests for both hosts mirroring `test_team_gates.py` (merged spec gate, ship gate on head, author excluded, wrong repository).
- `test_team_init.py`: files per host, `--ci` refusal on CodeCommit, doctor checks and notes.
- Schema tests: new enum values, `aws_identity`, uniqueness and missing-identity reports.
- `specs trace` on GitLab through the adapter.
- Existing GitHub and GitLab tests unchanged and passing; skill budget tests; `gin docs check` and `mkdocs build --strict`.

## Open Technical Questions
