# Plan: Teamwork hardening

Spec: `.planning/specs/2026-10-06-teamwork-hardening-design.md` (requirement confirmed, workflow `teamwork-hardening`).

## Goal

Close the seven confirmed defects where gates pass on the wrong evidence: approval gates bind to this repository, the intended artifact, a valid plan, and the current commit; verification binds to the verified commit; external dependencies are proven present in the execution workspace; local-mode tracks always have an owner and a shared branch name.

## Architecture

Four sequential tracks on one branch. Track 1 hardens the approval validator (`team.py`, `team_host.py`) and threads a new `--spec` selector through `record` and `team check`. Track 2 binds `verification.passed` events to `branch`/`head` and derives the gate from the branch tip (`lifecycle_cli.py`). Track 3 splits `team deps` into a refresh that stores merge commits and a per-bead ancestry check, and requires `Owner:` in local mode (`team_beads.py`, `team_cli.py`, `team.py:check_plan`). Track 4 updates the `gin-team` skill and the docs to the new contracts and the team process.

## Tech Stack

Python 3 standard library, `unittest`, real `git` and `bd` in temporary repositories, fake `gh`/`glab` from `tests/workflow_core/team_fixtures.py`. No new dependencies.

## Global Constraints

Copied verbatim from the spec, section "Errors and compatibility":

- Exit 0: check passed. Exit 1: evidence rejected, plan invalid, dependency not integrated. Exit 2: missing selector/tool/config, detached HEAD, host unavailable.
- A rejected gate writes no event. A failed host query never closes a placeholder.
- Solo behavior changes only in Requirement 2. Team behavior without configured approvals is unchanged.
- Existing shared-Beads (`team.beads_sync`) installations keep their current orchestration and sync behavior, except the gate checks above.

Also from the spec: host interactions are fixtures, not live provider validation; keep skill instruction budgets and documentation checks passing.

## Model Guidance

- `default_model_class`: `standard_impl`
- `phase_guidance`: implement `standard_impl`; review `high_reasoning`; docs `cheap_simple`.
- `override_rule`: Track 1 runs at `high` reasoning because it is the security-relevant gate validator.

## Requirement Analysis

- Problem statement: team gates accept unrelated PRs, empty plans, and stale approvals; verification survives new commits; dependencies resolve without their code; unowned tracks and colliding branch names in local mode.
- Success criteria: every acceptance case in the spec's Testing section has a passing test; full suite passes; docs and skill describe the new contracts.
- Constraints: see Global Constraints.
- Non-goals: the spec's "Out of scope" list (revocation rechecks, plan-revision diffing, handoff holds, whole-feature reporting, PR search pagination, idempotent re-orchestration, host-revision content checks, automatic host configuration, `team.beads_sync` changes).

## Approach Options

### Option 1: Minimal fixes in the existing modules (selected)
- Summary: extend `check_approval`, `_gitlab`, `_delivery_gate_state`, `deps`, `check_plan` in place; one new CLI flag per command.
- Pros: small diff, follows existing patterns, no new modules.
- Cons: `team.py` grows by ~60 lines.

### Option 2: New `team_evidence.py` module for repository/artifact binding
- Summary: move binding into a separate module.
- Pros: separation.
- Cons: new module for ~60 lines of single-use code; YAGNI.

### Recommended Approach
- Selected option: Option 1.
- Reasoning: the spec asks for targeted fixes; existing modules already own these responsibilities.

## Scope

- In scope: spec Requirements 1–4.
- Out of scope: spec "Out of scope" section.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Four tracks; tracks 1 and 3 both edit team.py and the shared test fixtures, track 4 documents tracks 1-3.
```

Worktree `.planning/worktrees/teamwork-hardening`, branch `feat/teamwork-hardening`. Each track bead closes after its tests and an independent review (role `review`, reasoning `high`, provider different from the implementer) pass. The parent epic closes after the user-approved merge to master.

Commands (from the repository root of the worktree):

- `T="env PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest"`
- Full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py </dev/null` (baseline on master `b152a0d`: `Ran 856 tests`, `OK (skipped=3)`).

## Tasks

### Track 1: Approval gates bind to repository, artifact, plan, and commit

**Metadata:**
- Dependencies: none
- Provider role: `backend`
- Reasoning: `high`
- Model class: `high_reasoning`
- Estimated complexity: medium

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/team.py` (`_approver_roles` 240-251, `_plan_in` 254-261 removed, `check_approval` 264-290, `verify_gate` 333-342, `authorize_record` 345-355; new `repo_slug`, `origin_slug`, `_is_artifact`, `resolve_artifact`)
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/team_host.py` (`PrInfo` 21-31, `_gitlab` 84-103)
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py` (`check` parser 28-31, `check` command 82-87)
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py` (`record` parser 452-456; `authorize_record` call in `_record_command`)
- Modify: `tests/workflow_core/team_fixtures.py` (`make_team_repo` 85-96)
- Test: `tests/workflow_core/test_team_gates.py`

