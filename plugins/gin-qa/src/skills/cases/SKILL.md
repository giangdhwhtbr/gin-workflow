---
name: cases
description: Write or update test cases from gin-workflow specs, one file per case in qa/cases/<capability>/, traced to REQ-IDs, checked by the gin-qa CLI.
---

# Test Cases

`/gin-qa:cases <capability>` or `/gin-qa:cases --change <epic>`. All commands are `gin-qa cases <command>`; exit 1 means findings to fix, exit 2 means wrong usage or a missing tool.

1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists. Otherwise stop and name what to install or run: `install.sh --plugin gin-qa` (or `--plugin all`) from a gin-workflow clone or through `remote-install.sh`, or `/setup`. Exit 2 mentioning `specs reqs` means gin-workflow is too old: reinstall it.
2. `plan <capability>` (or `plan --change <epic>`) `--format json` gives `cases` (the folder), `guidelines` (a file), and the work: `missing`, `stale`, `obsolete`.
3. Read the guidelines file. If it does not exist, create it from [guidelines.md](../../templates/guidelines.md) and tell the user to adapt it. Create `README.md` next to it from [qa-readme.md](../../templates/qa-readme.md) when that file does not exist. The guidelines' rules override everything below.
4. A flat `<cases>/<capability>.md` file must be split before cases are added: run `gin-qa cases split <capability>`. On refusal, show the findings to the user and stop.
5. Format: [cases.md](../../templates/cases.md). One file per case: `<cases>/<capability>/<TC-ID>-<slug>.<type>.md`. The slug is the title in lower-case words joined by `-`; the type is one of the types under `## Types` in the guidelines (without that section, the suffix the guidelines name). A case that needs a type not listed there is written only after the user confirms adding `- `<type>`: <what it covers>` to `## Types`. The file starts with `# TC-<CAP>-NNN: <title>`, then `- **Key:** value` field lines: `REQ` (`REQ-<ID>@<hash8>`, several separated by `, `), `Priority`, and any extra fields. No `Type:` line. Then `**Preconditions:**` (optional), `**Test data:**` (optional), `**Steps:**` (`1.`, `2.`, …), and `**Expected:**` (`- ` bullets).
6. `missing`: for each REQ, read its `source`; write at least one case per scenario, and boundary or error cases where the requirement implies them. Get each ID from `next-id <capability>`; never pick numbers yourself. Write the `REQ` field with the `hash8` from the plan.
7. `stale`: re-read the REQ at `source`, update the case to match, then `pin <TC-ID>`. Never type a hash by hand.
8. `obsolete`: list the cases with their reason and ask the user whether to delete or keep each one. Never delete on your own.
9. `Test data`: write it when a case needs specific records or values. Each item is a literal value or a rule for producing one ("a unique 15-digit IMEI per run"). Name credentials only by environment variable; never write a secret value.
10. Never edit `Result`, `Run`, or `Bug` lines by hand. `gin-qa cases result <TC-ID> <status> [--run <ref>] [--bug <id>|none]` writes them.
11. Repeat `check` (add `--change <epic>` when scoped to a change) until it exits 0. Then report the cases added, changed, and removed.
12. Do not commit; the user reviews and commits.

Legacy layout (no REQ-IDs): cases use `Source: <spec path>#<heading>` instead of `REQ:`; `plan` has no work list and `check` covers structure and IDs only.

An HTML report: `/gin-qa:report`. A manual run that records results and files bugs: `/gin-qa:run`. Other formats: `export --format json` lists every case with its fields, `result`, `run`, `bug`, and `test_data`; build them from that.
