# Plan: Team handoff: one command to hand a track over, one to take it

Spec: `.planning/specs/2026-11-07-team-handoff-design.md`
Epic: gin-workflow-ht4l

## Objective

`gin team handoff <bead> (<email> | --release) [--worktree PATH]` refuses a dirty track worktree, pushes the track branch and its review ref, records `handoff` metadata on the bead, then reassigns the bead or releases it to the pool with the label `released`. `gin team takeover <bead> [--branch NAME]` runs in the main checkout, fetches the recorded branch, checks it out at `.planning/worktrees/<bead>` through the new `worktrees.checkout`, fetches the review ref, and claims. A `released` bead is listed by `team ready` for every member and claimable regardless of area. Docs and the team skill describe the two commands.

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
- Problem statement: handing a track over in team mode is a manual chain (push branch, commit ledger, `team reassign`; fetch, `git worktree add`, `team claim`) and a wrong order loses work. `reassign` (`team_beads.py:166-191`) touches Beads only; `worktrees.create` only makes new branches (`worktrees.py:40`); `claim` refuses beads outside the member's areas (`team_beads.py:127-129`); `ready` lists unassigned beads only for the member's areas (`team_beads.py:85-109`).
- Success criteria: R1–R6 and US-1..4 of the spec; existing `test_team_beads.py` and `test_worktrees.py` keep passing; the team skill stays under 6,000 characters.
- Constraints: `team_cli.main` maps `TeamError`/`ValueError` to exit 2 and `SyncConflict` to exit 1 (`team_cli.py:142-158`), so every step failure the spec wants at exit 1 is raised as `SyncConflict`; `worktrees._git` raises `RuntimeError`, which `team_cli` does not catch, so callers wrap it. `review-ledger.py push-refs` has no `--repository` and reads the ledger from the process cwd, so handoff calls `review_ledger.git_adapter.push_review_ref(repo_path, ref)` directly. `fetch_review_ref` has no force flag, so takeover fetches with `+ref:ref` through `worktrees._git`. `bd ready --json` and `bd list --json` rows carry `labels` but not `metadata`, so the pool flag is the label `released`. `bd show --json` omits `assignee`, `labels`, `metadata` when unset. Test fixtures: `make_team_repo` sets `origin` to a fake URL and makes no commit; real git pushes need a bare repo and `git remote set-url origin`.
- Non-goals: track beads from a plan, PR body, `team member`, host-settings check, notifications, the markdown backend.

## Architecture
`workflow_core/worktrees.py` gains `checkout` (existing branch, local or `origin/`). `workflow_core/team_beads.py` gains `handoff` and `takeover`, a `released`-aware `ready` and `claim`, and shares the reassign checks through `_reassign_target`. `workflow_core/team_cli.py` adds the two subcommands. No config schema change.

## Tech Stack
Python 3 standard library (`argparse`, `subprocess`, `json`), `bd` 1.0.5 through `team_beads._bd`, git through `worktrees._git`, `review_ledger.git_adapter.push_review_ref`.

## Global Constraints
- Ordering in `handoff`: checks, then branch push, then review ref, then metadata, then Beads; a failure at any step stops there and the message names the step. Beads is never changed before the branch is on `origin`.
- Uncommitted or untracked files in the track worktree: `handoff` exits 1, lists them, and changes nothing. It never commits on the owner's behalf.
- `reassign`, `claim`, and `ready` keep today's behaviour for beads without the `released` label.
- The `handoff` metadata is `{"branch", "from", "to", "at"}`; the pool flag is the label `released`.
- `takeover` runs in the main checkout only; the worktree is always `.planning/worktrees/<bead>`.
- The team skill stays at or under 6,000 characters (`tests/workflow_core/test_token_budget.py`, `SHARED_SKILLS`).

## Approach Options
### Option 1: Two new subcommands reusing reassign/claim internals (chosen in the spec)
- Summary: `handoff` and `takeover` in `team_beads.py`, `worktrees.checkout`, label-based pool flag.
- Pros: manual path unchanged; one write path per outcome; tests stay bd-only (no Dolt).
- Cons: the authority checks move into a shared helper (`_reassign_target`) that `reassign` and `handoff` both call.

### Option 2: Flags on `reassign` and `claim`
- Summary: `reassign --push`, `claim --checkout`.
- Pros: no new command names.
- Cons: `--release` does not fit `reassign`; rejected at discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed at discuss; the only technical refinement is the label `released` instead of a metadata flag, because `bd ready --json` rows have no metadata (spec R2 updated).

