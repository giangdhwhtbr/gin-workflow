---
name: mockup
description: Build an interactive, self-contained HTML mockup of a capability's screens in a dated asset folder, revise it with the BA until confirmed, and mark the folder confirmed so SDD discuss can cite it.
---

# Mockup

`/gin-ba:mockup <capability> [--date YYYY-MM-DD]`. Writes `<specs>/<cap>/assets/<date>/mockup/index.html` and the `description.md` of that folder. `/gin:discuss` cites the confirmed screens as the source of requirements. Never commit.

1. Preconditions. On a failure, stop and name the fix:
   - `gin` is on `PATH`; otherwise `./install.sh --plugin gin-workflow` from a gin-workflow clone.
   - `gin state --format json` reports `project.layout: sdd`; otherwise say the BA skills need the SDD layout (`/gin:migrate-specs` moves a project to it).
   - `<specs>` is `artifacts.specs` (default `docs/specs`). Normalize the capability to `[a-z][a-z0-9-]*`. Without a folder `<specs>/<cap>/`: when an existing capability nearly matches (`report`, `reports`), use it and say so; otherwise ask the user to confirm the new name before writing anything.
2. The folder is `<specs>/<cap>/assets/<date>/`, with `<date>` from `--date` or today.
   - Missing: create it and write `description.md` from `gin specs template iteration.md`, with `{{capability}}` and `{{date}}` filled in. `Kind:` is `new` when the capability has no earlier dated folder, else `change`. `Previous:` is the latest earlier dated folder as `assets/<YYYY-MM-DD>/`, or `none`. Ask once who gave the inputs for `Source:` (for example `customer workshop`).
   - Its `description.md` reads `Confirmed: <YYYY-MM-DD>`: the folder is frozen. Stop and ask for a new date; never edit it.
   - Otherwise continue in it and read the mockup already there. A `description.md` without a `Confirmed:` line gets `Confirmed: no` after `Previous:`.
3. Read the inputs: the BA's description in the conversation; `description.md` and `mockup/index.html` of each earlier dated folder of the capability; the images under any `legacy/` folder of the capability; and the product's existing UI in the repository (design tokens, theme, component library, stylesheets).
4. Pick the visual source, in order: the existing UI when the repository has one (reuse its colours, type, spacing, and components); else the `frontend-design` skill when the harness provides it; else [references/mockup-html.md](references/mockup-html.md). A missing `frontend-design` skill is not an error.
5. Write `mockup/index.html` as one self-contained file:
   - inline CSS and JavaScript; no network request, no CDN, no web font;
   - fictional sample data, never real customer data;
   - one `<section id="<screen-id>">` per screen, ids in `[a-z][a-z0-9-]*`, shown by the URL hash, with a navigation list of all screens;
   - the empty, error, and loading states of a screen that has them, switchable on the page;
   - no embedded image larger than a small icon: draw a placeholder box with its caption instead.
   The skeleton, hash routing, and state switch are in [references/mockup-html.md](references/mockup-html.md); follow it also when another visual source sets the look.
6. Give the BA the path and the screen ids (`mockup/index.html#<screen-id>`), then revise on each piece of feedback. Edit only this dated folder.
7. When the BA explicitly confirms the mockup, fill `description.md`:
   - `## Summary`: what the screens cover, in two or three sentences;
   - `## Changes`: for `change`, what differs from `Previous:`, one line per screen; for `new`, `none (first version)`;
   - `## Files`: one line per screen, `` `mockup/index.html#<screen-id>` `` and the screen's purpose;
   - `Confirmed: <today>` in place of `Confirmed: no`.
   Report the path and the next command, `/gin:discuss`.
8. Never confirm on the BA's behalf: only the BA's explicit answer sets `Confirmed:`. Do not commit; the BA reviews and commits the folder.
