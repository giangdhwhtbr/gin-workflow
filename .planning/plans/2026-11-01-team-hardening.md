# Plan: Team hardening: no conflicting claims, no lost Beads, proven gates

Epic: gin-workflow-rm-team-hardening
Spec: .planning/specs/2026-11-01-team-hardening-design.md

## Objective
Several members in different roles work in parallel while gates, claims, reviews, and Beads stay consistent, and a rejected Beads push never discards a local write.

## Goal
Copied from the spec:
- `_push` never resets local Beads; a rejected push retries through `sync` once and then reports a conflict with the local write intact.
- `claim` applies the same `area:` eligibility rule as `reassign`, carries a lease with a TTL, and reports itself as advisory without a Beads remote.
- `team init` and `setup doctor` warn on a team gate with no role policy; `team.strict` turns that warning into a configuration error.
- A gate proven in team mode is written into the epic bead's metadata, so `state` on a teammate's machine reports it.
- `record shipped` in team mode verifies the merged PR against the `ship` policy; `team check --gate ship` keeps the local-head check.
- `check_plan` rejects a file listed by two tracks.
- In team mode the review ledger refuses a reviewer who is the track owner and enforces `max_cycles`.

## Architecture
`S` = `plugins/gin-workflow/src`, `W` = `S/scripts/workflow_core`, `L` = `S/scripts/review_ledger`.
- `W/team_beads.py` owns every Beads write in team mode: claims, reassignments, pushes, and (new) the `gates` metadata of the epic bead. `W/lifecycle_cli.py` calls it after a successful `record` and reads it in `state`.
- `W/team.py` owns the team config (`TeamConfig`, `validate_team`, `has_policy`), gate verification (`verify_gate`, `authorize_record`), and `check_plan`.
- `W/team_init.py` owns `doctor_report`; `W/team_cli.py` prints.
- `L/projections.py` replays the ledger; `L/cli.py` builds `start-review`; `S/scripts/review-ledger.py` is the argparse front.
- Bead metadata keys: `claim = {"holder", "expires_at"}` on track beads; `gates = {"<gate>": {"pr_url", "merge_commit", "approvers", "actor", "at"}}` on the epic bead. Both are written with `bd update <id> --set-metadata <key>=<json>` (the `ai_usage` pattern, `W/usage.py:324`).

## Tech Stack
Python 3 standard library only; `unittest` via `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`; real `bd` (and `dolt` for the sync class) in `tests/workflow_core/test_team_beads.py`, fake `gh`/`bd` CLIs from `tests/workflow_core/team_fixtures.py` elsewhere.

