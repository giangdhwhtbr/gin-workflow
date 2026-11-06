---
name: report
description: Write an offline HTML report of the test cases, with charts, filters, and per-step e2e screenshots, into one folder to zip and share.
---

# QA Report

`/gin-qa:report [capability]`. The command is `gin-qa report`; exit 2 means no test cases in scope, wrong usage, or a missing tool.

1. Preconditions: `gin` and `gin-qa` are on `PATH`. Otherwise stop and name what to install: `install.sh --plugin gin-qa` (or `--plugin all`) from a gin-workflow clone or through `remote-install.sh`.
2. Run `gin-qa report [capability] --format json`. On exit 2, show stderr and stop.
3. Tell the user the `report` path (`index.html`), the number of cases and screenshots, and each run in `missing_evidence`: its folder is gone or unreadable, so those cases show their result without steps.
4. To share the report, zip the folder that holds `index.html`: it contains every screenshot the page shows. It lives under the evidence folder (`qa/evidence/` by default), which `gin-qa e2e init` git-ignores; do not commit it.
5. Do not open a browser, and do not change any case file.
