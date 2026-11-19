# Plan: Team mode delivers a member's tracks as one lane, one branch, one pull request

Workflow: team-lanes
Spec: `.planning/specs/2026-11-19-team-lanes-design.md`

## Objective

In team mode a member claims a lane (their tracks of one plan in one repository), runs every track of it on one branch `feat/<topic>-<lane>` in one worktree, and opens one pull request. Agents review each track; a person reviews the lane's pull request. `gin goal` runs a member's lane unattended. Epics orchestrated before this change finish on their `feat/<topic>-t<N>` branches.

## Global Constraints

Copied from the spec:

- The lane replaces per-track delivery in team mode. There is no configuration key that selects one or the other.
- One epic, one spec, and one plan stay. No child epics per area.
- Each track is reviewed by the agent reviewer `gin reviewer` picks. The rule that another member reviews each track on its pull request is removed. A person reviews once, on the lane's pull request, under `team.approvals.ship`.
- Lanes do not wait for each other's code. The plan fixes each interface two lanes exchange, and each lane builds against it. The joined behaviour is checked by a QA track that runs after the lanes have merged.
- This epic keeps the plan as detailed as today.
- A track bead without a `Lane:` line is its own lane `t<N>`: branch `feat/<topic>-t<N>`, worktree `.planning/worktrees/<bead>`, as before.
- Out of scope: the plan in two levels (epic `gin-workflow-g9az`), parallel tracks inside one lane, opening a pull request without the member's confirmation, the spec and plan gates, gin-console.

Added by this plan (test-enforced, see `tests/workflow_core/test_token_budget.py`):

- `skills/team/SKILL.md` stays at or under 6,000 characters; each stage chain (`python3 -m workflow_core.budget --report`) stays at or under 12,000. Before this change: team 5,982, plan 11,933, execute 11,983, ship 11,974. The wording in Track 6 was measured: team 5,884, plan 11,936, orchestrate 8,425, execute 11,816, ship 11,997. Use it as written; a longer sentence breaks the budget.
- Stage skills other than `team` contain no `` `bd `` token (`tests/test_no_direct_bd.py`) and exactly one line with `project.team` (`test_token_budget.py`).

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
- Problem statement: `gin team claim` gives each track its own branch from `origin/<default>`, so a member's dependent track waits for the previous track's pull request to merge; each track is reviewed by another member and approved by the lead.
- Success criteria: US-1 to US-5 of the spec pass as tests; the pull requests after the plan pull request number one per lane; the full suite passes, also with `bd` off `PATH`.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: Lane as a line on the track bead (confirmed at discuss)
- Summary: a track's `Lane:` names its lane; branch, worktree, claim, handoff, pending, complete, and goal work on the lane. A bead without the line is the implicit lane `t<N>`.
- Pros: one code path; no new bead type; in-flight epics need no migration.
- Cons: a member's tracks run one after another.

### Option 2: Child epic per area
- Summary: a parent epic holds the contract; each area gets an epic with its own spec, plan, and gates.
- Pros: clear ownership.
- Cons: more specs, plans, and gates; gates are not recursive today; rejected at discuss.

### Recommended Approach
- Selected option: Option 1.
- Rationale: confirmed by the user; it removes the per-track pull request without adding artifacts.

## Scope
- In scope: R1 to R16 of the spec.
- Out of scope: Global Constraints' out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 2 to 5 build on the lane helpers of Track 2 and share team_beads.py, team_pending.py and their test files; Track 6 rewrites skill text within a character budget measured over all of it; Tracks 7 and 8 document the result. They run one after another on feat/team-lanes.
```

## Tasks

All paths are relative to the repository root. `S` stands for `plugins/gin-workflow/src/scripts/workflow_core`, `K` for `plugins/gin-workflow/src/skills`. Test helpers come from `tests/workflow_core/team_fixtures.py` (`make_team_repo`, `init_beads`, `git`, `fake_cli`, `path_with`, `gh_pr`, `run_cli`, `PLAN`) and the local helpers of each test file (`bd`, `create`, `show`, `claim_meta` in `test_team_beads.py`). Tests that call `bd` live in classes with `@unittest.skipUnless(HAS_BD, "bd is not installed")`; new classes carry the same guard.