## Global Constraints
Copied from the spec:
- Identity beyond `git config user.email` is out of scope (documented as a known limit).
- Parsing Dolt exit codes is out of scope; the conflict detection in `sync` stays text based.
- No configurable Dolt branch: the only reader of `origin/main` is `reset_to_remote`, which this epic removes.
- No background job releases expired claims; expiry only lets another member claim.
- No `dolt reset` runs anywhere in gin-workflow.
- Solo mode (no `team:` block) never reads or writes `metadata.gates`.
- `team check` stays read only.
- Config schema version is unchanged: the new keys are optional.
- Ledgers created before this change have no `owner` and no `max_cycles`; both checks are skipped for them.
- Commit only on `feat/team-hardening` or a track branch, never on `master`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three tracks edit disjoint line ranges of W/team.py and four touch docs/reference/cli.md; sequential dispatch avoids merge conflicts, and the real-bd tests share one machine.
```

## Tasks

### Track 1: Team config keys and gate-policy doctor check
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py:54-60` (`strict`, `claim_ttl_hours` in `_TEAM.properties`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:13-15,37-45,72-107,120-135,394-396` (`POLICY_GATES`, `TeamConfig.strict`/`claim_ttl_hours`, `_has_policy`, strict rule in `validate_team`, `load_team`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_init.py:138-168` (`gate_policy_gap`, `gate_policy` check and fix)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:66-72` (warning after `team init`)
  - Modify `docs/reference/config.md:170` (`strict`, `claim_ttl_hours`)
  - Test `tests/workflow_core/test_schema_2_7.py`
  - Test `tests/workflow_core/test_team_init.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** two optional schema keys, one dataclass field pair, one doctor check; every message is fixed in the spec.
- **Acceptance criteria**: US-3. `setup doctor` reports `gate_policy: false` naming `ship` when `approvals.ship` is absent; `team init` prints the same warning and exits 0; `team.strict: true` with a missing policy fails `state` with `team.strict: team.approvals.ship has no role policy`; `claim_ttl_hours: 0` is rejected; `load_team` defaults are `strict=False`, `claim_ttl_hours=48`.
- **Estimated complexity**: low

Interfaces produced (Tracks 2 and 4 consume them):
- `team.POLICY_GATES = ("requirement_confirmed", "plan_approved", "ship")`
- `TeamConfig.strict: bool`, `TeamConfig.claim_ttl_hours: int`
- `team_init.gate_policy_gap(team: TeamConfig) -> list[str]`

Steps:

1. Tests. Append to `tests/workflow_core/test_schema_2_7.py` inside `TestSchema27`:

```python
    def test_strict_and_claim_ttl_hours(self):
        validate_portable_config({"schema_version": "2.7", "team": {**RAW, "strict": True, "claim_ttl_hours": 12}})
        with self.assertRaises(ConfigValidationError):
            validate_portable_config({"schema_version": "2.7", "team": {**RAW, "claim_ttl_hours": 0}})
        team = load_team({"team": RAW})
        self.assertEqual((False, 48), (team.strict, team.claim_ttl_hours))
        team = load_team({"team": {**RAW, "strict": True, "claim_ttl_hours": 12}})
        self.assertEqual((True, 12), (team.strict, team.claim_ttl_hours))

    def test_strict_requires_a_policy_for_every_gate(self):
        raw = {"members": {"a@b.c": {"roles": ["dev"], "login": "a"}}, "strict": True,
               "approvals": {"requirement_confirmed": ["dev"]}}
        self.assertEqual(["team.strict: team.approvals.plan_approved has no role policy",
                          "team.strict: team.approvals.ship has no role policy"], validate_team(raw))
        self.assertEqual([], validate_team({**raw, "strict": False}))
        self.assertEqual([], validate_team({**raw, "approvals": {"requirement_confirmed": ["dev"], "ship": ["dev"]},
                                            "areas": {"api": {"paths": ["api/**"], "lead": "dev"}}}))
```
   Add `validate_team` to the `from workflow_core.team import ...` line of that file if it is not imported yet. In `tests/workflow_core/test_team_init.py`, change the expected dict of `test_team_section_reports_each_fix_until_healthy` (line 148) to include `"gate_policy": True`, and append to `TestTeamInit`:

```python
    def test_gate_policy_check_names_missing_gates(self):
        team = TEAM.format(host="github").replace("    ship: [qe]\n", "")
        root = make_team_repo(self.base / "nopolicy", team=team, extra="artifacts:\n  spec_review: pr\n")
        fake_cli(self.bin, "gh", [{"argv": ["auth", "status"], "stdout": "ok"}])
        detail = self.doctor(root)["checks_details"]["team"]
        self.assertFalse(detail["checks"]["gate_policy"])
        self.assertIn("set team.approvals.<gate> to a role list or area_lead (gates without a policy: ship)",
                      detail["actions"])
        result = run_cli(root, "team", "init")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("warning: gates without a role policy: ship (set team.approvals.<gate>, or team.strict: "
                         "true to require one)", result.stdout.splitlines()[-1])
        strict = make_team_repo(self.base / "strict", team=team + "  strict: true\n")
        failed = run_cli(strict, "state")
        self.assertEqual(2, failed.returncode)
        self.assertIn("team.strict: team.approvals.ship has no role policy", failed.stderr)
```
   (`self.bin` and `self.doctor` exist on the doctor test class; put the new test in that class if it is not `TestTeamInit`.) Run: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_schema_2_7 tests.workflow_core.test_team_init` fails.

2. `W/schemas.py`: inside `_TEAM["properties"]`, after `"beads_sync": {...},` add:

```python
        "strict": {"type": "boolean"},
        "claim_ttl_hours": {"type": "integer", "minimum": 1},
```

3. `W/team.py`:
   - after `DEFAULT_APPROVALS` add `POLICY_GATES = ("requirement_confirmed", "plan_approved", "ship")`.
   - `TeamConfig`: add fields `strict: bool = False` and `claim_ttl_hours: int = 48` after `permissions`.
   - replace `has_policy` with:

```python
def _has_policy(policy: Any, areas: Mapping[str, Any]) -> bool:
    return policy == "area_lead" and bool(areas) or isinstance(policy, list) and bool(policy)


def has_policy(gate: str, team: TeamConfig) -> bool:
    return _has_policy(team.approvals.get(gate, []), team.areas)
```
   - `validate_team`, before `return errors`:

```python
    if raw.get("strict"):
        approvals = {**DEFAULT_APPROVALS, **dict(raw.get("approvals") or {})}
        errors += [f"team.strict: team.approvals.{gate} has no role policy" for gate in POLICY_GATES
                   if not _has_policy(approvals.get(gate, []), areas)]
```
   - `load_team`: add `strict=bool(raw.get("strict", False)), claim_ttl_hours=int(raw.get("claim_ttl_hours", 48)),` to the `TeamConfig(...)` call.

4. `W/team_init.py`: import `POLICY_GATES` from `.team` next to `TeamConfig`; add before `doctor_report`:

```python
def gate_policy_gap(team: TeamConfig) -> list[str]:
    from .team import has_policy

    return [gate for gate in POLICY_GATES if not has_policy(gate, team)]
```
   In `doctor_report`, after the `codeowners` entry of `checks` add `"gate_policy": not gate_policy_gap(team),` and in `fixes` add
   `"gate_policy": f"set team.approvals.<gate> to a role list or area_lead (gates without a policy: {', '.join(gate_policy_gap(team))})",`.

5. `W/team_cli.py` `init` branch: after the `skipped` lines, add

```python
            gap = team_init.gate_policy_gap(team)
            if gap:
                lines.append(f"warning: gates without a role policy: {', '.join(gap)} (set team.approvals.<gate>, "
                             "or team.strict: true to require one)")
```
   and include `"warnings": gap` in the JSON payload (`_emit({**result, "warnings": gap}, ...)`).

6. `docs/reference/config.md:170`: append two sentences: "`strict: true` makes a missing policy for `requirement_confirmed`, `plan_approved`, or `ship` a configuration error; unset, `setup doctor` and `team init` only warn. `claim_ttl_hours` (default 48) is the lease length `team claim` writes into the bead's `claim` metadata."

7. Run the two test modules (pass), then `tests.test_all`; commit `feat(team): strict gate policies and claim_ttl_hours config`.

### Track 2: Claims with eligibility and leases, push without reset
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:1-14,46-58,74-146` (imports, `ready`, delete `_dolt_dir`/`reset_to_remote`, `claim`, `_push`, `reassign`, lease helpers)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_cli.py:104-114` (`ready` and `claim` text output)
  - Modify `docs/reference/cli.md:182-184` (`ready`, `claim`, `reassign` rows)
  - Modify `docs/guides/team.md:48` (claim lease sentence)
  - Modify `plugins/gin-workflow/src/skills/gin-team/SKILL.md:28-29` (claim bullets)
  - Test `tests/workflow_core/test_team_beads.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded module with real-`bd` tests; the lease and takeover rules have several ordered cases, all enumerated in the spec.
- **Acceptance criteria**: US-1, US-2. A rejected push retries through `sync` once and never calls `dolt reset`; a `sync` failure raises `SyncConflict` naming the bead and `gin-workflow team sync`; `claim` refuses an ineligible area, writes `claim.holder`/`claim.expires_at`, renews for the holder, takes over an expired or metadata-less claim with the note, refuses an unexpired one naming `expires_at`, and reports `advisory: true` without a remote; `team ready` lists expired claims with `expired_claim`.
- **Estimated complexity**: medium

Interfaces produced:
- `team_beads.claim(...) -> {"status": "claimed" | "renewed", "bead", "assignee", "expires_at", "advisory": bool}`
- `team_beads.claim_of(issue: Mapping) -> dict` and `team_beads.claim_expired(issue: Mapping, now: str) -> bool`
- `team_beads.utc_now() -> str` (`%Y-%m-%dT%H:%M:%SZ`)

Steps:

1. Tests in `tests/workflow_core/test_team_beads.py`.
   - Add helper after `show`:

```python
def claim_meta(root: Path, bead: str, holder: str, expires_at: str) -> None:
    bd(root, "update", bead, "--set-metadata",
       f'claim={json.dumps({"holder": holder, "expires_at": expires_at})}')
```
   - In `TestTeamBeadsLocal.test_claim_and_already_claimed`, after `bd(self.root, "update", held, "--claim", actor="em@corp.com")` add `claim_meta(self.root, held, "em@corp.com", "2999-01-01T00:00:00Z")`, and change the assertion to `self.assertIn("already claimed by em@corp.com until 2999-01-01T00:00:00Z", refused.stdout)`. Also assert after the first claim:

```python
        meta = team_beads.claim_of(claimed)
        self.assertEqual("binh@corp.com", meta["holder"])
        self.assertGreater(meta["expires_at"], team_beads.utc_now())
        again = run_cli(self.root, "team", "claim", free, "--format", "json")
        self.assertEqual("renewed", json.loads(again.stdout)["status"])
        self.assertTrue(json.loads(again.stdout)["advisory"])
        self.assertIn("advisory: no Beads remote", run_cli(self.root, "team", "claim", free).stdout)
```
   - Add to `TestTeamBeadsLocal`:

```python
    def test_claim_refuses_an_area_the_member_may_not_own(self):
        frontend = create(self.root, "form", "area:frontend")
        refused = run_cli(self.root, "team", "claim", frontend)
        self.assertEqual(1, refused.returncode)
        self.assertIn("binh@corp.com may not own tracks in frontend", refused.stdout)

    def test_expired_claim_is_listed_and_taken_over(self):
        held = create(self.root, "held", "area:backend")
        bd(self.root, "update", held, "--claim", actor="em@corp.com")
        claim_meta(self.root, held, "em@corp.com", "2000-01-01T00:00:00Z")
        legacy = create(self.root, "legacy", "area:backend")
        bd(self.root, "update", legacy, "--claim", actor="em@corp.com")
        rows = json.loads(run_cli(self.root, "team", "ready", "--format", "json").stdout)["ready"]
        self.assertEqual({held: "em@corp.com", legacy: "em@corp.com"},
                         {row["id"]: row.get("expired_claim") for row in rows if row.get("expired_claim")})
        self.assertIn("(expired claim: em@corp.com)", run_cli(self.root, "team", "ready").stdout)
        result = run_cli(self.root, "team", "claim", held)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        taken = show(self.root, held)
        self.assertEqual(("binh@corp.com", "in_progress"), (taken["assignee"], taken["status"]))
        self.assertIn("took over expired claim from em@corp.com", taken.get("notes", ""))
        self.assertEqual("binh@corp.com", team_beads.claim_of(taken)["holder"])
```
   - Replace `TestPushWithoutReset` with:

```python
class TestPushWithoutReset(unittest.TestCase):
    """A rejected push retries through sync once; local Beads are never reset."""

    def test_req_016_rejected_push_raises_and_never_resets(self):
        rejected = subprocess.CompletedProcess([], 1, "", "rejected")
        with mock.patch.object(team_beads, "_bd", return_value=rejected):
            with self.assertRaisesRegex(team_beads.SyncConflict, "rejected"):
                team_beads.push(Path("."), TeamConfig(beads_remote="x"))
        self.assertFalse(hasattr(team_beads, "reset_to_remote"))

    def test_req_016_push_without_remote_calls_nothing(self):
        with mock.patch.object(team_beads, "_bd") as run:
            team_beads.push(Path("."), TeamConfig())
            team_beads._push(Path("."), TeamConfig(), "t-1")
        run.assert_not_called()

    def test_rejected_push_syncs_once_and_succeeds(self):
        rejected = subprocess.CompletedProcess([], 1, "", "rejected")
        with mock.patch.object(team_beads, "_bd", return_value=rejected) as run, \
                mock.patch.object(team_beads, "sync", return_value={"status": "synced"}) as synced:
            team_beads._push(Path("."), TeamConfig(beads_remote="x"), "t-1")
        synced.assert_called_once()
        self.assertEqual([["dolt", "push"]], [call.args[1] for call in run.call_args_list])

    def test_rejected_push_then_conflict_keeps_local_beads(self):
        rejected = subprocess.CompletedProcess([], 1, "", "rejected")
        with mock.patch.object(team_beads, "_bd", return_value=rejected), \
                mock.patch.object(team_beads, "sync", side_effect=team_beads.SyncConflict("bd dolt pull: conflict")):
            with self.assertRaisesRegex(team_beads.SyncConflict,
                                        "push rejected for t-1; local Beads kept, run gin-workflow team sync"):
                team_beads._push(Path("."), TeamConfig(beads_remote="x"), "t-1")
```
   - In `TestTeamBeadsSync`, replace `test_lost_race_resets_local_beads_to_the_remote` with:

```python
    def test_lost_race_keeps_local_beads(self):
        team = team_for_repo(self.lead)
        member = team.member("binh@corp.com")
        bd(self.member, "update", self.bead, "--claim", actor="em@corp.com")
        bd(self.member, "dolt", "push")
        with mock.patch.object(team_beads, "sync", side_effect=[{"status": "synced"},
                                                                team_beads.SyncConflict("bd dolt pull: conflict")]):
            with self.assertRaisesRegex(team_beads.SyncConflict, f"push rejected for {self.bead}; local Beads kept"):
                team_beads.claim(self.lead, team, member, self.bead)
        self.assertEqual("binh@corp.com", show(self.lead, self.bead)["assignee"])
```
   Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_team_beads` (fails).

2. `W/team_beads.py`:
   - imports: add `from datetime import datetime, timedelta, timezone` and `from typing import Any, Mapping`; import `Area` from `.team`.
   - delete `_dolt_dir` and `reset_to_remote`.
   - add after `_show`:

```python
def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expires(team: TeamConfig) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=team.claim_ttl_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def metadata_json(issue: Mapping[str, Any], key: str) -> dict[str, Any]:
    """A JSON object stored under `metadata.<key>` (bd returns it parsed or as a string); {} when absent."""
    metadata = issue.get("metadata") if isinstance(issue.get("metadata"), Mapping) else {}
    value = metadata.get(key)
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return dict(value) if isinstance(value, Mapping) else {}


def claim_of(issue: Mapping[str, Any]) -> dict[str, Any]:
    return metadata_json(issue, "claim")


def claim_expired(issue: Mapping[str, Any], now: str) -> bool:
    """True when the claim lease is past, or the bead was claimed before leases existed."""
    expires_at = str(claim_of(issue).get("expires_at") or "")
    return expires_at < now


def _areas_of(team: TeamConfig, issue: Mapping[str, Any]) -> list[Area]:
    return [team.areas[name] for label in issue.get("labels") or [] if label.startswith("area:")
            if (name := label[5:]) in team.areas]
```
   - `ready`: after the existing loop, add expired rows from in-progress beads:

```python
    now = utc_now()
    for issue in tasks.without_held(_bd_json(root, ["list", "--status", "in_progress"]), held):
        assignee = (issue.get("assignee") or "").lower()
        areas = {label[5:] for label in issue.get("labels") or [] if label.startswith("area:")}
        if assignee and assignee != member.email and claim_expired(issue, now) \
                and (areas & mine or (not areas and not team.areas)):
            result.append({"id": issue["id"], "title": issue.get("title", ""), "assignee": assignee,
                           "areas": sorted(areas), "expired_claim": assignee})
```
     (If `bd ready` already lists in-progress beads, de-duplicate by id: `seen = {row["id"] for row in result}` and skip ids in `seen`.)
   - replace `claim`:

```python
def claim(root: Path, team: TeamConfig, member: Member, bead: str) -> dict[str, Any]:
    """Claim or renew a bead; an expired lease held by someone else is taken over with a note."""
    if team.beads_remote:
        sync(root)
    issue = _show(root, bead)
    ineligible = [area.name for area in _areas_of(team, issue) if not team.eligible(member, area)]
    if ineligible:
        raise SyncConflict(f"{member.email} may not own tracks in {', '.join(ineligible)}")
    holder = (issue.get("assignee") or "").lower()
    expires_at = _expires(team)
    lease = json.dumps({"holder": member.email, "expires_at": expires_at})
    if holder and holder != member.email:
        if not claim_expired(issue, utc_now()):
            raise SyncConflict(f"{bead} is already claimed by {holder} until {claim_of(issue)['expires_at']}")
        argv = ["update", bead, "--assignee", member.email, "--status", "in_progress",
                "--append-notes", f"took over expired claim from {holder}", "--set-metadata", f"claim={lease}"]
    else:
        argv = ["update", bead, "--claim", "--set-metadata", f"claim={lease}"]
    completed = _bd(root, argv, actor=member.email)
    if completed.returncode != 0:
        raise SyncConflict(completed.stderr.strip() or completed.stdout.strip())
    _push(root, team, bead)
    return {"status": "renewed" if holder == member.email else "claimed", "bead": bead, "assignee": member.email,
            "expires_at": expires_at, "advisory": not team.beads_remote}
```
   - replace `_push`:

```python
def _push(root: Path, team: TeamConfig, bead: str) -> None:
    """Push the local write; a rejected push syncs once and retries. Local Beads are never reset."""
    if not team.beads_remote or _bd(root, ["dolt", "push"]).returncode == 0:
        return
    try:
        sync(root)
    except (SyncConflict, TeamError) as error:
        raise SyncConflict(f"push rejected for {bead}; local Beads kept, run gin-workflow team sync ({error})") from error
```
   - `reassign`: replace the `areas = [...]` comprehension with `areas = _areas_of(team, issue)`, and add `"--set-metadata", f'claim={json.dumps({"holder": target.email, "expires_at": _expires(team)})}'` to its `bd update` argv.

3. `W/team_cli.py`: `ready` text line becomes `f"{row['id']} {row['title']}" + (f" (expired claim: {row['expired_claim']})" if row.get("expired_claim") else "")`; `claim` text becomes `f"{result['status']} {args.bead}" + (" (advisory: no Beads remote, teammates cannot see this claim)" if result["advisory"] else "")`.

4. Docs. `docs/reference/cli.md`: `ready` row adds "and beads held by another member whose claim lease has expired (`expired_claim`)"; `claim` row becomes "Claim a bead as yourself, or renew your claim. Refused when you hold no role allowed in one of its `area:` labels, or another member's lease (`claim.expires_at`, `team.claim_ttl_hours` ahead) has not expired; an expired lease is taken over with a note. Without `team.beads_sync.remote` the claim is advisory: only this machine sees it"; `reassign` row adds "and writes a fresh claim lease for the new assignee". `docs/guides/team.md:48`: after `claim it with \`team claim <bead>\`` add "(a lease of `team.claim_ttl_hours`, renewed by claiming again; an expired lease lets another member take the bead)". `S/skills/gin-team/SKILL.md:28`: replace "exit 1 means someone else holds it, so pick another" with "exit 1 means someone else holds an unexpired lease or you may not own its area, so pick another; `team ready` marks expired claims you may take over. Without `team.beads_sync` the claim is advisory and the output says so".

5. Run `tests.workflow_core.test_team_beads` (pass; the `TestTeamBeadsSync` class needs `dolt`), then `tests.test_all`; commit `feat(team): claim leases and eligibility; push never resets Beads`.

### Track 3: Proven gates shared through the epic bead, ship proof at record
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:180-200` (append `gates_of`, `write_gate`, `epic_for`, `shared_gates`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:427-453` (`verify_gate` for `shipped`, `authorize_record`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py:1-20,113-145,196-270,271-300,560-566` (imports, `_delivery_state(epic=...)`, `_share_gate`, `_record_command`, `_state_command`, warning print)
  - Modify `docs/concepts/state-model.md:32` (shared gate proofs)
  - Modify `docs/reference/cli.md:68-76` (`shipped` row and exit codes)
  - Modify `plugins/gin-workflow/src/skills/gin-team/SKILL.md:10-13,36` (gates and ship)
  - Modify `plugins/gin-workflow/src/skills/ship/SKILL.md:37` (`record shipped` in team mode)
  - Test `tests/workflow_core/test_team_gates.py`
- **Provider role**: `backend`
- **Model:** `opus`
- **Effort:** `high`
- **Why:** cross-module change to the state model (`record`, `state`, team verification, Beads metadata) with failure paths for an unavailable tracker.
- **Acceptance criteria**: US-4, US-5. `record plan-approved` writes `metadata.gates.plan_approved`; `state` with an empty log reports it `satisfied`; `record orchestration-ready --epic E` seeds `E.metadata.gates` and adds `workflow:<id>`; solo mode never calls `--set-metadata gates=`; `record shipped` in team mode with a `ship` policy rejects a sha, rejects an approval on an older commit, accepts one on `head_sha` regardless of local HEAD, and stores the PR's `merge_commit`; `team check --gate ship` still reports `is not local HEAD`.
- **Estimated complexity**: high

Interfaces produced:
- `team_beads.gates_of(issue) -> dict[str, dict]`
- `team_beads.write_gate(root, epic, gate, proof, *, actor) -> None` (raises `TeamError`)
- `team_beads.epic_for(root, workflow_id, recorded) -> str`
- `team_beads.shared_gates(root, workflow_id, recorded) -> tuple[str, dict[str, dict], str | None]` (epic, gates, cause)

Steps:

1. Tests in `tests/workflow_core/test_team_gates.py`. Add a fake `bd` helper to `GateCase`:

```python
    def bd(self, beads: dict[str, dict]) -> None:
        """A fake bd: `show <id> --json` answers from `beads`; `list ... --json` returns [] ; updates succeed."""
        rules = [{"argv": ["show", bead], "stdout": [row]} for bead, row in beads.items()]
        rules += [{"argv": ["show"], "exit": 1, "stderr": "not found"}, {"argv": ["list"], "stdout": []},
                  {"argv": ["update"], "stdout": ""}]
        fake_cli(self.bin, "bd", rules)

    def bd_updates(self) -> list[list[str]]:
        return [call for call in calls(self.bin) if call[:2] == ["bd", "update"]]
```
   Add class `TestSharedGates(GateCase)`:

```python
class TestSharedGates(GateCase):
    def setUp(self):
        super().setUp()
        write(self.root, ".agent-workflow/config.yaml",
              (self.root / ".agent-workflow/config.yaml").read_text() + "providers:\n  task_tracking: beads\n")

    def test_record_writes_the_proof_into_the_epic_bead(self):
        self.gh(gh_pr(author="em-dev", files=[PLAN_PATH], reviews=[("binh-dev", "APPROVED", "c"),
                                                                    ("chi-fe", "APPROVED", "c")]))
        self.bd({"e-1": {"id": "e-1", "issue_type": "epic", "status": "open", "metadata": {}}})
        result = run_cli(self.root, "record", "plan-approved", "--evidence", PR, "--workflow-id", "e-1", env=self.env)
        self.assertEqual(0, result.returncode, result.stderr)
        update = self.bd_updates()[-1]
        self.assertEqual(["bd", "update", "e-1", "--set-metadata"], update[:4])
        gates = json.loads(update[4].removeprefix("gates="))
        proof = gates["plan_approved"]
        self.assertEqual((PR, "m" * 40, ["binh@corp.com", "chi@corp.com"], "binh@corp.com"),
                         (proof["pr_url"], proof["merge_commit"], proof["approvers"], proof["actor"]))
        self.assertRegex(proof["at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_state_reads_a_gate_from_the_epic_bead(self):
        proof = {"pr_url": PR, "merge_commit": "m" * 40, "approvers": ["binh@corp.com"], "actor": "binh@corp.com",
                 "at": "2026-11-01T00:00:00Z"}
        self.bd({"e-1": {"id": "e-1", "issue_type": "epic", "status": "open",
                         "metadata": {"gates": json.dumps({"plan_approved": proof})}}})
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "e-1", "--format", "json", env=self.env).stdout)
        self.assertEqual("satisfied", state["gates"]["plan_approved"])
        self.assertEqual("unmet", state["gates"]["requirement_confirmed"])

    def test_orchestration_ready_seeds_the_epic_and_labels_it(self):
        self.gh(gh_pr(author="binh-dev", files=[SPEC_PATH], reviews=[("an-ba", "APPROVED", "c1")]))
        self.bd({"e-2": {"id": "e-2", "issue_type": "epic", "status": "open", "metadata": {}}})
        self.assertEqual(0, self.record("requirement-confirmed").returncode)
        self.assertIn("no epic bead to share it", self.record("requirement-confirmed").stdout + "")
        ready = run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                        "--epic", "e-2", env=self.env)
        self.assertEqual(0, ready.returncode, ready.stderr)
        updates = self.bd_updates()
        self.assertIn(["bd", "update", "e-2", "--add-label", "workflow:w"], updates)
        gates = next(json.loads(u[4].removeprefix("gates=")) for u in updates if u[2] == "e-2" and u[3] == "--set-metadata")
        self.assertEqual(PR, gates["requirement_confirmed"]["pr_url"])

    def test_state_finds_the_epic_by_workflow_label(self):
        proof = {"pr_url": PR, "merge_commit": "m" * 40, "approvers": ["an@corp.com"], "actor": "binh@corp.com",
                 "at": "2026-11-01T00:00:00Z"}
        epic = {"id": "e-3", "issue_type": "epic", "status": "open", "labels": ["workflow:w"],
                "metadata": {"gates": json.dumps({"requirement_confirmed": proof})}}
        self.bd({"e-3": epic})
        fake_cli(self.bin, "bd", json.loads((self.bin / "bd.json").read_text())[:-2]
                 + [{"argv": ["list", "--label", "workflow:w"], "stdout": [epic]}, {"argv": ["list"], "stdout": []},
                    {"argv": ["update"], "stdout": ""}])
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "w", "--format", "json", env=self.env).stdout)
        self.assertEqual("satisfied", state["gates"]["requirement_confirmed"])

    def test_tracker_failure_keeps_the_local_value_and_warns(self):
        fake_cli(self.bin, "bd", [{"argv": [], "exit": 1, "stderr": "dolt: connection refused"}])
        state = json.loads(run_cli(self.root, "state", "--workflow-id", "e-1", "--format", "json", env=self.env).stdout)
        self.assertEqual("unmet", state["gates"]["plan_approved"])
        self.assertTrue(any("tracker unavailable" in w for w in state["warnings"]), state["warnings"])

    def test_solo_mode_never_writes_gates(self):
        root = make_team_repo(Path(self.tmp.name) / "solo", team="", extra="providers:\n  task_tracking: beads\n")
        self.bd({})
        run_cli(root, "record", "plan-approved", "--evidence", PLAN_PATH, "--workflow-id", "w", "--actor", "me",
                env=self.env)
        self.assertEqual([], self.bd_updates())
