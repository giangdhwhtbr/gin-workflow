# Ship gate accepts pull requests of workspace children

Epic: gin-workflow-ws-ship-gate
Status: confirmed by the user on 2026-11-10.

## Goal and scope

`gin team check --gate ship` and `gin record shipped` accept a pull request opened in a workspace child repository, comparing it with that child's remote and HEAD instead of the parent's.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`, cluster "Ship gate accepts pull requests of workspace children", P1) found that every child pull request fails the ship gate (QA-3, BE-LEAD-1, FE-LEAD-3). Research on 2026-11-10 confirmed the cause:
- `check_approval` compares the pull request's repository with `origin_url(root)` (`plugins/gin-workflow/src/scripts/workflow_core/team.py:424-426`). `team_cli` resolves `root` to the workspace parent (`team_cli.py:185`, `workspace.py:146-157`), so a child pull request is always "not this repository".
- `verify_gate` takes `_head(root)`, the parent's HEAD, for the `ship` gate (`team.py:516`); it would be wrong even after the origin check passes.
- `record shipped` uses the same `verify_gate` and fails only on the origin check (it skips HEAD).
- Approvals and policy use only the pull request and the team config, so they need no change.
- Nothing maps a pull request to a `workspace.repos` entry; hosts fetch a pull request by its full URL from any working directory (`hosts/github.py:28-31`).

In scope:
- Resolve the repository a ship pull request belongs to: the parent, or the `workspace.repos` entry whose URL matches.
- Compare with that repository's URL and HEAD.
- Tests and docs.

Out of scope:
- Several pull request URLs in one `record shipped --evidence` (BE-LEAD-13) and `team deps` searching a child's pull requests (BE-LEAD-16): `gin-workflow-ws-branch-model`.
- Approval policy (`gin-workflow-approval-roles`).
- The requirement, plan, and roadmap gates, which stay on the parent.
- Any change to the `gates` metadata schema.

Confirmed summary (user, 2026-11-10): core fix only; for the `ship` gate the local HEAD comes from the git repository of the working directory when it belongs to that child (its main checkout or a linked worktree), else from the child's main checkout.

## Requirements

R1. A function `repo_for_pr(root, team, pr_url)` in `team.py` returns the expected repository URL and the directory whose HEAD the `ship` gate compares:
- When the pull request's repository id (`host.repo_id(pr_url, pr=True)`) equals the parent's (`host.repo_id(origin_url(root))`), it returns the parent's origin URL and `root`, exactly as today.
- Otherwise, when `root` has a `workspace.repos` manifest, it finds the entry whose `host.repo_id(entry.url)` equals the pull request's repository id. The directory is the current working directory's git top level when that directory shares the entry checkout's git common directory (the main checkout or a linked worktree of the child); otherwise it is the entry's checkout (`<root>/<path>`).
- When no entry matches, or there is no manifest, it returns the parent's origin URL, so the existing refusal "PR belongs to <actual>, not this repository (<expected>)" stays.
- When the matching entry is not cloned, it raises `TeamError` naming `gin workspace clone <path>`.

R2. `check_approval` compares the pull request's repository with the expected URL from R1 instead of always `origin_url(root)`. When no repository matches in a workspace, the refusal also lists the workspace repository ids it accepts.

R3. `verify_gate` resolves R1 once per call for the `ship` and `shipped` gates and, for `ship`, takes the local HEAD from the directory of R1. The `requirement_confirmed`, `plan_approved`, and `roadmap` gates keep comparing with the parent's origin.

R4. `gin team check <url> --gate ship` and `gin record shipped --evidence <url>` pass for an approved child pull request whose head matches the child HEAD of R1, when run from the parent, the child's checkout, or a linked worktree of the child.

R5. `docs/guides/team.md`, the ship part of `docs/guides/workspace.md`, and the `team` skill state that a ship pull request may belong to the parent or to a workspace child, and which HEAD is compared.

## User Stories

### US-1: Ship a child pull request
As a backend engineer in a workspace, I want the ship gate to accept my service's pull request, so that a track in a child repository can be shipped in team mode.

Acceptance criteria:
- From the child's track worktree, `gin team check <child-pr-url> --gate ship` exits 0 for an approved pull request whose head equals the worktree HEAD.
- With a different head, it fails with "PR head ... is not local HEAD ..." naming the child HEAD.
- `gin record shipped --evidence <child-pr-url>` records the gate for a merged, approved child pull request.

### US-2: Clear refusals
As a tech lead, I want a pull request from an unknown repository or an uncloned child refused with a clear reason, so that I know what to fix.

Acceptance criteria:
- A pull request from a repository not in `workspace.repos` and not the parent is refused with "not this repository" and the accepted repository ids.
- A pull request of a listed but uncloned child fails with a message naming `gin workspace clone <path>`.
- Parent pull requests behave exactly as before.

## Errors and compatibility

- Without a workspace, behaviour is unchanged: the expected repository is the parent's origin and HEAD comes from `root`.
- A host that cannot fetch the pull request still raises `HostUnavailable`, as today.
- No JSON, config, or Beads metadata change; gin-console is unaffected.

## Testing

- `tests/workflow_core/test_team_gates.py`, with a workspace fixture whose child entry has a real-looking URL and a `git init` checkout:
  - child pull request passes `ship` from the parent, the child checkout, and a linked worktree of the child;
  - head mismatch against the child HEAD is refused;
  - unlisted repository refused with the accepted ids;
  - uncloned child raises the `gin workspace clone` message;
  - `record shipped` with a child pull request passes;
  - existing ship gate tests unchanged.
- `gin docs check` on the changed docs pages.

## Open Technical Questions

## Assumptions

- `host.repo_id` normalises SSH, scp-style, and HTTPS URLs to the same id, so the entry URL in `workspace.repos` may use any of these forms.
- The working directory is the process working directory of the `gin` command.