## Scope
- In scope: `plugins/gin-workflow/src/scripts/workflow_core/{worktrees,team_beads,team_cli}.py`; `tests/workflow_core/{test_worktrees,test_team_beads}.py`; `docs/reference/cli.md`; `docs/guides/{team,team.vi,ai-strategy}.md`; `plugins/gin-workflow/src/skills/team/SKILL.md`.
- Out of scope: `review-ledger.py`, `setup_service.py`, schemas, gin-console.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 2, 3, and 4 all edit team_beads.py, team_cli.py, and test_team_beads.py, and Track 4 calls the checkout from Track 1 and the claim rules from Track 2; one track at a time avoids merge conflicts and keeps each review small.
```

## Tasks

### Track 1: `worktrees.checkout` and `gin worktree checkout` (US-4)
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/worktrees.py:32-76` (add `checkout` after `create`; add the `checkout` subparser and dispatch in `main`)
  - Test `tests/workflow_core/test_worktrees.py` (three new tests in `WorktreeTests`)
  - Modify `docs/reference/cli.md:321-328` (the `gin worktree` block)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded function with a clear spec and three cases (local branch, remote-only branch, errors); the git flags are given below.
- **Steps**:
  1. Add to `tests/workflow_core/test_worktrees.py`, inside `WorktreeTests` after `test_create_from_explicit_base_ref`:
     ```python
     def test_checkout_existing_local_branch(self):
         git(self.root, "branch", "feat/x")
         path = worktrees.checkout(self.root, "t3", "feat/x")
         self.assertEqual(self.worktrees / "t3", path)
         self.assertEqual("feat/x", git(path, "rev-parse", "--abbrev-ref", "HEAD"))

     def test_checkout_remote_only_branch_tracks_origin(self):
         remote = self.root.parent / f"{self.root.name}-origin.git"
         git(self.root, "init", "-q", "--bare", str(remote))
         self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(remote)], check=False))
         git(self.root, "remote", "add", "origin", str(remote))
         git(self.root, "push", "-q", "origin", "HEAD:refs/heads/feat/remote")
         git(self.root, "fetch", "-q", "origin")
         path = worktrees.checkout(self.root, "t4", "feat/remote")
         self.assertEqual("feat/remote", git(path, "rev-parse", "--abbrev-ref", "HEAD"))
         self.assertEqual("origin/feat/remote", git(path, "rev-parse", "--abbrev-ref", "@{upstream}"))

     def test_checkout_refuses_unknown_branch_and_existing_directory(self):
         with self.assertRaisesRegex(ValueError, "does not exist"):
             worktrees.checkout(self.root, "t5", "nope")
         worktrees.create(self.root, "t6", "bead/t6")
         with self.assertRaisesRegex(ValueError, "already exists"):
             worktrees.checkout(self.root, "t6", "bead/t6")
     ```
     Run `python3 -m pytest -q tests/workflow_core/test_worktrees.py`: the three new tests fail with `AttributeError: module ... has no attribute 'checkout'`.
  2. In `worktrees.py`, after `create` (line 41) add:
     ```python
     def checkout(repo: Path, track_id: str, branch: str) -> Path:
         """Existing branch `branch` checked out at `.planning/worktrees/<track_id>`; a branch that exists only on origin is created tracking it."""
         target = _target(repo, track_id)
         if target.exists():
             raise ValueError(f"directory {target} already exists")
         if not branch.strip():
             raise ValueError("branch is required")
         if _git(repo, "branch", "--list", branch):
             _git(repo, "worktree", "add", "--", str(target), branch)
         elif _git(repo, "branch", "-r", "--list", f"origin/{branch}"):
             _git(repo, "worktree", "add", "--track", "-b", branch, "--", str(target), f"origin/{branch}")
         else:
             raise ValueError(f"branch {branch} does not exist locally or on origin")
         return target
     ```
  3. In `main`, after the `create_parser` block add:
     ```python
         checkout_parser = commands.add_parser("checkout")
         checkout_parser.add_argument("--repository", default=".")
         checkout_parser.add_argument("track_id")
         checkout_parser.add_argument("branch")
     ```
     and in the `try` block, before `elif (removed := cleanup(...)) is None:` add:
     ```python
             elif args.command == "checkout":
                 path = checkout(repo, args.track_id, args.branch)
                 print(f"Worktree created at: {path} on branch {args.branch}")
     ```
  4. Run `python3 -m pytest -q tests/workflow_core/test_worktrees.py`: all pass.
  5. In `docs/reference/cli.md`, after line 323 (`gin worktree cleanup ...`) add the line `gin worktree checkout [--repository DIR] TRACK_ID BRANCH`; in the paragraph at line 326, after the `create` sentence add: `` `checkout` checks out an existing branch `BRANCH` at the same path; a branch that exists only on `origin` is created locally tracking it; it refuses an existing directory and an unknown branch. ``
  6. Commit: `feat(worktree): gin worktree checkout for an existing branch (gin-workflow-ht4l)`.
- **Interfaces**: produces `worktrees.checkout(repo: Path, track_id: str, branch: str) -> Path` (raises `ValueError` for an existing directory or unknown branch, `RuntimeError` from `_git`); consumed by Track 4.
- **Acceptance criteria**: US-4; `test_worktrees.py` passes; the CLI block in cli.md lists `checkout`.
- **Estimated complexity**: low

