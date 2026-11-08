# Team handoff: one command to hand a track over, one to take it

Epic: gin-workflow-ht4l
Status: draft for user review.

## Goal and scope

Handing a track to another member in team mode is a chain of commands run by hand: push the track branch, commit the review ledger, `gin team reassign`, then on the other machine fetch, `git worktree add`, `gin team claim`. A wrong order loses work: `reassign` before the push leaves the commits on the first machine, an uncommitted ledger does not travel, and a worktree at the wrong path breaks `gin worktree cleanup`.

Today:
- `gin team reassign <bead> <email>` only checks authority and eligibility, sets the assignee, appends a note, writes a fresh claim lease, and pushes Beads (`plugins/gin-workflow/src/scripts/workflow_core/team_beads.py:166-191`). It does not push the branch or the ledger.
- `gin worktree create` makes a new branch only (`git worktree add -b`, `workflow_core/worktrees.py:40`), so the new owner runs raw `git worktree add` (`docs/guides/ai-strategy.md:76-91`).
- `review-ledger.py push-refs --bead-id <id>` pushes the ledger's review refs only; the ledger files under `.planning/reviews/<bead>/` travel with the branch only when committed (`docs/guides/team.md:64`).
- `gin team claim` refuses a bead whose `area:` labels the member may not own (`team_beads.py:122-145`), and `gin team ready` lists unassigned beads only for the member's areas (`team_beads.py:85-109`).
- `bd assign <id> ""` unassigns; `bd update --set-metadata` and `--unset-metadata` store free-form metadata per bead.

Epic `gin-workflow-ht4l` named four independent subsystems (track handoff, track beads from a plan, PR body fields, members) plus two candidates (host-settings check, shared Beads bootstrap). This spec covers the first; the epic is narrowed to it. The other three are proposed as their own epics (listed under assumptions) and are out of scope here.

This spec adds two `gin team` subcommands:
- `gin team handoff <bead> (<email> | --release) [--worktree <path>]`: the current owner (or an area lead) pushes the track branch and the review refs, records the branch on the bead, then hands the bead to a named member or releases it to the pool.
- `gin team takeover <bead> [--branch <name>]`: the new owner fetches the branch, checks it out at `.planning/worktrees/<bead>`, fetches the review refs, and claims the bead. A released bead can be taken by any member, whatever their areas.

Decisions confirmed with the user:
- Two new commands; `reassign` and `claim` keep their behaviour for the manual path.
- Uncommitted changes in the track worktree: `handoff` refuses and lists the files. It never commits on the owner's behalf.
- `--release` returns the bead to the pool; after a release any member may take it, not only members of its areas.

Assumptions:
- After this spec is confirmed, the description of `gin-workflow-ht4l` is narrowed to the handoff scope, and the remaining work is proposed as three epics for the user to create: "Track beads from an approved plan: `gin team tracks <plan>` creates beads, labels, dependencies, and the routes JSON" (reuses `team.plan_tracks`); "Track pull request body: `gin team pr <bead>` fills `Plan:`, `Tracks:`, `Spec:`, `Beads:`" (first `gh`/`glab` write call); "Members: `gin team member add|remove|roles` with `validate_team`" (works around `--set` splitting keys on `.`). The host-settings check after `team init` is left for the members epic to decide.
- `handoff` runs on the owner's machine with `origin` reachable; `takeover` runs on the receiver's machine in the main checkout of a clone that has the same `origin`.
- The `handoff` metadata key is reserved for these commands; `orchestrate` does not write it (recording the branch at orchestrate time is a follow-up, not needed here because `handoff` reads the branch from the worktree).

Out of scope:
- Creating track beads from a plan, filling the pull request body, and `gin team member` commands (separate epics, see assumptions).
- Checking host settings after `team init`; shared Beads bootstrap.
- Notifying the new owner (`gin notify` is not called).
- Moving the plan's `Owner:` field.
- The markdown task backend: `gin team` already requires Beads.

## Requirements

