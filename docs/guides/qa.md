# QA Add-on (`gin-qa`)

`gin-qa` is an optional plugin that writes test cases from your specs and turns end-to-end cases into Playwright specs with recorded evidence. It needs `gin-workflow` and is not installed by default.

## Install

From a clone of this repository, or remotely:

```bash
./install.sh --plugin gin-qa          # or --plugin all for both plugins
curl -sSL https://raw.githubusercontent.com/giangdhwhtbr/gin-workflow/master/remote-install.sh | bash -s -- --plugin gin-qa
```

This installs the plugin for each harness and links the `gin-qa` launcher into `~/.local/bin`.

## Test cases: `/gin-qa:cases`

`/gin-qa:cases <capability>` (or `--change <epic>`) writes cases for a capability's requirements into `qa/cases/<capability>.md` (`qa.cases`), following the team rules in `qa/guidelines.md` (`qa.guidelines`, created from a template on first use).

```markdown
### TC-AUTH-004: Fifth failed login locks the account
REQ: REQ-AUTH-003@1a2b3c4d
Type: e2e
Priority: high
Preconditions:
- a user with four failed attempts
Steps:
1. Log in with a wrong password
Expected:
- the account is locked for fifteen minutes
```

- `gin-qa cases plan` lists the work: requirements with no case (`missing`), cases whose requirement changed since they were pinned (`stale`), and cases whose requirement is gone (`obsolete`).
- IDs come from `gin-qa cases next-id <capability>`; `pin <TC-ID>` records the requirement's current hash after a case is updated.
- `gin-qa cases check` must exit 0. Obsolete cases are deleted only with your approval, and the skill never commits.
- In the legacy layout (no REQ-IDs) cases use `Source: <spec path>#<heading>` and `check` covers structure and IDs only.
- `gin-qa cases export --format json` feeds your own report tooling.

Requirements and their hashes come from the living specs, so the [SDD layout](sdd.md) gives the most traceability.

## End-to-end specs: `/gin-qa:e2e`

`/gin-qa:e2e <capability>` turns `Type: e2e` cases into Playwright specs under `qa/e2e/<capability>/` (`qa.e2e`), one spec per case:

- `gin-qa e2e init` copies the evidence fixture `qa/e2e/evidence.ts` (yours to edit) and git-ignores `qa/evidence/`.
- The skill builds each spec step by step against the running application, reading the ARIA snapshot (`NN.aria.yml`) and URL the fixture records after every step, and reviews the screenshots before reporting a case. Where the harness has subagents it works on several cases in parallel (`--parallel N`, default 3).
- `gin-qa e2e run` runs them; each run leaves a screenshot per step and a `result.json` per case (and per Playwright project when the config names projects) under `qa/evidence/`.
- `gin-qa e2e check --run <folder>` checks a run's evidence; `gin-qa e2e export --run <folder> --format json` exports it.

Your project provides `@playwright/test` 1.49 or later and its Playwright config (`baseURL`, browsers, video, trace).

## Commands

`gin-qa cases {plan,next-id,pin,check,export}` and `gin-qa e2e {init,plan,pin,run,check,export}`; exit 0 ok, 1 findings, 2 usage or environment error. See [CLI](../reference/cli.md#gin-qa) and the [`qa` configuration keys](../reference/config.md#qa).
