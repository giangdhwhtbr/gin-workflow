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
- `gin goal --workflow-id <id>` covers the tracks assigned to you; `--lane <name>` picks one lane and also covers its unassigned tracks. It leaves out tracks that need a human or wait for another lane to merge.
- When the lane's PR has merged and tracks remain, the next `gin team claim` starts the branch again from the default branch. If the host kept the merged branch, delete it on origin before the next push. If the claim reports commits made after the merged PR, merge `origin/<default>` into the branch. Never force-push.

## Ship

- Deliver the closed tracks of the lane that no merged PR lists yet; each needs its review approved or waived. Open tracks stay for a later PR of the same lane.
- Fill the generated PR template: `Plan:` with the plan path, `Tracks:` with every delivered track number (`gin team deps` and `gin team complete` read both), `Beads:`, and one line per track under `## Tracks`.
- A fix the PR reviewer asks for is committed on the lane branch and pushed. With `project.review_ledger: true`, first reopen the last approved track and have it reviewed again.
- After the merge, when the lane has no open track, run `gin worktree cleanup <epic>-<lane>` from the main checkout (in a workspace, `gin worktree cleanup --repository <repo> <epic>-<lane>` from the parent).
