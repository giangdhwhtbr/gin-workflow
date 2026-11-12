---
name: capture
description: Describe an existing feature from screenshots in a dated asset folder (per-screen fields, rules, open questions) and mark it confirmed by the BA so SDD discuss starts the rebuild from it.
---

# Legacy Capture

`/gin-ba:capture <capability> [--date YYYY-MM-DD] [code paths...]`. Copies the screenshots the BA names under `<specs>/<cap>/assets/<date>/legacy/`, reads them, and writes the `description.md` of that folder with `Kind: legacy`. `/gin:discuss` starts the requirements of a rebuild from it. Never commit.

1. Preconditions. On a failure, stop and name the fix:
   - `gin` is on `PATH`; otherwise `./install.sh --plugin gin-workflow` (Windows: `.\install.ps1 -Plugin gin-workflow`) from a gin-workflow clone.
   - `gin state --format json` reports `project.layout: sdd`; otherwise say the BA skills need the SDD layout (`/gin:migrate-specs` moves a project to it).
   - `<specs>` is `artifacts.specs` (default `docs/specs`). Normalize the capability to `[a-z][a-z0-9-]*`. Without a folder `<specs>/<cap>/`: when an existing capability nearly matches (`order`, `orders`), use it and say so; otherwise ask the user to confirm the new name before writing anything; a new name the user confirms is created with `--new-capability`.
2. The folder is `<specs>/<cap>/assets/<date>/`, with `<date>` from `--date` or today.
   - Add the screenshots the BA names, from inside or outside the repository: `gin specs assets add <cap> <files...> --legacy --date <date>`. It copies them under `<date>/legacy/`, accepts only `.png`, `.jpg`, `.jpeg`, `.webp`, or `.gif`, and writes `description.md` with `Kind: legacy`, `Previous:`, and `Confirmed: no` when it is missing. On exit 2, report its message and stop; a folder whose `description.md` reads `Confirmed: <YYYY-MM-DD>` is frozen: ask for a new date and never edit it.
   - With no files named and none under `<date>/legacy/`, ask the BA for the screenshot paths.
   - Ask once who gave the screenshots for `Source:`.
3. Read each screenshot in name order. Read the code paths the user named, and only those, to confirm a field's type, whether it is required, or a rule; never widen the search on your own.
4. Write `description.md` per [references/legacy-description.md](references/legacy-description.md):
   - keep the header lines and the template sections;
   - `## Summary`: what the feature does today, in two or three sentences;
   - `## Changes`: `none (as-is)`;
   - `## Files`: each file under `legacy/`, one line each, with the screen it shows;
   - `## As-is behaviour`: one `### <Screen>` per screen, with the screenshot file, the screen's purpose, a table `Field | Type | Required | Rule`, and the actions the screen offers;
   - `## Rules`: business rules seen across screens, each naming the screens or code paths it comes from;
   - `## Open questions`: everything the screenshots and code do not settle.
   Never guess: a cell the evidence does not settle reads `?` and gets an open question.
5. Show the description and revise it on the BA's feedback. Edit only this dated folder.
6. When the BA explicitly confirms the description, ask who else agreed (business owner, PM), then run `gin specs assets confirm <cap> --date <date> --agreed-with "<names>"`, omitting the flag when no one else agreed. Report the path and the next commands: `/gin-ba:mockup <cap>` for a redesign, or `/gin:discuss`.
7. Never confirm on the BA's behalf: only the BA's explicit answer runs `gin specs assets confirm`. Do not commit; `/gin:discuss` commits the confirmed folder with the change folder that cites it.
