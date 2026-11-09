# Plan: Team mode hosts: Gitea and AWS CodeCommit

Epic: gin-workflow-uj2o
Spec: `.planning/specs/2026-11-09-team-hosts-design.md`

## Objective

Team mode accepts `team.host: gitea` (self-hosted included, through the official `gt` CLI, Gitea 28 or later) and `team.host: codecommit` (through `aws codecommit`, members matched by `aws_identity`). Gates with approving roles record from a pull request URL on both hosts; `team init`, `team check`, `team deps`, `setup doctor`, and `specs trace` work; GitHub and GitLab behave exactly as today.

**Goal** (spec): one host adapter per host behind one interface; Gitea and CodeCommit adapters; configuration, skills, and docs.

**Architecture.** A new package `plugins/gin-workflow/src/scripts/workflow_core/hosts/` holds `base.py` (the interface and `HostFiles`), a lazy registry in `__init__.py`, and one module per host. `team_host.py` stays the facade: it keeps `PrInfo`, `HostUnavailable`, the shared CLI runner `_run(host, argv, cwd)`, the imported `tool`, `fetch_pr(url, host, cwd)`, and `merged_with_text(host, text, cwd)`. Adapters call `team_host._run` through the module object at call time, so the existing tests that patch `workflow_core.team_host._run` and `workflow_core.team_host.tool` keep working. `team.py`, `team_init.py`, `team_beads.py`, and `specs_trace.py` reach hosts only through the registry.

**Tech stack.** Python 3 standard library, existing `jsonschema` validation, `unittest` with the `fake_cli` fixture (`tests/workflow_core/team_fixtures.py:129-145`), Markdown skills and docs.

**Global Constraints** (from the spec):
- Out of scope: CI for CodeCommit (CodeBuild, CodePipeline); `gin team init --ci` refuses on CodeCommit.
- Out of scope: generating or applying a CodeCommit approval rule template.
- Out of scope: Forgejo: it may work through the Gitea adapter, but it is not tested or documented as supported.
- Out of scope: gin-console: it only displays the `host` string from `gin state`.
- GitHub and GitLab behaviour does not change; their existing tests pass unchanged.
- Existing configurations validate unchanged; no schema migration.
- Skill files stay within their character budgets (`tests/workflow_core/test_token_budget.py`).
- Vietnamese text is written with the `vietnamese-tech-writing` skill.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: host logic lives in `team_host.py:13-141` plus branches in `team.py:343-364,398,507`, `team_init.py:22-27,157-188`, `team_beads.py:362-370`, `specs_trace.py:58-77`, `schemas.py:19`, `executables.py:14`; `specs_trace.status` calls `gh` on every host.
- Success criteria: spec R1–R7 and US-1–US-4; the full suite passes; existing GitHub/GitLab tests unchanged.
- Constraints: the Global Constraints above; `gt` (Gitea) needs server 28+; `gt` is also the name of Graphite's CLI.
- Non-goals: CodeCommit CI, approval rule template generation, Forgejo, gin-console.

## Approach Options
### Option 1: Adapter package behind the existing facade
- Summary: `hosts/` modules implement one interface; `team_host.py` keeps its public names and the patched `_run`/`tool`.
- Pros: no host names in callers; new hosts are new modules; existing tests unchanged.
- Cons: adapters reach `team_host._run` through the module object (a deliberate indirection for test patching).

### Option 2: `elif` branches in place
- Summary: add `gitea` and `codecommit` branches wherever `github`/`gitlab` appear.
- Pros: smaller first diff.
- Cons: five files keep host branches; each new host edits all of them.

### Recommended Approach
- Selected option: Option 1 (user decision 2026-11-09, approach 1).
- Rationale: one interface, isolated adapters, unchanged tests.

## Scope
- In scope: spec R1–R7.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Track 1 builds the adapter interface and moves GitHub/GitLab; Tracks 2 (Gitea) and 3 (CodeCommit) are new modules plus disjoint edits and run in parallel after it; Track 4 (skills and docs) needs the shipped facts of 2 and 3.
```

## Interfaces

Produced by Track 1, consumed by Tracks 2–4 (`workflow_core/hosts/base.py`):

```python
@dataclass(frozen=True)
class HostFiles:
    codeowners: str | None
    template: str | None
    ci: str | None
    ci_template: str | None          # path under templates/, e.g. "team/github-ci.yml"


