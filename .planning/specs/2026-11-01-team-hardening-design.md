# Team hardening: no conflicting claims, no lost Beads, proven gates

Epic: gin-workflow-rm-team-hardening
Status: confirmed by the user on 2026-11-01.

## Goal and scope

Several members in different roles work in parallel while gates, claims, reviews, and Beads stay consistent, and a rejected Beads push never discards a local write.

In scope:
- `_push` never resets local Beads; a rejected push retries through `sync` once and then reports a conflict with the local write intact.
- `claim` applies the same `area:` eligibility rule as `reassign`, carries a lease with a TTL, and reports itself as advisory without a Beads remote.
- `team init` and `setup doctor` warn on a team gate with no role policy; `team.strict` turns that warning into a configuration error.
- A gate proven in team mode is written into the epic bead's metadata, so `state` on a teammate's machine reports it.
- `record shipped` in team mode verifies the merged PR against the `ship` policy; `team check --gate ship` keeps the local-head check.
- `check_plan` rejects a file listed by two tracks.
- In team mode the review ledger refuses a reviewer who is the track owner and enforces `max_cycles`.

Out of scope:
- Identity beyond `git config user.email` (documented as a known limit).
- Parsing Dolt exit codes; the conflict detection in `sync` stays text based.
- A configurable Dolt branch: the only reader of `origin/main` is `reset_to_remote`, which this epic removes, so `beads_sync.branch` has no reader and is not added.
- A background job that releases expired claims; expiry only lets another member claim.

Current behavior this changes (`S` = `plugins/gin-workflow/src`, `W` = `S/scripts/workflow_core`, `L` = `S/scripts/review_ledger`):
- `W/team_beads.py:105-111` `_push`: a non-zero `bd dolt push` calls `reset_to_remote` (`:82-91`), which runs `dolt fetch origin` and `dolt reset --hard origin/main`, then raises `SyncConflict`. The branch is hardcoded at `:88`. `push()` (`:113-118`) never resets; `sync()` (`:61`) runs `bd dolt pull` then `bd dolt push`.
- `W/team_beads.py:94-103` `claim`: syncs when a remote exists, refuses when the assignee is someone else, runs `bd update <bead> --claim` with the member email as actor, pushes. It reads no `area:` label and has no lease; without a remote it reports `claimed <bead>` like a shared claim. `reassign` (`:121-146`) checks `team.eligible(target, area)` for every `area:` label.
- `W/schemas.py:15-62` `_TEAM` has no `strict` and no `claim_ttl_hours`; `additionalProperties: False` rejects them today.
- `W/team_init.py:138-168` `doctor_report` checks `member`, `host_cli`, `codeowners`, `hook`, `spec_review`, `beads_remote`; nothing reports a gate without a policy. `W/team.py:394-396` `has_policy` defines when a gate has one.
- `W/lifecycle_cli.py:196-230` `_record_command`: `authorize_record` (`W/team.py:442-453`) verifies the PR and adds `pr_url`, `merge_commit`, `approvers`, `repository` to the event payload; the event goes only to `.agent-workflow/runtime/events.jsonl`, local to the machine (`docs/concepts/state-model.md:32`). Nothing is written to a bead. `_state_command` (`:271`) derives `requirement_confirmed`, `plan_approved`, `orchestration_ready` from local events only (`_process_gate_state`, `:65`).
- `W/team.py:13` `GATES` holds `ship`, but `record shipped` passes gate `shipped` to `authorize_record`, which returns `{}` for a gate not in `GATES`: the `ship` policy is enforced only by `team check --gate ship` run from `S/skills/gin-team/SKILL.md:36` before merging. `verify_gate` (`:427-439`) passes the local HEAD for `ship`, and `check_approval` (`:346-384`) rejects a PR head that is not the local HEAD and ignores approvals not made on the PR head.
- `W/team.py:252-276` `check_plan` validates each track's area, owner, membership, and eligibility; it never compares files across tracks.
- `S/scripts/review-ledger.py:138-160` `init` and `:179-194` `start-review` take `--actor-id`; `L/cli.py:684-748` `build_start_review_operations` refuses only an active lease held by another actor. No command compares the reviewer with the implementer, and `max_cycles` (`W/project.py:72`) is parsed but compared with nothing; `S/skills/gin-review-response/SKILL.md:34` asks for a human decision in prose only.
- `W/usage.py:324` writes bead metadata with `bd update <bead> --set-metadata ai_usage=<json>`; the same path serves the new metadata keys.

## Requirements