**Interfaces:**
- Produces `repo_slug(location: str) -> str` and `origin_slug(root: Path) -> str` in `team.py`.
- Produces `resolve_artifact(pr, root: Path, gate: str, selected: str | None) -> str` in `team.py`.
- Changes `check_approval(gate, pr, team, *, root: Path, artifact: str = "", local_head: str = "") -> list[str]` (the `plan=` keyword is replaced by `artifact=`).
- Changes `verify_gate(root, team, gate, url, *, plan=None, spec=None) -> tuple[PrInfo, str, list[str]]` (returns `(pr, artifact, reasons)`).
- Changes `authorize_record(root, team, gate, evidence, *, actor=None, plan=None, spec=None)`; payload adds `repository` and, for spec/plan gates, `artifact`.
- `PrInfo` gains `approval_note: str = ""` (last field).
- CLI: `gin-workflow record ... --spec PATH`, `gin-workflow team check URL --gate G [--plan P] [--spec S]`.

**Steps:**

1. Fixtures. In `make_team_repo`, after `git config user.name`, add the origin remote that matches the fake PR/MR URLs:
   ```python
       origin = {"gitlab": "https://gitlab.corp.com/group/app.git"}.get(host, "git@github.com:org/app.git")
       git(root, "remote", "add", "origin", origin)
   ```
   In `test_team_gates.py` add `SPEC_PATH = ".planning/specs/2026-10-03-login-design.md"` and write it in `GateCase.setUp` (`write(self.root, SPEC_PATH, "# Login\n")`). Give `TestRecordGitLab.glab` a `files: list[str] = (PLAN_PATH, SPEC_PATH)` parameter used for the `changes` stub.

2. Update existing tests to the new contract, then add failing tests. Existing: every `requirement-confirmed` PR stub gets `files=[SPEC_PATH]`; `test_requirement_confirmed_by_ba_is_recorded_with_proof` expects payload `{"evidence": PR, "pr_url": PR, "merge_commit": "m"*40, "approvers": [...], "repository": "github.com/org/app", "artifact": SPEC_PATH}`; `test_team_check_reverifies_without_recording` stub gets `files=[SPEC_PATH]`. New tests in `TestRecordGitHub`:
   - `test_repo_slug_forms_compare_equal`: `repo_slug` of `git@github.com:Org/App.git`, `ssh://git@github.com/org/app`, `https://github.com/org/app.git`, `https://github.com/org/app/pull/7` all equal `github.com/org/app`; `https://gitlab.corp.com/group/app/-/merge_requests/12` → `gitlab.corp.com/group/app`.
   - `test_pr_from_another_repository_is_rejected`: stub `gh pr view <PR>` with `url="https://github.com/other/app/pull/7"`, files `[SPEC_PATH]`, approved by `an-ba` → exit 1, stderr contains `PR belongs to github.com/other/app, not this repository (github.com/org/app)`, no events. (Stub the `gh` rule on argv `["pr", "view", PR]` and pass `PR` as evidence; only the returned `url` differs.)
   - `test_no_origin_exits_2`: `git remote remove origin` → `record requirement-confirmed` exit 2, stderr contains `no git remote 'origin'`.
   - `test_requirement_needs_exactly_one_spec_in_the_pr`: files `["README.md"]` → exit 2 with `pass --spec`; files `[SPEC_PATH, ".planning/specs/other.md"]` → exit 2 with `found: .planning/specs/2026-10-03-login-design.md, .planning/specs/other.md`; `--spec .planning/specs/other.md` with files `[SPEC_PATH]` → exit 1 with `PR does not change .planning/specs/other.md`; `--spec SPEC_PATH` with files `[SPEC_PATH, ".planning/specs/other.md"]` → exit 0.
   - `test_plan_gate_runs_check_plan`: write `PLAN_PATH` as `"# Plan\n"` (no tracks), stub files `[PLAN_PATH]` approved by `binh-dev` and `chi-fe` → exit 1 with `no '### Track N:' sections`; write PLAN with Track 1 `Area: nowhere` → exit 1 with `unknown area nowhere`.
   - `test_verification_ignores_approval_without_commit`: commit, stub `state="OPEN"`, `head=<local head>`, reviews `[("dung-qe", "APPROVED", "")]` → exit 1 with `missing approval from one of qe`.
   - Existing `test_plan_approved_without_plan_file_needs_plan_flag` keeps its assertions (exit 2, `pass --plan`).
   New tests in `TestRecordGitLab`:
   - Extend `glab()` with `reset: bool = True`, `status: str = "mergeable"`, `patch: str | None = "p1"`: the `mr view` stub adds `"detailed_merge_status": status`; add rules `["api", "--hostname", "gitlab.corp.com", "projects/42/approvals"]` → `{"reset_approvals_on_push": reset}` and `[... f"{base}/versions"]` → `[{"head_commit_sha": "h"*40, "patch_id_sha": patch}]`.
   - Also give `glab()` a `head: str = "h" * 40` parameter used for the stub's `sha` and the version's `head_commit_sha`.
   - `test_verification_needs_reset_on_push`: commit; `head = git rev-parse HEAD`; every stub below uses `head=head`, `state="opened"`, approver `dung-qe`. `reset=False` → exit 1, stderr contains `reset_approvals_on_push`. `status="approvals_syncing"` → exit 1 with `approvals still syncing; retry`. `patch=None` → exit 1 with `approvals still syncing; retry`. Defaults (`reset=True`) → exit 0.
   - `test_head_change_between_reads_is_unsettled` (in-process): `with mock.patch("workflow_core.team_host._run", side_effect=fake)` where `fake(host, argv, cwd)` returns the `mr view` payload with `sha` `"a"*40` on the first call and `"b"*40` on the second, `{"approved_by": [{"user": {"username": "dung-qe"}}]}` for `/approvals`, `{"changes": []}` for `/changes`, `{"reset_approvals_on_push": True}` for `projects/42/approvals`, `[{"head_commit_sha": "a"*40, "patch_id_sha": "p"}]` for `/versions`; assert `fetch_pr(MR, "gitlab", root)` has `approvals == (("dung-qe", ""),)` and `approval_note == "approvals still syncing; retry"`.
   Run `$T tests.workflow_core.test_team_gates`; expect the new tests to fail.