class HostAdapter(Protocol):
    name: str                         # "github" | "gitlab" | "gitea" | "codecommit"
    executable: str                   # "gh" | "glab" | "gt" | "aws"
    login_fix: str                    # shown when the CLI is missing or not logged in
    auth_exit_codes: tuple[int, ...]  # CLI exit codes meaning "not logged in" (gt: (4,)); () for none
    identity_key: str                 # member field approvals are matched on: "login" or "aws_identity"
    files: HostFiles

    def auth_check_argv(self, root: Path) -> list[str]: ...
    def fetch_pr(self, url: str, cwd: Path) -> PrInfo: ...
    def merged_with_text(self, text: str, cwd: Path) -> list[PrInfo]: ...
    def pr_for_branch(self, branch: str, cwd: Path) -> PrInfo | None: ...   # newest PR of any state
    def repo_id(self, location: str, *, pr: bool = False) -> str: ...      # remote or PR URL -> comparable id
    def doctor_checks(self, root: Path) -> dict[str, tuple[bool, str]]: ...  # extra check name -> (ok, fix)
    def doctor_notes(self) -> list[str]: ...
```

Registry (`workflow_core/hosts/__init__.py`):

```python
HOSTS = ("github", "gitlab", "gitea", "codecommit")

def adapter(host: str) -> HostAdapter:
    """The adapter module's ADAPTER; ValueError for an unknown host."""
