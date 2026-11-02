# Review ledger: the cycle limit and how a review gets stuck

**Context**
During epic `gin-workflow-rm-windows-parity` (2026-11-02) track `.4` reached `routing.review.max_cycles` (3) with every finding terminal and could not be approved; the bead was closed by a human decision recorded in its notes (bug `gin-workflow-yjd8`, fixed 2026-11-02: at the limit `start-review` now starts a verification pass when the ledger has at least one finding and every finding is terminal; an open finding, or no finding at all, still refuses).

**Decision/Solution**
- `approve` is allowed only from `review-in-progress`; `start-review` is refused at the cycle limit while the bead is `review-requested` until a `record-human-decision` event exists; `record-human-decision` is accepted only for a finding in `human-decision-required`, a state no CLI subcommand produces; `init` is a no-op on an existing ledger, so `max_cycles` cannot be raised. A finding the reviewer adds in the last cycle therefore blocks approval even when it is a SUGGESTION, because the reviewer cannot move an `open` finding to a terminal state alone (the worker must `dispute-finding` or `propose-deferral` first).
- Operating rules when a cycle still has an open finding at the limit: in the last allowed cycle the reviewer records non-blocking remarks in the report, not as findings; a SUGGESTION raised earlier is closed by `propose-deferral` (worker) then `approve-deferral` (reviewer), which needs no lease when none is active; with `project.review_ledger` off, `task close` is not gated, so a human decision in the bead notes is the record.
- Recovery used for `.4`: move the stuck ledger directory to `<bead>-cycles-1-3` (keep it as evidence), run `init` again for the same bead and review ref at the integration branch HEAD, `checkpoint`, `transition-requested`, then one verification cycle by a fresh reviewer that confirms every archived finding and records only new remarks; `approve`, commit the ledger, `bd reopen <bead>` and `task close` with the new evidence, `push-refs`. This is a real re-review, not an edit of the hash chain.
- Ledger commands are written with literal flags; zsh does not word-split a `$CMD` variable, so `RL="python3 review-ledger.py"; $RL init ...` fails with exit 127.
- Parallel Bash calls that each start with `cd` share one shell and race; the Track 1 ledger was initialized inside the Track 3 worktree that way. Use `git -C`, `--repository`, or one sequential call per worktree.

**Consequences**
- Plan a review so that cycle 3 is a verification pass only.
- The lease TTL is 600 s: finish the analysis before `start-review`, then write the ledger entries.

**References**
- `plugins/gin-workflow/src/scripts/review_ledger/bead_fsm.py`, `finding_fsm.py`, `cli.py` (`start-review` guard)
- `.planning/reviews/gin-workflow-rm-windows-parity.4/review.md`
- Beads: `gin-workflow-yjd8`, `gin-workflow-rm-windows-parity.4`

**Scope**
Every review run through `review-ledger.py` in this repository.
