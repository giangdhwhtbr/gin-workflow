# Plan: Branch, pull request, and review ledger model for workspace children

Spec: .planning/specs/2026-11-14-ws-branch-model-design.md
Epic: gin-workflow-ws-branch-model

## Objective

`gin team claim` creates a member's track worktree in the track's repository, `gin team takeover` works for a child track, review ledgers of child tracks are written to and validated from the parent, `gin team complete <epic>` closes a multi-member epic once its pull requests have merged, and the skills and guides describe the team-mode branch model.

**Goal** (spec): In team mode, a track pull request in a workspace child targets that child's default branch; `gin team claim` creates the member's track worktree in the right repository; `gin team takeover` fetches from the child; review ledgers of child tracks live in the parent; and `gin team complete <epic>` closes a multi-member epic once every pull request has merged.

**Architecture**:
- `workflow_core/team_beads.py`: `claim` gains worktree creation from the bead's `Plan:` and `Repo:` lines (new helpers `track_of(issue)` and `default_branch(repo)`); `takeover` fetches and checks out in the child; `handoff` and `takeover` sync the parent branch that holds the ledger; `_ledger_ref` reads the ledger from its new place.
- `workflow_core/workspace.py`: new `ledger_root(start)`, the directory that holds `.planning/reviews/` for a review run at `start`.
- `scripts/review-ledger.py` and `scripts/review_ledger/cli.py`: run every command from `ledger_root(cwd)`; `init` records `history_path` (the child checkout) next to `repository_path` (the worktree); `validate --in-history` falls back to `history_path`.
- New `workflow_core/team_complete.py` and a `complete` subcommand in `team_cli.py`.
- Skill and docs text: the `team` skill names a new `skills/team/references/workspace.md`; orchestrate, plan, review, and ship get one sentence each; guides and references follow.

**Tech Stack**: Python 3 standard library; unittest/pytest; fixtures `tests/workflow_core/team_fixtures.py` (`make_team_repo`, `fake_cli`, `gh_pr`, `path_with`, `init_beads`, `run_cli`), `tests/workflow_core/test_workspace.py` (`git`, `init_repo`), local bare remotes as in `tests/workflow_core/test_workspace_cli.py`; `gin docs check`.

**Global Constraints** (spec "Errors and compatibility", verbatim):
- Solo mode and single-repository team projects keep their flow; the only change for a single-repository team is that `team claim` also creates the track worktree.
- `team claim` without a `Plan:` line behaves as today.
- `review-ledger.py` outside a workspace keeps the current directory as the ledger root; existing ledgers stay readable.
- `gin team complete` never closes the epic when a check fails or the host is unavailable.
- The JSON of existing commands only gains keys.

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
- Problem statement: in a workspace, team-mode tracks have no defined base, members cannot create their own track worktrees, takeover fails for child branches, review ledgers land in service repositories, and nothing closes a multi-member epic.
- Success criteria: spec R1 to R9 and US-1 to US-4, as tests (code) or checked text (skills, docs); existing tests pass; budgets hold.
- Constraints: Global Constraints above; the `team` skill is 5,995 of 6,000 characters, so its new rules go into `skills/team/references/workspace.md`; stage chains (plan 11,647, orchestrate 7,331, execute 11,805, ship 11,312, review 11,785 of 12,000); `team.py`, `team_beads.py`, and `specs_trace.py` contain no host names (use `team_host`); tests use local bare remotes and `fake_cli` host fakes.
- Non-goals: several URLs in `record shipped` and `team deps` for children (`gin-workflow-ws-ship-records`); read-only siblings (`gin-workflow-ws-track-env`); quick in team mode (`gin-workflow-quick-team`); solo mode.

## Approach Options
### Option 1: extend claim, takeover, handoff, and review-ledger; add `team complete` (confirmed)
- Summary: as the Architecture above.
- Pros: members keep the commands they know; one new command.
- Cons: `review-ledger.py` gains workspace awareness.

### Option 2: one workspace flow command
- Summary: a single command that claims, creates worktrees, and syncs ledgers.
- Pros: one entry point.
- Cons: duplicates claim and takeover and mixes lead and member work; rejected in `/discuss`.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-14).
- Rationale: smallest change that meets R1 to R9 and keeps solo and single-repository flows as they are.

