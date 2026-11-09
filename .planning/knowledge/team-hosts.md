# Team mode hosts: adapter package, Gitea through gt, CodeCommit through aws

**Context**
Epic `gin-workflow-uj2o` (2026-11-09). Team mode verified pull requests on GitHub and GitLab only (`team_host.py` branches plus `if host` code in five modules). The next project uses AWS CodeCommit, and a self-hosted Gitea was requested too.

**Decision/Solution**
- `workflow_core/hosts/` holds one adapter per host (`github`, `gitlab`, `gitea`, `codecommit`) behind `HostAdapter` (`hosts/base.py`): `executable`, `login_fix`, `auth_exit_codes`, `identity_key`, `files` (`HostFiles`, `None` when a host has none), `ci_unsupported`, `auth_check_argv`, `fetch_pr`, `merged_with_text`, `pr_for_branch`, `repo_id(location, pr=)`, `doctor_checks`, `doctor_notes`. The lazy registry is `hosts.adapter(host)`. `team.py`, `team_init.py`, `team_beads.py`, and `specs_trace.py` contain no host names.
- `team_host.py` stays the facade: `PrInfo`, `HostUnavailable`, `HostCliMissing`, `_run(host, argv, cwd)`, `tool`. Adapters call `team_host._run` through the module object at call time, so tests that patch `workflow_core.team_host._run` or `.tool` keep working.
- Gitea uses the official CLI `gt` (docs.gitea.com/cli, Gitea 28 or later), not `tea`: `gt api --host <instance base URL>` on every call that has a URL (or an http(s) origin); exit 4 means not logged in. `repo_id` is `host/owner/repo` (port and subpath ignored). Approvals: per reviewer the latest APPROVED or REQUEST_CHANGES review decides; a dismissed latest one clears the reviewer; COMMENT/PENDING/REQUEST_REVIEW are ignored. Doctor tells Gitea's `gt` from Graphite's `gt` by `gt --version` (`gt version ...`), and an SSH origin finds its instance among `gt auth status --json` rows by host.
- CodeCommit uses `aws codecommit ... --region <r> --output json`. Approvals come from the current `revisionId` and carry `sourceCommit`. Members carry `aws_identity`, matched to the IAM user name or the assumed-role session name. `repo_id` is `codecommit/<region>/<repo>`; a remote without a known region fails closed (`AWS_REGION`, `AWS_DEFAULT_REGION`, or `codecommit::<region>://`). `fetch_pr` checks the PR's target repository equals the URL's, because CodeCommit PR ids are not repository-scoped. `team init` writes only the commit-msg hook; `--ci` and `team codeowners` exit 2.

**Consequences**
- A new host is a new module plus a schema enum value; no caller changes.
- `test_rename_sweep.py` forbids old skill names such as `gin-team` in docs and skills, except right after `#` (anchors); a docs rename must not touch `cli.md#gin-team`.
- Session names on CodeCommit are chosen by whoever assumes the role; without AWS SSO or an `sts:RoleSessionName` trust condition a principal can approve as a member. Follow-up `gin-workflow-49ra` pins the role.
- Gitea identifies a repository by `host/owner/repo`: two instances on one host with the same repo paths are indistinguishable. `pr_for_branch` scans the newest 500 PRs; `merged_with_text` at most 100 hits.
- `gt` and `aws` were not installed when this shipped: every behaviour is tested with `fake_cli` fakes and the CLI facts in the bead notes of `.2` and `.3`, not against a live instance or account.

**References**
- `plugins/gin-workflow/src/scripts/workflow_core/hosts/{__init__,base,github,gitlab,gitea,codecommit}.py`, `team_host.py`, `team.py`, `team_init.py`, `team_cli.py`, `specs_trace.py`, `schemas.py`, `executables.py`, `templates/team/gitea-ci.yml`
- Tests: `tests/workflow_core/test_hosts_{registry,gitea,codecommit}.py`
- Skills: `skills/team/references/hosts.md`, `skills/{team,team-setup,ship,sdd}/SKILL.md`; docs: `docs/guides/team.md`, `docs/guides/git-flow.md` (and `.vi.md`), `docs/reference/{config,cli}.md`
- `.planning/specs/2026-11-09-team-hosts-design.md`, `.planning/plans/2026-11-09-team-hosts.md`
- Beads: `gin-workflow-uj2o`, `.1` to `.4`; follow-up `gin-workflow-49ra`
- Related: [docs-refresh](docs-refresh.md)

**Scope**
Team mode pull request verification, `team init`, `team check`, `team deps`, `setup doctor`, `specs trace`.