3. `team_host.py`: append `approval_note: str = ""` to `PrInfo`. Rewrite `_gitlab`:
   ```python
   _UNSETTLED = {"checking", "approvals_syncing"}


   def _gitlab(url: str, cwd: Path) -> PrInfo:
       repo, iid = _gitlab_ref(url)
       host = urlparse(url).netloc
       view = ["mr", "view", iid, "-R", repo, "-F", "json"]
       data = _run("gitlab", view, cwd)
       project = f"projects/{data['project_id']}"
       base = f"{project}/merge_requests/{iid}"
       approvals = _run("gitlab", ["api", "--hostname", host, f"{base}/approvals"], cwd)
       changes = _run("gitlab", ["api", "--hostname", host, f"{base}/changes"], cwd)
       after = _run("gitlab", view, cwd)
       settings = _run("gitlab", ["api", "--hostname", host, f"{project}/approvals"], cwd) or {}
       versions = _run("gitlab", ["api", "--hostname", host, f"{base}/versions"], cwd) or []
       head = data.get("sha", "")
       commit, note = "", ""
       if not settings.get("reset_approvals_on_push"):
           note = ("GitLab approvals are not tied to a commit: enable 'Reset approvals on push' "
                   "(reset_approvals_on_push) on the project")
       elif (after.get("sha") != head
             or {data.get("detailed_merge_status"), after.get("detailed_merge_status")} & _UNSETTLED
             or not any(item.get("head_commit_sha") == head and item.get("patch_id_sha") for item in versions)):
           note = "approvals still syncing; retry"
       else:
           commit = head
       state = {"opened": "open"}.get(str(data.get("state", "")), str(data.get("state", "")))
       return PrInfo(
           url=data.get("web_url", url),
           state=state,
           merged=state == "merged",
           merge_commit=data.get("merge_commit_sha") or data.get("squash_commit_sha") or "",
           head_sha=head,
           author=(data.get("author") or {}).get("username", ""),
           approvals=tuple(((item.get("user") or {}).get("username", ""), commit)
                           for item in approvals.get("approved_by") or []),
           files=tuple(item.get("new_path", "") for item in changes.get("changes") or []),
           body=data.get("description") or "",
           approval_note=note,
       )
   ```