### R1. `gin team handoff` locates the worktree and refuses dirty trees
- Parser in `workflow_core/team_cli.py`: `handoff <bead> [email] [--release] [--worktree PATH]`; exactly one of `email` or `--release` is required, else exit 2 with the usage message. Logic lives in `team_beads.handoff(root, team, member, bead, email=None, release=False, worktree=None)`.
- The track worktree is `--worktree` when given, else `<toplevel>/.planning/worktrees/<bead>` (`worktrees._target`). A missing directory exits 1: `no worktree for <bead>; pass --worktree <path>`.
- `git status --porcelain` in the worktree must be empty (tracked and untracked files alike). Otherwise exit 1 listing each path, and nothing is pushed or written to Beads.
- Authority and target checks are those of `reassign`: the caller is the current assignee or the lead of one of the bead's areas; a closed bead, a non-member target, a target already holding the bead, or a target ineligible for an area is refused with the existing messages. These checks run before any push.

### R2. `handoff` pushes the branch and the review refs
- Branch: `git rev-parse --abbrev-ref HEAD` in the worktree; a detached HEAD exits 1.
- `git push -u origin <branch>` from the worktree. No `origin` remote, or a rejected push, exits 1 with git's message; Beads is untouched.
- When `.planning/reviews/<bead>/review.json` exists in the worktree, run `review-ledger.py push-refs --bead-id <bead>` (same interpreter, `--repository` the worktree); a failure exits 1 after the branch push with the ledger's message. When no ledger exists, print `no review ledger for <bead>` and continue.
- Then write the bead metadata `handoff` as JSON `{"branch": "<branch>", "from": "<caller email>", "to": "<email or null>", "at": "<UTC ISO>"}` with `bd update <bead> --set-metadata handoff=<json>` (actor = caller). The pool flag is the label `released` (R3, R4), not a metadata key: `bd ready --json` and `bd list --json` rows carry labels but not metadata, and `team ready` reads those rows.

### R3. `handoff` reassigns or releases
- With `<email>`: call the existing `reassign` path (assignee, note, fresh lease, Beads push). Output: `{"status": "handed-off", "bead", "branch", "assignee"}`.
- With `--release`: `bd update <bead> --assignee "" --status open --unset-metadata claim --add-label released --append-notes "released to the pool by <me>"` (actor = caller), then `_push` with shared Beads. Output: `{"status": "released", "bead", "branch"}`.
- Both print the next step for the receiver on stderr: `next: gin team takeover <bead>`.

### R4. Released beads are open to every member
- `team ready` lists an unassigned bead labelled `released` for every member, regardless of `area:` labels, with `"released": true` in the row.
- `team claim` (and so `takeover`) skips the area eligibility check when the bead is labelled `released`, and on success removes that label (`--remove-label released`) so later claims follow the normal rules.
- Beads without the `released` label behave exactly as today.

### R5. `gin team takeover` checks out and claims
- Parser: `takeover <bead> [--branch NAME]`; `require_member` as for `claim`. Logic in `team_beads.takeover(root, team, member, bead, branch=None)`.
- Must run in the main checkout (`git rev-parse --git-dir` equals `--git-common-dir`); inside a linked worktree exit 1: `run gin team takeover from the main checkout`.
- Branch: `--branch`, else `handoff.branch` from the bead metadata; neither exits 1: `no handoff branch recorded for <bead>; pass --branch`.
- `git fetch origin <branch>`; a failure exits 1 with git's message.
- `worktrees.checkout(repo, bead, branch)` (new): `git worktree add --track -b <branch> <toplevel>/.planning/worktrees/<bead> origin/<branch>` when the local branch does not exist, else `git worktree add <path> <branch>`; an existing directory exits 1 with the existing `directory ... already exists` message. The CLI gets `gin worktree checkout <track-id> <branch>` for the same function.
- When the branch holds `.planning/reviews/<bead>/review.json`, run `review_ledger.git_adapter.fetch_review_ref(<worktree>, "origin", <bead>)`; a missing remote ref prints a warning and continues.
- Then `claim` (R4 rules). Output: `{"status": "claimed"|"renewed", "bead", "branch", "worktree": "<path>"}` and the hint `next: gin team deps --bead <bead>`.

### R6. Documentation and skill
- `docs/reference/cli.md` `## gin team` table: rows for `handoff` and `takeover`; `## gin worktree`: `checkout`.
- `docs/guides/team.md` and `docs/guides/team.vi.md`: the handoff paragraph (line 64 / 64) describes the two commands and the release option; `docs/guides/ai-strategy.md:76-91` replaces the manual chain with them.
- `plugins/gin-workflow/src/skills/team/SKILL.md:32`: the out-of-quota bullet names `team handoff` and `team takeover`. The team skill has a 6,000-character budget (`tests/workflow_core/test_token_budget.py`); the bullet gets shorter, not longer.

