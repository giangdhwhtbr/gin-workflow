---
name: cases
description: Write or update test cases from gin-workflow specs — one block per case in qa/cases/<capability>.md, traced to REQ-IDs, checked by the gin-qa CLI.
---

# Test Cases

`/gin-qa:cases <capability>` or `/gin-qa:cases --change <epic>`. All commands are `gin-qa cases <command>`; exit 1 means findings to fix, exit 2 means wrong usage or a missing tool.

1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists. Otherwise stop and name what to install or run: `install.sh --plugin gin-qa` (or `--plugin all`) from a gin-workflow clone or through `remote-install.sh`, or `/setup`. Exit 2 mentioning `specs reqs` means gin-workflow is too old: reinstall it.
2. `plan <capability>` (or `plan --change <epic>`) `--format json` gives `cases` (the folder), `guidelines` (a file), and the work: `missing`, `stale`, `obsolete`.
3. Read the guidelines file. If it does not exist, create it from [guidelines.md](../../templates/guidelines.md) and tell the user to adapt it. Its rules override everything below.
4. Format: [cases.md](../../templates/cases.md). One file per capability, `<cases>/<capability>.md`, starting with `# Test cases: <capability>`. Each case: `### TC-<CAP>-NNN: <title>`, then `REQ: <REQ-ID>@<hash8>` (several separated by `, `), `Type:`, `Priority:`, any extra `Key: value` fields, then `Preconditions:` (optional, `- ` bullets), `Steps:` (`1.`, `2.`, …), `Expected:` (`- ` bullets).
5. `missing`: for each REQ, read its `source`; write at least one case per scenario, and boundary or error cases where the requirement implies them. Get each ID from `next-id <capability>`; never pick numbers yourself. Write the `REQ:` line with the `hash8` from the plan.
6. `stale`: re-read the REQ at `source`, update the case to match, then `pin <TC-ID>`. Never type a hash by hand.
7. `obsolete`: list the cases with their reason and ask the user whether to delete or keep each one. Never delete on your own.
8. Repeat `check` (add `--change <epic>` when scoped to a change) until it exits 0. Then report the cases added, changed, and removed.
9. Do not commit; the user reviews and commits.

Legacy layout (no REQ-IDs): cases use `Source: <spec path>#<heading>` instead of `REQ:`; `plan` has no work list and `check` covers structure and IDs only.

Reports and other formats: `export --format json` lists every case with its fields; build them from that.