4. `team.py`: add `from urllib.parse import urlparse`, then:
   ```python
   _SCP = re.compile(r"^[\w.-]+@([^:/]+):(.+)$")


   def repo_slug(location: str) -> str:
       """`host/group/project` of a git remote or PR/MR URL; SSH, scp-style and HTTPS forms compare equal."""
       text = location.strip()
       scp = _SCP.match(text)
       if scp and "://" not in text:
           host, path = scp.group(1), scp.group(2)
       else:
           parsed = urlparse(text)
           host, path = parsed.hostname or "", parsed.path
       path = path.strip("/")
       for marker in ("/-/merge_requests/", "/pull/"):
           path = path.split(marker)[0]
       return f"{host}/{path.removesuffix('.git')}".lower()


   def origin_slug(root: Path) -> str:
       done = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, text=True, capture_output=True,
                             check=False)
       if done.returncode != 0 or not done.stdout.strip():
           raise TeamError("no git remote 'origin'; team gates compare the PR repository with it")
       return repo_slug(done.stdout)


   def _is_artifact(path: str, gate: str, changes: str) -> bool:
       if gate == "requirement_confirmed":
           return (path.startswith(".planning/specs/") and path.endswith(".md")) or (
               path.startswith(f"{changes}/") and path.endswith("/spec-delta.md"))
       return (path.startswith(".planning/plans/") and path.endswith(".md")) or (
           path.startswith(f"{changes}/") and path.endswith("/plan.md"))


   def resolve_artifact(pr: Any, root: Path, gate: str, selected: str | None) -> str:
       """The spec or plan the gate approves: the selector, else the one candidate the PR changes."""
       if selected:
           return selected
       from .specs import load_config, sdd_config

       kind, flag = ("spec", "--spec") if gate == "requirement_confirmed" else ("plan", "--plan")
       changes = str(sdd_config(load_config(Path(root)))["changes"]).strip("/")
       candidates = [item for item in pr.files if _is_artifact(item, gate, changes)]
       if len(candidates) != 1:
           raise TeamError(f"the PR must change exactly one {kind} file (found: {', '.join(candidates) or 'none'}); "
                           f"pass {flag} <path>")
       return candidates[0]
   ```
   Delete `_plan_in`. In `_approver_roles` change the commit filter to `if on_commit and commit != on_commit: continue` and its docstring to "excluding the PR author and approvals not made on `on_commit`". Rewrite `check_approval`:
   ```python
   def check_approval(gate: str, pr: Any, team: TeamConfig, *, root: Path, artifact: str = "",
                      local_head: str = "") -> list[str]:
       """Reasons the PR does not satisfy the gate's policy (empty = pass)."""
       policy = team.approvals.get(gate, [])
       reasons: list[str] = []
       expected, actual = origin_slug(Path(root)), repo_slug(pr.url)
       if actual != expected:
           reasons.append(f"PR belongs to {actual}, not this repository ({expected})")
       if gate == "verification_passed":
           if pr.state not in ("open", "merged"):
               reasons.append(f"PR is {pr.state}")
           if local_head and pr.head_sha != local_head:
               reasons.append(f"PR head {pr.head_sha[:12]} is not local HEAD {local_head[:12]}")
           approvers = _approver_roles(pr, team, on_commit=pr.head_sha)
           if not approvers and pr.approval_note:
               reasons.append(pr.approval_note)
       else:
           if not pr.merged:
               reasons.append(f"PR is {pr.state}, not merged")
           if artifact not in pr.files:
               reasons.append(f"PR does not change {artifact}")
           approvers = _approver_roles(pr, team)
       tracks: list[Track] = []
       if gate == "plan_approved":
           plan = Path(root) / artifact
           if plan.is_file():
               reasons += check_plan(team, plan)
               tracks = plan_tracks(plan)
           else:
               reasons.append(f"{artifact} is not in this checkout; pull the merged plan")
       held = set().union(*approvers.values()) if approvers else set()
       if policy == "area_lead":
           for name in sorted({track.area for track in tracks if track.area}):
               area = team.areas.get(name)
               if area is not None and area.lead not in held:
                   reasons.append(f"missing approval from {area.lead} for area {name}")
       elif policy and not held & set(policy):
           reasons.append(f"missing approval from one of {', '.join(policy)}")
       return reasons
   ```
   (Unknown areas are reported by `check_plan` as `Track N: unknown area X`.) `verify_gate`:
   ```python
   def verify_gate(root: Path, team: TeamConfig, gate: str, url: str, *, plan: str | None = None,
                   spec: str | None = None) -> tuple[Any, str, list[str]]:
       """Fetch the PR/MR and return it, the approved artifact, and the reasons it fails the gate."""
       from .team_host import fetch_pr

       if not url.startswith(("https://", "http://")):
           raise TeamError(f"{gate} needs a PR/MR URL as --evidence in team mode, got {url!r}")
       pr = fetch_pr(url, team.host, Path(root))
       artifact = "" if gate == "verification_passed" else resolve_artifact(
           pr, Path(root), gate, plan if gate == "plan_approved" else spec)
       head = _head(Path(root)) if gate == "verification_passed" else ""
       return pr, artifact, check_approval(gate, pr, team, root=Path(root), artifact=artifact, local_head=head)
   ```
   `authorize_record` gains `spec: str | None = None`, calls `pr, artifact, reasons = verify_gate(root, team, gate, evidence, plan=plan, spec=spec)`, and returns payload `{"pr_url": pr.url, "merge_commit": pr.merge_commit, "approvers": approver_payload(pr, team), "repository": repo_slug(pr.url), **({"artifact": artifact} if artifact else {})}`.

