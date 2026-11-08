# BA asset intake: CLI commands for dated spec asset folders and a lint-enforced freeze

Epic: gin-workflow-tp83
Status: draft for user review.

## Goal and scope

With the SDD layout, every batch of inputs for a capability (requirements, screenshots of an existing feature, a mockup) goes into a dated folder `<specs>/<cap>/assets/<YYYY-MM-DD>/` with a `description.md` from the `iteration.md` template. Today a person or an agent builds that folder by hand:
- the gin-ba `capture` skill (step 2) asks the BA to move screenshots under `<date>/legacy/` and never copies files from outside the repository; it writes `description.md` itself and works out `Kind:` and `Previous:`;
- the gin-ba `mockup` skill (step 2) and the `sdd` skill (discuss, step 3) do the same, the latter with `git mv`;
- `docs/guides/ba.md` and `docs/guides/sdd.md` tell the BA to place files by hand.

No code reads `Kind:`, `Previous:`, or `Confirmed:`. Lint checks only that a dated folder has a `description.md` (`lint_iterations`, `scripts/workflow_core/specs.py:353`); a misnamed folder is skipped silently. A confirmed folder is "frozen" only in skill text, so nothing stops an edit to it.

This spec adds:
- `gin specs assets add`, which validates the capability, creates the dated folder, copies the files in, and writes `description.md`;
- `gin specs assets confirm`, which marks a folder confirmed;
- a lint check that reports any change to a folder confirmed on the base branch;
- skill and docs updates so agents and BAs use the commands instead of building folders by hand.

Decisions confirmed with the user:
- One module `scripts/workflow_core/specs_assets.py` and a nested subcommand `gin specs assets add|confirm` (approach 1), not flat commands and not skill text only.
- The freeze is enforced by the CLI and by lint against a base ref, not by the CLI alone.
- Files are copied, including from outside the repository; originals stay where they are.
- The scoped commit for BAs and testers is out of this epic and goes into a separate epic.

Out of scope:
- A command that commits BA or tester output (separate epic).
- Deleting or moving the original files after a copy.
- The legacy layout: both commands need `artifacts.layout: sdd`, like every other `specs` command after `require_layout` (`specs_cli.py:95`).
- gin-console: it reads none of these files.

## Requirements

### R1. `gin specs assets add`
Usage: `gin specs assets add <cap> [files...] [--date YYYY-MM-DD] [--legacy] [--new-capability] [--repository PATH] [--format text|json]`.
- Requires the SDD layout (`require_layout(cfg, "sdd")`).
- `<cap>` must match `_CAP` (`specs.py:36`). When `<specs>/<cap>/` does not exist and `--new-capability` is not given, exit 2 with a message naming up to three close matches among the existing capability folders (`difflib.get_close_matches`), or saying there is none.
- `--date` must match `_ISO_DATE` (`specs.py:350`) and be a real calendar date; default is today. The target folder is `<specs>/<cap>/assets/<date>/`, and with `--legacy` the files go into `<date>/legacy/`.
- With `--legacy`, every file must end in `.png`, `.jpg`, `.jpeg`, `.webp`, or `.gif` (case-insensitive). Without it, any regular file is accepted.
- Exit 2 without writing anything when:
  - a source path is missing or not a regular file;
  - two sources share a file name, or a source's name already exists in the target folder;
  - the dated folder has a `description.md` whose `Confirmed:` value is an ISO date.
- Files are copied byte for byte (mode 0644), from anywhere on disk; a relative source path is relative to the current directory.
- When the dated folder has no `description.md`, the command writes it from `template_text(root, "iteration.md")` (`specs.py:205`) rendered with `capability` and `date` (`render`, `specs.py:214`), and sets:
  - `Kind:` `legacy` with `--legacy`; else `new` when the capability has no earlier dated folder; else `change`;
  - `Previous:` the latest dated folder of the capability before `<date>`, written `assets/<YYYY-MM-DD>/`, or `none`;
  - `Confirmed: no`.
