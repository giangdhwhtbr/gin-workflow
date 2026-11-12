---
name: report
description: Write an offline HTML report of the test cases, with charts, filters, and per-step e2e screenshots, into one folder to zip and share.
---

# QA Report

`/gin-qa:report [capability]`. The command is `gin-qa report`; exit 2 means no test cases in scope, wrong usage, or a missing tool.

1. Preconditions: `gin` and `gin-qa` are on `PATH`. Otherwise stop and name what to install: `install.sh --plugin gin-qa` (or `--plugin all`) from a gin-workflow clone or through `remote-install.sh`.
2. Run `gin-qa report [capability] --format json`. On exit 2, show stderr and stop.
3. Tell the user the `report` path (`index.html`), the number of cases and screenshots, and each run in `missing_evidence`: its folder is gone or unreadable, so those cases show their result without steps.
4. To share the report, run `gin-qa report [capability] --zip`: it also writes `<folder>.zip`, with every screenshot the page shows. The report lives under `evidence/` of the QA home, which `gin-qa report` adds to `.gitignore`; do not commit it. Publish it where the reviewer can open it: with CI, the job that runs the tests uploads the zip as an artifact (`docs/guides/qa.md`, Publish the evidence) and the approval comment gives the artifact URL; without CI, attach the zip to a pull request comment and give that comment's link.
5. Do not open a browser, and do not change any case file.