5. `team_cli.py`: `item.add_argument("--spec")` after `--plan` on `check`; the command becomes `pr, artifact, reasons = team_core.verify_gate(root, team, args.gate, args.url, plan=args.plan, spec=args.spec)` and the payload adds `"artifact": artifact`. `lifecycle_cli.py`: `parser.add_argument("--spec", help="team mode: the spec file a requirement-confirmed PR approves")` after `--plan`; pass `spec=args.spec` to `authorize_record`.

6. Run `$T tests.workflow_core.test_team_gates tests.workflow_core.test_team_init tests.workflow_core.test_team_beads tests.workflow_core.test_schema_2_7`; expect OK. Run the full suite; expect `OK (skipped=3)`.

**Acceptance criteria:**
- Defects 1–3 closed: foreign repository, missing/ambiguous artifact, empty or invalid plan, commit-less approval on verification, unsettled GitLab approvals are all rejected with no event written.
- GitHub and GitLab happy paths still record.
- Independent review approves.

### Track 2: Verification binds to the verified commit

**Metadata:**
- Dependencies: Track 1 (both edit `lifecycle_cli.py`; sequential to avoid conflicts)
- Provider role: `backend`
- Reasoning: `medium`
- Model class: `standard_impl`
- Estimated complexity: medium

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py` (`_delivery_gate_state` 106-138, `_record_command` 164-204; new `_git`, `_spec_prefixes`, `_verification_current`)
- Test: `tests/workflow_core/test_lifecycle_cli.py` (existing tests at 297-306 and 329-340; new class)

**Interfaces:**
- Produces `_verification_current(repo_path: Path, event_store: WorkflowEventStore, workflow_id: str) -> bool`.
- `verification.passed` payload gains `branch: str` and `head: str`; its idempotency key becomes `f"{workflow_id}:{gate}:{evidence}:{head}"`.

**Steps:**

1. Tests. Add to the test class a helper:
   ```python
   def _git(self, *args, cwd=None):
       return subprocess.run(["git", *args], cwd=cwd or self.repo_path, check=True, capture_output=True,
                             text=True).stdout.strip()

   def _git_repo(self):
       self._git("init", "-q", "-b", "main")
       self._git("config", "user.email", "t@example.com")
       self._git("config", "user.name", "T")
       self._git("commit", "-q", "--allow-empty", "-m", "base")
   ```
   Call `self._git_repo()` at the start of `test_verification_passed_is_recordable_and_shipped_follows_closed_epic` and `test_standalone_bead_reaches_ship_without_discuss_or_plan_gates`. New tests (each starts with `self._git_repo()`; `verify = lambda **kw: cli_main(["record", "verification-passed", "--repository", str(kw.get("repo", self.repo_path)), "--evidence", "tests OK", "--actor", "user"])`):
   - `test_new_commit_invalidates_verification`: verify → `self._state_gates()["verification_passed"] == "satisfied"`; `git commit --allow-empty -m code` → `"unmet"`; verify again → returns 0, last event's payload `head` equals the new HEAD, gate `"satisfied"`.
   - `test_spec_only_commit_keeps_verification`: verify; write `.planning/specs/x.md` and `docs/changes/archive/c/spec-delta.md`, commit → `"satisfied"`; write `src/a.py`, commit → `"unmet"`.
   - `test_event_without_head_is_unmet`: append `WorkflowEvent.create(event_type="verification.passed", workflow_id="default-workflow", actor="user", payload={"evidence": "old"}, idempotency_key="old")` to `.agent-workflow/runtime/events.jsonl` via `WorkflowEventStore` → `"unmet"`.
   - `test_worktree_record_is_read_from_main_checkout`: `git worktree add -q -b feat/x <tmp>/wt`; verify with `repo=<tmp>/wt` → returns 0; state from `self.repo_path` → `"satisfied"`; commit in the worktree → `"unmet"` from the main checkout.
   - `test_detached_head_refuses_to_record`: `git checkout -q --detach` → verify returns 2; no `verification.passed` event.
   - `test_deleted_branch_after_ship_keeps_shipped`: `_record_orchestration(epic="bug-1")`; `git checkout -q -b feat/y`; verify; record `shipped`; with `_fake_beads([], epic_status="closed")` read `before = self._state()`; `git checkout -q main`; `git branch -q -D feat/y`; read `after = self._state()` under the same patch. Assert `after["gates"]["shipped"] == "satisfied"`, `after["gates"]["verification_passed"] == "unmet"`, and `after["stage"] == before["stage"]`.
   Run `$T tests.workflow_core.test_lifecycle_cli`; expect the new tests to fail.

2. Implement in `lifecycle_cli.py`:
   ```python
   _SPEC_DIRS = (".planning/specs/", ".planning/plans/")


   def _git(repo_path: Path, *argv: str) -> str:
       done = subprocess.run(["git", *argv], cwd=repo_path, text=True, capture_output=True, check=False)
       return done.stdout.strip() if done.returncode == 0 else ""


   def _spec_prefixes(repo_path: Path) -> tuple[str, ...]:
       from .specs import sdd_config

       cfg = sdd_config(resolve_effective_config(repo_path, write=False).config.to_dict())
       return _SPEC_DIRS + tuple(f"{str(cfg[key]).strip('/')}/" for key in ("specs", "changes"))


   def _verification_current(repo_path: Path, event_store: WorkflowEventStore, workflow_id: str) -> bool:
       """The latest verification still describes its branch: the tip is the verified commit, or every
       later commit only changes spec artifacts (the SDD archive commit at ship)."""
       payload: Mapping[str, Any] = {}
       for event in event_store.read_all():
           if event.workflow_id == workflow_id and event.event_type == "verification.passed":
               payload = event.payload if isinstance(event.payload, Mapping) else {}
       head, branch = str(payload.get("head", "")), str(payload.get("branch", ""))
       if not head or not branch:
           return False
       tip = _git(repo_path, "rev-parse", "--verify", "-q", f"refs/heads/{branch}")
       if tip == head:
           return True
       if not tip or subprocess.run(["git", "merge-base", "--is-ancestor", head, tip], cwd=repo_path,
                                    capture_output=True, check=False).returncode != 0:
           return False
       prefixes = _spec_prefixes(repo_path)
       return all(path.startswith(prefixes) for path in _git(repo_path, "diff", "--name-only", head, tip).splitlines())
   ```
   In `_delivery_gate_state`, replace the `any(...)` for `verification_passed` with `_verification_current(repo_path, event_store, workflow_id)` and update the docstring ("verification from its recorded event while the branch tip is the verified commit"). In `_record_command`, right after the `--epic` check:
   ```python
       head = ""
       if args.gate == "verification-passed":
           repository = Path(args.repository).resolve()
           branch, head = _git(repository, "symbolic-ref", "--short", "-q", "HEAD"), _git(repository, "rev-parse", "HEAD")
           if not branch or not head:
               return {"status": "error", "message": "verification-passed needs a checked-out branch with a commit "
                       "(detached HEAD or no git repository)"}, 2
           base_payload = {**base_payload, "branch": branch, "head": head}
   ```
   and the idempotency key `f"{args.workflow_id}:{args.gate}:{args.evidence}" + (f":{head}" if head else "")`.

3. Run `$T tests.workflow_core.test_lifecycle_cli tests.workflow_core.test_team_gates tests.workflow_core.test_end_to_end`, then the full suite; expect `OK (skipped=3)`.

**Acceptance criteria:**
- Defect 4 closed for solo and team: a new non-spec commit returns `verification_passed` to unmet; re-verification records a new event; spec-artifact-only commits keep it met; worktree and main checkout agree; detached HEAD exits 2.
- Independent review approves.

### Track 3: Dependencies proven in the workspace; owners required in local mode

**Metadata:**
- Dependencies: Track 1 (edits `team.py` and `team_fixtures.py`)
- Provider role: `backend`
- Reasoning: `medium`
- Model class: `standard_impl`
- Estimated complexity: medium

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py` (`deps` 121-137; new `_has_commit`, `deps_for`)
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py` (`deps` parser line 33, `deps` command 106-111)
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/team.py` (`check_plan` 215-237)
- Modify: `tests/workflow_core/team_fixtures.py` (`PLAN` Track 2 metadata)
- Test: `tests/workflow_core/test_team_beads.py`, `tests/workflow_core/test_team_gates.py` (`TestPlanChecks`)