```
   Add to `TestRecordGitHub`:

```python
    def test_shipped_needs_approval_on_the_merged_pr_head(self):
        self.bd({"w": {"id": "w", "issue_type": "task", "status": "closed", "metadata": {}}})
        self.assertEqual(0, run_cli(self.root, "record", "orchestration-ready", "--evidence", "w", "--workflow-id", "w",
                                    "--epic", "w", env=self.env).returncode)
        sha = self.record("shipped", "m" * 40)
        self.assertEqual(2, sha.returncode)
        self.assertIn("shipped needs the PR URL as --evidence in team mode", sha.stderr)
        self.gh(gh_pr(state="MERGED", head="f" * 40, author="em-dev", reviews=[("dung-qe", "APPROVED", "old")]))
        self.assertIn("missing approval from one of qe", self.record("shipped").stderr)
        self.gh(gh_pr(state="MERGED", head="f" * 40, author="em-dev", reviews=[("dung-qe", "APPROVED", "f" * 40)]))
        result = self.record("shipped")
        self.assertEqual(0, result.returncode, result.stderr)
        event = self.events()[-1]
        self.assertEqual(("delivery.shipped", "m" * 40, PR), (event["event_type"], event["payload"]["merge_commit"],
                                                              event["payload"]["pr_url"]))
        self.assertNotIn("is not local HEAD", result.stderr)