- An existing `description.md` of an unconfirmed folder is left unchanged.
- With no files, the command only creates the folder and its `description.md` (the mockup flow).
- All writes (copied files and `description.md`) go through one `atomic_write_many` call like `new_change` (`specs.py:533`), so a failure writes nothing.
- Output: text prints the folder path relative to the repository, then one line per copied file; json prints `{"folder", "description", "created", "files"}` where `created` says whether `description.md` was written. The output never names a plugin other than gin-workflow.

### R2. `gin specs assets confirm`
Usage: `gin specs assets confirm <cap> --date YYYY-MM-DD [--repository PATH] [--format text|json]`.
- Requires the SDD layout. `--date` is required.
- Sets the `Confirmed:` line of `<specs>/<cap>/assets/<date>/description.md` to today's ISO date; adds the line after `Previous:` when it is missing, or after the first line when there is no `Previous:` line either.
- Exit 2 when the folder or its `description.md` does not exist, or the folder is already confirmed (the message names the date).
- Output: the `description.md` path and the date (json: `{"description", "confirmed"}`).

### R3. Lint: `Confirmed:` value
- `specs lint` and `specs lint --change` report a dated folder whose `description.md` has a `Confirmed:` line that is neither `no` nor an ISO date: `<path>:<line>: Confirmed: must be 'no' or a YYYY-MM-DD date`.
- A missing `Confirmed:` line means `no` (older files).

### R4. Lint: frozen folders
- Base ref: `--against` when given (living `specs lint` gains the flag); otherwise `default_base(root)` (`specs.py:578`).
- When no base can be found (`default_base` raises, or `--against` does not resolve), lint prints `warning: frozen asset check skipped: <reason>` to stderr and skips this check; other findings and the exit code are unchanged.
- For each dated folder whose `description.md` on the base ref has `Confirmed: <ISO date>`, every path under the folder that differs between the base and the working tree is a finding: modified, deleted, or added, including untracked files that are not ignored (`git ls-files --others --exclude-standard`).
- Finding: `<path>: assets/<YYYY-MM-DD>/ was confirmed on <date> at <base>; add a new dated folder`.
- R3 and R4 run in the `specs lint` command, with and without `--change`; `specs archive`, which calls `lint_change`, does not run them.
- A folder confirmed on the current branch but not yet on the base is not covered until it reaches the base; `assets add` still refuses it (R1). The docs state this limit.

### R5. Skills
- gin-ba `capture`: step 2 runs `gin specs assets add <cap> <files> --legacy [--date D]` with the files the BA names, from inside or outside the repository, and handles exit 2 by reporting the message; the rule "never copy from outside the repository" and the hand-written `description.md` steps go; asking once for `Source:` stays. Step 6 runs `gin specs assets confirm <cap> --date D` after the BA's explicit confirmation.
- gin-ba `mockup`: step 2 runs `gin specs assets add <cap> [--date D]`; step 7 runs `gin specs assets confirm`.
- `sdd` skill, discuss step 3: an input asset goes in with `gin specs assets add` (with `--legacy` for screenshots of an existing feature) instead of `git mv` or a hand-made folder; the original is deleted only when the user asks.
- `templates/iteration.md`: the comment names the two commands.
- Skills keep within their size budgets (`tests/gin_ba/test_ba_packaging.py`, skill budget tests).

### R6. Docs
- `docs/guides/ba.md` and `ba.vi.md`: the legacy and mockup steps use the commands; confirming uses `assets confirm`.
- `docs/guides/sdd.md` and its `.vi` pair, section "Images and mockups": the commands replace placing files by hand; the freeze is checked by lint against the base, with the limit from R4.
- `docs/reference/cli.md`: `specs assets add`, `specs assets confirm`, and `--against` on living `specs lint`.

## User Stories