**Interfaces:**
- `deps(root, team) -> {"closed": [...], "waiting": [...]}` unchanged in shape; each closed placeholder also gets bead metadata `merge_commit=<sha>`.
- Produces `deps_for(root: Path, bead: str) -> {"bead": str, "ok": list[str], "missing": list[{"id": str, "reason": str}]}`.
- CLI: `gin-workflow team deps [--bead ID]`; with `--bead`, exit 1 when `missing` is non-empty.
- `check_plan` adds `Track N: missing Owner: (required when Beads are not shared)` when `team.beads_remote` is empty.

**Steps:**

1. Tests. In `team_fixtures.PLAN` add `- Owner: chi@corp.com` under Track 2's `- Area: frontend`; update `test_plan_tracks_reads_area_owner_and_files` to expect owner `chi@corp.com` for Track 2. Add to `TestPlanChecks`:
   - `test_local_mode_requires_owner`: PLAN with Track 2's Owner line removed → `check_plan` contains `Track 2: missing Owner: (required when Beads are not shared)`; a team loaded from config with `beads_sync: {remote: "file:///tmp/x"}` added under `team:` → no such finding.
   In `TestTeamBeadsLocal`, add `git(self.root, "commit", "-q", "--allow-empty", "-m", "base")` to `setUp`, and:
   - Extend `test_deps_closes_placeholders_whose_track_merged`: `show(self.root, done)["metadata"]["merge_commit"] == "abc"`.
   - `test_deps_for_bead_checks_ancestry_in_this_workspace`: `base = git rev-parse HEAD`; `git commit --allow-empty -m merged`; `merged = git rev-parse HEAD`; `work = create("work", "area:backend")`; `ext = create("external: .planning/plans/p.md#2")`; `bd dep add work ext`; fake `gh pr list` returning `mergeCommit.oid = merged` and body `Plan: .planning/plans/p.md\nTracks: 2\n`; `team deps` → exit 0; `team claim work` → exit 0 (status `in_progress`); `team deps --bead work --format json` → exit 0, `ok == [ext]`; `git checkout -q --detach <base>` → `team deps --bead work` exit 1 and stdout contains `fetch/rebase` and `merged`.
   - `test_deps_for_bead_ignores_other_beads`: `a = create("a")`, `b = create("b")`, `ext = create("external: .planning/plans/p.md#5")`, `bd dep add b ext`; `team deps --bead a` → exit 0, stdout `a has no external dependencies` (with the bead ID in place of `a`); `team deps --bead b` → exit 1 with `has not merged; run team deps`.
   - `test_refresh_unblocks_ready_without_deadlock`: `work = create("work", "area:backend")`, `ext = create("external: .planning/plans/p.md#2")`, `bd dep add work ext`; `team ready` JSON does not list `work`; with the fake merged PR, `team deps` → exit 0; `team ready` lists `work`.
   Run `$T tests.workflow_core.test_team_beads tests.workflow_core.test_team_gates`; expect the new tests to fail.