```
   (Each `GateCase` test that records in team mode with `providers.task_tracking: beads` needs `self.bd(...)`; tests of `TestRecordGitHub` keep the markdown tracker, where `record` writes no bead metadata because `shared_gates`/`write_gate` run only when `tasks.backend(root) == "beads"`.) Run `tests.workflow_core.test_team_gates` (fails).

2. `W/team.py`:
   - `verify_gate`: map `shipped` to the `ship` policy and skip the local head:

```python
    policy_gate = "ship" if gate == "shipped" else gate
    artifact = "" if policy_gate == "ship" else resolve_artifact(pr, Path(root), gate, plan if gate == "plan_approved" else spec)
    head = _head(Path(root)) if gate == "ship" else ""
    reasons = check_approval(policy_gate, pr, team, root=Path(root), artifact=artifact, local_head=head)
    if gate == "shipped" and not pr.merged:
        reasons.append("PR is not merged")
    return pr, artifact, reasons
```
     (`check_approval` for `ship` accepts an open PR; `shipped` additionally requires `pr.merged`, the `PullRequest.merged: bool` field of `W/team_host.py:25`.)
   - `authorize_record`: change the first guard to `if (gate not in GATES and gate != "shipped") or not has_policy("ship" if gate == "shipped" else gate, team): return member.email, {}`, and before `verify_gate` add:

```python
    if gate == "shipped" and not evidence.startswith(("https://", "http://")):
        raise TeamError("shipped needs the PR URL as --evidence in team mode")