### Beads push without reset
- `_push` runs `bd dolt push`; on a non-zero exit it runs `sync()` once (pull, then push) and returns when that succeeds.
- When `sync()` raises, `_push` raises `SyncConflict` whose message names the bead, says the local write is kept, and tells the member to run `gin-workflow team sync`. No `dolt reset` runs anywhere in gin-workflow.
- `reset_to_remote` and `_dolt_dir` are removed, together with `tests/workflow_core/test_team_beads.py::test_lost_race_resets_local_beads_to_the_remote`.
- A `SyncConflict` from `_push` still exits 1 with `conflict: ...` in `team claim` and `team reassign`.

### Claim eligibility, lease, and advisory mode
- `claim` collects the bead's `area:` labels that name a configured area and refuses with `SyncConflict("<member> may not own tracks in <areas>")` when `team.eligible(member, area)` is false for any of them. Labels naming no configured area are ignored, as in `reassign`.
- A claim writes bead metadata `claim = {"holder": <member email>, "expires_at": <UTC ISO-8601>}` in the same `bd update` call as `--claim`. `expires_at` is now plus `team.claim_ttl_hours` (integer, minimum 1, default 48).
- `claim` on a bead held by another member succeeds only when the bead's `claim.expires_at` is in the past or the `claim` metadata is missing while the assignee is set by an older version; it then sets the assignee to the member, writes a fresh `claim`, and adds the note `took over expired claim from <holder>`. An unexpired claim by another member still raises `SyncConflict("<bead> is already claimed by <holder>")` and names `expires_at`.
- `claim` by the current holder renews `expires_at` and returns `status: renewed`.
- Without `team.beads_sync.remote`, `claim` returns `advisory: true` and the text output reads `claimed <bead> (advisory: no Beads remote, teammates cannot see this claim)`. With a remote the key is `advisory: false`.
- `team ready` lists, besides today's rows, beads assigned to another member whose `claim.expires_at` is in the past, with `expired_claim: <holder>` in the row; the text output appends `(expired claim: <holder>)`.
- `reassign` writes the same `claim` metadata for the target.

### Gate role policies and `team.strict`
- `team.strict` (boolean, default false) is accepted by the schema.
- `doctor_report` adds the check `gate_policy`: true when each of `requirement_confirmed`, `plan_approved`, `ship` satisfies `has_policy`. Its fix text names the gates without a policy: `set team.approvals.<gate> to a role list or area_lead (gates without a policy: ...)`. `team init` prints the same line as a warning after its file report; the exit code does not change.
- With `team.strict: true`, `validate_team` returns one error per gate without a policy: `team.strict: team.approvals.<gate> has no role policy`. Config loading fails as for any other `validate_team` error, so `state`, `record`, and every `team` command stop until the policy exists.
- With `team.strict: false` nothing fails; an existing team config validates as today.

### Proven gates shared through the epic bead
- After `authorize_record` succeeds for a gate with a policy, `record` writes the proof into the epic bead's metadata key `gates`: a JSON object whose `<gate>` entry is `{"pr_url", "merge_commit", "approvers": [<emails>], "actor": <member email>, "at": <UTC ISO-8601>}`. Existing entries for other gates are kept; the same gate is overwritten.
- The epic for a `record` call is, in this order: the `--workflow-id` when `bd show` finds a bead with that id; else the epic named by the latest local `orchestration.ready` event of that workflow; else none, and the proof is written only to the local log (the `state` output then carries the warning `gate <gate> proven locally; no epic bead to share it`).
- `record orchestration-ready --epic <E>` in team mode copies every gate already recorded in the local log for that workflow into `E.metadata.gates` (with the payload the local event holds) and adds the label `workflow:<workflow-id>` to `E`.
- `state` in team mode resolves the epic the same way, plus a lookup `bd list --type epic --label workflow:<workflow-id>` when the first two fail, and treats a gate as satisfied when the local event or `metadata.gates.<gate>` exists. A tracker failure during that read leaves the gate at its local value and adds the existing `tracker unavailable` cause.
- Solo mode (no `team:` block) never reads or writes `metadata.gates`.
- `team check` stays read only.

### Ship proof at record time
- `record shipped` in team mode with `has_policy("ship")` requires `--evidence` to be a PR URL; a merge commit sha is rejected with `shipped needs the PR URL as --evidence in team mode`.
- The PR must be merged and carry an approval from a required role on `pr.head_sha`, excluding the PR author; the local HEAD is not compared. The reasons reuse `check_approval` wording.
- The event payload carries `pr_url`, `merge_commit` (from the PR), `approvers`, `repository`; `metadata.gates.shipped` is written as for the other gates.
- `team check --gate ship <url>` keeps today's behavior: the PR may be open, the approval must be on the PR head, and the PR head must equal the local HEAD.
- `S/skills/ship/SKILL.md` and `S/skills/gin-team/SKILL.md` state both checks: `team check` before merging, `record shipped --evidence <pr-url>` after.

