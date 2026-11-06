---
name: capture
description: Describe an existing feature from screenshots in a dated asset folder (per-screen fields, rules, open questions) and mark it confirmed by the BA so SDD discuss starts the rebuild from it.
---

# Legacy Capture

`/gin-ba:capture <capability> [--date YYYY-MM-DD] [code paths...]`. Reads the screenshots under `<specs>/<cap>/assets/<date>/legacy/` and writes the `description.md` of that folder with `Kind: legacy`. `/gin:discuss` starts the requirements of a rebuild from it. Never commit.

1. Preconditions. On a failure, stop and name the fix:
   - `gin` is on `PATH`; otherwise `./install.sh --plugin gin-workflow` from a gin-workflow clone.
   - `gin state --format json` reports `project.layout: sdd`; otherwise say the BA skills need the SDD layout (`/gin:migrate-specs` moves a project to it).
   - `<specs>` is `artifacts.specs` (default `docs/specs`). Normalize the capability to `[a-z][a-z0-9-]*`. Without a folder `<specs>/<cap>/`: when an existing capability nearly matches (`order`, `orders`), use it and say so; otherwise ask the user to confirm the new name before writing anything.
2. The folder is `<specs>/<cap>/assets/<date>/`, with `<date>` from `--date` or today.
   - Its `description.md` reads `Confirmed: <YYYY-MM-DD>`: the folder is frozen. Stop and ask for a new date; never edit it.
   - The screenshots are the files under `<date>/legacy/` ending in `.png`, `.jpg`, `.jpeg`, `.webp`, or `.gif`. With none, stop and ask the BA to put the screenshots there first. When the BA names files outside the repository, ask them to move the files there; never copy from outside the repository.
   - Without `description.md`, write it from `gin specs template iteration.md`, with `{{capability}}` and `{{date}}` filled in, `Kind: legacy`, and `Previous:` set to the latest earlier dated folder as `assets/<YYYY-MM-DD>/`, or `none`. Ask once who gave the screenshots for `Source:`. A `description.md` without a `Confirmed:` line gets `Confirmed: no` after `Previous:`.
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
6. When the BA explicitly confirms the description, set `Confirmed: <today>` in place of `Confirmed: no`. Report the path and the next commands: `/gin-ba:mockup <cap>` for a redesign, or `/gin:discuss`.
7. Never confirm on the BA's behalf: only the BA's explicit answer sets `Confirmed:`. Do not commit; the BA reviews and commits the folder.