```

3. `W/team_beads.py`, append:

```python
def gates_of(issue: Mapping[str, Any]) -> dict[str, Any]:
    return metadata_json(issue, "gates")


def write_gate(root: Path, epic: str, gate: str, proof: Mapping[str, Any], *, actor: str) -> None:
    """Merge one proven gate into the epic bead's `gates` metadata."""
    gates = {**gates_of(_show(root, epic)), gate: dict(proof)}
    completed = _bd(root, ["update", epic, "--set-metadata", f"gates={json.dumps(gates, sort_keys=True)}"], actor=actor)
    if completed.returncode != 0:
        raise TeamError(f"bd update {epic} --set-metadata gates failed: {completed.stderr.strip()}")


def epic_for(root: Path, workflow_id: str, recorded: str) -> str:
    """The bead that shares a workflow's gates: the workflow id when it is a bead, else the recorded epic, else
    the epic labelled workflow:<id>; "" when none exists. Raises TeamError when bd is unavailable."""
    if _bd(root, ["show", workflow_id, "--json"]).returncode == 0:
        return workflow_id
    if recorded:
        return recorded
    rows = [row for row in _bd_json(root, ["list", "--label", f"workflow:{workflow_id}", "--all", "--limit", "0"])
            if row.get("issue_type") == "epic"]
    return str(rows[0]["id"]) if rows else ""


