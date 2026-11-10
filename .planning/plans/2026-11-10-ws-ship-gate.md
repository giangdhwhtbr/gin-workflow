# Plan: Ship gate accepts pull requests of workspace children

Spec: .planning/specs/2026-11-10-ws-ship-gate-design.md
Epic: gin-workflow-ws-ship-gate
Workflow: gin-workflow-ws-ship-gate

## Objective

`gin team check --gate ship` and `gin record shipped` accept an approved pull request of a `workspace.repos` child, compared with that child's URL and with the HEAD of the working directory's checkout of that child (else the child's main checkout); parent pull requests behave exactly as before.

**Goal** (spec): `gin team check --gate ship` and `gin record shipped` accept a pull request opened in a workspace child repository, comparing it with that child's remote and HEAD instead of the parent's.

**Architecture**: one new function `repo_for_pr` in `team.py` resolves the expected repository URL and the HEAD directory; `check_approval` takes the expected URL as a parameter; `verify_gate` calls `repo_for_pr` once for `ship`/`shipped`. No other module changes.

**Tech Stack**: Python 3 standard library; unittest with the `team_fixtures` helpers (`make_team_repo`, `fake_cli`, `gh_pr`, `run_cli`, `git`, `write`, `LAUNCHER`).

**Global Constraints** (spec, verbatim):
- Without a workspace, behaviour is unchanged: the expected repository is the parent's origin and HEAD comes from `root`.
- The `requirement_confirmed`, `plan_approved`, and `roadmap` gates keep comparing with the parent's origin.
- No JSON, config, or Beads metadata change; gin-console is unaffected.
- Out of scope: several pull request URLs in one `record shipped --evidence` (BE-LEAD-13) and `team deps` for children (BE-LEAD-16), both `gin-workflow-ws-branch-model`; approval policy (`gin-workflow-approval-roles`); any `gates` metadata schema change.

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
- Problem statement: the ship gate compares every pull request with the parent's origin and HEAD, so child pull requests always fail.
- Success criteria: spec R1 to R5; US-1 and US-2 acceptance criteria as tests.
- Constraints: Global Constraints above.
- Non-goals: see Global Constraints.

## Approach Options
### Option 1: resolve the repository once in `verify_gate`
- Summary: `repo_for_pr` returns `(expected_url, head_dir)`; `check_approval` gets `expected_repo`.
- Pros: one call site; parent path unchanged; no new module.
- Cons: `check_approval` gains a parameter.

### Option 2: resolve the child in `team_cli` and pass a different root
- Summary: run the whole check with the child as root.
- Pros: no change to `check_approval`.
- Cons: the child has no team config; `record shipped` goes through `lifecycle_cli`, so two call sites would need it.

### Recommended Approach
- Selected option: Option 1.
- Rationale: smallest change that covers both `team check` and `record shipped`.

## Scope
- In scope: R1 to R5.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: One track; the code, tests, and docs change together.
```

## Tasks

### Track 1: Resolve the ship pull request's repository and HEAD
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:384-389` (`origin_url` unchanged; add `repo_for_pr` after it), `:418-426` (`check_approval` parameter), `:505-518` (`verify_gate`)
  - Modify `docs/guides/team.md:55` (gates row: "The pull request must belong to this repository" sentence)
  - Modify `docs/guides/workspace.md:87-89` (Ship row and paragraph)
  - Modify `plugins/gin-workflow/src/skills/team/SKILL.md:42` (ship paragraph, one clause)
  - Test `tests/workflow_core/test_team_gates.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to one module with exact rules; the tests need a workspace fixture with a git child and a linked worktree, which is careful but not intricate.
- **Interfaces**:
  - `team.repo_for_pr(root: Path, team: TeamConfig, pr_url: str, cwd: Path | None = None) -> tuple[str, Path, list[str]]` returning `(expected_url, head_dir, accepted_ids)`; `accepted_ids` is the parent id plus every workspace entry id (empty list without a workspace); `cwd` defaults to `Path.cwd()`.
  - `team.check_approval(..., expected_repo: str = "", accepted: Sequence[str] = ())`: with `expected_repo` empty it uses `origin_url(root)` as today.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_gates.py`, new class `TestChildShipGate(GateCase)` placed before the `if __name__ == "__main__":` guard and not between any decorator and its class:
     ```python
     CHILD_PR = "https://github.com/org/api/pull/9"
     CHILD_WORKSPACE = """workspace:
       repos:
         - {path: services/api, url: "git@github.com:org/api.git", shape: backend}
         - {path: apps/web, url: "git@github.com:org/web.git", shape: frontend}
     """


     class TestChildShipGate(GateCase):
         def setUp(self):
             self.tmp = tempfile.TemporaryDirectory()
             self.root = make_team_repo(Path(self.tmp.name) / "repo", host=self.host, extra=CHILD_WORKSPACE)
             self.bin = Path(self.tmp.name) / "bin"
             self.env = path_with(self.bin)
             self.child = self.root / "services/api"
             self.child.mkdir(parents=True)
             git(self.child, "init", "-q", "-b", "main")
             git(self.child, "config", "user.email", "binh@corp.com")
             git(self.child, "config", "user.name", "T")
             git(self.child, "remote", "add", "origin", "git@github.com:org/api.git")
             git(self.child, "commit", "-q", "--allow-empty", "-m", "feat: api")
             self.head = git(self.child, "rev-parse", "HEAD").strip()

         def child_pr(self, head, state="OPEN", url=CHILD_PR):
             fake_cli(self.bin, "gh", [{"argv": ["pr", "view", url], "exit": 0,
                                        "stdout": gh_pr(url, state=state, head=head,
                                                        reviews=[("dung-qe", "APPROVED", head)])}])

         def run_in(self, cwd, *args):
             return subprocess.run([sys.executable, str(LAUNCHER), *args], cwd=cwd, text=True, capture_output=True,
                                   env={**os.environ, **self.env}, check=False)

         def test_child_pr_passes_from_parent_child_and_worktree(self):
             self.child_pr(self.head)
             self.assertEqual(0, run_cli(self.root, "team", "check", CHILD_PR, "--gate", "ship", env=self.env).returncode)
             self.assertEqual(0, self.run_in(self.child, "team", "check", CHILD_PR, "--gate", "ship").returncode)
             worktree = Path(self.tmp.name) / "wt"
             git(self.child, "worktree", "add", "-q", "-b", "track", str(worktree))
             git(worktree, "commit", "-q", "--allow-empty", "-m", "feat: track")
             track_head = git(worktree, "rev-parse", "HEAD").strip()
             self.child_pr(track_head)
             self.assertEqual(0, self.run_in(worktree, "team", "check", CHILD_PR, "--gate", "ship").returncode)
             mismatch = self.run_in(self.child, "team", "check", CHILD_PR, "--gate", "ship")
             self.assertEqual(1, mismatch.returncode)
             self.assertIn("is not local HEAD", mismatch.stdout)

         def test_unlisted_repository_is_refused_with_accepted_ids(self):
             other = "https://github.com/org/other/pull/3"
             self.child_pr(self.head, url=other)
             result = run_cli(self.root, "team", "check", other, "--gate", "ship", env=self.env)
             self.assertEqual(1, result.returncode)
             self.assertIn("not this repository", result.stdout)
             self.assertIn("github.com/org/api", result.stdout)

         def test_uncloned_child_names_workspace_clone(self):
             url = "https://github.com/org/web/pull/4"
             self.child_pr(self.head, url=url)
             result = run_cli(self.root, "team", "check", url, "--gate", "ship", env=self.env)
             self.assertNotEqual(0, result.returncode)
             self.assertIn("gin workspace clone apps/web", result.stdout + result.stderr)

         def test_record_shipped_accepts_a_merged_child_pr(self):
             self.child_pr(self.head, state="MERGED")
             result = run_cli(self.root, "record", "shipped", "--evidence", CHILD_PR, "--workflow-id", "w", env=self.env)
             self.assertEqual(0, result.returncode, result.stderr)
     ```
     Import `os`, `subprocess`, `sys` if not already imported, and `LAUNCHER`, `path_with`, `make_team_repo`, `git`, `gh_pr`, `fake_cli`, `run_cli` from `team_fixtures` as the file already does. If `record shipped --workflow-id w` is refused for an unrelated reason (for example "no epic"), follow how the existing `shipped` tests in this file set it up (search `"shipped"`), keeping the child PR as evidence.
  2. Run `python3 -m pytest tests/workflow_core/test_team_gates.py -k TestChildShipGate -q` → fails ("not this repository").
  3. In `team.py`, after `origin_url`:
     ```python
     def repo_for_pr(root: Path, team: TeamConfig, pr_url: str, cwd: Path | None = None) -> tuple[str, Path, list[str]]:
         """The URL a ship PR must match, the directory whose HEAD the `ship` gate compares, and the repository ids a
         workspace accepts. The parent when the PR is its own; else the `workspace.repos` entry with the PR's
         repository, taking HEAD from `cwd` when it is that child's checkout or one of its worktrees."""
         from .checkout import main_checkout
         from . import workspace as workspace_core

         host = adapter(team.host)
         parent = origin_url(Path(root))
         wanted = host.repo_id(pr_url, pr=True)
         if wanted == host.repo_id(parent):
             return parent, Path(root), []
         space = workspace_core.load(Path(root))
         if space is None:
             return parent, Path(root), []
         accepted = [host.repo_id(parent)] + [host.repo_id(entry.url) for entry in space.repos if entry.url]
         for entry in space.repos:
             if entry.url and host.repo_id(entry.url) == wanted:
                 checkout = space.checkout(entry)
                 if not (checkout / ".git").exists():
                     raise TeamError(f"{entry.path} is not cloned; run gin workspace clone {entry.path}")
                 here = Path(cwd or Path.cwd()).resolve()
                 same = main_checkout(here) == checkout.resolve()
                 return entry.url, (here if same else checkout), accepted
         return parent, Path(root), accepted
     ```
     If `workspace.Repo.url` can be missing or the `Repo` field name differs, read `workspace.py:29-52` and adapt the attribute names only.
  4. `check_approval` gains `expected_repo: str = "", accepted: Sequence[str] = ()` (add `Sequence` to the typing import). Replace the origin line with:
     ```python
     expected, actual = host.repo_id(expected_repo or origin_url(Path(root))), host.repo_id(pr.url, pr=True)
     if actual != expected:
         also = f"; accepted: {', '.join(accepted)}" if accepted else ""
         reasons.append(f"PR belongs to {actual}, not this repository ({expected}){also}")
     ```
  5. In `verify_gate`, after fetching the PR:
     ```python
     expected, head_dir, accepted = (repo_for_pr(Path(root), team, url) if gate in ("ship", "shipped")
                                     else ("", Path(root), []))
     ```
     use `head = _head(head_dir) if gate == "ship" else ""` and pass `expected_repo=expected, accepted=accepted` to `check_approval`.
  6. Run step 2 → passes. Run `python3 -m pytest tests/workflow_core/test_team_gates.py tests/workflow_core/test_lifecycle_cli.py -q -n auto` → passes (existing parent ship tests unchanged).
  7. Docs:
     - `docs/guides/team.md:55`: replace "The pull request must belong to this repository" with "The pull request must belong to this repository, or for `ship` to a `workspace.repos` child".
     - `docs/guides/workspace.md` Ship row (line 87) append: "; `team check --gate ship` and `record shipped` accept a child's pull request and compare it with the HEAD of the child checkout or track worktree you run them from, else the child's main checkout". Keep sentences at most 35 words; split if needed.
     - `plugins/gin-workflow/src/skills/team/SKILL.md:42`: after "before merging run `gin team check --gate ship <pr-url>`" add " (in a workspace, from the child's track worktree for a child PR)". Then run `cd plugins/gin-workflow/src/scripts && python3 -m workflow_core.budget --report --src ../ && cd -`; every stage chain stays at most 12,000.
     - Run `gin docs check docs/guides/team.md docs/guides/workspace.md` → no findings.
  8. Run `python3 -m pytest tests/workflow_core/test_token_budget.py -q` → passes; run `python3 -m pytest -n auto -q` and read the summary line → passes.
  9. Commit: `fix(team): ship gate accepts pull requests of workspace children (gin-workflow-ws-ship-gate)`.
- **Acceptance criteria**: R1 to R5; US-1 and US-2 pass as the tests above; existing team gate tests pass; budgets hold.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/ws-ship-gate`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto -q` passes (pre-push runs it).
- [ ] `gin docs check docs/guides/team.md docs/guides/workspace.md` reports no findings.
- [ ] `python3 -m pytest tests/workflow_core/test_token_budget.py -q` passes.

## Notes
- Omit `Effort:` when the catalog lists no efforts.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
- Test hygiene from earlier reviews: new classes above the `__main__` guard, never between a decorator and its class, no duplicate class names; check `--collect-only` counts.