```

Facade (`team_host.py`, names unchanged): `PrInfo`, `HostUnavailable`, `_run(host, argv, cwd)`, `fetch_pr(url, host, cwd)`, `merged_with_text(host, text, cwd)`; new `pr_for_branch(host, branch, cwd)`.

Team model (`team.py`): `Member.aws_identity: str = ""`; `TeamConfig.by_identity(name: str, key: str = "login") -> Member | None`; `by_login(login)` stays as `by_identity(login, "login")`; `origin_url(root) -> str` (raw remote; `origin_slug` removed with its only caller).

## Tasks
### Track 1: Host adapter interface; GitHub and GitLab moved behind it
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/hosts/__init__.py` (registry, `HOSTS`)
  - Create `plugins/gin-workflow/src/scripts/workflow_core/hosts/base.py` (`HostFiles`, `HostAdapter`)
  - Create `plugins/gin-workflow/src/scripts/workflow_core/hosts/github.py` (code of `_github` and the GitHub half of `merged_with_text`, `repo_id` = current `repo_slug`)
  - Create `plugins/gin-workflow/src/scripts/workflow_core/hosts/gitlab.py` (code of `_gitlab_ref`, `_gitlab`, `_UNSETTLED`, the GitLab half of `merged_with_text`, the GitLab Free note)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_host.py:13-141` (facade; `_run` takes executable, login fix, and auth exit codes from the adapter)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:56-57,326-364,393-400,478-508` (`by_identity`, `_approver_roles` uses the adapter's `identity_key`, `check_approval` and `authorize_record` compare `adapter.repo_id`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_init.py:22-32,59-69,96-98,153-189` (files and doctor from the adapter; `--ci` on a host whose `files.ci` is None raises `TeamError`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:361-370` (unchanged call through the facade)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_trace.py:58-77` (`pr_for_branch` of the configured host; status `<executable>_unavailable` when the CLI is missing)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:19` (enum `["github", "gitlab", "gitea", "codecommit"]`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/executables.py:14` (add `"gt"`, `"aws"`)
  - Create `plugins/gin-workflow/src/scripts/workflow_core/hosts/gitea.py` and `hosts/codecommit.py` as stubs whose `ADAPTER` raises `HostUnavailable("<host> support is not built yet")` from every method (replaced by Tracks 2 and 3; keeps the enum and registry consistent)
  - Test `tests/workflow_core/test_hosts_registry.py` (new: registry, unknown host, stub hosts raise, `specs_trace.status` on GitLab calls `glab mr list --source-branch spec/<change> --all -F json`)
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** cross-module refactor over seven modules with test patch points that must keep working (`test_team_gates.py:555,568`, `test_team_beads.py:274`).
- **Steps**:
  1. Write `test_hosts_registry.py`: `adapter("github").executable == "gh"`, `adapter("gitlab").executable == "glab"`, `adapter("nope")` raises `ValueError`, `adapter("gitea").fetch_pr(...)` raises `HostUnavailable`; a `make_team_repo(host="gitlab")` repo with an SDD change and a `fake_cli` `glab` answering `mr list` returns status `merged` from `specs_trace.status`. Run `python3 -m pytest -q tests/workflow_core/test_hosts_registry.py` → fails (no package).
  2. Create `hosts/base.py` and `hosts/__init__.py` (`importlib.import_module(f".{host}", __name__).ADAPTER` after checking `host in HOSTS`).
  3. Move GitHub and GitLab code into `hosts/github.py` and `hosts/gitlab.py` as frozen dataclass adapters; they `from .. import team_host` at module top and call `team_host._run(self.name, argv, cwd)` and build `team_host.PrInfo`. GitLab `pr_for_branch`: `glab mr list --source-branch <branch> --all -F json` (newest first; confirm the flags with `glab mr list --help`); GitHub: today's `gh pr list --head <branch> --state all --json url,state,mergeCommit`.
  4. Rewrite `team_host.py` as the facade; `_run(host, argv, cwd)` keeps its signature, resolves `adapter(host)`, maps a return code in `auth_exit_codes` to `HostUnavailable(f"{executable} is not logged in: run {login_fix}")`.
  5. Update `team.py`, `team_init.py`, `specs_trace.py` as listed; `repo_slug` stays (tests import it) and backs `github`/`gitlab` `repo_id`.
  6. Run `python3 -m pytest -q tests/workflow_core/test_hosts_registry.py tests/workflow_core/test_team_gates.py tests/workflow_core/test_team_init.py tests/workflow_core/test_team_beads.py tests/workflow_core/test_schema_2_7.py tests/workflow_core/test_specs_archive_trace.py tests/gin_orchestrator/test_harness_packaging.py` → all pass with no edits to existing expectations (add the new `hosts/*.py` paths to the packaging list if `test_harness_packaging.py:41-80` requires every shipped script).
  7. Commit `refactor(team): host adapter interface; GitHub and GitLab behind it (gin-workflow-uj2o.1)`.
- **Acceptance criteria**: US-3; no `"github"`/`"gitlab"` string literals left in `team.py`, `team_init.py`, `team_beads.py`, `specs_trace.py` (`grep -nE '"(github|gitlab)"'` prints nothing for them); existing tests unchanged and passing.
- **Estimated complexity**: high

### Track 2: Gitea adapter (`gt`, self-hosted)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/hosts/gitea.py` (replace the stub)
  - Create `plugins/gin-workflow/src/templates/team/gitea-ci.yml` (from `github-ci.yml` without `hashFiles`: the second step runs `test -f .agent-workflow/config.yaml || exit 0` in shell)
  - Test `tests/workflow_core/test_hosts_gitea.py` (new)
  - Modify `tests/workflow_core/team_fixtures.py` (add `gitea_pr(...)` JSON builder next to `gh_pr`, no change to existing helpers)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded new module behind a fixed interface, but many URL, remote, and review edge cases (subpath, ports, stale and dismissed reviews, exit 4).
- **Steps**:
  1. Confirm against the docs (docs.gitea.com/cli, the Gitea API swagger at `/api/swagger` of any Gitea 28 instance or gitea.com) and record in the bead notes: the `gt api` syntax and how `--host` is passed; `gt auth status --host <url>` exit codes; the JSON of `pulls/{n}` (`state`, `merged`, `merge_commit_sha`, `head.sha`, `user.login`, `body`, `html_url`), `pulls/{n}/reviews` (`state`, `commit_id`, `dismissed`, `stale`, `user.login`), `pulls/{n}/files` (`filename`), `repos/{owner}/{repo}/pulls?state=all` (head ref field), the issue search for merged PR text, `version`; how `gt --version` identifies itself (to tell it from Graphite's `gt`); `gt pr create` flags. Where a fact cannot be confirmed, follow the swagger and note it.
  2. Write `test_hosts_gitea.py` with `fake_cli("gt", ...)` rules: merged PR with two reviewers (one APPROVED on head, one APPROVED then dismissed) → one approval with `commit_id`; review with empty `commit_id` → `("login", "")` and the note; `merged_with_text` keeps only merged results; `pr_for_branch`; `repo_id` equal for `https://git.example.com/gitea/org/app/pulls/5` (pr), `ssh://git@git.example.com:2222/org/app.git`, `git@git.example.com:org/app.git`, `https://git.example.com/gitea/org/app.git`, and different for another host or repo; every `gt api` call carries `--host https://git.example.com/gitea`; exit 4 → `HostUnavailable` naming `gt auth login --host https://git.example.com/gitea`; doctor: `gt` that is not Gitea's CLI, no login for the instance, version `27.x` → failing checks with fixes, `28.0` → passing; `gin team init --ci` with `host: gitea` writes `.gitea/CODEOWNERS`, `.gitea/PULL_REQUEST_TEMPLATE.md`, `.gitea/workflows/gin-workflow.yml`; a full `gin record requirement-confirmed --evidence <gitea url>` and `gin team check --gate ship <url>` through `run_cli` mirroring `test_team_gates.py` (merged spec gate passes with a listed role; author excluded; ship counts only head-commit approvals; another repository rejected).
  3. Run it → fails. Implement `hosts/gitea.py` (`executable="gt"`, `login_fix="gt auth login --host <instance>"` filled per URL, `auth_exit_codes=(4,)`, `identity_key="login"`, files as above), with `instance_base(url)` = everything before `/<owner>/<repo>/pulls/`, and `repo_id` = `host/owner/repo` lower-cased (the two segments before `/pulls/`, or the last two path segments of a remote, `.git` removed; port and subpath ignored).
  4. Doctor: `doctor_checks` returns `gitea_cli` (version output names Gitea), `host_login` (`gt auth status --host <instance of origin>`), `server_version` (`gt api --host <instance> version` ≥ 28).
  5. Run the new tests and `tests/workflow_core/test_team_*.py` → pass. Commit `feat(team): Gitea host through gt, self-hosted instances (gin-workflow-uj2o.2)`.
- **Acceptance criteria**: US-1 (all bullets); spec R2.
- **Estimated complexity**: medium

### Track 3: CodeCommit adapter and `aws_identity`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/hosts/codecommit.py` (replace the stub)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:21-31` (member property `aws_identity`, non-empty string)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:27-31,82-121,124-131` (`Member.aws_identity`; `validate_team`: unique `aws_identity`; with an adapter whose `identity_key` is `aws_identity`, an error for each member without it who holds a role used in `team.approvals`; `load_team` reads it)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:103-120` (`team check` prints a warning per member without `aws_identity` and no approving role, on such a host)
  - Test `tests/workflow_core/test_hosts_codecommit.py` (new)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded new module plus a small model change, with many edge cases (ARN forms, revisions, pagination, three remote forms, regions).
- **Steps**:
  1. Confirm against the AWS CLI reference and record in the bead notes: `get-pull-request` fields (`pullRequestStatus`, `pullRequestTargets[].sourceCommit|destinationCommit|mergeBase|mergeMetadata.isMerged|mergeCommitId`, `authorArn`, `revisionId`, `description`, `title`), `get-pull-request-approval-states --revision-id` (`approvals[].userArn`, `approvalState`), `get-differences` (`differences[].afterBlob.path`, `beforeBlob.path`, `NextToken`), `list-pull-requests --pull-request-status CLOSED` (`pullRequestIds`, `nextToken`), `create-pull-request --targets`; whether a push creates a new `revisionId` and drops earlier approvals; the console URL form.
  2. Write `test_hosts_codecommit.py` with `fake_cli("aws", ...)` rules (every call carries `codecommit`, `--region <region>`, `--output json`): OPEN PR with approvals by `arn:aws:sts::1:assumed-role/Dev/alice` and `arn:aws:iam::1:user/bob` on the current revision → approvals `("alice", sourceCommit)`, `("bob", sourceCommit)`; CLOSED+isMerged → `merged` with `mergeCommitId`; CLOSED not merged → `closed`; files across two `get-differences` pages; `merged_with_text` over a paged list keeps merged PRs whose description contains the text; `pr_for_branch` by `sourceReference` `refs/heads/<branch>`; `repo_id` equal for the console URL `https://eu-west-1.console.aws.amazon.com/codesuite/codecommit/repositories/app/pull-requests/7?region=eu-west-1`, `codecommit::eu-west-1://app`, `https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/app`, and `codecommit://dev@app` with `AWS_REGION=eu-west-1`; different for another region or repo; a non-console URL → `HostUnavailable` showing the expected form; schema accepts `aws_identity`; duplicate `aws_identity` and an approver without it are config errors; `team check` warns for a non-approver without it; `gin team init` on CodeCommit writes only `.githooks/commit-msg`; `--ci` exits 2 with "CodeCommit has no CI workflow file; use CodeBuild or CodePipeline"; doctor `host_cli` runs `aws sts get-caller-identity` and the note "CodeCommit does not enforce code owners; create an approval rule template (see docs/guides/team.md)"; gate flow via `run_cli`: member `aws_identity: alice` approves → spec gate passes; ship counts only approvals of the current revision whose source commit is local HEAD.
  3. Run → fails. Implement `hosts/codecommit.py` (`executable="aws"`, `login_fix="aws configure or aws sso login"`, `auth_exit_codes=()`, `identity_key="aws_identity"`, `files=HostFiles(None, None, None, None)`), ARN → name (`user/<name>` → name; `assumed-role/<role>/<session>` → session), the schema, model, and `team check` changes.
  4. Run the new tests and `tests/workflow_core/test_team_*.py tests/workflow_core/test_schema_2_7.py` → pass. Commit `feat(team): CodeCommit host and aws_identity (gin-workflow-uj2o.3)`.
- **Acceptance criteria**: US-2 (all bullets); spec R3, R4.
- **Estimated complexity**: medium

### Track 4: Skills and docs for four hosts
- **Dependencies**: Track 2, Track 3
- **Files**:
  - Create `plugins/gin-workflow/src/skills/team/references/hosts.md` (one table: host, CLI, login, open-PR command, branch-protection setting, approval reset setting)
  - Modify `plugins/gin-workflow/src/skills/team-setup/SKILL.md:11,15,20` (four hosts; `aws_identity` per member on CodeCommit; per-host advice through `team/references/hosts.md`)
  - Modify `plugins/gin-workflow/src/skills/team/SKILL.md` (ship note: GitLab "Reset approvals on push", Gitea "Dismiss stale approvals", CodeCommit revision-bound approvals; link to `references/hosts.md`)
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:32` and `plugins/gin-workflow/src/skills/sdd/SKILL.md:17` (open the PR with the host's command from `team/references/hosts.md`; GitHub default without team mode)
  - Modify `docs/guides/team.md` and `docs/guides/team.vi.md` (hosts; Gitea self-hosted login with `gt auth login --host`, Gitea 28+, proxy options, system-trusted certificates; CodeCommit `aws_identity` and the approval rule template steps)
  - Modify `docs/guides/git-flow.md` and `docs/guides/git-flow.vi.md` (Host procedures: Gitea and CodeCommit web steps and CLI; remove the CodeCommit limitation sentence and its pointer)
  - Modify `docs/reference/config.md` (`team.host` values, `aws_identity`), `docs/reference/cli.md` (`team init --ci` on CodeCommit, doctor checks per host)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** text over known facts from Tracks 2 and 3 (their bead notes) with character budgets and a Vietnamese pair; no code.
- **Steps**:
  1. Read the bead notes of Tracks 2 and 3 for the confirmed commands; check each command and flag written against `--help` or the cited manual.
  2. Write the files above. Before any `.vi.md`, read `~/.claude/plugins/marketplaces/vietnamese-language-skill/skills/vietnamese-tech-writing/SKILL.md` and its `references/glossary.md`, `references/banned-phrases.md`, and run its `scripts/validate_copy.py --register eng-impersonal` on the changed `.vi.md` files.
  3. Run `python3 -m pytest -q tests/workflow_core/test_token_budget.py tests/workflow_core/test_docs_check.py tests/workflow_core/test_docs_coverage.py tests/workflow_core/test_walkthrough_docs.py` → pass; `gin docs check` on every changed page → `ok`; heading parity for each changed `.vi.md` pair → no output.
  4. Commit `docs(team): Gitea and CodeCommit hosts in skills and guides (gin-workflow-uj2o.4)`.
- **Acceptance criteria**: US-4; spec R6, R7; skill budgets pass.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/team-hosts`
- **Merge strategy**: parallel-then-merge (Track 1, then Tracks 2 and 3 in parallel, then Track 4)

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] Existing GitHub/GitLab tests pass with unchanged expectations
- [ ] `gin docs check` and `mkdocs build --strict` pass
- [ ] Manual: `gin setup doctor` in a repository with `team.host: gitea` and no `gt` lists the `gt` fix

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric; the user may override them before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- The Parent Bead `gin-workflow-uj2o` remains open until the human-confirmed merge; track beads close once tests and review pass, so dependents unblock.
- `gt` is also Graphite's CLI name; the Gitea adapter's doctor check tells them apart (Track 2 step 4).