def shared_gates(root: Path, workflow_id: str, recorded: str) -> tuple[str, dict[str, Any], str | None]:
    """(epic, its `gates` metadata, None) or ("", {}, cause) when the tracker cannot answer."""
    try:
        epic = epic_for(root, workflow_id, recorded)
        return epic, (gates_of(_show(root, epic)) if epic else {}), None
    except (TeamError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        return "", {}, f"tracker unavailable: {error}"
```
   `_bd` raises `TeamError("bd is not installed")` when `bd` is missing, which `shared_gates` reports as a cause.

4. `W/lifecycle_cli.py`:
   - imports: `from datetime import datetime, timezone`.
   - `_delivery_state(repo_path, events, workflow_id, epic: str | None = None)`: replace `epic = _recorded_epic(events, workflow_id)` with `epic = _recorded_epic(events, workflow_id) if epic is None else epic`.
   - add after `_record_refusal`:

```python
_SHARED_EVENTS = {"requirement.confirmed": "requirement_confirmed", "approval.recorded": "plan_approved",
                  "delivery.shipped": "shipped"}


def _proof(payload: Mapping[str, Any], actor: str, at: str) -> dict[str, Any]:
    return {"pr_url": payload.get("pr_url", ""), "merge_commit": payload.get("merge_commit", ""),
            "approvers": [a.get("email", "") for a in payload.get("approvers", []) if isinstance(a, Mapping)],
            "actor": actor, "at": at}


def _share_gate(repo_path: Path, events: Sequence[WorkflowEvent], args: argparse.Namespace, actor: str,
                team_payload: Mapping[str, Any]) -> str | None:
    """Team mode: mirror the PR proof of this record (and, at orchestration-ready, earlier ones) into the epic bead.
    Returns a warning when nothing could be shared; the local event stays the source of truth."""
    from .tasks import backend
    from .team_beads import epic_for, write_gate

    if backend(repo_path) != "beads":
        return None
    gate = args.gate.replace("-", "_")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if args.gate == "orchestration-ready":
            for prior in events:
                payload = prior.payload if isinstance(prior.payload, Mapping) else {}
                if prior.workflow_id == args.workflow_id and prior.event_type in _SHARED_EVENTS and payload.get("pr_url"):
                    write_gate(repo_path, args.epic, _SHARED_EVENTS[prior.event_type],
                               _proof(payload, prior.actor, prior.timestamp), actor=actor)
            labelled = subprocess.run(["bd", "update", args.epic, "--add-label", f"workflow:{args.workflow_id}"],
                                      cwd=repo_path, text=True, capture_output=True, check=False, timeout=30)
            if labelled.returncode != 0:
                return f"could not label {args.epic} workflow:{args.workflow_id}: {labelled.stderr.strip()}"
            return None
        epic = epic_for(repo_path, args.workflow_id, _recorded_epic(events, args.workflow_id))
        if not epic:
            return f"gate {gate} proven locally; no epic bead to share it"
        write_gate(repo_path, epic, gate, _proof(team_payload, actor, now), actor=actor)
    except Exception as error:  # the local event is recorded; sharing is best effort
        return f"gate recorded locally; could not write it to the epic bead: {error}"
    return None
```
     Use `team_beads._bd` instead of `subprocess.run` for the label write if the module exposes a public wrapper; otherwise keep `subprocess.run` with `shutil.which("bd")`.
   - `_record_command`: capture `prior = list(tx.events)` inside the transaction before `tx.append`; after the `try` block add:

```python
    warning = None
    if team is not None and appended and (team_payload or args.gate == "orchestration-ready"):
        warning = _share_gate(Path(args.repository).resolve(), prior, args, actor, team_payload)
    result = {"status": ..., ..., "message": f"{args.gate} recorded for {args.workflow_id}"}
    if warning:
        result["warning"] = warning
    return result, 0
```
     In the `record` text output (around line 566), after printing the message print `f"warning: {payload['warning']}"` to stderr when present.
   - `_state_command`: after `gates_state = _process_gate_state(events, workflow_id)` add:

```python
        shared_epic, shared, shared_cause = "", {}, None
        if team_for_repo(repo_path) is not None and tasks_backend(repo_path) == "beads":
            from .team_beads import shared_gates

            shared_epic, shared, shared_cause = shared_gates(repo_path, workflow_id,
                                                             _recorded_epic(events, workflow_id))
            for gate in ("requirement_confirmed", "plan_approved"):
                if gate in shared and not gates_state.get(gate):
                    gates_state[gate] = True
        delivery, standalone, tracker_error = _delivery_state(repo_path, events, workflow_id,
                                                              epic=shared_epic or None)
        if "shipped" in shared and standalone:
            delivery["shipped"] = True
```
     (`tasks_backend` = `from .tasks import backend as tasks_backend` at the top.) Append `shared_cause` to `causes` when set, and when team mode is on, no epic was found, and a local event with `pr_url` exists for the workflow, append `f"gate {gate} proven locally; no epic bead to share it"` to the warnings list for each such gate.

5. Docs and skills.
   - `docs/concepts/state-model.md:32`: replace "The store is local to the machine; team mode proves gates with pull requests instead." with "The store is local to the machine. In team mode with Beads, `record` also writes the PR proof of a gate into the epic bead's `gates` metadata (`pr_url`, `merge_commit`, `approvers`, `actor`, `at`); `record orchestration-ready --epic` copies the gates recorded before the epic existed and labels it `workflow:<id>`. `state` treats a gate as satisfied when the local log or the epic bead holds it, so a teammate's checkout sees a gate the lead recorded."
   - `docs/reference/cli.md:68-76`: in the `shipped` row add "team mode with a `ship` policy: evidence is the merged PR URL, approved on its head commit by a listed role; the local HEAD is not compared"; in the exit-code paragraph add "a merge commit sha as `shipped` evidence in team mode" to the usage errors.
   - `S/skills/gin-team/SKILL.md:13`: add "In team mode with Beads, `record` mirrors the proof into the epic bead; a teammate's `state --workflow-id <epic>` shows the gate without re-proving it." `:36`: after "stop if it reports reasons" add "; after the merge, `gin-workflow record shipped --workflow-id <id> --evidence <pr-url>` proves the approval on the merged head (a standalone bead) or the epic closes as usual".
   - `S/skills/ship/SKILL.md:37`: after `--evidence <merge commit> --actor <id>` add "(team mode with a `ship` policy: `--evidence <pr-url>`)".

6. Run `tests.workflow_core.test_team_gates`, then `tests.test_all`; commit `feat(team): share proven gates through the epic bead; verify ship at record`.

### Track 4: `check_plan` rejects a file listed by two tracks
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/team.py:252-276` (`check_plan`)
  - Modify `docs/reference/cli.md:181` (`check-plan` row)
  - Modify `plugins/gin-workflow/src/skills/gin-team/SKILL.md:19` (plan rule)
  - Test `tests/workflow_core/test_team_gates.py`
- **Provider role**: `backend`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** one loop over an existing list with a fixed message.
- **Acceptance criteria**: US-6. `team check-plan` exits 1 with `` `src/a.py` is listed by tracks 1 and 3 `` for a plan whose tracks 1 and 3 both list `src/a.py`; disjoint plans pass as today.
- **Estimated complexity**: low

Steps:

1. Test in `TestPlanChecks` (`tests/workflow_core/test_team_gates.py`):

```python
    def test_a_file_in_two_tracks_is_rejected(self):
        plan = PLAN.replace("- Modify: `web/login.tsx:10-20`\n",
                            "- Modify: `web/login.tsx:10-20`\n- Modify: `services/auth/login.py`\n") + \
            "\n### Track 3: Docs\n**Metadata:**\n- Area: backend\n- Owner: em@corp.com\n\n**Files:**\n" \
            "- Modify: `services/auth/login.py:1-5`\n"
        path = write(self.root, PLAN_PATH, plan)
        self.assertIn("`services/auth/login.py` is listed by tracks 1, 2 and 3", check_plan(self.team, path))
        self.assertEqual(1, run_cli(self.root, "team", "check-plan", str(path)).returncode)
```
   (Track 2's `services/auth/login.py` is also outside `frontend`; that error is expected too and not asserted.)

2. `W/team.py` `check_plan`, before `return errors`:

```python
    listed: dict[str, list[int]] = {}
    for track in tracks:
        for item in track.files:
            listed.setdefault(item, []).append(track.number)
    for item, numbers in listed.items():
        if len(numbers) > 1:
            names = [str(n) for n in sorted(numbers)]
            errors.append(f"`{item}` is listed by tracks {', '.join(names[:-1])} and {names[-1]}")
    return errors
```

3. Docs: `docs/reference/cli.md:181` add "and that no path is listed by two tracks"; `S/skills/gin-team/SKILL.md:19` after "split a track that crosses areas" add "; no file may be listed by two tracks".

4. Run `tests.workflow_core.test_team_gates`; commit `feat(team): check-plan rejects a file listed by two tracks`.

### Track 5: Review ledger owner and bounded cycles
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/projections.py:183-230,237-240,294-297,382-386` (`owner`, `max_cycles`, `cycles`, `decided_since_cycle`)
  - Modify `plugins/gin-workflow/src/scripts/review_ledger/cli.py:296-360,684-704` (`initialize_ledger(max_cycles=...)`, guards in `build_start_review_operations`)
  - Modify `plugins/gin-workflow/src/scripts/review-ledger.py:138-160,418-420,446-470,802-807` (`init --max-cycles`, `status --format`, handlers)
  - Modify `docs/reference/cli.md:359-363` (review-ledger `Lifecycle` and `Inspection` rows, and the paragraph after the table)
  - Modify `plugins/gin-workflow/src/skills/review/SKILL.md:15,22,30` (team actor ids, `--max-cycles`, enforcement)
  - Modify `plugins/gin-workflow/src/skills/gin-team/SKILL.md:26-34` (new `## review` section)
  - Modify `plugins/gin-workflow/src/skills/gin-review-response/SKILL.md:34` (enforced by the ledger)
  - Test `tests/review_ledger/test_cli.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to the ledger projection and one command builder; exact messages and exit codes are in the spec; backward compatibility with existing ledgers must hold.
- **Acceptance criteria**: US-7. `start-review` by the init actor exits 1 with `must differ from the track owner`; with `--max-cycles 2` the third `start-review` exits 1 with `max review cycles (2) reached` and succeeds after `record-human-decision`; a ledger without `--max-cycles` allows any number of cycles; a pre-change ledger (no `owner`) accepts any reviewer; `status --format json` has `owner`, `max_cycles`, `cycles`.
- **Estimated complexity**: medium

Steps:

1. Tests. Add a class to `tests/review_ledger/test_cli.py`, reusing the `setUp` of `TestTransitionRequestedAppliesState` (copy it, with `init` extended by `"--max-cycles", "2"`):

```python
class TestOwnerAndCycles(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script = str(Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts/review-ledger.py")
        subprocess.run(["git", "init", "-q", "."], cwd=self.test_dir, check=True)
        Path(self.test_dir, "f.txt").write_text("x\n")
        subprocess.run(["git", "add", "f.txt"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"],
                       cwd=self.test_dir, check=True)
        subprocess.run(["git", "update-ref", "refs/gin/review/bead-t", "HEAD"], cwd=self.test_dir, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, self.script, *args], cwd=self.test_dir, capture_output=True, text=True)

    def init(self, *extra):
        return self.run_cli("init", "--bead-id", "bead-t", "--repo-id", "r", "--repo-path", ".", "--include", "f.txt",
                            "--review-ref", "refs/gin/review/bead-t", "--base-sha", "HEAD", "--actor-id", "a@x", *extra)

    def request_review(self):
        self.run_cli("transition-requested", "--bead-id", "bead-t", "--to", "review-requested",
                     "--actor-role", "worker", "--actor-id", "a@x")

    def start(self, reviewer):
        return self.run_cli("start-review", "--bead-id", "bead-t", "--actor-id", reviewer)

    def lease_of(self, result):
        return result.stdout.strip().split()[-1].rstrip(".")

    def changes_requested(self, lease):
        self.run_cli("transition-requested", "--bead-id", "bead-t", "--to", "changes-requested",
                     "--actor-role", "reviewer", "--actor-id", "b@x", "--lease-id", lease)
        self.run_cli("release-lease", "--bead-id", "bead-t", "--actor-id", "b@x", "--lease-id", lease)
        self.run_cli("transition-requested", "--bead-id", "bead-t", "--to", "implementation-in-progress",
                     "--actor-role", "worker", "--actor-id", "a@x")
        self.request_review()

    def test_reviewer_must_differ_from_the_owner(self):
        self.init()
        self.request_review()
        refused = self.start("a@x")
        self.assertEqual(1, refused.returncode)
        self.assertIn("reviewer a@x must differ from the track owner", refused.stderr + refused.stdout)
        self.assertEqual(0, self.start("b@x").returncode)

    def test_max_cycles_stops_the_third_review_until_a_human_decides(self):
        self.init("--max-cycles", "2")
        self.request_review()
        first = self.start("b@x")
        self.changes_requested(self.lease_of(first))
        second = self.start("b@x")
        self.assertEqual(0, second.returncode, second.stderr)
        self.changes_requested(self.lease_of(second))
        third = self.start("b@x")
        self.assertEqual(1, third.returncode)
        self.assertIn("max review cycles (2) reached; record a human decision", third.stderr + third.stdout)
        status = json.loads(self.run_cli("status", "--bead-id", "bead-t", "--format", "json").stdout)
        self.assertEqual(("a@x", 2, 2), (status["owner"], status["max_cycles"], status["cycles"]))
        self.run_cli("record-human-decision", "--bead-id", "bead-t", "--finding-id", "none", "--question", "continue?",
                     "--decision", "one more cycle", "--reason", "scope grew", "--actor-id", "lead@x")
        self.assertEqual(0, self.start("b@x").returncode)

    def test_without_max_cycles_any_number_of_reviews_runs(self):
        self.init()
        self.request_review()
        for _ in range(3):
            started = self.start("b@x")
            self.assertEqual(0, started.returncode, started.stderr)
            self.changes_requested(self.lease_of(started))
        status = json.loads(self.run_cli("status", "--bead-id", "bead-t", "--format", "json").stdout)
        self.assertEqual((None, 3), (status["max_cycles"], status["cycles"]))

    def test_legacy_ledger_without_owner_accepts_any_reviewer(self):
        self.init()
        path = Path(self.test_dir, ".planning/reviews/bead-t/review.json")
        data = json.loads(path.read_text())
        for event in data["events"]:
            if event["action"] == "ledger-created":
                event["payload"].pop("owner", None)
        path.write_text(json.dumps(data))
        self.request_review()
        self.assertEqual(0, self.start("a@x").returncode)
```
   `import json` at the top of the file if missing. Where the stored `review.json` keeps a hash or revision over the payload, adapt the legacy test to rebuild the file through `mutate_ledger` with a payload that lacks `owner`; the invariant tested is "no `owner` means no check". Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.review_ledger.test_cli` (fails).

2. `L/projections.py` `ReviewProjection`:
   - `__init__`: add `self.owner: str = ""`, `self.max_cycles: Optional[int] = None`, `self.cycles: int = 0`, `self.decided_since_cycle: bool = False`.
   - `to_dict`/`from_dict`: add the four keys (`from_dict` defaults: `""`, `None`, `0`, `False`).
   - `apply_event`: in the `LEDGER_CREATED` branch add `self.owner = str(payload.get("owner") or "")` and `self.max_cycles = payload.get("max_cycles")`; in `REVIEW_STARTED` add `self.cycles += 1` and `self.decided_since_cycle = False`; in `HUMAN_DECISION_RECORDED` add `self.decided_since_cycle = True` before the finding lookup.

3. `L/cli.py`:
   - `initialize_ledger(..., max_cycles: Optional[int] = None)`: add `payload["owner"] = actor_id` and, when `max_cycles is not None`, `payload["max_cycles"] = max_cycles`, before `mutate_ledger`.
   - `build_start_review_operations`, after the `ttl_seconds` check:

```python
    if projection.owner and actor_id == projection.owner:
        raise LeaseError(f"reviewer {actor_id} must differ from the track owner")
    if (projection.max_cycles is not None and projection.review_state == "review-requested"
            and projection.cycles >= projection.max_cycles and not projection.decided_since_cycle):
        raise LeaseError(f"max review cycles ({projection.max_cycles}) reached; record a human decision")
```

4. `S/scripts/review-ledger.py`:
   - `p_init.add_argument("--max-cycles", type=int)`; reject `< 1` in the handler with `raise ValueError("--max-cycles must be at least 1")`; pass `max_cycles=args.max_cycles` to `initialize_ledger`.
   - `p_stat.add_argument("--format", choices=["text", "json"], default="text")`; in the handler, with `json`, print `json.dumps({"review_state": proj.review_state, "owner": proj.owner, "max_cycles": proj.max_cycles, "cycles": proj.cycles, "findings": len(proj.findings), "unresolved": unresolved}, sort_keys=True)` instead of the three lines.

5. Docs and skills.
   - `docs/reference/cli.md:359-363`: in the paragraph after the command table, add that `init` gains "`--max-cycles N` caps `start-review` to N review cycles (a cycle is one `review-started` event) until `record-human-decision`; the init actor is stored as `owner` and may not start a review"; `status` gains "`--format json` adds `owner`, `max_cycles`, `cycles`".
   - `S/skills/review/SKILL.md:15`: add "`--max-cycles <routing.review.max_cycles from state --format json>`" to the `init` command; `:22`: add "the ledger refuses the init actor as reviewer"; `:30`: replace "Stop at the maximum review cycles (`routing.review.max_cycles`) and return `human_decision_required`; never loop unbounded." with "`start-review` exits 1 at `max_cycles` (`max review cycles (N) reached`); return `human_decision_required` instead of retrying. Never loop unbounded."
   - `S/skills/gin-team/SKILL.md`: add after `## execute`:

```markdown
## review
`init` and `start-review` take the member email from `team whoami` as `--actor-id`, so the ledger refuses the track owner as reviewer; another member (or an agent run by one) reviews. `init` passes `--max-cycles` from `routing.review.max_cycles`.
```
   - `S/skills/gin-review-response/SKILL.md:34`: replace "At the configured maximum cycle count with unresolved findings, require a human decision." with "At `routing.review.max_cycles` the ledger refuses `start-review` until `record-human-decision` is written; ask the user for that decision instead of retrying."

6. Run `tests.review_ledger.test_cli`, then `tests.test_all`; commit `feat(review-ledger): owner check and max_cycles enforcement`.

## Integration
- **Branch**: `feat/team-hardening`
- **Merge strategy**: sequential (tracks 1 → 2 and 3; 4 and 5 any time; `W/team.py` is edited by tracks 1, 3, 4 in disjoint ranges; `docs/reference/cli.md` by 2, 3, 4, 5)

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes (`TestTeamBeadsSync` runs only where `dolt` is installed)
- [ ] `gin-workflow rules --files <changed paths>` consulted before each track
- [ ] `grep -rn "reset_to_remote\|reset --hard" plugins/gin-workflow/src/scripts/workflow_core/team_beads.py` prints nothing
- [ ] Manual: in a repo with `team:` and `providers.task_tracking: beads`, `record plan-approved --evidence <pr>` then `bd show <epic> --json` shows `metadata.gates.plan_approved`

## Notes
- `Model:` and `Effort:` come from the `claude` catalog (`haiku`, `sonnet`, `opus`; efforts `low`..`max`).
- The Parent Bead `gin-workflow-rm-team-hardening` stays open until the human-confirmed merge; track beads close after tests and review pass.
- The spec names `status --format json`; the ledger's other commands have no format flag, so `--format` is new to `status` only.