### Duplicate files across tracks
- `check_plan` returns one error per path listed by two or more tracks: `` `<path>` is listed by tracks <n> and <m> `` (track numbers ascending, joined by `, ` with `and` before the last).
- Paths compare as the exact strings `plan_tracks` returns; glob patterns are not expanded.
- `team check-plan` therefore exits 1 for such a plan, and `plan_approved` records refuse it as today for any `check_plan` error.

### Review ledger: distinct reviewer and bounded cycles
- `review-ledger.py init` records `owner = --actor-id` in the initialization event payload and accepts `--max-cycles <n>` (integer, minimum 1, default none).
- `start-review` exits 1 with `reviewer <id> must differ from the track owner` when `--actor-id` equals the ledger's `owner`.
- A review cycle is one `review-started` event. When `max_cycles` is set and the ledger already holds `max_cycles` such events, `start-review` exits 1 with `max review cycles (<n>) reached; record a human decision` unless a `human-decision-recorded` event follows the latest `review-started`.
- `status --format json` reports `owner`, `max_cycles`, and `cycles` (the count of `review-started` events).
- Ledgers created before this change have no `owner` and no `max_cycles`; both checks are skipped for them.
- `S/skills/review/SKILL.md` and `S/skills/gin-team/SKILL.md`: in team mode, `init` and `start-review` pass the member email from `team whoami` as `--actor-id`, and `init` passes `--max-cycles` from `routing.review.max_cycles` in `state --format json`. Solo mode keeps today's actor ids (`W/reviewer.py:119-126`), which already differ between implementer and reviewer.

## User Stories

### US-1: A lost claim race keeps my Beads
As a member whose `team claim` push is rejected, I want my local Beads kept and the conflict named, so that no unpushed bead update of mine is discarded.

Acceptance criteria:
- With a fake `bd` whose first `dolt push` fails and whose `dolt pull` and second `dolt push` succeed, `team claim` exits 0 and no `dolt reset` or `dolt fetch` is invoked.
- With a fake `bd` whose `dolt pull` reports a conflict, `team claim` exits 1, prints `conflict:` with the bead id and `gin-workflow team sync`, and no `dolt reset` is invoked.
- `grep -r "reset" W/team_beads.py` finds no `dolt` reset.

### US-2: Claims respect areas and expire
As an area lead, I want claims to follow the same eligibility rule as reassignments and to expire, so that a track is never held by an ineligible or absent member.

Acceptance criteria:
- A member without the area's roles gets exit 1 and `may not own tracks in <area>` from `team claim`.
- A successful claim stores `claim.holder` and `claim.expires_at` 48 hours ahead by default and `team.claim_ttl_hours` hours when set.
- A second member's `team claim` on an unexpired claim exits 1 naming the holder and `expires_at`; on an expired claim it exits 0, the assignee changes, and the note `took over expired claim from <holder>` is written.
- `team ready` shows a bead with an expired claim held by someone else with `expired_claim`.
- Without a Beads remote, `team claim --format json` reports `advisory: true` and the text output contains `advisory`.

### US-3: Doctor tells me which gates nobody approves
As a team lead running `setup doctor`, I want gates without a role policy listed, so that I can decide whether to configure one, and I want `team.strict` to make the gap an error.

Acceptance criteria:
- With `approvals.ship` absent, `setup doctor` reports `gate_policy: false` and the fix line names `ship`; `team init` prints the same warning and exits 0.
- With `team.strict: true` and `approvals.ship` absent, `state` fails with `team.strict: team.approvals.ship has no role policy`.
- With every gate configured, `gate_policy` is true and `team.strict: true` validates.
- A schema test accepts `strict` and `claim_ttl_hours` and rejects `claim_ttl_hours: 0`.

### US-4: A teammate sees my proven gates
As a member on another machine, I want `state --workflow-id <epic>` to show `plan_approved: satisfied` once the lead recorded it, so that I can start `/orchestrate` or `/execute` without re-proving the gate.

Acceptance criteria:
- After `record plan-approved --evidence <pr>` on machine A (fake `gh`, fake `bd`), the epic's metadata holds `gates.plan_approved` with `pr_url`, `merge_commit`, `approvers`, `actor`, `at`.
- On a checkout with an empty `events.jsonl`, `state --workflow-id <epic> --format json` reports `plan_approved: satisfied` when the bead metadata holds it.
- `record orchestration-ready --epic E` copies earlier local gates into `E.metadata.gates` and adds `workflow:<id>`; `state --workflow-id <topic>` then finds `E` by label.
- In solo mode `bd update --set-metadata gates=` is never called.

