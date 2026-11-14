# Learn comments: stages post findings on the bead, ship writes knowledge

Epic: gin-workflow-fgil
Kind: capability
Status: draft for user review.

## Goal and scope

Every lifecycle stage, on any machine, records reusable findings in one shared place: a `[gin learn]` comment on the workflow's bead, or, before a bead exists, a `## Learnings` line in the spec or plan. `/gin:ship` then turns them into `.planning/knowledge/` records, and its reminder works on every machine.

Problem (user, 2026-11-14): knowledge is captured only during execute and reconciled at ship; when earlier stages run on another member's machine, what they learned is lost or invisible. Checked on master `5290042b`:
- Capture is wired only into execute (`plugins/gin-workflow/src/skills/execute/SKILL.md:28`, "Record notable decisions or risks per `learn`") and reconcile into ship (`skills/ship/SKILL.md:37`). Discuss and plan have no capture step, and they forbid writing to the bead: discuss "never write a comment" (`skills/discuss/SKILL.md:14`), plan "write nothing to the spec or the bead" (`skills/plan/SKILL.md:16`).
- The `learn` skill (`skills/learn/SKILL.md`, 1,671 of 6,000 characters) writes `.planning/knowledge/<topic>.md` during execute; a record written on another member's unmerged branch reaches the others only with its pull request.
- The ship reminder `_knowledge_warning` (`workflow_core/lifecycle_cli.py:392-412`) needs an `orchestration.ready` event in the local `.agent-workflow/runtime/events.jsonl`. That event is not shared (only requirement, approval, and shipped are, through the epic bead), so the reminder never fires on a machine that did not orchestrate.
- Workers return an optional `knowledge_candidates` list (`skills/execute/references/result-contract.md:14`; `gin_orchestrator/worker_dispatch.py:432-446`) that nothing consumes; the `gin:developer` agent (`agents/developer.md`, 3,636 of 4,000 characters) reports no learnings.
- Comment tags are skill conventions read by the agent; no Python parses them. The established form is `[gin <tag>] <id>: <text>` (`[gin question]`, `[gin answer]`, `[gin accept]`, `[gin roadmap]`, `[gin ship]`). In team mode, Beads comments travel only through `gin team sync` (`workflow_core/team_beads.py:180-192`); a plain `gin task comment` does not push.
- A bead exists from the start for a roadmap epic and a standalone bead; with the SDD layout, discuss creates the epic after the design is confirmed (`skills/sdd/SKILL.md:12`); an ad-hoc workflow (`Workflow: <topic>`, legacy layout) has no bead until `/gin:orchestrate`.
- Budgets left (`tests/workflow_core/test_token_budget.py`): plan chain 413 characters, execute 404, review 215, ship 878, discuss 1,317; agents 4,000 each; all descriptions 158.

In scope:
- The `[gin learn]` format and capture rules in the `learn` skill.
- One short rule each in `discuss`, `plan`, `execute`, and the `gin:developer` agent; ship's reconcile and its post-approval path list.
- `_knowledge_warning` reading learn comments from the bead.
- Docs.

Out of scope:
- The reviewer posting learnings (the review chain has 215 characters left); execute may post findings from a review report.
- gin-console showing learnings.
- Creating the bead earlier for ad-hoc workflows.

Confirmed decisions (user, 2026-11-14): learnings are `[gin learn]` comments on the bead, and ship writes the knowledge records from them; before a bead exists, discuss and plan write the same line under `## Learnings` in the spec or plan; workers return learnings and the dispatching session posts them.

Rejected alternatives: every stage writing knowledge files directly (files on unmerged branches and the local-event reminder keep the cross-machine gap); `gin task remember` (Beads memories are not tied to an epic, so ship cannot tell which belong to it).

## Requirements

R1. Format. A learning is one line: `[gin learn] <stage> <track-id|->: <fact>. Evidence: <file:line | command | bead>`. `<stage>` is `discuss`, `plan`, `orchestrate`, `execute`, `review`, or `ship`; `-` stands for no track. One fact per line. The `learn` skill keeps today's rule for what counts as reusable knowledge.

R2. Where it goes. The `learn` skill's capture section says, in this order:
- With the Beads backend and a bead for the workflow (a roadmap epic, an SDD epic once created, a standalone bead, or the epic created by orchestrate), post the line with `gin task comment <bead> "<line>"`. A track's learning goes on its epic.
- With no bead yet (discuss or plan of an ad-hoc workflow), append the line under a `## Learnings` heading at the end of the spec or plan, which is committed with it.
- With the markdown backend (no comments), write or update the record in `.planning/knowledge/` directly, as today.
- In team mode, run `gin team sync` after posting.
- A failed `gin task comment` never blocks the stage: say so and write the line under `## Learnings` of the spec or plan instead when one exists, else in the handoff.

R3. Workers. A worker never posts. The `gin:developer` agent adds a `Learnings` item to its output (facts with evidence, or `none`). A worker dispatched through gin-orchestrator returns them in `knowledge_candidates` (objects with `fact` and `evidence`). The dispatching session posts each as a `[gin learn] execute <track-id>:` line (R2).