## Scope
- In scope: R1 to R9.
- Out of scope: see Non-goals.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 and 2 both change team_beads.py (takeover, handoff), Tracks 1 to 3 all edit docs/reference/cli.md, and Track 4's text describes the commands of Tracks 1 to 3. One lane.
```

## Tasks

`S` is `plugins/gin-workflow/src/scripts/workflow_core`.

### Track 1: Worktree on claim and takeover in a child
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:194-221` (`claim`), `:378-420` (`takeover`); new `track_of`, `default_branch`, `track_worktree`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:251-255,268-271` (claim and takeover text output)
  - Modify `docs/reference/cli.md` (the `gin team` section: `claim`, `takeover`)
  - Test `tests/workflow_core/test_team_beads.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `medium`
- **Why:** crosses Beads leases, git worktrees, the workspace manifest, and bead description parsing; bounded logic with a clear spec.
- **Interfaces**:
  - `team_beads.track_of(issue: Mapping[str, Any]) -> tuple[str, int, str | None] | None`: from the bead description, `(topic, number, repo)` where `topic` is `team_pending.topic_of(<plan path>)` and `number` comes from `team_pending._TRACK_LINE` (`^Plan: <path>, Track <N>`), and `repo` from a `^Repo:\s*`?([^`\s]+)`?\s*$` line (None without one); None when the description has no `Plan: ..., Track <N>` line.
  - `team_beads.default_branch(repo: Path, entry: workspace.Repo | None) -> str`: `entry.default_branch` for a child; else the branch `git -C <repo> symbolic-ref --short refs/remotes/origin/HEAD` names without `origin/`, else `main`.
  - `team_beads.track_worktree(root: Path, issue: Mapping[str, Any], bead: str) -> dict[str, Any] | None`: None when `track_of` is None. Otherwise `repo_dir` is the child checkout `space.checkout(entry)` for a `Repo:` that `workspace.locate(root).workspace` lists, else `root`; target `worktrees._target(repo_dir, bead, root)`; when the target exists returns `{"worktree": str(target), "branch": <its branch>, "created": False}`; else runs `git -C <repo_dir> fetch origin <default>` and `worktrees.create(repo_dir, bead, f"feat/{topic}-t{number}", f"origin/{default}", root)` and returns `{"worktree", "branch", "created": True}`. Git failures raise `SyncConflict` with the git message.
  - `claim(root, team, member, bead)`:
    - before writing the lease: when `track_of` names a `Repo:` that is in `workspace.repos` but not present (`space.present(entry)` False), raise `SyncConflict(f"{repo} is not cloned; run gin workspace clone {repo}")`; a `Repo:` not in `workspace.repos` raises `SyncConflict(f"Repo: {repo} is not in workspace.repos")`;
    - after the lease: `track_worktree(...)`; its `SyncConflict` is re-raised as `SyncConflict(f"{error}; the claim is kept; run gin team claim {bead} again")`;
    - the result gains `worktree` and `branch` when a worktree exists or was created.
  - `takeover(root, team, member, bead, branch=None)`: when `track_of(issue)` names a `Repo:` in the workspace, fetch (`git -C <child> fetch origin <branch>`), check out (`worktrees.checkout(child, bead, branch, root)`), and fetch the review ref in the child; a child not cloned raises `SyncConflict(... gin workspace clone <path>)`; the "run from the main checkout" refusal applies only to beads without a workspace `Repo:`; without a `Repo:`, everything stays as today.
  - CLI text: `claimed <bead>` / `renewed <bead>` followed by ` at <worktree> on <branch>` when the result has a worktree.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_beads.py` (a parent from `make_team_repo` with `init_beads`, a `workspace:` block passed through `extra=`, and a child `services/order-api` cloned from a local bare remote whose `main` has one commit):
     - claim of a bead whose description has `Plan: .planning/plans/2026-11-14-x.md, Track 2` and `Repo: services/order-api` creates `.planning/worktrees/<bead>` as a worktree of the child on `feat/x-t2` whose first parent is `origin/main` of the child; the result and the text name the worktree;
     - claiming again renews the lease and keeps the worktree (`created: False`);
     - with the child not cloned, exit 1, the message names `gin workspace clone services/order-api`, and the bead has no assignee;
     - a fetch failure (child `origin` pointed at a missing path) keeps the lease and says to run the claim again;
     - a bead without a `Plan:` line: lease only, no worktree (today's result keys unchanged);
     - a single-repository team (no `workspace:`) with a `Plan:` line: the worktree is created in the parent from `origin/<default>`;
     - takeover of a child bead after a handoff that pushed `feat/x-t2` to the child's remote checks it out at `.planning/worktrees/<bead>` in the child.
  2. Run `python3 -m pytest tests/workflow_core/test_team_beads.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "team or workspace or worktree"` → pass; `gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(team): claim creates the track worktree and takeover works in a workspace child (gin-workflow-ws-branch-model)`.
- **Acceptance criteria**: R1 (branch and base), R3, R4 (child fetch); US-1; US-2.
- **Estimated complexity**: medium

### Track 2: Review ledgers of child tracks in the parent
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/workspace.py` (new `ledger_root`)
  - Modify `plugins/gin-workflow/src/scripts/review-ledger.py` (start-up: absolute `--repo-path`, then run from `ledger_root`; `validate_ledger` ~48-70: `history_path` fallback)
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/cli.py:325-345` (`init` records `history_path`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:292-305` (`_ledger_ref`), `handoff` and `takeover` (parent branch sync)
  - Modify `docs/concepts/state-model.md` (ledger location in a workspace)
  - Test `tests/review_ledger/test_cli.py`, `tests/workflow_core/test_team_beads.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** changes where every ledger command reads and writes and how approved sources are found in history; a wrong path breaks review evidence across repositories.
- **Interfaces**:
  - `workspace.ledger_root(start: Path) -> Path`:
    - `top` is `git -C <start> rev-parse --show-toplevel` (on failure return `start`);
    - when `top.parent.name == "worktrees"` and `top.parent.parent.name == ".planning"`, and the main checkout of `top` (`main_checkout(top)`) is a `workspace.repos` entry of the workspace that `locate(top)` finds, return `top.parent.parent.parent`;
    - elif `locate(start).repo` is not None (start is inside a child checkout), return `locate(start).root`;
    - else return `start` unchanged.
  - `review-ledger.py` start-up: resolve `--repo-path` (when given) to an absolute path against the original cwd, compute `root = workspace.ledger_root(Path.cwd())`, then `os.chdir(root)` before dispatching; every existing relative path (`.planning/reviews/<bead>`, `repository_path`) then resolves against `root`. When `root` differs from the original cwd and `--repo-path` was not given, `init` and `checkpoint` use the original cwd's toplevel as the repository.
  - `review_ledger.cli` `init`: the repository entry keeps `repository_path` (the worktree, relative to the ledger root) and gains `history_path`: the child checkout `main_checkout(<repo>)` relative to the ledger root, only when it differs from `repository_path`.
  - `validate_ledger`: when `repository_path` is not a git repository root and `history_path` is, use `history_path` for the history checks (`ensure_review_commit`, `find_reviewed_commit`, `approved_successor`).
  - `team_beads._ledger_ref(worktree, bead)`: reads `<workspace.ledger_root(worktree)>/.planning/reviews/<bead>/review.json`; `handoff` checks the same path for the "no review ledger" message.
  - `handoff`: after the track branch and review ref, when `ledger_root(path) != path` and the ledger root's current branch has commits that are not on its upstream (`git rev-list --count @{u}..HEAD` > 0), or has no upstream and its name starts with `feat/`, run `git -C <ledger root> push -u origin <branch>`; a failure raises `SyncConflict`.
  - `takeover`: for a child bead, before checking out, when the root's current branch has an upstream run `git -C <root> pull --rebase`; a failure raises `SyncConflict`.
- **Steps**:
  1. Failing tests:
     - `tests/review_ledger/test_cli.py`: a parent workspace with a child cloned from a bare remote and a child worktree at `<parent>/.planning/worktrees/b-1`; `init` run with cwd in the worktree writes `<parent>/.planning/reviews/b-1/review.json` with `repository_path: .planning/worktrees/b-1` and `history_path: services/order-api`, and the worktree has no `.planning/reviews`; `checkpoint` creates `refs/gin/review/b-1` in the child; after `approve` and removing the worktree, `validate --in-history --bead-id b-1` run from the parent exits 0; outside a workspace, `init` writes under the cwd as before and `history_path` is absent.
     - `tests/workflow_core/test_team_beads.py`: `handoff` of a child bead pushes the parent's `feat/x` when it has an unpushed ledger commit; `takeover` pulls it first.
  2. Run `python3 -m pytest tests/review_ledger/test_cli.py tests/workflow_core/test_team_beads.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/review_ledger -q -n auto` and `python3 -m pytest tests/workflow_core -q -n auto -k "team or workspace"` → pass; `gin docs check docs/concepts/state-model.md` → ok.
  5. Commit: `feat(review): ledgers of workspace child tracks live in the parent and validate from it (gin-workflow-ws-branch-model)`.
- **Acceptance criteria**: R4 (parent branch sync), R5, R6; US-3.
- **Estimated complexity**: high

### Track 3: `gin team complete`
- **Dependencies**: Track 2
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/team_complete.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py` (parser: `complete <epic>`; dispatch)
  - Modify `docs/reference/cli.md` (the `gin team` section: `complete`)
  - Test `tests/workflow_core/test_team_complete.py` (new)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** one new command with a clear spec, but several checks across Beads, the workspace, git, and the host, each with its own failure.
- **Interfaces**:
  - `team_complete.complete(root: Path, team: TeamConfig, member: Member, epic: str) -> dict[str, Any]`:
    - the member must hold the lead role of some area (`any(area.lead in member.roles for area in team.areas.values())`), else `TeamError("only an area lead completes an epic")`;
    - children: `bd list --parent <epic> --all --limit 0 --json` (through `team_pending._beads` or `tasks.query_result`); each child not labelled `prep` and not `closed` is a missing item `<id> is <status>`;
    - per track child with `team_beads.track_of(issue)`: the repository directory as in `team_beads.track_worktree` (child checkout or `root`; a child not cloned is a missing item naming `gin workspace clone <path>`); `team_host.pr_for_branch(team.host, f"feat/{topic}-t{n}", repo_dir)`; None or a state other than `merged` is a missing item `<branch>: <state or no pull request>`; a merged one adds its URL;
    - in a workspace (`workspace.locate(root).workspace` not None): when `git ls-remote --heads origin feat/<topic>` in `root` lists the branch (topic from the first track), its pull request must be `merged` too;
    - no missing item: `bd close <epic> --reason "shipped: <urls joined with ', '>"` as the member; returns `{"status": "completed", "epic", "pull_requests": [urls], "missing": []}`;
    - otherwise returns `{"status": "incomplete", "epic", "pull_requests": [...], "missing": [...]}` and closes nothing;
    - `HostCliMissing` and `HostUnavailable` propagate (exit 2 in `team_cli.main`).
  - CLI: `gin team complete <epic> [--format json]`; text: `completed <epic>` and one `merged <url>` line each, then `next: gin team sync` when `team.beads_sync` is set; or `incomplete <epic>` and one `missing <item>` line each; exit 0 completed, 1 incomplete, 2 team mode off, not a lead, host failure.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_complete.py` (`make_team_repo`, `init_beads`, an epic with two track beads carrying `Plan:` lines, `fake_cli` `gh` answering `pr list --head feat/x-t1` and `feat/x-t2`):
     - both tracks closed and both pull requests merged: exit 0, the epic is closed, its close reason lists both URLs;
     - one pull request open: exit 1, `missing feat/x-t2: open`, the epic stays open;
     - one track bead open: exit 1 naming it;
     - a member without a lead role: exit 2;
     - team mode off: exit 2;
     - the `gh` fake exiting with an auth error: exit 2, the epic stays open;
     - a workspace parent whose `origin` has `feat/x` with an open pull request: exit 1 naming it.
  2. Run `python3 -m pytest tests/workflow_core/test_team_complete.py -q` → fail.
  3. Implement per the interfaces.
  4. Run step 2 → pass; `python3 -m pytest tests/workflow_core -q -n auto -k "team"` → pass; `gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(team): gin team complete closes an epic once every pull request has merged (gin-workflow-ws-branch-model)`.
- **Acceptance criteria**: R8; US-4.
- **Estimated complexity**: medium

### Track 4: Skills and guides for the team branch model
- **Dependencies**: Track 3
- **Files**:
  - Create `plugins/gin-workflow/src/skills/team/references/workspace.md`
  - Modify `plugins/gin-workflow/src/skills/team/SKILL.md` (one pointer to the reference; stay at or below 6,000 characters)
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md:24` (step 6, team mode), `plugins/gin-workflow/src/skills/plan/SKILL.md:21` (team mode base), `plugins/gin-workflow/src/skills/review/SKILL.md` (ledger in a workspace), `plugins/gin-workflow/src/skills/ship/SKILL.md` (team mode in a workspace: the parent pull request, then `gin team complete`)
  - Modify `docs/guides/git-flow.md` and `.vi.md`, `docs/guides/team.md` and `.vi.md`, `docs/guides/workspace.md` and `.vi.md`, `docs/starters/brownfield.md` and `.vi.md`
  - Test `tests/workflow_core/test_skill_routing.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** skill and guide text with every rule fixed by spec R1, R2, R7, and R9; several files and budget limits, no logic.
- **Interfaces** (facts the text must carry; wording may be tighter):
  - `skills/team/references/workspace.md` (team mode with a workspace): track branches `feat/<topic>-t<N>` start from `origin/<default_branch>` of the track's repository and their pull requests target that branch, approved by the `ship` roles; orchestrate creates no child branch and pushes the parent's `feat/<topic>` from the parent's default branch; `gin team claim <bead>` creates the member's track worktree, run from a parent checkout (or worktree) on `feat/<topic>`; ledgers of child tracks are written to the parent's `.planning/reviews/` on `feat/<topic>`: each ledger session starts with `git pull --rebase` and ends with a commit of `.planning/reviews/<bead>/` and a push; `handoff` pushes that branch and `takeover` pulls it; ship opens the parent's `feat/<topic>` pull request; after the last pull request merges, an area lead runs `gin team complete <epic>`.
  - `team/SKILL.md`: one sentence: "In a workspace, follow [references/workspace.md](references/workspace.md) for branches, worktrees, ledgers, and closing the epic." (at most 6,000 characters in total).
  - orchestrate step 6: in team mode, tracks start from the default branch after the spec and plan pull requests merge; worktrees come from `gin team claim` (the `team` skill).
  - plan: in team mode, the plan is committed on `plan/<topic>` and tracks start from the default branch after it merges.
  - review: in a workspace, the ledger of a child track lives in the parent's `.planning/reviews/` (`review-ledger.py` finds it from the track worktree).
  - ship: in team mode with a workspace, open the parent's `feat/<topic>` pull request; the epic closes with `gin team complete <epic>` once every pull request has merged.
  - `git-flow.md`: a base column (spec, plan, roadmap: the default branch; a track: the default branch of the track's repository; the parent's `feat/<topic>` in a workspace: the parent's default branch); `team.md`: claim creates the worktree, `team complete`; `workspace.md`: ledgers in the parent, claim from a parent checkout on `feat/<topic>`; `brownfield.md`: the same steps in the walkthrough. `.vi.md` pages follow the Vietnamese guide (`~/.claude/plugins/marketplaces/vietnamese-language-skill/skills/vietnamese-tech-writing/SKILL.md`) and keep English anchors.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_skill_routing.py`: the team skill names `references/workspace.md`; the reference has `gin team claim <bead>`, `gin team complete <epic>`, `git pull --rebase`, and `origin/<default_branch>`; orchestrate, plan, review, and ship have their sentences (`gin team complete <epic>` in ship; `.planning/reviews/` with "parent" in review).
  2. Run `python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_walkthrough_docs.py tests/workflow_core/test_docs_coverage.py -q` → fail.
  3. Edit the skills and docs.
  4. Run step 2 → pass; `gin docs check` on every changed page → ok; print the plan, orchestrate, review, and ship chain sizes and `wc -c plugins/gin-workflow/src/skills/team/SKILL.md`.
  5. Commit: `docs(team): branch model, claim worktrees, parent ledgers, and team complete for workspaces (gin-workflow-ws-branch-model)`.
- **Acceptance criteria**: R1, R2, R7, R9.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/ws-branch-model`; track branches `feat/ws-branch-model-t1` to `-t4` stacked in order.
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass (`python3 -m pytest -n auto`, run by the pre-push hook)
- [ ] `gin docs check` on changed pages
- [ ] Budgets hold (`tests/workflow_core/test_token_budget.py`)

## Notes
- A member works on an epic from a parent checkout or a worktree of it on the parent's `feat/<topic>`: `team claim` puts the track worktree under that checkout, and `review-ledger.py` writes the ledger there. Solo flows already work this way (an epic worktree).
- `takeover` keeps its "run from the main checkout" refusal for beads without a workspace `Repo:`, because it creates a worktree of the repository it runs in.
- Deliverable merge-holds apply only to the Parent Bead; track beads close after tests and review pass.
- The user may override `Model:` and `Effort:` before plan approval.