### Track 2: `released` beads in `ready` and `claim` (R4)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:85-145` (`ready`, `claim`; add the `RELEASED` constant near line 20)
  - Test `tests/workflow_core/test_team_beads.py` (two tests in `TestTeamBeadsLocal`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** two small conditional changes with exact code; the fixture already covers the area rules.
- **Steps**:
  1. Add to `TestTeamBeadsLocal` in `tests/workflow_core/test_team_beads.py` (after `test_claim_refuses_an_area_the_member_may_not_own`):
     ```python
     def test_released_bead_is_ready_and_claimable_outside_its_areas(self):
         frontend = create(self.root, "form", "area:frontend", "released")
         listed = run_cli(self.root, "team", "ready", "--format", "json")
         self.assertEqual(0, listed.returncode)
         row = next(r for r in json.loads(listed.stdout)["ready"] if r["id"] == frontend)
         self.assertTrue(row["released"])
         claimed = run_cli(self.root, "team", "claim", frontend)
         self.assertEqual(0, claimed.returncode, claimed.stdout + claimed.stderr)
         issue = show(self.root, frontend)
         self.assertEqual("binh@corp.com", issue["assignee"])
         self.assertNotIn("released", issue.get("labels") or [])

     def test_unreleased_frontend_bead_stays_hidden_and_refused(self):
         frontend = create(self.root, "form", "area:frontend")
         listed = run_cli(self.root, "team", "ready", "--format", "json")
         self.assertNotIn(frontend, [r["id"] for r in json.loads(listed.stdout)["ready"]])
         self.assertEqual(1, run_cli(self.root, "team", "claim", frontend).returncode)
     ```
     Run `python3 -m pytest -q tests/workflow_core/test_team_beads.py -k released_bead`: the first test fails (`StopIteration` or exit 1); the second passes already.
  2. In `team_beads.py`, after `_EXTERNAL`/`_TRACKS_LINE` (line 19) add `RELEASED = "released"`.
  3. In `ready`, change the first loop's condition to:
     ```python
             labels = issue.get("labels") or []
             areas = {label[5:] for label in labels if label.startswith("area:")}
             released = RELEASED in labels
             if assignee == member.email or (not assignee and (released or areas & mine or (not areas and not team.areas))):
                 result.append({"id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                                "areas": sorted(areas), "released": released})
     ```
     (the second loop is unchanged).
  4. In `claim`, replace lines 127-129 with:
     ```python
         released = RELEASED in (issue.get("labels") or [])
         ineligible = [] if released else [area.name for area in _areas_of(team, issue) if not team.eligible(member, area)]
         if ineligible:
             raise SyncConflict(f"{member.email} may not own tracks in {', '.join(ineligible)}")
     ```
     and after the `argv = [...]` if/else (line 139) add:
     ```python
         if released:
             argv += ["--remove-label", RELEASED]
     ```
  5. Run `python3 -m pytest -q tests/workflow_core/test_team_beads.py` (about 160 s, run with a 600000 ms timeout): all pass.
  6. Commit: `feat(team): released beads are ready for and claimable by every member (gin-workflow-ht4l)`.
- **Interfaces**: produces `team_beads.RELEASED = "released"` and the `released` key in `ready` rows; `claim` unchanged in signature.
- **Acceptance criteria**: US-2 bullets 2 and 3; `test_team_beads.py` passes.
- **Estimated complexity**: low

### Track 3: `gin team handoff` (R1, R2, R3)
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py` (imports at 13-15; `_reassign_target` extracted from `reassign` at 166-191; new `handoff_of`, `_track_worktree`, `_ledger_ref`, `_local_ref`, `handoff` after `reassign`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:34-37` (parser) and `:121-124` (dispatch)
  - Test `tests/workflow_core/test_team_beads.py` (new class `TestTeamHandoff`)
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** cross-module change: git pushes from a worktree, review refs through `review_ledger.git_adapter`, Beads writes, and a strict failure order; the test needs a bare origin and a real worktree.
- **Steps**:
  1. Add to `tests/workflow_core/test_team_beads.py`, after `TestTeamBeadsLocal`:
     ```python
     @unittest.skipUnless(HAS_BD, "bd is not installed")
     class TestTeamHandoff(unittest.TestCase):
         def setUp(self):
             self.tmp = tempfile.TemporaryDirectory()
             base = Path(self.tmp.name)
             self.origin = base / "origin.git"
             git(base, "init", "-q", "--bare", str(self.origin))
             self.root = make_team_repo(base / "repo")
             git(self.root, "remote", "set-url", "origin", str(self.origin))
             git(self.root, "commit", "-q", "--allow-empty", "-m", "base")
             git(self.root, "push", "-q", "origin", "main")
             init_beads(self.root)
             self.bead = create(self.root, "API", "area:backend")
             self.assertEqual(0, run_cli(self.root, "team", "claim", self.bead).returncode)
             self.worktree = worktrees.create(self.root, self.bead, "feat/api-t1")
             (self.worktree / "api.txt").write_text("v1", encoding="utf-8")
             git(self.worktree, "add", "api.txt")
             git(self.worktree, "commit", "-q", "-m", "api v1")

         def tearDown(self):
             self.tmp.cleanup()

         def remote_branches(self):
             return git(self.origin, "branch", "--list", "feat/api-t1").split()

         def test_handoff_refuses_a_dirty_worktree_and_changes_nothing(self):
             (self.worktree / "scratch.txt").write_text("x", encoding="utf-8")
             refused = run_cli(self.root, "team", "handoff", self.bead, "em@corp.com")
             self.assertEqual(1, refused.returncode)
             self.assertIn("scratch.txt", refused.stdout)
             self.assertEqual([], self.remote_branches())
             self.assertEqual("binh@corp.com", show(self.root, self.bead)["assignee"])

         def test_handoff_pushes_branch_records_metadata_and_reassigns(self):
             done = run_cli(self.root, "team", "handoff", self.bead, "em@corp.com")
             self.assertEqual(0, done.returncode, done.stdout + done.stderr)
             self.assertEqual(["feat/api-t1"], self.remote_branches())
             issue = show(self.root, self.bead)
             self.assertEqual("em@corp.com", issue["assignee"])
             handoff = team_beads.handoff_of(issue)
             self.assertEqual({"branch": "feat/api-t1", "from": "binh@corp.com", "to": "em@corp.com"},
                              {k: handoff[k] for k in ("branch", "from", "to")})
             self.assertEqual("em@corp.com", team_beads.claim_of(issue)["holder"])
             self.assertIn("next: gin team takeover", done.stderr)

         def test_handoff_release_reopens_and_labels_the_bead(self):
             done = run_cli(self.root, "team", "handoff", self.bead, "--release")
             self.assertEqual(0, done.returncode, done.stdout + done.stderr)
             issue = show(self.root, self.bead)
             self.assertFalse(issue.get("assignee"))
             self.assertEqual("open", issue["status"])
             self.assertIn("released", issue["labels"])
             self.assertEqual({}, team_beads.claim_of(issue))
             self.assertIsNone(team_beads.handoff_of(issue)["to"])
             git(self.root, "config", "user.email", "chi@corp.com")
             listed = run_cli(self.root, "team", "ready", "--format", "json")
             self.assertIn(self.bead, [r["id"] for r in json.loads(listed.stdout)["ready"]])

         def test_handoff_refuses_missing_worktree_and_bad_arguments(self):
             other = create(self.root, "DB", "area:backend")
             self.assertEqual(0, run_cli(self.root, "team", "claim", other).returncode)
             missing = run_cli(self.root, "team", "handoff", other, "em@corp.com")
             self.assertEqual(1, missing.returncode)
             self.assertIn("no worktree for", missing.stdout)
             self.assertEqual(2, run_cli(self.root, "team", "handoff", self.bead).returncode)
             self.assertEqual(2, run_cli(self.root, "team", "handoff", self.bead, "em@corp.com", "--release").returncode)
     ```
     Add `from workflow_core import team_beads, worktrees` next to the existing `team_beads` import at the top of the file (keep the existing import if it already names `team_beads`). Run `python3 -m pytest -q tests/workflow_core/test_team_beads.py -k TestTeamHandoff`: the four tests fail (`gin team handoff` is an unknown command, exit 2).
  2. In `team_beads.py` imports (line 13-15) add `import sys` and `from . import worktrees`. The review-ref push is imported inside `handoff` (`from review_ledger.git_adapter import GitAdapterError, push_review_ref`, resolved from the `scripts` directory on `sys.path` as `review-ledger.py:28-36` does) so importing `team_beads` never depends on the ledger package.
  3. Extract the checks of `reassign` into a helper placed right before `reassign`:
     ```python
     def _reassign_target(team: TeamConfig, member: Member, bead: str, issue: Mapping[str, Any], email: str) -> tuple[str, Member]:
         """(holder, target) after the reassign rules: authority, open bead, member target, eligible target."""
         target = team.member(email)
         if target is None:
             raise TeamError(f"{email} is not a team member")
         if issue.get("status") == "closed":
             raise SyncConflict(f"{bead} is closed")
         holder = (issue.get("assignee") or "").lower()
         areas = _areas_of(team, issue)
         if holder != member.email and not any(area.lead in member.roles for area in areas):
             raise SyncConflict(f"only {holder or 'an area lead'} or the lead of its area may reassign {bead}")
         if holder == target.email:
             raise SyncConflict(f"{bead} is already assigned to {target.email}")
         ineligible = [area.name for area in areas if not team.eligible(target, area)]
         if ineligible:
             raise SyncConflict(f"{target.email} may not own tracks in {', '.join(ineligible)}")
         return holder, target
     ```
     and rewrite `reassign` to:
     ```python
     def reassign(root: Path, team: TeamConfig, member: Member, bead: str, email: str) -> dict[str, Any]:
         """Hand a track to another member: only the current assignee or the lead of one of its areas may."""
         if team.member(email) is None:
             raise TeamError(f"{email} is not a team member")
         if team.beads_remote:
             sync(root)
         issue = _show(root, bead)
         holder, target = _reassign_target(team, member, bead, issue, email)
         _write_reassign(root, team, member, bead, holder, target)
         _push(root, team, bead)
         return {"status": "reassigned", "bead": bead, "from": holder, "assignee": target.email}


     def _write_reassign(root: Path, team: TeamConfig, member: Member, bead: str, holder: str, target: Member) -> None:
         note = f"reassigned {holder or 'nobody'} -> {target.email} by {member.email}"
         completed = _bd(root, ["update", bead, "--assignee", target.email, "--append-notes", note,
                                "--set-metadata", f'claim={json.dumps({"holder": target.email, "expires_at": _expires(team)})}'], actor=member.email)
         if completed.returncode != 0:
             raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
     ```
     Run `python3 -m pytest -q tests/workflow_core/test_team_beads.py -k reassign`: the three reassign tests still pass.
  4. After `_write_reassign` add:
     ```python
     def handoff_of(issue: Mapping[str, Any]) -> dict[str, Any]:
         return metadata_json(issue, "handoff")


     def _track_worktree(root: Path, bead: str, worktree: str | None) -> Path:
         path = Path(worktree).resolve() if worktree else worktrees._target(root, bead)
         if not path.is_dir():
             raise SyncConflict(f"no worktree for {bead}; pass --worktree <path>")
         return path


     def _ledger_ref(worktree: Path, bead: str) -> str:
         """The review ref the bead's ledger names, else the default refs/gin/review/<bead>."""
         ledger = worktree / ".planning/reviews" / bead / "review.json"
         default = f"refs/gin/review/{bead}"
         if not ledger.is_file():
             return default
         repos = json.loads(ledger.read_text(encoding="utf-8")).get("repositories") or [{}]
         return repos[0].get("checkpoint_ref") or repos[0].get("review_ref") or default


     def _local_ref(worktree: Path, ref: str) -> bool:
         try:
             worktrees._git(worktree, "rev-parse", "--verify", "--quiet", ref)
         except RuntimeError:
             return False
         return True


     def handoff(root: Path, team: TeamConfig, member: Member, bead: str, *, email: str | None = None,
                 release: bool = False, worktree: str | None = None) -> dict[str, Any]:
         """Push the track branch and review ref, record the branch on the bead, then reassign or release it."""
         from review_ledger.git_adapter import GitAdapterError, push_review_ref

         if bool(email) == release:
             raise TeamError("pass exactly one of <email> or --release")
         path = _track_worktree(root, bead, worktree)
         dirty = worktrees._git(path, "status", "--porcelain")
         if dirty:
             raise SyncConflict(f"{bead}: uncommitted changes in {path}:\n{dirty}")
         if team.beads_remote:
             sync(root)
         issue = _show(root, bead)
         holder = (issue.get("assignee") or "").lower()
         target = None
         if email:
             holder, target = _reassign_target(team, member, bead, issue, email)
         else:
             if issue.get("status") == "closed":
                 raise SyncConflict(f"{bead} is closed")
             areas = _areas_of(team, issue)
             if holder != member.email and not any(area.lead in member.roles for area in areas):
                 raise SyncConflict(f"only {holder or 'an area lead'} or the lead of its area may release {bead}")
         branch = worktrees._git(path, "rev-parse", "--abbrev-ref", "HEAD")
         if branch == "HEAD":
             raise SyncConflict(f"{path} is on a detached HEAD; check out the track branch first")
         try:
             worktrees._git(path, "push", "-u", "origin", branch)
         except RuntimeError as error:
             raise SyncConflict(f"git push of {branch} failed: {error}") from error
         ref = _ledger_ref(path, bead)
         if _local_ref(path, ref):
             try:
                 push_review_ref(str(path), ref)
             except GitAdapterError as error:
                 raise SyncConflict(f"review ref push failed for {ref}: {error}") from error
         else:
             print(f"no review ledger for {bead}", file=sys.stderr)
         meta = json.dumps({"branch": branch, "from": member.email, "to": target.email if target else None, "at": utc_now()})
         completed = _bd(root, ["update", bead, "--set-metadata", f"handoff={meta}"], actor=member.email)
         if completed.returncode != 0:
             raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
         if target:
             _write_reassign(root, team, member, bead, holder, target)
         else:
             completed = _bd(root, ["update", bead, "--assignee", "", "--status", "open", "--unset-metadata", "claim",
                                    "--add-label", RELEASED, "--append-notes", f"released to the pool by {member.email}"],
                             actor=member.email)
             if completed.returncode != 0:
                 raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
         _push(root, team, bead)
         print(f"next: gin team takeover {bead}", file=sys.stderr)
         result: dict[str, Any] = {"status": "handed-off" if target else "released", "bead": bead, "branch": branch}
         if target:
             result["assignee"] = target.email
         return result
     ```
  5. In `team_cli.py` `_parser`, after the `reassign` parser (line 36) add:
     ```python
         item = sub.add_parser("handoff", parents=[common])
         item.add_argument("bead")
         item.add_argument("email", nargs="?")
         item.add_argument("--release", action="store_true")
         item.add_argument("--worktree")
     ```
     and in `_run`, after the `reassign` branch (line 124) add:
     ```python
             if args.command == "handoff":
                 if bool(args.email) == args.release:
                     raise team_core.TeamError("pass exactly one of <email> or --release")
                 result = team_beads.handoff(root, team, member, args.bead, email=args.email, release=args.release,
                                             worktree=args.worktree)
                 _emit(result, args.format, f"{result['status']} {args.bead} on {result['branch']}"
                       + (f" -> {result['assignee']}" if result.get("assignee") else ""))
                 return 0
     ```
  6. Run `python3 -m pytest -q tests/workflow_core/test_team_beads.py` (600000 ms timeout): all pass, including the four `TestTeamHandoff` tests. If `bd update --assignee ""` is refused by bd, replace that pair of arguments with a separate `_bd(root, ["assign", bead, ""], actor=member.email)` call before the `update` and keep the rest; re-run.
  7. Commit: `feat(team): gin team handoff pushes the track and reassigns or releases it (gin-workflow-ht4l)`.
- **Interfaces**: consumes `worktrees._target`, `worktrees._git`, `push_review_ref(repo_path: str, review_ref: str)`, `RELEASED`; produces `team_beads.handoff(root, team, member, bead, *, email=None, release=False, worktree=None) -> dict`, `handoff_of(issue) -> dict`, `_reassign_target`, `_write_reassign`, `_ledger_ref`, `_local_ref` (reused by Track 4).
- **Acceptance criteria**: US-1 and US-2 bullet 1; the four new tests and the existing reassign tests pass.
- **Estimated complexity**: medium

### Track 4: `gin team takeover` (R5)
- **Dependencies**: Track 3
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py` (new `takeover` after `handoff`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py` (parser after `handoff`; dispatch after the `handoff` branch)
  - Test `tests/workflow_core/test_team_beads.py` (three tests appended to `TestTeamHandoff`)
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** cross-module: git fetch and worktree creation, review ref fetch, the main-checkout check, and claim; the test simulates the second machine by deleting the local worktree and branch.
- **Steps**:
  1. Append to `TestTeamHandoff`:
     ```python
     def test_takeover_checks_out_the_handed_off_branch_and_claims(self):
         self.assertEqual(0, run_cli(self.root, "team", "handoff", self.bead, "em@corp.com").returncode)
         worktrees.cleanup(self.root, self.bead)
         git(self.root, "branch", "-D", "feat/api-t1")
         git(self.root, "config", "user.email", "em@corp.com")
         taken = run_cli(self.root, "team", "takeover", self.bead, "--format", "json")
         self.assertEqual(0, taken.returncode, taken.stdout + taken.stderr)
         result = json.loads(taken.stdout)
         path = Path(result["worktree"])
         self.assertEqual(self.root / ".planning/worktrees" / self.bead, path)
         self.assertEqual("feat/api-t1", git(path, "rev-parse", "--abbrev-ref", "HEAD"))
         self.assertEqual("v1", (path / "api.txt").read_text(encoding="utf-8"))
         self.assertEqual("em@corp.com", show(self.root, self.bead)["assignee"])
         self.assertIn("next: gin team deps --bead", taken.stderr)

     def test_takeover_refuses_worktree_cwd_missing_branch_and_existing_directory(self):
         shutil.copytree(self.root / ".agent-workflow", self.worktree / ".agent-workflow")
         inside = run_cli(self.worktree, "team", "takeover", self.bead)
         self.assertEqual(1, inside.returncode)
         self.assertIn("main checkout", inside.stdout)
         other = create(self.root, "DB", "area:backend")
         missing = run_cli(self.root, "team", "takeover", other)
         self.assertEqual(1, missing.returncode)
         self.assertIn("pass --branch", missing.stdout)
         git(self.worktree, "push", "-q", "-u", "origin", "feat/api-t1")
         existing = run_cli(self.root, "team", "takeover", self.bead, "--branch", "feat/api-t1")
         self.assertEqual(1, existing.returncode)
         self.assertIn("already exists", existing.stdout)

     def test_takeover_with_explicit_branch_when_no_metadata(self):
         git(self.worktree, "push", "-q", "-u", "origin", "feat/api-t1")
         worktrees.cleanup(self.root, self.bead)
         git(self.root, "branch", "-D", "feat/api-t1")
         taken = run_cli(self.root, "team", "takeover", self.bead, "--branch", "feat/api-t1")
         self.assertEqual(0, taken.returncode, taken.stdout + taken.stderr)
         self.assertTrue((self.root / ".planning/worktrees" / self.bead / "api.txt").is_file())
     ```
     Notes on the second test: `run_cli(self.worktree, ...)` passes `--repository <worktree>` with `cwd=<worktree>`, and `team_cli._run` needs `.agent-workflow/config.yaml` there, hence the `copytree` (`shutil` is already imported in this file); the main-checkout check in `takeover` runs before any Beads call, so the worktree needs no `.beads`. The push before the last call makes `git fetch` succeed so the failure is the existing directory. Run `python3 -m pytest -q tests/workflow_core/test_team_beads.py -k takeover`: the three tests fail (unknown command).
  2. In `team_beads.py` after `handoff` add:
     ```python
     def takeover(root: Path, team: TeamConfig, member: Member, bead: str, *, branch: str | None = None) -> dict[str, Any]:
         """Fetch the handed-off branch, check it out at .planning/worktrees/<bead>, fetch the review ref, claim."""
         git_dir = (root / worktrees._git(root, "rev-parse", "--git-dir")).resolve()
         common = (root / worktrees._git(root, "rev-parse", "--git-common-dir")).resolve()
         if git_dir != common:
             raise SyncConflict("run gin team takeover from the main checkout, not a linked worktree")
         if team.beads_remote:
             sync(root)
         issue = _show(root, bead)
         branch = branch or str(handoff_of(issue).get("branch") or "")
         if not branch:
             raise SyncConflict(f"no handoff branch recorded for {bead}; pass --branch <name>")
         try:
             worktrees._git(root, "fetch", "origin", branch)
             path = worktrees.checkout(root, bead, branch)
         except (RuntimeError, ValueError) as error:
             raise SyncConflict(str(error)) from error
         ref = _ledger_ref(path, bead)
         try:
             worktrees._git(path, "fetch", "origin", f"+{ref}:{ref}")
         except RuntimeError:
             print(f"no review ref {ref} on origin for {bead}", file=sys.stderr)
         result = claim(root, team, member, bead)
         print(f"next: gin team deps --bead {bead}", file=sys.stderr)
         return {**result, "branch": branch, "worktree": str(path)}
     ```
  3. In `team_cli.py` `_parser`, after the `handoff` parser add:
     ```python
         item = sub.add_parser("takeover", parents=[common])
         item.add_argument("bead")
         item.add_argument("--branch")
     ```
     and in `_run`, after the `handoff` branch add:
     ```python
             if args.command == "takeover":
                 result = team_beads.takeover(root, team, member, args.bead, branch=args.branch)
                 _emit(result, args.format, f"{result['status']} {args.bead} at {result['worktree']} on {result['branch']}")
                 return 0
     ```
  4. Run `python3 -m pytest -q tests/workflow_core/test_team_beads.py tests/workflow_core/test_worktrees.py` (600000 ms timeout): all pass.
  5. Commit: `feat(team): gin team takeover checks out the handed-off branch and claims (gin-workflow-ht4l)`.
- **Interfaces**: consumes `worktrees.checkout` (Track 1), `claim` with `RELEASED` (Track 2), `handoff_of`, `_ledger_ref` (Track 3); produces `team_beads.takeover(root, team, member, bead, *, branch=None) -> dict` with keys `status, bead, assignee, expires_at, advisory, branch, worktree`.
- **Acceptance criteria**: US-3; the three takeover tests pass; the whole `test_team_beads.py` passes.
- **Estimated complexity**: medium

### Track 5: Docs and the team skill (R6)
- **Dependencies**: Track 4
- **Files**:
  - Modify `docs/reference/cli.md:188` (two rows after `reassign`)
  - Modify `docs/guides/team.md:64` and `docs/guides/team.vi.md:64` (the handoff paragraph)
  - Modify `docs/guides/ai-strategy.md:66-67` (mermaid nodes) and `:76-91` (the handoff section)
  - Modify `plugins/gin-workflow/src/skills/team/SKILL.md:32`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** five files in two languages and a skill line that must shrink: the team skill is at 5,809 of 6,000 characters, so wording needs judgement, not a weakest-model paste.
- **Steps**:
  1. `docs/reference/cli.md`: after the `reassign BEAD EMAIL` row (line 188) add:
     ```
     | `handoff BEAD [EMAIL] [--release] [--worktree PATH]` | Hand a track over in one step. Refuses a track worktree (`.planning/worktrees/<bead>`, or `--worktree`) with uncommitted or untracked files, listing them. Otherwise pushes the track branch to `origin`, pushes the review ref when the ledger exists, records `handoff` metadata (`branch`, `from`, `to`, `at`), then either reassigns the bead as `reassign` does (`EMAIL`) or releases it to the pool (`--release`: no assignee, status `open`, lease cleared, label `released`). Checks run before any push; Beads changes only after the branch is on `origin`. Exactly one of `EMAIL` or `--release` |
     | `takeover BEAD [--branch NAME]` | Take a handed-off track on your machine. Runs in the main checkout only; fetches the branch recorded by `handoff` (or `--branch`), checks it out at `.planning/worktrees/<bead>` (`gin worktree checkout`), fetches the review ref when present, then claims the bead. A bead labelled `released` can be claimed by any member; the label is removed on claim |
     ```
     In the `claim BEAD` row, after `Refused when you hold no role allowed in one of its `area:` labels` insert ` (unless the bead is labelled `released` by `handoff --release`)`. In the `ready` row (line 186), append `; a bead labelled `released` is listed for every member`.
  2. `docs/guides/team.md:64`, replace the paragraph with:
     ```
     To hand a track over (a member runs out of quota or is away), the current assignee or the area lead runs `gin team handoff <bead> <email>` from the main checkout. It refuses when the track worktree has uncommitted or untracked files, then pushes the track branch and the review ref, records the branch on the bead, and reassigns it with a fresh lease. `gin team handoff <bead> --release` instead returns the bead to the pool: it loses its assignee and lease, reopens, and gets the label `released`, so any member sees it in `gin team ready` and may claim it whatever their areas. The new owner runs `gin team takeover <bead>` in the main checkout of their clone: it fetches the branch, checks it out at `.planning/worktrees/<bead>`, fetches the review ref, and claims. The plan's `Owner:` field is not changed.
     ```
     `docs/guides/team.vi.md:64`, replace the paragraph with the Vietnamese equivalent, keeping every command, path, and label verbatim:
     ```
     Để bàn giao một track (một thành viên hết quota hoặc vắng mặt), assignee hiện tại hoặc area lead chạy `gin team handoff <bead> <email>` từ main checkout. Lệnh từ chối khi worktree của track còn file chưa commit hoặc chưa track, rồi push branch của track và review ref, ghi branch lên bead, và reassign với lease mới. `gin team handoff <bead> --release` trả bead về pool: bead mất assignee và lease, mở lại, và nhận label `released`, nên mọi thành viên thấy nó trong `gin team ready` và có thể claim dù thuộc area nào. Owner mới chạy `gin team takeover <bead>` trong main checkout của clone của mình: lệnh fetch branch, checkout tại `.planning/worktrees/<bead>`, fetch review ref, và claim. Trường `Owner:` của plan không bị đổi.
     ```
  3. `docs/guides/ai-strategy.md`: line 66 becomes `  B -->|"one member"| C["team handoff"]` and line 67 `  C --> D["team takeover"]`. Replace lines 76-91 with:
     ```
     ### Hand a track to another member

     The current assignee or the area lead runs one command from the main checkout; it refuses a dirty worktree, pushes the branch and the review ref, and reassigns the bead (or `--release` returns it to the pool for any member):

     ```bash
     gin team handoff <bead> <email>
     ```

     The new owner takes it in one command from the main checkout of their clone; it fetches the branch, creates `.planning/worktrees/<bead>`, fetches the review ref, and claims:

     ```bash
     gin team takeover <bead>
     ```
     ```
  4. `plugins/gin-workflow/src/skills/team/SKILL.md:32`, replace the line with (one line, 318 characters, shorter than today's):
     ```
     - Out of quota or unavailable: the assignee (or the area lead) runs `team handoff <bead> <email>` (or `--release` to the pool) from the main checkout: it refuses a dirty worktree, pushes the branch and review ref, then reassigns. The new owner runs `team takeover <bead>` in their main checkout: fetch, worktree, claim. The plan's `Owner:` is not changed.
     ```
  5. Run `python3 -m pytest -q tests/workflow_core/test_token_budget.py tests/workflow_core/test_role_aware_skills.py`: pass; `wc -c plugins/gin-workflow/src/skills/team/SKILL.md` prints at most 6000.
  6. Commit: `docs(team): gin team handoff and takeover replace the manual handoff chain (gin-workflow-ht4l)`.
- **Interfaces**: none.
- **Acceptance criteria**: R6; the skill stays under 6,000 characters; every command, flag, and label in the docs matches Tracks 1–4.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/team-handoff`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -q tests/workflow_core/test_worktrees.py tests/workflow_core/test_team_beads.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_team_gates.py` passes (about 3 minutes; bd and dolt are installed on this host)
- [ ] `wc -c plugins/gin-workflow/src/skills/team/SKILL.md` prints at most 6000
- [ ] Manual: two clones of a repo with a bare `origin` and a `team:` block; in clone A claim a bead, create its worktree, commit, `gin team handoff <bead> <email-of-B>`; in clone B `gin team takeover <bead>` then `gin team deps --bead <bead>` exits 0

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog (`haiku`, `sonnet`, `opus`; `low`…`max`) using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply exclusively to the Parent Bead `gin-workflow-ht4l`. Track beads close upon passing tests and code review.
