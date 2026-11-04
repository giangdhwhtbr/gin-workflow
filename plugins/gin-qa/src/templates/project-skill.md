---
name: {{name}}-qa
description: QA process of this repository - which gin-qa skill writes cases, builds tests, runs manual cases, files bugs, and makes reports. Use for any testing or QA request here.
---

# QA process

Written by `/gin-qa:setup`; rerun it to update this file. This file holds the process only. The rules are in `{{guidelines}}` and the process for people in `{{readme}}`: read both before any QA work.

1. Test cases for a capability or a change: `/gin-qa:cases <capability>` or `/gin-qa:cases --change <epic>`.
2. Tests for the cases: `/gin-qa:e2e <capability>` for `e2e` cases; `/gin-qa:tests <capability> --type <type>` for each type under `## Automated types` in the guidelines. `manual` cases have no tests.
3. Manual run: `/gin-qa:run <capability>`; it records each result and files a bug bead for each failure.
4. Report: `/gin-qa:report [capability]`.
5. Before handing work over, `gin-qa cases check` must print `ok`.

Read case data only through the gin-qa CLI (`gin-qa cases export --format json`, `gin-qa cases plan`, `gin-qa e2e plan`, `gin-qa tests plan`). Never parse case files yourself, and never write `Result`, `Run`, or `Bug` lines.