### US-5: Shipping needs approval on what was merged
As a QE role holder, I want `record shipped` to fail when the merged PR head lacks my approval, so that the ship policy holds without relying on the skill text.

Acceptance criteria:
- With `approvals.ship: [qe]`, `record shipped --evidence <merge-sha>` exits 1 asking for the PR URL.
- With a merged PR whose approval is on an older commit, `record shipped --evidence <pr-url>` exits 1 with `missing approval from one of qe`; with the approval on `head_sha` it exits 0 regardless of the local HEAD, and the event carries the PR's `merge_commit`.
- `team check --gate ship` on an open PR whose head is not the local HEAD still reports `is not local HEAD`.

### US-6: A plan cannot give one file to two tracks
As a plan author, I want `team check-plan` to reject a file listed by two tracks, so that two owners never edit the same file in parallel.

Acceptance criteria:
- A plan whose tracks 1 and 3 both list `src/a.py` makes `team check-plan` exit 1 with `` `src/a.py` is listed by tracks 1 and 3 ``.
- A plan with disjoint files passes as today.

### US-7: My track is reviewed by someone else, a bounded number of times
As a track owner in team mode, I want the ledger to refuse me as my own reviewer and to stop at `max_cycles`, so that the review rules are enforced by the tool.

Acceptance criteria:
- `init --actor-id a@x` then `start-review --actor-id a@x` exits 1 with `must differ from the track owner`; `--actor-id b@x` succeeds.
- With `init --max-cycles 2`, the third `start-review` after two `review-started` events exits 1 with `max review cycles (2) reached`; after `record-human-decision` it succeeds.
- A ledger initialized without `--max-cycles` allows any number of cycles, and one from before this change (no `owner`) accepts any reviewer.
- `status --format json` contains `owner`, `max_cycles`, `cycles`.

## Errors and compatibility

- `_push` conflict: exit 1, `conflict: push rejected for <bead>; local Beads kept, run gin-workflow team sync`. Dolt conflict resolution is manual, as `sync` reports it today.
- `claim` on an unexpired claim: exit 1, `conflict: <bead> is already claimed by <holder> until <expires_at>`.
- `claim` ineligible: exit 1, `conflict: <member> may not own tracks in <areas>`.
- `record` with an unreachable tracker while writing `metadata.gates`: the local event is still appended (it is the source of truth); the command exits 0 and prints `warning: gate recorded locally; could not write it to <epic>: <cause>`.
- `record shipped` without a PR URL in team mode: exit 2 (usage error, as for other `TeamError`s).
- `team.strict` violation: the config error path used by `validate_team` today.
- `start-review` owner or cycle refusal: exit 1; the ledger is unchanged.
- Config schema version is unchanged: the two new keys are optional and solo configs do not have a `team` block.
- gin-console reads `ai_usage` from bead metadata and ignores other keys; `gates` and `claim` are additive. A later gin-console epic may display them.
- Known limit, documented in `docs/concepts/providers.md` or the team section of `docs/reference/config.md`: member identity is `git config user.email`; nothing verifies it.

## Testing

- `tests/workflow_core/test_team_beads.py`: push retry through sync, conflict without reset, claim eligibility, lease write and renew, expired takeover, unexpired refusal, advisory flag, `ready` expired rows, `reassign` writes `claim`.
- `tests/workflow_core/test_team_init.py` and `test_schema_2_7.py`: `gate_policy` check and fix text, `team init` warning, `strict` error, new schema keys.
- `tests/workflow_core/test_team_gates.py`: `record` writes `metadata.gates`, `orchestration-ready` seeding and label, `state` reads bead metadata with an empty log, solo mode writes nothing, `record shipped` PR verification, `team check --gate ship` unchanged, `check_plan` duplicate files.
- `tests/review_ledger/test_cli.py`: owner refusal, `max_cycles` refusal and release by human decision, legacy ledger compatibility, `status` fields.
- Docs: `docs/concepts/state-model.md` (gate proofs mirrored into the epic bead in team mode), `docs/reference/config.md` (`team.strict`, `team.claim_ttl_hours`), `docs/reference/cli.md` (`team claim`, `team ready`, `record shipped`, `review-ledger.py init --max-cycles`), `S/skills/gin-team/SKILL.md`, `S/skills/ship/SKILL.md`, `S/skills/review/SKILL.md`, `S/skills/gin-review-response/SKILL.md`.
- `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes.