2. `team.py` `check_plan`, inside the loop before `if track.owner:`:
   ```python
           if not track.owner and not team.beads_remote:
               errors.append(f"{label}: missing Owner: (required when Beads are not shared)")
   ```

3. `team_beads.py`: in `deps`, before closing, store the merge commit:
   ```python
           noted = _bd(root, ["update", issue["id"], "--set-metadata", f"merge_commit={found.merge_commit}"])
           if noted.returncode != 0:
               raise TeamError(f"bd update {issue['id']} failed: {noted.stderr.strip()}")
   ```
   Add:
   ```python
   def _has_commit(root: Path, commit: str) -> bool:
       return bool(commit) and subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=root,
                                              capture_output=True, check=False).returncode == 0


   def deps_for(root: Path, bead: str) -> dict[str, Any]:
       """The bead's `external:` placeholders: ok only when closed with its merge commit in this workspace."""
       ok: list[str] = []
       missing: list[dict[str, str]] = []
       for dep in _show(root, bead).get("dependencies") or []:
           match = _EXTERNAL.match(dep.get("title", ""))
           if not match:
               continue
           commit = str((dep.get("metadata") or {}).get("merge_commit", ""))
           if dep.get("status") != "closed":
               missing.append({"id": dep["id"], "reason": f"{match.group(1)}#{match.group(2)} has not merged; run team deps"})
           elif not commit:
               missing.append({"id": dep["id"], "reason": "no merge commit recorded; run team deps"})
           elif not _has_commit(root, commit):
               missing.append({"id": dep["id"], "reason": f"fetch/rebase onto the plan's integration branch to include {commit}"})
           else:
               ok.append(dep["id"])
       return {"bead": bead, "ok": ok, "missing": missing}
   ```
   (`bd show <id> --json` lists dependencies with `id`, `title`, `status`, `metadata`; verified with bd during planning.)

4. `team_cli.py`: `sub.add_parser("deps", parents=[common]).add_argument("--bead")`; in the `deps` branch:
   ```python
           if args.command == "deps" and args.bead:
               result = team_beads.deps_for(root, args.bead)
               lines = [f"ok {item}" for item in result["ok"]]
               lines += [f"missing {row['id']}: {row['reason']}" for row in result["missing"]]
               _emit(result, args.format, "\n".join(lines) or f"{args.bead} has no external dependencies")
               return 1 if result["missing"] else 0
   ```
   placed before the existing `if args.command == "deps":` branch.

5. Run `$T tests.workflow_core.test_team_beads tests.workflow_core.test_team_gates tests.workflow_core.test_team_init`, then the full suite; expect `OK (skipped=3)`.

**Acceptance criteria:**
- Defects 5–6 closed: `--bead` passes only when the merge commit is in the workspace, independent of other beads and of bead status; refresh before `team ready` still unblocks; local-mode plans without owners fail `check-plan` and therefore `plan_approved`.
- Independent review approves.

### Track 4: Skill, docs, and team process

**Metadata:**
- Dependencies: Track 1, Track 2, Track 3
- Provider role: `docs`
- Reasoning: `low`
- Model class: `cheap_simple`
- Estimated complexity: low