### US-1: A BA adds screenshots without building folders
As a BA, I want to hand the agent screenshots from anywhere on my machine, so that they land in the right dated folder with a correct `description.md` without me creating folders.

Acceptance criteria:
- `gin specs assets add orders ~/Desktop/a.png --legacy` creates `<specs>/orders/assets/<today>/legacy/a.png` and a `description.md` with `Kind: legacy`, the right `Previous:`, and `Confirmed: no`.
- The original `~/Desktop/a.png` still exists.
- A `.pdf` with `--legacy`, a name clash, or a missing source exits 2 and writes nothing.

### US-2: A typo in the capability name is caught
As a BA, I want the command to stop on an unknown capability and suggest the close one, so that assets do not land in a misnamed folder that lint ignores.

Acceptance criteria:
- With `<specs>/orders/` present, `gin specs assets add order a.png` exits 2 and the message names `orders`.
- `--new-capability` creates `<specs>/order/assets/<date>/`.
- `Order` or `1orders` exits 2 for an invalid name.

### US-3: A confirmed folder stays frozen
As a BA, I want a confirmed folder to be protected, so that the inputs a design was built on cannot change after I confirmed them.

Acceptance criteria:
- `gin specs assets confirm orders --date 2026-11-07` sets `Confirmed: <today>`; running it again exits 2.
- `gin specs assets add orders b.png --date 2026-11-07` on that folder exits 2.
- When the folder is confirmed on the base branch, `gin specs lint` reports an edited, deleted, or added file in it and exits 1.
- Without a base (no `main`/`master` merge-base and no `--against`), lint warns on stderr and does not fail on this check.

### US-4: Agents use the commands
As a developer maintaining the skills, I want capture, mockup, and discuss (SDD) to call the commands, so that every folder is built the same way.

Acceptance criteria:
- The capture, mockup, and sdd skills name `gin specs assets add` and (capture, mockup) `gin specs assets confirm`, and no longer describe writing `description.md` fields or `git mv` by hand.
- The BA and SDD guides describe the commands and the freeze check.

## Errors and compatibility
- Usage and validation errors raise `SpecsError` and exit 2 with `specs error: <message>`, like the other `specs` commands (`specs_cli.py` `main`). Lint findings exit 1.
- On the legacy layout both commands exit 2 with the existing `require_layout` message.
- Existing dated folders and `description.md` files stay valid; a missing `Confirmed:` line reads as `no`.
- CI that runs `gin specs lint` on a shallow clone gets a warning instead of a failure from the freeze check.
- The new lint findings can fail a repository whose confirmed folders were edited after confirmation; that is the intended change.

## Testing
- `tests/workflow_core/test_specs_assets.py`, using `make_repo(layout="sdd")` from `tests/workflow_core/specs_fixtures.py` and a subprocess `run_specs` helper like the one in `tests/workflow_core/test_specs.py:21`:
  - add: `Kind` new/change/legacy; `Previous` latest earlier folder or `none`; copy from a temp dir outside the repository; adding to an unconfirmed same-date folder keeps `description.md`; no files creates folder and description only; json output;
  - add refusals (exit 2, nothing written): bad extension with `--legacy`, duplicate names, existing name, missing source, confirmed folder, unknown capability with suggestion, invalid capability, invalid date, legacy layout;
  - confirm: sets today's date, inserts a missing line, refuses a second confirm, a missing folder, or a missing description.
- Lint tests (in the same file or `test_specs.py`): malformed `Confirmed:`; a folder confirmed on `main` then edited, deleted from, or added to on a branch is reported by living and `--change` lint; an unconfirmed folder is not; a folder confirmed only on the branch is not; no merge-base prints the warning and does not change the exit code; `--against` on living lint.
- Update `tests/gin_ba/test_ba_packaging.py` content needles for the changed capture and mockup steps, and any skill-routing or docs-coverage test that the new commands touch.

## Open Technical Questions