## User Stories

### US-1: Handing a track to a named teammate
As the owner of a track who is out of quota, I want one command that pushes my branch and review refs and reassigns the bead, so that nothing I committed is lost and the new owner can start without asking me.

Acceptance criteria:
- With a clean worktree and a valid target, `gin team handoff <bead> <email>` pushes the branch, pushes the review refs when a ledger exists, writes `handoff` metadata with the branch, reassigns the bead with a fresh lease, and prints the takeover hint.
- With uncommitted or untracked files, it exits 1, lists them, and changes nothing remote or in Beads.
- With a rejected push, it exits 1 and the bead keeps its assignee.
- A non-owner non-lead caller, a closed bead, or an ineligible target is refused with the `reassign` messages.

### US-2: Releasing a track to the pool
As the owner of a track with no obvious successor, I want to release it so that any teammate can pick it up from `gin team ready`.

Acceptance criteria:
- `gin team handoff <bead> --release` pushes as in US-1, then unassigns the bead, sets it `open`, clears the claim lease, and appends the release note.
- Every member sees the bead in `gin team ready` with `released: true`, including members outside its areas.
- `gin team claim` by a member outside its areas succeeds on a released bead and removes the `released` label; a second member is then refused as today.

### US-3: Taking over a handed-off track
As the new owner, I want one command that gives me the branch, the worktree at the standard path, the review refs, and the claim, so that `gin worktree cleanup` and `team deps` work as for any track.

Acceptance criteria:
- From the main checkout, `gin team takeover <bead>` fetches `handoff.branch`, creates `.planning/worktrees/<bead>` on that branch tracking `origin/<branch>`, fetches the review ref when the ledger exists, claims the bead, and prints the worktree path.
- Without recorded branch and without `--branch`, it exits 1 and names the flag.
- Run inside a linked worktree, it exits 1 and names the main checkout.
- An existing `.planning/worktrees/<bead>` directory exits 1 without touching it.

### US-4: Checking out an existing branch as a track worktree
As a developer, I want `gin worktree checkout <track-id> <branch>` so that an existing branch gets a worktree at the standard path without raw `git worktree add`.

Acceptance criteria:
- An existing local branch is checked out at `.planning/worktrees/<track-id>`.
- A branch that exists only on `origin` is created locally tracking it.
- An existing directory or an unknown branch exits 1 with git's or the existing message.

## Errors and compatibility

- Ordering: checks, then branch push, then review refs, then metadata, then Beads; a failure at any step stops there and the message names the step. Beads is never changed before the branch is on `origin`.
- `reassign`, `claim`, and `ready` are unchanged for beads without `handoff` metadata; existing tests keep passing.
- `handoff` metadata is a free-form bd key; no config schema change, no `schema_version` bump.
- Shared Beads (`team.beads_sync`): `handoff` and `takeover` sync before reading and push after writing through the existing `sync` and `_push`; without a remote, the claim stays advisory as today.
- `team_cli.main` keeps returning 2 for `TeamError`, `HostUnavailable`, and `ValueError`; git failures surface as `TeamError` with git's stderr.

## Testing

- `tests/workflow_core/test_team_beads.py` (real `bd`, skipped without it), using a bare `origin` for git as the shared-Beads class already does: handoff refuses a dirty worktree and changes nothing; handoff to a member pushes the branch, writes `handoff` metadata, and reassigns; `--release` unassigns, reopens, clears the lease, and `ready` lists the bead for a member outside its areas; `claim` on a released bead by an outside member succeeds and clears `released`; takeover from the main checkout creates the worktree on the pushed branch and claims; takeover inside a worktree, without a branch, or onto an existing directory exits 1.
- `tests/workflow_core/test_worktrees.py`: `checkout` of a local branch, of a remote-only branch, and the existing-directory error.
- `tests/workflow_core/test_token_budget.py` stays green (team skill under 6,000 characters).
- Manual check with two clones and a bare remote: handoff on one, takeover on the other, `gin team deps --bead <bead>` exits 0 in the new worktree.

## Open Technical Questions