R4. Discuss. The sentence "never write a comment" becomes "write no comment except `[gin learn]` per `learn`". When discuss summarises an epic's comments, it leaves `[gin learn]` comments out of the summary and out of the `Comments considered:` count.

R5. Plan. "write nothing to the spec or the bead" allows `[gin learn]` comments and the `## Learnings` section. The check for comments newer than `Comments considered:` ignores `[gin learn]` comments, so a learning never stops plan.

R6. Execute. Line 28 says to post each worker's learnings and the session's own as `[gin learn]` per `learn`.

R7. Ship.
- Step 1: the paths that may change after the newest approved commit add `.planning/knowledge/`.
- Reconcile moves from step 7 to the end of step 1, before the options are presented, so the records land with any option (merge or pull request). Per `learn`: in team mode run `gin team sync` first; read every `[gin learn]` comment of the epic (`gin task comments <epic> --json`) and the `## Learnings` lines of the spec and plan; merge duplicates; write or update records in `.planning/knowledge/` (search first, as today); commit them on the feature branch. With no learnings, say so in one sentence. Step 7 keeps showing the `warnings` of `gin state`.
- The `learn` skill's reconcile section names the same two sources.

R8. Reminder. `_knowledge_warning`:
- With the Beads backend, it reads the comments of the epic `gin state` resolved (the recorded epic, or the shared epic in team mode) and warns `<n> learn comments not yet in <knowledge path>; reconcile knowledge (learn) before ship` when `implementation_complete` holds and at least one `[gin learn]` comment is newer than the last commit that changed the knowledge directory (or there is no such commit). A tracker failure or an epic it cannot resolve gives no warning.
- With the markdown backend, it keeps today's check (a local `orchestration.ready` and no knowledge commit since).
- The comment text test is `text.startswith("[gin learn]")` after stripping leading whitespace.

R9. Docs. `docs/concepts/lifecycle.md` (where learnings go and when ship writes them), `docs/reference/cli.md` (the warning), `docs/guides/team.md` and its `.vi.md` (sync after posting), and the `learn` row of `docs/reference/skills.md` and `.vi.md` if its description changes.

## User Stories

### US-1: A finding from discuss survives to ship on another machine
As a tech lead who ships an epic that a BA discussed on another machine, I want the BA's findings in front of me at ship, so that they become knowledge records.

Acceptance criteria:
- `/gin:discuss <roadmap-epic>` that finds a reusable fact posts `[gin learn] discuss -: <fact>. Evidence: <ref>` on the epic.
- `/gin:ship` of that epic, run on another machine after `gin team sync`, lists the comment and writes or updates a record under `.planning/knowledge/` that contains the fact.
- `gin state --format json --workflow-id <epic>` on that machine warns about the unreconciled learn comment until the record is committed, without any local `orchestration.ready` event.

### US-2: Learnings never interrupt planning
As a planner, I want learn comments to stay out of the comment summary and the new-comment check, so that plan does not stop each time someone posts a learning.

Acceptance criteria:
- An epic whose only comments newer than `Comments considered:` are `[gin learn]` comments goes through plan step 1 without asking whether to return to discuss.
- Discuss's comment summary and `Comments considered:` count leave `[gin learn]` comments out.

### US-3: Worker findings reach the bead
As a lead running execute, I want each worker's findings posted for it, so that workers on any harness need no tracker access.

Acceptance criteria:
- The `gin:developer` output has a `Learnings` item.
- A worker result with `knowledge_candidates` leads to one `[gin learn] execute <track-id>:` comment per candidate on the epic.

### US-4: No bead yet, or no comments
As a solo user, I want learnings kept when there is no bead or no comment support, so that nothing is lost.

Acceptance criteria:
- Discuss or plan of an ad-hoc workflow writes the line under `## Learnings` in the spec or plan, and ship reads it.
- With the markdown backend, capture writes the record directly and the reminder works as today.

## Errors and compatibility

- Projects without `[gin learn]` comments see no change, except that the Beads-backend reminder no longer fires on an epic with no learn comments; ship still runs reconcile.
- A failed comment never blocks a stage (R2).
- In team mode a learning is visible on another machine only after both sides run `gin team sync`; ship syncs first (R7).
- `## Learnings` is a new optional section; `gin specs lint` must keep accepting a spec or plan that has it.
- Older gin ignores `[gin learn]` comments; a mixed team still gets the comments, and only the reminder differs.

## Testing

- `tests/workflow_core/test_lifecycle_cli.py`: the reminder with the Beads backend (an unreconciled learn comment warns; a newer knowledge commit clears it; no learn comments, no warning; a tracker failure, no warning; the shared epic in team mode with no local event) and with the markdown backend (today's cases unchanged).
- `tests/workflow_core/test_skill_routing.py`: the new sentences in `learn`, `discuss`, `plan`, `execute`, `ship`, and `agents/developer.md`.
- `tests/workflow_core/test_epic_comments.py`: every existing needle still passes.
- `tests/workflow_core/test_specs.py`: a spec with a `## Learnings` section lints `ok`.
- `tests/workflow_core/test_token_budget.py`: every chain, agent, and description stays within budget.
- `gin docs check` on changed pages; full suite `python3 -m pytest -n auto`.

## Open Technical Questions
