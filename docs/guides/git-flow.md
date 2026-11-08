# Team git agreement

## Purpose and scope

This agreement says how the team branches, commits, opens, reviews, approves, and merges work. It binds every member of a project that has [team mode](team.md) on. Team mode holds the mechanics; this page holds the rules.

In this agreement, SHALL marks an obligation and SHALL NOT marks a prohibition. A member who breaks either has not met the agreement. Words that are neither describe a recommended default that the team may change.

You do not need to know git to follow it. The Host procedures section gives the steps on your host, and the appendix gives prompts that ask the AI agent to do the git work.

## Terms

- Branch: a named line of work, kept apart from the main line until it is merged.
- Base branch: the branch the team keeps as the agreed state of the project, usually `main` or `master`.
- Commit: one saved set of changes, with a message that says what changed.
- Pull request: a request to merge a branch into the base branch, with a page for review. GitLab calls it a merge request.
- Review: reading the changes in a pull request and commenting on them.
- Approve: mark a pull request as acceptable to merge.
- Request changes: mark a pull request as not acceptable until the author changes it.
- Merge: add the changes of a branch to the base branch.
- Conflict: two branches changed the same lines, so the host cannot merge them without a person's choice.
- Gate: a checkpoint that gin records once the right people have approved the matching pull request.
- Approving role: a role listed for a gate in `team.approvals` of `.agent-workflow/config.yaml`.
- Track: one slice of a plan, delivered by one pull request.
- Bead: a task record in the project's task tracker.
- CI: automatic checks that run on every pull request.
- Host: the service that stores the repository and its pull requests: GitHub, GitLab, or AWS CodeCommit.
- Roadmap: the file that lists the epics the team plans to deliver.
- Epic: a large piece of work in the task tracker, made of several tracks.
- Spec: the file that states what a piece of work must do, in business terms.
- Requirement: one rule in a spec that the finished work must meet.
- User story: a short statement of who needs something and why, inside a spec.
- Acceptance criterion: a check that shows a requirement is met.
- Plan: the file that splits a spec into tracks and says who builds each one.
- Artifact: a roadmap, spec, plan, or track that the team reviews.
- Area: a part of the repository, with a lead role, that owns certain paths.
- Owner: the member who builds a track.
- Change folder: a folder in the SDD layout that holds one change to the specs.
- SDD layout: the repository layout that keeps living specs and change folders under `docs/`.
- Skill: a command of the AI agent that runs one stage of the work.
- BA: the business analyst, who writes and confirms specs.
- Developer: the member who builds a track.
- Tester: the member who checks that the work meets its spec.
- Tech lead: the member who writes the plan and leads the areas.

## Branches

The base branch is protected. Members SHALL NOT commit to it directly.

Every piece of work SHALL have its own branch, and the branch name SHALL show the kind of work.

| Kind of work | Branch name |
|---|---|
| Roadmap | `roadmap/<topic>` |
| Spec | `spec/<topic>`, or `spec/<epic>-<slug>` with the [SDD layout](sdd.md) |
| Plan | `plan/<topic>` |
| Track of a plan | `feat/<topic>-t<N>`, where `<N>` is the track number |
| Other work | `chore/<topic>` |

A branch SHALL carry one kind of work. A spec and a plan do not share a branch.

## Commits

Every commit message SHALL follow the convention set in `team.commit_convention`. The commit-msg hook that `gin team hooks` installs checks the message when you commit, and CI checks it again on the pull request.

With the value `conventional`, a message reads `type(scope): subject`, for example `docs(ba): add legacy edge cases`. With the value `none`, any message is accepted.

## Pull requests

Every artifact that has a gate SHALL reach the base branch through a pull request. The roles that approve come from the project's `team.approvals`.

| Artifact | Branch | Approved by | Gate |
|---|---|---|---|
| Roadmap | `roadmap/<topic>` | roles listed for `roadmap` | `roadmap` |
| Spec | `spec/<topic>` | roles listed for `requirement_confirmed` | `requirement_confirmed` |
| Plan | `plan/<topic>` | roles listed for `plan_approved` | `plan_approved` |
| Track | `feat/<topic>-t<N>` | roles listed for `ship` | `ship` |

The author SHALL fill the pull request template that `gin team init` writes. It has these fields:

- Summary: what changes and why, in two or three sentences.
- Plan: the plan file, or `none`.
- Tracks: the track numbers the pull request delivers, for example `1,2`. Other members' machines read this field, so write it exactly.
- Spec: the change folder or spec file, and the requirement IDs it touches.
- Beads: the bead IDs.
- Tests: the commands run and their result.
- Checklist: the commit convention is followed, every changed requirement has a test, and review comments are resolved.

## Review

Each pull request SHALL be reviewed by a member who holds an approving role for its gate. Each reviewer SHALL use the checklist for their role below. The checklists are the agreement's own rule and a team convention that the team may change.

The BA reviews a spec and checks that:

- every user story has acceptance criteria;
- every requirement has a `Source:` line that names where it comes from;
- the edge cases of the old system are covered.

The tester reviews a developer's pull request and checks that:

- every acceptance criterion in the spec is met;
- test evidence is present in the Tests field.

The tech lead reviews a plan and checks that:

- every track has an area and an owner;
- the tracks do not list the same file.

gin checks only part of this itself. `gin team check-plan` checks the area, owner, and file paths of a plan, and `gin specs lint` checks the structure of a spec. The rest depends on the reviewer.

