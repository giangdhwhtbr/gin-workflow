# Lanes

Read this in team mode. A lane is the tracks of one plan that one member does in one repository. It has one branch `feat/<topic>-<lane>` (`<topic>` is the plan file name without its date and without `.lane-<lane>`), one worktree `.planning/worktrees/<epic>-<lane>`, and one pull request. A track bead without a `Lane:` line was orchestrated before lanes: it is its own lane `t<N>` and keeps `feat/<topic>-t<N>` and `.planning/worktrees/<bead>`. The lead's plan may declare a lane and leave its tracks to the lane's owner, who writes them in a lane plan.

## Plan

- Every track's Metadata has `- **Lane**: <name>`: lowercase letters, digits, and `-`, never `t<digits>`. The area name is the usual choice. The tracks of a lane share `Owner:` and `Repo:`; a lane may span areas its owner may own.
- Add `## Contracts` before `## Tasks`, with one entry per interface that a track of one lane produces and a track of another lane consumes. An HTTP endpoint lists method, path, request, response, and error codes; anything else lists its exact names and types. The consuming track names the entry in its Interfaces and does not depend on the producing track.
- A track depends on a track of another lane only when it needs that lane's merged code, such as an end-to-end QA track.
- A contract entry changed after approval goes through a new plan PR.
- To leave a lane's tracks to its owner, add `## Lanes` before `## Contracts`, with one `### Lane <name>` per lane:
  ```markdown
  ### Lane be
  - **Owner**: em@corp.com
  - **Area**: backend
  - **Repo**: services/api
  - **Scope**: the login API and its tests
  - **Acceptance criteria**: POST /login answers 200 with a session and 401 on a wrong password
  - **Contracts**: produces `POST /login`
  - **Depends on lanes**: fe
  ```
  Repeat `Area:` per area; `Repo:` only in a workspace; `Depends on lanes:` only when the lane's tracks need another lane's merged code. A track whose `Lane:` names a declared lane has that lane's owner and repository, and the lead plans that lane here. A declared lane without tracks is planned by its owner (Lane plan). A plan with `## Lanes` needs no track.
- Answer only the technical questions that concern more than one area. Write a question for one lane as `- TQ-<n> (lane <name>): <question>` and leave it open for the lane's owner. `gin record plan-approved` accepts it open when the plan declares the lane, so pass `--plan <path>` with the PR URL; it refuses a question marked for a lane the plan does not declare. With `area_lead`, the lead of each declared lane's area approves the plan PR.

## Orchestrate

- Each track bead gets the label `lane:<lane>` and the line `Lane: <lane>` in its description, after the `Plan:` line.
- A dependency inside a lane is `gin task dep add <blocked> <blocker>`. For a dependency on a track of another lane, create a bead titled `external: <plan path>#<N>` and make it block the dependent track, with and without `team.beads_sync`. `gin team deps` closes it when a merged PR lists that track.
- For each declared lane without tracks, create one lane bead under the epic, titled `Lane <name>: <scope>`, with the labels `lane:<name>` and `area:<area>` per area, `--assignee <owner>`, and the description lines `Plan: <plan path>, Lane <name>` and `Lane: <name>` (in a workspace also `Repo: <path>`). It is not a track: it gets no `track:` label and no route.
- For each name in a lane's `Depends on lanes:`, create one bead titled `external: <plan path>#lane-<name>`, once per named lane. The dependent lane's tracks will depend on it. `gin team deps` closes it when lane `<name>` has no open bead and merged PRs list every track of it.

## Lane plan

- `gin team ready` lists your lane bead. `gin team claim <bead>` claims it with every open track of the lane and creates the lane's worktree. Run `/plan` for the lane in that worktree: record no gate and ask no other member.
- Write the lane plan next to the lead's plan as `<lead plan stem>.lane-<lane>.md`, with `Spec: <design doc path>` under its title and tracks in the schema of the `plan` skill, numbered from 1. Every track has the lane's `Lane:`, `Owner:`, and `Repo:`, one of its areas as `Area:`, and files inside that area; it uses only the `## Contracts` entries the lane's `Contracts:` names.
- Ask the user about each `- TQ-<n> (lane <lane>):` question of the design doc as the plan stage does, and write `Decision: <answer>` under it. Leave every other question alone.
- `gin team check-plan <lane plan>` must exit 0: it checks each track against the lane's declaration in the lead's plan, reports each question marked for the lane without a decision and each malformed question line, and refuses a `Spec:` path outside the repository. Then commit the lane plan and the design doc on the lane branch; when the lane's `Repo:` is a workspace child, on the parent's `feat/<topic>` instead. The lead reviews them with the lane's PR.

## Lane orchestrate

- Run `/orchestrate` for the lane plan in the lane worktree. While `gin team check-plan <lane plan>` exits 1, create nothing.
- Read the epic's children with `gin task list --parent <epic> --all --json`. For each track of the lane plan that has no bead with the line `Plan: <lane plan path>, Track <N>`, create one under the epic with that line and `Lane: <lane>` (in a workspace also `Repo:` and `Reads:`), the labels `track:<N>`, `area:<area>`, and `lane:<lane>`, and `--assignee <owner>`. Add the dependencies between them with `gin task dep add`, and make each track depend on every `external: <lead plan path>#lane-<name>` bead of the lane's `Depends on lanes:`.
- Write the routes of these tracks only and run `gin routes resolve --workflow-id <epic id> --tracks <file> --json`; it merges them into the workflow's assignment manifest.
- When every track has its bead, close the lane bead with `gin task close <lane bead> --reason "planned in <lane plan path>: <track bead ids>"`. Record no gate. After a failure, run it again: it creates only the missing beads.

## Execute

- `gin team claim <bead>` claims every open track of the bead's lane and creates or reuses the lane's worktree. It refuses when another member holds an unexpired lease on any of them. Claim again at the start of each track: it renews the lease and marks that track in progress.
- Run the lane's tracks in dependency order in that worktree. The reviewed diff of a track runs from the lane branch's head when the track started to the track's last commit. After the track closes, `git push -u origin feat/<topic>-<lane>` and go on to the next one.
- `gin goal --workflow-id <id>` covers the tracks assigned to you; `--lane <name>` picks one lane and also covers its unassigned tracks. It leaves out tracks that need a human or wait for another lane to merge.
- When the lane's PR has merged and tracks remain, the next `gin team claim` starts the branch again from the default branch. If the host kept the merged branch, delete it on origin before the next push. If the claim reports commits made after the merged PR, merge `origin/<default>` into the branch. Never force-push.

## Ship

- With a lane plan, `gin team check-plan <lane plan>` must exit 0 before the PR: ship stops while a question marked for the lane has no `Decision:`.
- Deliver the closed tracks of the lane that no merged PR lists yet; each needs its review approved or waived. Open tracks stay for a later PR of the same lane.
- Fill the generated PR template: `Plan:` with the plan path (the lane plan path for its tracks), `Tracks:` with every delivered track number (`gin team deps` and `gin team complete` read both), `Beads:`, and one line per track under `## Tracks`.
- A fix the PR reviewer asks for is committed on the lane branch and pushed. With `project.review_ledger: true`, first reopen the last approved track and have it reviewed again.
- After the merge, when the lane has no open track, run `gin worktree cleanup <epic>-<lane>` from the main checkout (in a workspace, `gin worktree cleanup --repository <repo> <epic>-<lane>` from the parent).