### Track 1: Lane in the plan and the plan check (R1, R2)
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py` (`Track`, `_META`, `plan_tracks`, `check_plan`, new `valid_lane`)
  - Modify `tests/workflow_core/team_fixtures.py` (`PLAN`)
  - Test `tests/workflow_core/test_team_gates.py` (`TestPlanChecks`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one parser field and four findings in one module, with the messages fixed by the spec.
- **Interfaces produced**:
  - `team.Track.lane: str = ""` (last field).
  - `team.valid_lane(name: str) -> bool`.
- **Steps**:
  1. In `tests/workflow_core/team_fixtures.py`, add `- Lane: api` after `- Owner: em@corp.com` and `- Lane: web` after `- Owner: chi@corp.com` in `PLAN`.
  2. Write failing tests in `TestPlanChecks` (`tests/workflow_core/test_team_gates.py`), building plans with `PLAN.replace(...)` and `write(self.root, PLAN_PATH, plan)` as the class does:
     - `plan_tracks` returns `["api", "web"]` for `[t.lane for t in tracks]`; a `- **Lane**: `api`` line (bold label, backticked value) parses the same.
     - `check_plan` returns `[]` for `PLAN`.
     - Without the `- Lane: api` line: `"Track 1: missing Lane:"`.
     - `- Lane: API`, `- Lane: t3`, and `- Lane: -x` each give `"Track 1: invalid lane <name>"`.
     - Both tracks in `Lane: api`: `"lane api: tracks 1 and 2 have different owners"`. With the same owner on both and one `- Repo: services/a`: `"lane api: tracks 1 and 2 are in different repositories"`.
     - With `team.beads_sync` set (the class's existing way to load such a team) and both tracks in one lane, one with `Owner:` and one without: the `different owners` finding.
  3. Run `timeout 300 python3 -m pytest tests/workflow_core/test_team_gates.py -q`: the new tests fail.
  4. In `S/team.py`:
     - `Track`: add `lane: str = ""` after `reads`.
     - `_META = re.compile(r"^-\s*(?:\*\*)?(Area|Owner|Repo|Lane)(?:\*\*)?:\s*`?([^`\s]+)`?\s*$")`.
     - After `_FENCE`:
       ```python
       _LANE = re.compile(r"[a-z0-9][a-z0-9-]*")
       _IMPLICIT_LANE = re.compile(r"t\d+")


       def valid_lane(name: str) -> bool:
           """A lane name: lowercase letters, digits and `-`, never `t<digits>` (the lane of a bead without `Lane:`)."""
           return bool(_LANE.fullmatch(name)) and not _IMPLICIT_LANE.fullmatch(name)
       ```
     - `plan_tracks`: add `"lane": ""` to the `current` dict and pass `current["lane"]` as the last argument of `Track(...)` in `close()`.
     - `check_plan`, after the per-track loop and before the `listed` loop:
       ```python
       lanes: dict[str, list[Track]] = {}
       for track in tracks:
           if not track.lane:
               errors.append(f"Track {track.number}: missing Lane:")
           elif not valid_lane(track.lane):
               errors.append(f"Track {track.number}: invalid lane {track.lane}")
           else:
               lanes.setdefault(track.lane, []).append(track)
       for name, members in lanes.items():
           first = members[0]
           for other in members[1:]:
               if other.owner.lower() != first.owner.lower():
                   errors.append(f"lane {name}: tracks {first.number} and {other.number} have different owners")
               if (other.repo or ".") != (first.repo or "."):
                   errors.append(f"lane {name}: tracks {first.number} and {other.number} are in different repositories")
       ```
  5. Run `timeout 600 python3 -m pytest tests/workflow_core/test_team_gates.py tests/workflow_core/test_team_pending.py tests/workflow_core/test_team_init.py -q`. Other tests that build a plan without `Lane:` and expect `check_plan` or the `plan_approved` gate to pass now fail with `missing Lane:`; add a `Lane:` line to those plans (search the tests for `Owner:`). Passes.
  6. Commit: `feat(team): plan tracks carry a lane; check-plan checks it (<bead>)`.
- **Acceptance criteria**: R1 and R2; the four findings print exactly as in the spec; existing team tests pass.
- **Estimated complexity**: low

### Track 2: Lane of a bead, lane claim, lane branch and worktree (R3, R6, R7)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_pending.py` (new `_LANE_LINE`, `track_lane`, `lane_branch`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py` (`_track_place`, `track_worktree`, `claim`; new `lane_of`, `lane_beads`, `_lane_targets`, `_lane_key`, `_restart_delivered`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py` (`claim` text)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_complete.py:45` (the `_track_place` call, kept working until Track 4 replaces it)
  - Test `tests/workflow_core/test_team_beads.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** leases over several beads, git worktree and branch state, a host lookup, and backward compatibility for beads without a lane, all in the module every other team command builds on.
- **Interfaces produced**:
  - `team_pending.track_lane(description: str) -> tuple[str, int, str, bool] | None`: `(plan path, track number, lane, named)`; `named` is False for the implicit `t<N>`.
  - `team_pending.lane_branch(description: str) -> str | None`: `feat/<topic>-<lane>`.
  - `team_beads.lane_of(issue) -> str | None`.
  - `team_beads.lane_beads(root, issue) -> list[dict]`: the track beads of the issue's lane, any status.
  - `team_beads._lane_targets(root, issue) -> list[dict]`: `issue` first, then the other open tracks of its lane by track number.
  - `team_beads._lane_key(issue, bead: str) -> str`: the worktree id, `<epic>-<lane>` or `<bead>`.
  - `team_beads._track_place(root, track, lane: str)` (third parameter added).
  - `team_beads.track_worktree(root, team, issue, bead, *, delivered: bool = False) -> dict | None` (parameters `team` and `delivered` added; the result may carry `note`).
  - `team_beads.claim(...)` result adds `lane` (str or None), `beads` (list of ids), and `note` when there is one.
- **Steps**:
  1. Write failing tests in a new class `TestTeamLaneClaim` in `tests/workflow_core/test_team_beads.py`. `setUp` follows `test_single_repository_team_creates_the_worktree_in_the_parent` (a bare `origin`, `make_team_repo`, a pushed base commit, `init_beads`), then creates an epic and tracks with a helper:
     ```python
     PLAN = ".planning/plans/2026-11-19-shop.md"

     def track(self, number: int, lane: str | None = "be", area: str = "backend") -> str:
         text = f"Plan: {self.PLAN}, Track {number}" + (f"\nLane: {lane}" if lane else "")
         return json.loads(bd(self.root, "create", f"Track {number}", "--parent", self.epic, "-l", f"area:{area}",
                              "--description", text, "--json"))["id"]
     ```
     The epic: `json.loads(bd(self.root, "create", "Shop", "-t", "epic", "--json"))["id"]`. Every test that claims while a track of the lane is closed puts a fake `gh` on `PATH` (`fake_cli(bin, "gh", rules)`, `env=path_with(bin)`), so the real `gh` is never called. Tests:
     - Lane claim: tracks 1, 2, 3 in `be` and track 4 in `fe`. `team claim <t1> --format json` gives `lane == "be"`, `beads == [t1, t2, t3]`, `branch == "feat/shop-be"`, `worktree` ending in `.planning/worktrees/<epic>-be`, `created` true. `show(t1)` is `in_progress`; `show(t2)` and `show(t3)` are `open`, assigned to `binh@corp.com`, with `claim_of(...)["expires_at"]` equal to t1's; `show(t4)` has no assignee.
     - Next track: after the claim, commit a file in the worktree, `bd close <t1>`, then `team claim <t2>` (fake `gh` answering `[]` to `["pr", "list"]`): `created` false, the same `worktree`, `git log` there shows the commit, `show(t2)` is `in_progress`, `beads == [t2, t3]`.
     - Refusal: t3 claimed by `em@corp.com` (`bd update <t3> --claim` with `actor="em@corp.com"`, `claim_meta(..., "2999-01-01T00:00:00Z")`). `team claim <t1>` exits 1 with `lane be is claimed by em@corp.com until 2999-01-01T00:00:00Z (<t3>)` in stdout, and `show(t1)` has no assignee and no `claim` metadata.
     - Expired lease: the same with `"2000-01-01T00:00:00Z"`: exit 0, `show(t3)` assigned to `binh@corp.com`, its notes contain `took over expired claim from em@corp.com`.
     - Eligibility: a lane with one track labelled with an area `binh@corp.com` may not own (see `TEAM` in the fixtures): exit 1 with `may not own tracks in <area>`, nothing claimed.
     - Implicit lane: two tracks created with `lane=None`. Claiming the first gives `lane == "t1"`, `beads == [<first>]`, `branch == "feat/shop-t1"`, `worktree` ending in `.planning/worktrees/<first>`; the second has no assignee. A foreign unexpired lease on the first refuses with the existing message `already claimed by em@corp.com until`.
     - Restart after a merged pull request: claim t1, commit, `git push -u origin feat/shop-be`, close t1, push a new commit to `origin/main` from the main checkout. Fake `gh`: `["pr", "list", "--head", "feat/shop-be"]` returns `[{"url": URL, "state": "MERGED", "mergeCommit": {"oid": "m" * 40}}]` and `["pr", "view", URL]` returns `gh_pr(URL, state="MERGED", head=<worktree HEAD>)`. `team claim <t2>` exits 0, the worktree's `HEAD` equals `origin/main`, and `note` contains `restarted from origin/main`.
     - Commits after the merged head: the same, with one more commit in the worktree after the head given to `gh_pr`: the branch `HEAD` is unchanged and `note` contains `has commits after its merged pull request`.
     - Host unreachable: the fake `gh` exits 1 for `["pr", "list"]`: the claim still exits 0 and `note` starts with `cannot ask the host`.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_team_beads.py -q`: the new tests fail.
  3. In `S/team_pending.py`, after `_TRACK_LINE`:
     ```python
     _LANE_LINE = re.compile(r"^Lane:\s*`?([a-z0-9][a-z0-9-]*)`?\s*$", re.MULTILINE)


     def track_lane(description: str) -> tuple[str, int, str, bool] | None:
         """(plan path, track number, lane, named) of a track bead description. The lane is its `Lane:` line, else
         the implicit `t<N>` with `named` False (a bead orchestrated before lanes). None without a
         `Plan: <path>, Track <N>` line."""
         track = _TRACK_LINE.search(description)
         if track is None:
             return None
         lane = _LANE_LINE.search(description)
         return track[1], int(track[2]), lane[1] if lane else f"t{track[2]}", lane is not None


     def lane_branch(description: str) -> str | None:
         """`feat/<topic>-<lane>` of a track bead description; None for a bead that is no track."""
         found = track_lane(description)
         return None if found is None else f"feat/{topic_of(found[0])}-{found[2]}"
     ```
     Move `topic_of` above them if it is defined later in the file.
  4. In `S/team_beads.py`:
     - Import: `from .team_pending import _TRACK_LINE, topic_of, track_lane`.
     - After `track_of`:
       ```python
       def _lane(issue: Mapping[str, Any]) -> tuple[str, int, str, bool] | None:
           return track_lane(str(issue.get("description") or ""))


       def lane_of(issue: Mapping[str, Any]) -> str | None:
           """The lane of a track bead: its `Lane:` line, else the implicit `t<N>`; None for a bead that is no track."""
           found = _lane(issue)
           return found[2] if found else None


       def lane_beads(root: Path, issue: Mapping[str, Any]) -> list[dict[str, Any]]:
           """The track beads of `issue`'s lane, any status: the children of its epic with the same plan path and
           lane. Just `issue` for a bead that is no track or has no parent."""
           own, epic = _lane(issue), issue.get("parent")
           if own is None or not epic:
               return [dict(issue)]
           rows = [row for row in _bd_json(root, ["list", "--parent", str(epic), "--all", "--limit", "0"])
                   if (found := _lane(row)) is not None and (found[0], found[2]) == (own[0], own[2])]
           return rows if any(row["id"] == issue["id"] for row in rows) else [dict(issue), *rows]


       def _lane_targets(root: Path, issue: Mapping[str, Any]) -> list[dict[str, Any]]:
           """`issue`, then the other open tracks of its lane in track order: what a lane command writes to."""
           others = [row for row in lane_beads(root, issue) if row["id"] != issue["id"] and row.get("status") != "closed"]
           return [dict(issue), *sorted(others, key=lambda row: (_lane(row) or ("", 0))[1])]


       def _lane_key(issue: Mapping[str, Any], bead: str) -> str:
           """The worktree id of the bead's lane: `<epic>-<lane>` for a named lane, else the bead id."""
           found, epic = _lane(issue), issue.get("parent")
           return f"{epic}-{found[2]}" if found and found[3] and epic else bead
       ```
     - `_track_place(root, track, lane)`: add the parameter, build `branch = f"feat/{topic}-{lane}"`, and say `feat/<topic>-<lane>` in the docstring.
     - `track_worktree(root, team, issue, bead, *, delivered=False)`:
       ```python
       track, lane = track_of(issue), lane_of(issue)
       if track is None or lane is None:
           return None
       repo_dir, entry, branch = _track_place(root, track, lane)
       key = _lane_key(issue, bead)
       try:
           target = worktrees._target(repo_dir, key, root)
           if target.exists():
               if not _worktree_of(target, repo_dir):
                   raise SyncConflict(f"{target} is not a worktree of {repo_dir}; remove it")
               note = _restart_delivered(team, repo_dir, entry, target, branch) if delivered else None
               made = {"worktree": str(target), "branch": worktrees._git(target, "rev-parse", "--abbrev-ref", "HEAD"),
                       "created": False}
               return {**made, "note": note} if note else made
           # the three existing branches (local, origin, new from origin/<default>) with `key` in place of `bead`
       ```
       Keep the existing `except (RuntimeError, ValueError)` wrapper around the whole block and the final `return {"worktree": str(target), "branch": branch, "created": True}`.
     - New, above `track_worktree`:
       ```python
       def _restart_delivered(team: TeamConfig, repo_dir: Path, entry: workspace.Repo | None, target: Path,
                              branch: str) -> str | None:
           """Start `branch` again from `origin/<default>` in the worktree `target` when its newest pull request has
           merged and the branch still sits on that pull request's head. Returns what happened, a warning when the
           branch has commits made after the merged head, or None when there is nothing to do. A host that cannot be
           reached leaves the branch as it is."""
           from . import team_host

           try:
               found = team_host.pr_for_branch(team.host, branch, repo_dir)
               if found is None or found.state != "merged":
                   return None
               merged_head = team_host.fetch_pr(found.url, team.host, repo_dir).head_sha
           except team_host.HostUnavailable as error:
               return f"cannot ask the host whether {branch} has merged: {error}"
           default = default_branch(repo_dir, entry)
           worktrees._git(repo_dir, "fetch", "origin", default)
           if worktrees._git(target, "rev-parse", "HEAD") == merged_head:
               if worktrees._git(target, "status", "--porcelain"):
                   raise SyncConflict(f"{target} has uncommitted changes; commit or remove them, then claim again")
               worktrees._git(target, "checkout", "-B", branch, f"origin/{default}")
               return (f"{branch} restarted from origin/{default} after {found.url} merged; if the host kept the "
                       f"merged branch, delete it on origin before the next push")
           try:
               worktrees._git(target, "merge-base", "--is-ancestor", merged_head, "HEAD")
           except RuntimeError:  # restarted earlier, or the merged head is not in this clone
               return None
           if worktrees._git(target, "rev-list", "--count", f"{merged_head}..HEAD", f"^origin/{default}") != "0":
               return f"{branch} has commits after its merged pull request {found.url}; merge origin/{default} into it"
           return None
       ```
     - `claim`: replace the body between `issue = _show(root, bead)` and `_push(root, team, bead)` with
       ```python
       own = _lane(issue)
       targets = _lane_targets(root, issue)
       now = utc_now()
       for target in targets:
           labels = target.get("labels") or []
           ineligible = [] if RELEASED in labels else [area.name for area in _areas_of(team, target)
                                                       if not team.eligible(member, area)]
           if ineligible:
               raise SyncConflict(f"{member.email} may not own tracks in {', '.join(ineligible)}")
           holder = (target.get("assignee") or "").lower()
           if holder and holder != member.email and not claim_expired(target, now):
               until = claim_of(target)["expires_at"]
               raise SyncConflict(f"lane {own[2]} is claimed by {holder} until {until} ({target['id']})"
                                  if own and own[3] else f"{bead} is already claimed by {holder} until {until}")
       track = track_of(issue)
       if track is not None:
           _track_place(root, track, own[2])  # an unusable child or branch name refuses before the lease
       named_holder = (issue.get("assignee") or "").lower()
       expires_at = _expires(team)
       lease = json.dumps({"holder": member.email, "expires_at": expires_at})
       for target in targets:
           holder = (target.get("assignee") or "").lower()
           if target["id"] == bead and not holder:
               argv = ["update", bead, "--claim"]
           else:
               argv = ["update", target["id"], "--assignee", member.email]
               if target["id"] == bead:
                   argv += ["--status", "in_progress"]
               if holder and holder != member.email:
                   argv += ["--append-notes", f"took over expired claim from {holder}"]
           argv += ["--set-metadata", f"claim={lease}"]
           if RELEASED in (target.get("labels") or []):
               argv += ["--remove-label", RELEASED]
           completed = _bd(root, argv, actor=member.email)
           if completed.returncode != 0:
               raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
       ```
       then `_push(root, team, bead)` as today, and
       ```python
       delivered = any(row.get("status") == "closed" for row in lane_beads(root, issue))
       try:
           made = track_worktree(root, team, issue, bead, delivered=delivered)
       except SyncConflict as error:
           raise SyncConflict(f"{error}; the claim is kept; run gin team claim {bead} again") from error
       return {"status": "renewed" if named_holder == member.email else "claimed", "bead": bead,
               "lane": own[2] if own else None, "beads": [target["id"] for target in targets],
               "assignee": member.email, "expires_at": expires_at, "advisory": not team.beads_remote, **(made or {})}
       ```
       Only the named bead becomes `in_progress`; the other tracks keep their status so `gin team ready` still lists the next one.
  5. In `S/team_cli.py`, `claim` branch: append `+ (f"\nnote: {result['note']}" if result.get("note") else "")` to the text.
  6. In `S/team_complete.py:45`, pass the lane: `team_beads._track_place(root, track, team_beads.lane_of(child))`.
  7. Fix callers and existing tests: `takeover` and `handoff` call `track_worktree` or `_track_place` only through `claim`; a test that calls `team_beads.track_worktree` or `_track_place` directly gets the new arguments. Run `timeout 900 python3 -m pytest tests/workflow_core/test_team_beads.py tests/workflow_core/test_team_complete.py tests/workflow_core/test_team_pending.py -q`: passes.
  8. Commit: `feat(team): claim takes the whole lane on one branch and worktree (<bead>)`.
- **Acceptance criteria**: R3 (lane of a bead), R6, R7; the claim criteria of US-1 and US-4; every earlier claim test passes unchanged.
- **Estimated complexity**: high

### Track 3: Handoff, takeover, reassign, and ready over a lane (R8, R9)
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py` (`_track_worktree`, `handoff`, `takeover`, `reassign`, `ready`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py` (`ready` text; `handoff` and `reassign` text)
  - Test `tests/workflow_core/test_team_beads.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** bounded to one module with the helpers of Track 2, but each command has several refusal paths and a review-ledger step that must run per bead.
- **Interfaces consumed**: `_lane_targets`, `_lane_key`, `lane_of`, `lane_branch` (Track 2).
- **Interfaces produced**: `handoff`, `takeover`, and `reassign` results add `lane` and `beads`; `ready` rows add `lane` and `branch`.
- **Steps**:
  1. Write failing tests in a new class `TestTeamLaneHandoff` in `tests/workflow_core/test_team_beads.py`, set up like `TestTeamHandoff` (bare `origin.git`) with the epic and `track` helper of `TestTeamLaneClaim` (move both into a small mixin both classes use). Lane `be` has tracks 1 (closed after a first claim and commit), 2, and 3; the member claimed track 2. Every command runs with a fake `gh` answering `[]` to `["pr", "list"]`.
     - `team handoff <t2> em@corp.com --format json`: `beads == [t2, t3]`, `lane == "be"`, `branch == "feat/shop-be"`; `show(t2)` and `show(t3)` are assigned to `em@corp.com` with `handoff_of(...)["branch"] == "feat/shop-be"`; `show(t1)` keeps `binh@corp.com`; `git ls-remote --heads origin feat/shop-be` is not empty.
     - `team handoff <t2> --release`: t2 and t3 have no assignee, status `open`, the label `released`, and no `claim` metadata.
     - Takeover: after the handoff, in a second clone configured as `em@corp.com` (the way the existing takeover test builds one), `team takeover <t2>` creates `.planning/worktrees/<epic>-be` on `feat/shop-be`, and t2 and t3 carry `em@corp.com`'s lease.
     - A handoff by a member who neither holds the lane nor leads its area exits 1 with the existing `only ... may reassign` message and changes nothing.
     - `team reassign <t2> em@corp.com`: t2 and t3 are assigned to `em@corp.com`.
     - `team ready --format json` for the holder: the rows of lane tracks carry `"lane": "be"` and `"branch": "feat/shop-be"`; a bead without a `Plan:` line carries `"lane": None`. Text output has the line `feat/shop-be (binh@corp.com)` followed by the indented rows of that lane.
     - Expired open track: t3 is `open`, assigned to `em@corp.com`, with a lease of `2000-01-01T00:00:00Z`, and `binh@corp.com` may own its area: `team ready --format json` lists t3 with `"expired_claim": "em@corp.com"`.
  2. Run `timeout 600 python3 -m pytest tests/workflow_core/test_team_beads.py -q`: the new tests fail.
  3. In `S/team_beads.py`:
     - `_track_worktree(root, key, bead, worktree)`: `worktrees._target(root, key)`; the message keeps `bead`.
     - `handoff`: read `issue = _show(root, bead)` (after the optional `sync`) before resolving the path, then `path = _track_worktree(root, _lane_key(issue, bead), bead, worktree)` and the dirty check. `targets = _lane_targets(root, issue)`. Keep the authority check on `issue` as it is (`_reassign_target` for `email`, the closed and holder checks for `--release`); for each other target check only that the new owner is eligible: `team.eligible(target_member, area)` for `_areas_of(team, row)`, raising the existing `may not own tracks in` message. Push the branch once. Then, for each target: the review-ref block (`_ledger_ref`, `push_review_ref`, the two stderr notes), the `handoff=` metadata write, and `_write_reassign(root, team, member, row["id"], holder_of_row, target_member)` or the release update. `_push_ledger_branch(path)` and `_push(root, team, bead)` run once. The result adds `"lane": lane_of(issue)` and `"beads": [row["id"] for row in targets]`.
     - `takeover`: `key = _lane_key(issue, bead)`; `worktrees.checkout(repo_dir, key, branch, root)`; run the review-ref fetch for each of `_lane_targets(root, issue)`; the cleanup hint names `key`. `claim` already takes the lane.
     - `reassign`: after `_reassign_target` on `issue`, call `_write_reassign` for each of `_lane_targets(root, issue)` (skip a row already assigned to the target) and add `lane` and `beads` to the result.
     - `ready`: add to both row dicts `"lane": lane_of(issue)` and `"branch": lane_branch(str(issue.get("description") or ""))` (import `lane_branch` from `.team_pending`). In the first loop, a ready row that does not match the member, has an assignee other than the member, an expired claim (`claim_expired(issue, utc_now())`), and an area the member owns (the condition the expired loop uses) goes to `expired_group` with `expired_claim`.
  4. In `S/team_cli.py`:
     - `ready` text: rows without `branch` print as today. The others print under one header per branch, in order of first appearance: `f"{branch} ({holder or 'unclaimed'})"` with `holder` the `assignee` of the branch's first row, then each row indented by two spaces in today's format.
     - `handoff` and `reassign` text: append `f" (lane {result['lane']}: {', '.join(result['beads'])})"` when `len(result["beads"]) > 1`.
  5. Run the command of step 2 and `timeout 600 python3 -m pytest tests/workflow_core -q -k "team"`: passes.
  6. Commit: `feat(team): handoff, takeover, reassign and ready work on the lane (<bead>)`.
- **Acceptance criteria**: R8, R9; US-5; existing handoff, takeover, reassign, and ready tests pass.
- **Estimated complexity**: medium

### Track 4: Pending and complete by lane (R14, R15)
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_pending.py` (`candidates`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_complete.py` (`complete`)
  - Test `tests/workflow_core/test_team_pending.py`, `tests/workflow_core/test_team_complete.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** two small functions change what they look up; the proof for `complete` already exists in `team_beads._delivers`.
- **Interfaces consumed**: `team_pending.track_lane`, `team_pending.lane_branch` (Track 2); `team_beads._delivers`, `team_beads._track_repo`, `team_host.merged_with_text` (existing).
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_team_pending.py` (class `PendingCase` helpers `self.bd`, `self.gh`, `self.pending`):
     - Two open track beads of epic `e-1` with `Plan: {PLAN_PATH}, Track 2\nLane: web` and `Track 3\nLane: web`, and `self.gh(("feat/login-web", gh_pr(PR_TRACK, state="OPEN", ...)))`: `self.pending()` has exactly one row with `"branch": "feat/login-web"` and `"gate": None`.
     - The existing `TRACK` (no `Lane:`) still gives `feat/login-t2`.
  2. Failing tests in `tests/workflow_core/test_team_complete.py`. Rewrite the rules of the existing tests from `["pr", "list", "--head", "feat/login-t<N>"]` to the merged search, which `merged_with_text` runs as `gh pr list --state merged --search ...`:
     ```python
     {"argv": ["pr", "list", "--state", "merged"], "stdout": [
         {"url": "https://github.com/org/app/pull/1", "mergeCommit": {"oid": "m" * 40},
          "body": "Plan: .planning/plans/2026-11-14-login.md\nTracks: 1, 2\n"}]}
     ```
     - One merged pull request listing `Tracks: 1, 2`: `completed <epic>`, `merged https://github.com/org/app/pull/1` once, the epic closed.
     - Two merged pull requests listing one track each: both urls in the output and the close reason.
     - A merged pull request listing only track 1: exit 1, `incomplete <epic>`, and `missing <t2> (.planning/plans/2026-11-14-login.md#2): no merged pull request lists it`.
     - A merged pull request naming another plan with `Tracks: 1, 2`: both tracks missing.
     - The workspace tests keep their `["pr", "list", "--head", "feat/<topic>"]` rule for the parent's pull request.
  3. Run `timeout 600 python3 -m pytest tests/workflow_core/test_team_pending.py tests/workflow_core/test_team_complete.py -q`: the new and rewritten tests fail.
  4. `S/team_pending.py`, `candidates`: replace the `_TRACK_LINE` match with `found = track_lane(bead.get("description") or "")`; `topic = topic_of(found[0])`; `tracks[lane_branch(bead.get("description") or "")] = epic` for a live bead. Update the docstring: `feat/<topic>-<lane>` per lane with an open track bead.
  5. `S/team_complete.py`, `complete`: replace the per-branch lookup with
     ```python
     found = team_pending.track_lane(str(child.get("description") or ""))
     if found is not None:
         plan, number = found[0], found[1]
         topics.add(team_pending.topic_of(plan))
         try:
             repo_dir, _entry = team_beads._track_repo(root, team_beads.track_of(child)[2])
         except team_beads.SyncConflict as conflict:
             missing.append(f"{child['id']}: {conflict}")
             continue
         key = (plan, str(repo_dir))
         if key not in merged:
             merged[key] = team_host.merged_with_text(team.host, plan, repo_dir)
         pr = next((pr for pr in merged[key] if team_beads._delivers(pr.body, plan, number)), None)
         if pr is None:
             missing.append(f"{child['id']} ({plan}#{number}): no merged pull request lists it")
         elif pr.url not in pull_requests:
             pull_requests.append(pr.url)
     ```
     with `merged: dict[tuple[str, str], list[team_host.PrInfo]] = {}` before the loop. The parent `feat/<topic>` block is unchanged. Update the module and function docstrings.
  6. Run the command of step 3: passes.
  7. Commit: `feat(team): pending lists lane branches; complete reads the Tracks line of merged pull requests (<bead>)`.
- **Acceptance criteria**: R14, R15; the `pending` and `complete` criteria of US-2 and US-4.
- **Estimated complexity**: medium

### Track 5: Goal over the member's lanes (R10)
- **Dependencies**: Track 2
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/goal.py`
  - Test `tests/workflow_core/test_goal.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one pure function gains three keyword arguments and `main` reads the team; the output sentences are fixed by the spec.
- **Interfaces consumed**: `team_pending.track_lane` (Track 2); `team.load_team(config)`, `team.current_member(root, team)` (existing).
- **Interfaces produced**: `goal_text(epic, tracks, workflow_id, review_ledger, *, member: str | None = None, lane: str | None = None, waiting: frozenset[str] = frozenset())`; `gin goal --lane <name>`.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_goal.py`. Extend the local `track(...)` helper with `assignee=""` and `description=""` keys. Pure tests on `goal_text` with `member="a@corp.com"`:
     - Tracks e.1 and e.2 assigned to `a@corp.com`, e.3 to `b@corp.com`: the goal names `e.1, e.2` only, contains `` `git status -sb` `` and `not ahead of `origin``, and does not contain `implementation_complete`.
     - `lane="be"`: tracks whose description has `Plan: p.md, Track N\nLane: be` and that are assigned to the member or unassigned are covered; a track of lane `fe` assigned to the member is not.
     - `waiting={"x.1"}` and e.2 blocked by `x.1` (a `blocks` dependency), e.3 blocked by e.2: the goal names e.1 and ends with ` Do not start e.2, e.3: they wait for another lane to merge.`
     - A `human-gate` track and a waiting track together: both sentences, the human one first.
     - Nothing assigned to the member: `No goal: a@corp.com has no open track in epic epic.`; with `lane="be"`: `No goal: a@corp.com has no open track in lane be of epic epic.`
     - A bead titled `external: p.md#2` among `tracks` is never named.
     - Without `member`, every existing expectation holds (the existing tests stay as they are).
     `TestGoalCommand`: a config with a `team:` block (copy `TEAM` from the fixtures, `git config user.email` of a member) makes `main` pass the member; `--lane be` reaches `goal_text`; a git email that is no member prints `error: git user.email is not in team.members` and exits 1; `--lane` without team mode prints `error: --lane needs team mode` and exits 1.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_goal.py -q`: the new tests fail.
  3. In `S/goal.py`:
     - `import re`, `from .team_pending import track_lane`, `_EXTERNAL = re.compile(r"^external: ")`.
     - `goal_text`: drop tracks whose title matches `_EXTERNAL` first. Keep `found`, `blockers`, and `open_tracks` as they are. Replace the `held` loop with
       ```python
       held: set[str] = set()   # needs a human, or depends on such a track
       late: set[str] = set()   # waits for another lane to merge, or depends on such a track
       for bead, track in open_tracks.items():
           deps = {dep.get("depends_on_id") for dep in track.get("dependencies") or []
                   if dep.get("type", "blocks") == "blocks"}
           if HUMAN_GATE in (track.get("labels") or []) or blockers[bead] & held:
               held.add(bead)
           elif deps & waiting or blockers[bead] & late:
               late.add(bead)

       def mine(track: dict[str, Any]) -> bool:
           found_lane = track_lane(str(track.get("description") or ""))
           in_lane = lane is None or (found_lane is not None and found_lane[2] == lane)
           assignee = (track.get("assignee") or "").lower()
           return in_lane and (assignee == member or (lane is not None and not assignee))

       covered = open_tracks if member is None else {bead: t for bead, t in open_tracks.items() if mine(t)}
       runnable = [bead for bead in covered if bead not in held and bead not in late]
       ```
     - Messages, in this order: no open track (unchanged); `member` set and `covered` empty: `No goal: {member} has no open track in epic {epic}.`, or `... in lane {lane} of epic {epic}.` with a lane; nothing runnable and nothing in `late`: the existing `waits on a human` sentence over the gates in `covered`; nothing runnable otherwise: `No goal: every open track of epic {epic} assigned to {member} waits on a human or on another lane to merge: {ids}.`
     - Goal text: `f"/goal tracks {', '.join(runnable)} of epic {epic} are closed in Beads (`gin task show`)"`, then without `member` the existing `implementation_complete` clause, with `member` ``", and in each lane's worktree `git status -sb` shows the branch is not ahead of `origin`"``; then the ledger clause and the full stop as today; then ` Do not start {ids}: they need a human.` for the covered tracks in `held` and ` Do not start {ids}: they wait for another lane to merge.` for those in `late`.
     - `main`: `parser.add_argument("--lane")`. After `config` is read, with `checkout = main_checkout(args.repository)`:
       ```python
       from . import team as team_core

       member, waiting = None, frozenset()
       team = team_core.load_team(config)
       if team is None and args.lane:
           print("error: --lane needs team mode", file=sys.stderr)
           return 1
       if team is not None:
           who = team_core.current_member(checkout, team)
           if who is None:
               print("error: git user.email is not in team.members", file=sys.stderr)
               return 1
           member = who.email
           rows = query(args.repository, ["list", "--status", "open", "--limit", "0"])
           waiting = frozenset(row["id"] for row in rows or [] if _EXTERNAL.match(row.get("title", "")))
       print(goal_text(epic, tracks, args.workflow_id, project_settings(config).review_ledger,
                       member=member, lane=args.lane, waiting=waiting))
       ```
       This replaces the existing `print(goal_text(...))`; the `config = ...` line above it stays.
  4. Run the command of step 2: passes.
  5. Commit: `feat(goal): in team mode the goal covers the member's lanes and waits for merged lanes (<bead>)`.
- **Acceptance criteria**: R10; the goal criteria of US-1; output outside team mode is unchanged.
- **Estimated complexity**: medium

### Track 6: Skills, references, and the pull request template (R3, R4, R5, R11, R12, R13, R16 skills)
- **Dependencies**: Track 1, Track 2, Track 3, Track 4, Track 5
- **Files**:
  - Create `plugins/gin-workflow/src/skills/team/references/lanes.md`
  - Modify `plugins/gin-workflow/src/skills/team/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/team/references/workspace.md`
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md`
  - Modify `plugins/gin-workflow/src/references/stage-contract.md`
  - Modify `plugins/gin-workflow/src/templates/team/pull_request_template.md`
  - Test `tests/workflow_core/test_skill_routing.py`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** the wording is given below and was measured against the character budgets; the work is exact replacement plus the tests that pin skill text.
- **Steps**:
  1. Update the pinned strings in `tests/workflow_core/test_skill_routing.py` first:
     - `test_tracks_push_only_in_team_mode`: `"In team mode a track pushes its branch (its PR)"` becomes `"In team mode a track pushes its lane branch and returns"`.
     - `test_team_review_opens_the_pr_before_review`: rename to `test_team_review_needs_no_pull_request` and assert on the `## review` section: `"by the agent `gin reviewer` picks: no PR and no other member"` is in it and `"open its PR"` is not.
     - `test_team_and_roadmap_handle_host_approvals`: the needles for the `## review` section become `"`gin reviewer`"`, `"`review-response`"`, `"`project.review_ledger: true`"`, `"reviews the lane's PR at ship"`.
     - `test_progress_team_and_orchestrate_name_the_ledger_setting`: replace `line_with(team, "track owner", "another member")` with `line_with(team, "`start-review`", "`gin reviewer`", "refuses the owner")`.
     - `test_team_branch_model_is_in_the_skills`: add `self.assertIn("references/lanes.md", read("skills/team/SKILL.md"))` and, for `skills/team/references/lanes.md`, the needles `"feat/<topic>-<lane>"`, `"## Contracts"`, `"external: <plan path>#<N>"`, `"gin team claim <bead>"`, `"Tracks:"`.
     Run `timeout 300 python3 -m pytest tests/workflow_core/test_skill_routing.py -q`: these tests fail.
  2. Create `K/team/references/lanes.md`:
     ````markdown
     # Lanes

     Read this in team mode. A lane is the tracks of one plan that one member does in one repository. It has one branch `feat/<topic>-<lane>` (`<topic>` is the plan file name without its date), one worktree `.planning/worktrees/<epic>-<lane>`, and one pull request. A track bead without a `Lane:` line was orchestrated before lanes: it is its own lane `t<N>` and keeps `feat/<topic>-t<N>` and `.planning/worktrees/<bead>`.

     ## Plan

     - Every track's Metadata has `- **Lane**: <name>`: lowercase letters, digits, and `-`, never `t<digits>`. The area name is the usual choice. The tracks of a lane share `Owner:` and `Repo:`; a lane may span areas its owner may own.
     - Add `## Contracts` before `## Tasks`, with one entry per interface that a track of one lane produces and a track of another lane consumes. An HTTP endpoint lists method, path, request, response, and error codes; anything else lists its exact names and types. The consuming track names the entry in its Interfaces and does not depend on the producing track.
     - A track depends on a track of another lane only when it needs that lane's merged code, such as an end-to-end QA track.
     - A contract entry changed after approval goes through a new plan PR.

     ## Orchestrate

     - Each track bead gets the label `lane:<lane>` and the line `Lane: <lane>` in its description, after the `Plan:` line.
     - A dependency inside a lane is `gin task dep add <blocked> <blocker>`. For a dependency on a track of another lane, create a bead titled `external: <plan path>#<N>` and make it block the dependent track, with and without `team.beads_sync`. `gin team deps` closes it when a merged PR lists that track.

     ## Execute

     - `gin team claim <bead>` claims every open track of the bead's lane and creates or reuses the lane's worktree. It refuses when another member holds an unexpired lease on any of them. Claim again at the start of each track: it renews the lease and marks that track in progress.
     - Run the lane's tracks in dependency order in that worktree. The reviewed diff of a track runs from the lane branch's head when the track started to the track's last commit. After the track closes, `git push -u origin feat/<topic>-<lane>` and go on to the next one.
     - `gin goal --workflow-id <id>` covers the tracks assigned to you; `--lane <name>` picks one lane. It leaves out tracks that need a human or wait for another lane to merge.
     - When the lane's PR has merged and tracks remain, the next `gin team claim` starts the branch again from the default branch. If the host kept the merged branch, delete it on origin before the next push. If the claim reports commits made after the merged PR, merge `origin/<default>` into the branch. Never force-push.

     ## Ship

     - Deliver the closed tracks of the lane that no merged PR lists yet; each needs its review approved or waived. Open tracks stay for a later PR of the same lane.
     - Fill the generated PR template: `Plan:` with the plan path, `Tracks:` with every delivered track number (`gin team deps` and `gin team complete` read both), `Beads:`, and one line per track under `## Tracks`.
     - A fix the PR reviewer asks for is committed on the lane branch and pushed. With `project.review_ledger: true`, first reopen the last approved track and have it reviewed again.
     - After the merge, when the lane has no open track, run `gin worktree cleanup <epic>-<lane>` from the main checkout.
     ````
  3. `K/team/SKILL.md`: make these replacements, each old text occurring once.
     - Old: `In a workspace, follow [references/workspace.md](references/workspace.md) for branches, worktrees, ledgers, and closing the epic.`
       New: `Tracks are delivered in lanes: read [references/lanes.md](references/lanes.md). In a workspace, also follow [references/workspace.md](references/workspace.md).`
     - Old: ``Each track's Metadata adds `Area: <area>` and `Owner: <member email>` ``
       New: ``Each track's Metadata adds `Area: <area>`, `Lane: <lane>`, and `Owner: <member email>` ``
     - `## orchestrate`, old first line and bullets:
       ```
       Track beads get `--labels track:<N>,area:<area>` and `--assignee <owner>` if the track has one.
       - `team.beads_sync` set: the lead orchestrates once for everyone; run `team sync` before and after.
       - Not set: each member creates beads only for the tracks they own, and a bead titled `external: <plan path>#<N>` for each dependency on another member's track, blocking the dependent bead.
       ```
       New:
       ```
       Track beads get `--labels track:<N>,area:<area>,lane:<lane>` and `--assignee <owner>` if the track has one. A dependency on a track of another lane is a bead titled `external: <plan path>#<N>` that blocks the dependent bead.
       - `team.beads_sync` set: the lead orchestrates once for everyone; run `team sync` before and after.
       - Not set: each member creates beads only for the tracks they own.
       ```
     - `## execute`: replace all seven bullets with
       ```
       - `team deps` first: it closes `external:` placeholders whose track a merged PR lists.
       - Pick from `team ready`; `team claim <bead>` claims its whole lane; exit 1 means someone else holds an unexpired lease or you may not own its areas, so pick another; `team ready` marks expired claims you may take over. Without `team.beads_sync` the claim is advisory.
       - Out of quota or away: the assignee or area lead runs `team handoff <bead> <email>` (or `--release` to the pool) from the main checkout; the new owner runs `team takeover <bead>` in theirs. Both move the lane. The plan's `Owner:` is not changed.
       - In the lane worktree, `team deps --bead <bead>` must exit 0 before each track; exit 1 names the merge commit to merge in.
       - After a track closes, push the lane branch and go on to the next track; open no PR. Commits follow `team.commit_convention`.
       - With `team.beads_sync`, run `team sync` after closing a bead.
       ```
     - `## review`: replace the whole paragraph with
       ```
       A track is reviewed as outside team mode, by the agent `gin reviewer` picks: no PR and no other member. With `project.review_ledger: true`, `init` takes `--actor-id` from `team whoami` and `start-review` the `actor_id` of `gin reviewer`, so the ledger refuses the owner. A member with a `team.approvals.ship` role reviews the lane's PR at ship; the owner answers there (`review-response`).
       ```
     - `## ship`: old ``When `team.approvals.ship` has a policy:`` becomes ``Ship delivers one lane in one PR and needs only the tracks it delivers closed, not `implementation_complete`. When `team.approvals.ship` has a policy:``; old `(a child PR: from its track worktree)` becomes `(a child PR: from its lane worktree)`; old last sentence `A member's ship reports only their own tracks; the lead declares the feature complete when every track PR has merged.` becomes ``A member's ship covers only their own lanes; an area lead runs `gin team complete <epic>` once a merged PR lists every track.``
  4. `K/team/references/workspace.md`:
     - Old: ``A track branch `feat/<topic>-t<N>` starts from `origin/<default_branch>` of the track's repository (the child its `Repo:` names, else the parent).``
       New: ``A lane branch `feat/<topic>-<lane>` starts from `origin/<default_branch>` of the lane's repository (the child its tracks' `Repo:` names, else the parent).``
     - Old: ``creates the member's track worktree at `.planning/worktrees/<bead>` of the checkout where it runs``
       New: ``creates the member's lane worktree at `.planning/worktrees/<epic>-<lane>` of the checkout where it runs``
     - Old: `Spec and plan reach the default branch through their own PRs first; tracks start after both merge.`
       New: `Spec and plan reach the default branch through their own PRs first; lanes start after both merge.`
  5. Stage skills and the stage contract, one replacement each:
     - `K/plan/SKILL.md`: old ``tracks add `Area:`/`Owner:` and the plan is committed on `plan/<topic>` and approved through a PR, and tracks start from the default branch after it merges`` becomes ``tracks add `Area:`/`Lane:`/`Owner:`, the plan is committed on `plan/<topic>` and approved through a PR, and lanes start from the default branch after it merges``.
     - `K/orchestrate/SKILL.md`: old ``A track with `Area:` gets `--labels area:<name>`; the epic keeps`` becomes ``A track with `Area:` gets `--labels area:<name>`; one with `Lane:` gets `--labels lane:<name>` and the line `Lane: <name>` in its description; the epic keeps``. Old `label, assign, and sync track beads` becomes `label, assign, link, and sync track beads`. Old ``and `gin team claim` creates each worktree`` becomes ``and `gin team claim` creates each lane's worktree``.
     - `K/execute/SKILL.md`, step 4.3: replace from `In team mode a track pushes its branch (its PR) and stops at handoff with two options:` through `Otherwise its branch is merged at ship and not pushed, so the suite runs once.` (four lines) with one sentence on the same line as the text before it: ``In team mode a track pushes its lane branch and returns; ship opens the lane's PR (the `team` skill). Otherwise its branch is merged at ship and not pushed, so the suite runs once.`` Lines 1 to 15 of the file must not move (`test_execute_excludes_prep_tasks` reads lines 14 and 15 by index).
     - `K/ship/SKILL.md`: old ``With `project.team.enabled`, merging follows the host rules,`` becomes ``With `project.team.enabled`, ship delivers one lane, merging follows the host rules,``.
     - `plugins/gin-workflow/src/references/stage-contract.md`: old `` `execute` pushes a track branch only in team mode.`` becomes `` `execute` pushes a lane branch only in team mode.``
  6. `plugins/gin-workflow/src/templates/team/pull_request_template.md`: after the `Beads:` line add
     ```markdown

     ## Tracks

     <!-- One line per delivered track: <N>. <title> (<bead>): commits <first>..<last>; reviewer <id>, <cycles> review cycle(s), <findings> finding(s); tests: <command> -->
     ```
     If a test in `tests/workflow_core/test_team_init.py` compares the generated template with fixed text, update that text.
  7. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.budget --report`: plan, orchestrate, execute, and ship are each at or under 12,000; `wc -m plugins/gin-workflow/src/skills/team/SKILL.md` is at or under 6,000. Expected: plan 11,936, orchestrate 8,425, execute 11,816, ship 11,997, team 5,884. If a number is over, a replacement was not made as written.
  8. Run `timeout 900 python3 -m pytest tests/workflow_core/test_skill_routing.py tests/workflow_core/test_token_budget.py tests/workflow_core/test_role_aware_skills.py tests/workflow_core/test_epic_comments.py tests/workflow_core/test_team_init.py tests/test_no_direct_bd.py tests/gin_orchestrator/test_harness_packaging.py -q`: passes.
  9. Commit: `feat(team): skills run and ship a lane instead of a pull request per track (<bead>)`.
- **Acceptance criteria**: R3 (orchestrate text), R4, R5, R11, R12, R13, and the skill files of R16; the budget and skill-text tests pass.
- **Estimated complexity**: medium

### Track 7: Reference and concept documentation (R16)
- **Dependencies**: Track 6
- **Files**:
  - Modify `docs/reference/cli.md` (`gin team` section around lines 205-212, `gin goal`)
  - Modify `docs/concepts/lifecycle.md` (around lines 14, 74, 77)
  - Modify `docs/concepts/state-model.md` (around line 57)
  - Modify `docs/reference/skills.md`, `docs/reference/skills.vi.md` (around line 204)
  - Modify `docs/changelog.md`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** reference text for commands whose behaviour changed, checked against the code of Tracks 1 to 5.
- **Steps**:
  1. Read `S/team_beads.py` (`lane_of`, `lane_beads`, `claim`, `track_worktree`, `_restart_delivered`, `handoff`, `takeover`, `reassign`, `ready`), `S/team_pending.py` (`candidates`), `S/team_complete.py`, `S/goal.py`, `S/team.py` (`check_plan`), and `K/team/references/lanes.md`.
  2. `docs/reference/cli.md`:
     - `team check-plan`: the four lane findings, verbatim.
     - `team ready`: the `lane` and `branch` keys, the grouped text output, and open tracks with an expired lease.
     - `team claim`: the lane claim, the refusal message, the `lane`, `beads`, and `note` keys, the worktree `.planning/worktrees/<epic>-<lane>` on `feat/<topic>-<lane>`, the implicit lane `t<N>`, and the restart after a merged pull request.
     - `team reassign`, `team handoff`, `team takeover`: they move every open track of the lane.
     - `team pending`: one `feat/<topic>-<lane>` branch per lane with an open track.
     - `team deps`: a placeholder closes when a merged pull request lists the track.
     - `team complete`: the `Tracks:` proof and the `no merged pull request lists it` line.
     - `gin goal`: `--lane`, the team-mode scope, the two `Do not start` sentences, and the two `No goal` sentences.
  3. `docs/concepts/lifecycle.md`: in team mode a member runs a lane on one branch and only team mode pushes it; reviews are by agents per track and by a person on the lane's pull request. `docs/concepts/state-model.md`: the worktree of a lane and the `Lane:` line and `lane:` label of a track bead. `docs/reference/skills.md` and `skills.vi.md`: members claim lanes.
  4. `docs/changelog.md`: an entry at the top in the file's format: lanes replace a pull request per track in team mode; `Lane:` in team plans; `gin goal --lane`; beads without `Lane:` keep their branches.
  5. Run `gin docs check docs/reference/cli.md docs/concepts/lifecycle.md docs/concepts/state-model.md docs/reference/skills.md docs/reference/skills.vi.md docs/changelog.md` and `timeout 300 python3 -m pytest tests/workflow_core/test_docs_coverage.py -q`: pass.
  6. Commit: `docs(team): lanes in the CLI reference and the lifecycle and state concepts (<bead>)`.
- **Acceptance criteria**: R16 for these pages; every statement matches the code; the docs check exits 0.
- **Estimated complexity**: low

### Track 8: Guides and their translations (R16)
- **Dependencies**: Track 6
- **Files**:
  - Modify `docs/guides/git-flow.md`, `docs/guides/git-flow.vi.md` (around lines 24, 57, 82, 111)
  - Modify `docs/guides/ai-strategy.md`, `docs/guides/ai-strategy.vi.md` (around lines 81-110, 137-142)
  - Modify `docs/guides/team.md`, `docs/guides/team.vi.md` (around lines 97-121)
  - Modify `docs/guides/workspace.md`, `docs/guides/workspace.vi.md` (around lines 99-111)
  - Modify `docs/starters/brownfield.md`, `docs/starters/brownfield.vi.md` (around lines 353-358, 429-440, 507)
  - Modify `docs/roles.md`, `docs/roles.vi.md` (around lines 23-24, 79)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** six guides and their Vietnamese translations state a branch and a pull request per track; the change is the same fact in each, written for readers.
- **Steps**:
  1. Read `K/team/references/lanes.md`, `K/team/SKILL.md`, and the pages of Track 7 for the facts. Find every statement to change with `grep -n -e '-t<N>' -e 'track branch' -e "track's PR" -e 'track pull request' -e 'per track' -e 'team claim' -e 'team complete' docs/guides docs/starters docs/roles.md docs/roles.vi.md`.
  2. In each English page, replace the per-track statements with the lane: a lane is a member's tracks of one plan in one repository; branch `feat/<topic>-<lane>`; one worktree; `gin team claim` claims the lane; agents review each track; one pull request per lane, approved by the `ship` roles; `gin team complete` once a merged pull request lists every track. In `git-flow.md` change the branch and approval tables (rows "Track of a plan" and "Track") to the lane. In `team.md` add how a member runs a lane with `gin goal` and what the lead reviews, and that contracts between lanes are fixed in the plan. In `ai-strategy.md` and `brownfield.md` update the command walk-throughs (`gin team claim`, push of the lane branch, one pull request). Keep one sentence in `team.md` on beads without `Lane:` keeping `feat/<topic>-t<N>`.
  3. Make the same changes in each `.vi.md` page, in Vietnamese, with commands, paths, and identifiers left verbatim.
  4. Run `gin docs check` on the twelve pages and `timeout 300 python3 -m pytest tests/workflow_core/test_docs_coverage.py -q`: pass. Then `grep -rn -e 'feat/<topic>-t<N>' docs` shows only the sentences about beads without a `Lane:` line and the earlier changelog entries.
  5. Commit: `docs(team): guides describe lanes, one pull request per member (<bead>)`.
- **Acceptance criteria**: R16 for these pages; each `.vi.md` page says what its source says; the docs check exits 0.
- **Estimated complexity**: medium

## Integration
- **Branch**: `feat/team-lanes`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (pre-push hook).
- [ ] The same suite passes with `bd` off `PATH` (the release runner has none).
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.budget --report` shows every stage at or under 12,000.
- [ ] `gin docs check` on the changed pages exits 0.
- [ ] Manual: in a scratch team repository with a bare origin, claim a two-track lane, close the first track, claim the second, and confirm one worktree, one branch, and both commits on it.

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- The Parent Bead is the epic `/orchestrate` creates for the workflow `team-lanes`; merge holds apply only to it. Track beads close when their tests and review pass. `<bead>` in commit messages is the track's bead id.
- After the epic bead exists, add the dependency of `gin-workflow-g9az` (plan in two levels) on it.
- This repository is not in team mode, so the tracks of this plan carry no `Area:`, `Lane:`, or `Owner:`.
- After ship, reinstall (`./install.sh --platform all`) so the installed skills match `src`.