To approve, open the pull request on the host and choose Approve. To request changes, leave comments on the lines concerned and choose Request changes. The Host procedures section has the steps.

A reviewer should respond within one working day. This is a convention the team may change; gin does not enforce it.

## Approval and merge rules

Members SHALL NOT approve their own pull request.

An approval counts only on the latest commit. A push after approval SHALL be followed by a new approval.

Members SHALL NOT merge a pull request without the required approvals and passing CI.

By convention, the author merges and deletes the branch after the merge. This is a team convention that the team may change; gin does not enforce it.

## Gate approval

A gate is recorded from an approved pull request. The stage skill runs the command; the member does not type it. Each skill passes the pull request URL as evidence.

| Gate | Pull request state | Recorded by |
|---|---|---|
| `roadmap` | Merged | The `roadmap` skill checks it with `gin team check <url> --gate roadmap`; it records no gate |
| `requirement_confirmed` | Merged | The `discuss` skill, with `gin record requirement-confirmed --evidence <PR url>` |
| `plan_approved` | Merged | The `plan` skill, with `gin record plan-approved --evidence <PR url>` |
| `ship`, before the merge | Open and approved on its latest commit | The `ship` skill checks it with `gin team check --gate ship <url>`; this records nothing |
| `ship`, after the merge | Merged | The `ship` skill, with `gin record shipped --evidence <PR url>`, for a standalone bead only |

An epic with child beads ships when the epic bead closes, so it needs no `gin record shipped`.

gin accepts the pull request only when all of these hold:

- it belongs to this repository and changes the gate's artifact; when it changes several specs or plans, `--spec` or `--plan` picks one;
- a member with an approving role has approved it, and that member is not its author;
- for `plan_approved`, `gin team check-plan` also passes, and `area_lead` means the area's lead approves.

When gin rejects the pull request, it lists the missing approvals. The member SHALL get those approvals and ask the skill to run again. The member SHALL NOT replace the evidence or ask for a waiver. [Team mode](team.md#what-changes-in-each-stage) holds the mechanics.

## Conflicts and changes after approval

When the host reports a conflict, the author SHALL update the branch from the base branch, resolve the conflict, and ask for review again. The earlier approval no longer counts.

A requirement change after plan approval SHALL go in a new change folder, not in the approved spec. [SDD living specs](sdd.md) shows how.

## Host procedures

Pick the section for your host. The `gh` and `glab` commands do the same as the web steps, and they need a login with `gh auth login` or `glab auth login`.

### GitHub

1. Create: open the repository, choose Pull requests, then New pull request. Set base to the base branch and compare to your branch. Fill the template and choose Create pull request.
2. Review: open the pull request and choose Files changed. Hover over a line, choose the plus sign, write a comment, and choose Start a review.
3. Approve: choose Review changes, choose Approve, and choose Submit review.
4. Request changes: choose Review changes, choose Request changes, write what must change, and choose Submit review.
5. Merge: after the required approvals and passing checks, choose Merge pull request.
6. Delete branch: choose Delete branch on the merged pull request.

```bash
gh pr create --base <base-branch> --title "<title>" --body "<description>"
gh pr review --approve
gh pr review --request-changes -b "<comment>"
gh pr merge --delete-branch
```

### GitLab

1. Create: open the project, choose Merge requests, then New merge request. Pick the source branch and the base branch as target, fill the template, and choose Create merge request.
2. Review: open the merge request and choose Changes. Hover over a line, choose the comment icon, and write a comment.
3. Approve: choose Approve at the top of the merge request.
4. Request changes: where your GitLab version offers it, choose Request changes when you submit the review. Otherwise, leave a comment that says what must change.
5. Merge: after the required approvals and passing pipeline, choose Merge.
6. Delete branch: keep Delete source branch ticked when you merge.

```bash
glab mr create --target-branch <base-branch> --title "<title>" --description "<description>"
glab mr approve
glab mr note -m "<comment>"
glab mr merge --remove-source-branch
```

On GitLab the project SHALL turn on Reset approvals on push, so that an approval counts only on the latest commit.

### AWS CodeCommit

1. Set up once: in the AWS console, open CodeCommit, then Approval rule templates, and create a template that names the approving roles and the number of approvals. Associate the template with the repository.
2. Create: open the repository, choose Pull requests, then Create pull request. Pick the destination branch and your source branch, and fill the title and description.
3. Review: open the pull request and choose Changes. Choose a line to add a comment.
4. Approve: choose Approve. To withdraw an approval, choose Revoke approval.
5. Request changes: leave a comment that says what must change, and do not approve.
6. Merge: when the approval rule is satisfied, choose Merge, and tick the option to delete the source branch.

gin verifies pull requests on GitHub and GitLab only. On CodeCommit, a gate whose approving roles are set in `team.approvals` cannot be recorded from a pull request yet. See [Gate approval](#gate-approval).

## Appendix: AI support

These prompts ask the AI agent to do the git work. Replace the text in angle brackets.

Open a pull request for the current work:

```text
Commit my changes with a message that follows the team convention, push the branch, and open a pull request. Fill the template: Summary, Plan, Tracks, Spec, Beads, and Tests.
```

Summarise a pull request for review:

```text
Summarise pull request <url> for review against its spec. List what changed, which acceptance criteria are met, and which are not.
```

Address the review comments:

```text
Read the review comments on <url>. Address each one, commit the fixes, push, and tell me which comments you resolved.
```

Update the branch and resolve conflicts:

```text
Update my branch from the base branch and resolve the conflicts. Show me each conflict and the choice you made before you commit.
```