**Files:**
- Modify: `plugins/gin-workflow/src/skills/gin-team/SKILL.md` (discuss line 16, plan line 19, orchestrate lines 22-24, execute lines 26-31, verify line 34, ship line 37)
- Modify: `docs/guides/team.md` (lifecycle table rows 42-47; new "Host settings" section after line 50)
- Modify: `docs/reference/cli.md` (record synopsis line 57 and table 63-67; team table around line 155)
- Modify: `docs/concepts/lifecycle.md` (verify row line 15)

**Interfaces:** none (documentation of the CLI contracts from Tracks 1–3).

**Steps:**

1. `gin-team/SKILL.md`:
   - discuss: after "Record `requirement-confirmed --evidence <pr-url>` once it is merged" add "(`--spec <path>` when the PR changes several spec files)".
   - plan: replace "and, when the lead assigns it, `Owner: <member email>`" with "and `Owner: <member email>` (required unless `team.beads_sync` is set; reassigning a track means a new plan PR)".
   - orchestrate "Not set" bullet: "each member creates beads only for the tracks they own, and a bead titled `external: <plan path>#<N>` for each dependency on another member's track, blocking the dependent bead."
   - execute: replace the first two bullets and the branch bullet with: "`team deps` first: it closes `external:` placeholders whose track PR has merged." / "Pick from `team ready` and claim with `team claim <bead>`; exit 1 means someone else holds it, so pick another." / "In the track worktree, `team deps --bead <bead>` must exit 0 before implementation; exit 1 names the merge commit to fetch or rebase onto." / "Branch `feat/<topic>-t<N>` (`<topic>` from the plan file name, `<N>` the track number); existing branches keep their names."
   - verify: append "On GitLab the project must enable 'Reset approvals on push'; when the gate reports `approvals still syncing`, retry."
   - ship: append "A member's ship reports only their own tracks; the lead declares the feature complete once every track PR has merged."
   Keep the file within its instruction budget (`$T tests.workflow_providers.test_harness_packaging` enforces it).

2. `docs/guides/team.md`: update the `gates` row (add `--spec`, repository and artifact checks, plan checked inside the gate), `plan` row (Owner required without shared Beads), `orchestrate` row (own tracks only), `execute` row (`team deps` → `team ready` → `team claim` → `team deps --bead`; branch `feat/<topic>-t<N>`), `verify` row (approval must be on the latest commit; GitLab needs reset on push). Add a section `## Host settings` listing: GitHub — branch protection on the integration branch, "Dismiss stale pull request approvals when new commits are pushed", CODEOWNERS per area (`team init`); GitLab — "Reset approvals on push" (required for `verification_passed`). And a sentence: the lead declares a feature complete when every track PR has merged; a member's ship covers only their tracks.

3. `docs/reference/cli.md`: record synopsis adds `[--spec PATH]`; `requirement-confirmed` row: "team mode adds `--spec`"; `verification-passed` row: "records the branch and commit; a later non-spec commit makes the gate unmet"; team table: `check URL --gate GATE [--plan P] [--spec S]` and `deps [--bead ID]` ("without `--bead`: close placeholders whose track PR merged; with `--bead`: exit 1 unless each external dependency's merge commit is in this workspace").

4. `docs/concepts/lifecycle.md` verify row: append "The recorded event names the verified branch and commit; a later commit that changes more than spec artifacts returns the gate to unmet."

5. Run `$T tests.workflow_providers.test_harness_packaging tests.workflow_core.test_docs_coverage`, the full suite (expect `OK (skipped=3)`), and `bash tests/install_smoke_test.sh </dev/null` (expect exit 0). Rebuild the local install with `./install.sh --platform all` so `dist/` matches `src/`.

**Acceptance criteria:**
- Skill and docs match Tracks 1–3 and describe the team process from spec Requirement 4; packaging and docs checks pass.
- Independent review approves.

## Integration

- **Branch**: `feat/teamwork-hardening`
- **Merge strategy**: sequential

## Validation

- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py </dev/null` → `OK (skipped=3)` with more than 856 tests
- [ ] `bash tests/install_smoke_test.sh </dev/null` → exit 0
- [ ] Every row of the spec's Testing section maps to a named test in Tracks 1–3
- [ ] Manual: `gin-workflow record verification-passed` on this repository's feature branch, then an empty commit, then `gin-workflow state` shows `verification_passed: unmet`

## Notes

- No team uses team mode yet, so closed `external:` placeholders without `merge_commit` metadata (pre-change) are reported as `no merge commit recorded; run team deps` rather than migrated.
- Model guidance is planning metadata, not Beads state. Concrete providers and models are resolved at orchestration.
- The parent bead stays open until the human-confirmed merge; track beads close after tests and review pass.
