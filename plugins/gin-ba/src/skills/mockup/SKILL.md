---
name: mockup
description: Build an interactive, self-contained HTML mockup of a capability's screens in a dated asset folder, revise it with the BA until confirmed, and mark the folder confirmed so SDD discuss can cite it.
---

# Mockup

`/gin-ba:mockup <capability> [--date YYYY-MM-DD]`. Writes `<specs>/<cap>/assets/<date>/mockup/index.html` and the `description.md` of that folder. `/gin:discuss` cites the confirmed screens as the source of requirements. Never commit.

1. Preconditions. On a failure, stop and name the fix:
   - `gin` is on `PATH`; otherwise `./install.sh --plugin gin-workflow` (Windows: `.\install.ps1 -Plugin gin-workflow`) from a gin-workflow clone.
   - `gin state --format json` reports `project.layout: sdd`; otherwise say the BA skills need the SDD layout (`/gin:migrate-specs` moves a project to it).
   - `<specs>` is `artifacts.specs` (default `docs/specs`). Normalize the capability to `[a-z][a-z0-9-]*`. Without a folder `<specs>/<cap>/`: when an existing capability nearly matches (`report`, `reports`), use it and say so; otherwise ask the user to confirm the new name before writing anything; a new name the user confirms is created with `--new-capability`.
2. When the BA says the new screens copy the legacy ones without change, write nothing: the confirmed capture folder is the input for `/gin:discuss`. Say so and stop.
3. The folder is `<specs>/<cap>/assets/<date>/`, with `<date>` from `--date` or today.
   - Run `gin specs assets add <cap> --date <date>`: it creates the folder and, when missing, `description.md` with `Kind:` (`new` or `change`), `Previous:`, and `Confirmed: no`. On exit 2, report its message and stop. Ask once who gave the inputs for `Source:` (for example `customer workshop`).
   - Its `description.md` reads `Confirmed: <YYYY-MM-DD>`: the folder is frozen. Stop and ask for a new date; never edit it.
   - Otherwise continue in it and read the mockup already there.
4. Read the inputs: the BA's description in the conversation; `description.md` and `mockup/index.html` of each earlier dated folder of the capability; the images under any `legacy/` folder of the capability; and the product's existing UI (design tokens, theme, component library, stylesheets). In a workspace (`workspace` in `gin state --format json`), that is the cloned `shape: frontend` child of `workspace.repos`; ask the BA which one when there are several. When it is not cloned, name `gin workspace clone <path>` and use the next visual source. Otherwise it is the repository.
5. Pick the visual source, in order: the existing UI found in step 4, when there is one (reuse its colours, type, spacing, and components); else the `frontend-design` skill when the harness provides it; else [references/mockup-html.md](references/mockup-html.md). A missing `frontend-design` skill is not an error.
6. Write `mockup/index.html` as one self-contained file:
   - inline CSS and JavaScript; no network request, no CDN, no web font;
   - fictional sample data, never real customer data;
   - one `<section id="<screen-id>">` per screen, ids in `[a-z][a-z0-9-]*`, shown by the URL hash, with a navigation list of all screens;
   - the empty, error, and loading states of a screen that has them, switchable on the page;
   - no embedded image larger than a small icon: draw a placeholder box with its caption instead.
   The skeleton, hash routing, and state switch are in [references/mockup-html.md](references/mockup-html.md); follow it also when another visual source sets the look.
7. Give the BA the path and the screen ids (`mockup/index.html#<screen-id>`), then revise on each piece of feedback. Edit only this dated folder.
8. When the BA explicitly confirms the mockup, fill `description.md`:
   - `## Summary`: what the screens cover, in two or three sentences;
   - `## Changes`: for `change`, what differs from `Previous:`, one line per screen; for `new`, `none (first version)`;
   - `## Files`: one line per screen, `` `mockup/index.html#<screen-id>` `` and the screen's purpose;
   - ask the BA who else agreed (business owner, PM, area lead);
   - in team mode, when a `team.areas` entry in `.agent-workflow/config.yaml` has a `paths` glob matching the frontend child's path (or the UI path read in step 4), ask the BA to get that area's `lead` role to agree first;
   - then run `gin specs assets confirm <cap> --date <date> --agreed-with "<names>"`, omitting the flag when no one else agreed.
   Report the path and the next command, `/gin:discuss`.
9. Never confirm on the BA's behalf: only the BA's explicit answer runs `gin specs assets confirm`. Do not commit; the BA reviews and commits the folder.
