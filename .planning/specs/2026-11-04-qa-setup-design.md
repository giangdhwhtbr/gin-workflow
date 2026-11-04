# gin-qa project setup

Epic: gin-workflow-qa-setup
Status: confirmed by the user on 2026-11-04.

## Goal and scope

A project gets its QA rules and process from one interview: `/gin-qa:setup` writes `qa/guidelines.md`, `qa/README.md`, and a thin project-local skill, and leaves them passing `gin-qa cases check`. A project that already has these files gets the missing parts added and the managed parts updated, never overwritten.

In scope:
- The skill `plugins/gin-qa/src/skills/setup/SKILL.md`.
- The template `plugins/gin-qa/src/templates/project-skill.md`, and three new sections in `templates/guidelines.md` (`## Types`, `## Manual runs`, `## Bugs`) plus a `## Process` section in `templates/qa-readme.md`.
- A `## Types` check in `gin-qa cases check` (`plugins/gin-qa/src/scripts/gin_qa/cases.py`, `cli.py`).
- The `cases` and `run` skills read the new sections.
- The OpenCode bundle renames gin-qa's `setup` skill to `gin-qa-setup` (`install.sh`, `install.ps1`), so it does not shadow gin-workflow's `setup`.
- `docs/guides/qa.md`, `docs/guides/customizing-templates.md`, `docs/reference/skills.md`, `docs/reference/cli.md`, `docs/roles.md`; the rebuilt `dist/`.

Out of scope: generating the project skill for harnesses other than Claude Code (`docs/guides/qa.md` says where to copy it); running `gin-qa e2e init` (`/gin-qa:e2e` already runs it on first use); a `gin-qa setup` CLI command; syncing bugs to an external tracker; the existing OpenCode clash where gin-qa's `report` is also renamed `gin-workflow-report` (reported, not fixed here).

## Requirements

Guidelines sections (`templates/guidelines.md`)
- `## Types`: one bullet per case type, `` - `<type>`: <what the type covers> ``. The template lists `e2e` and `manual`. The top bullet "Type is the file suffix ..." is replaced by a pointer to this section.
- `## Manual runs`: the run reference `/gin-qa:run` proposes (default `manual <YYYY-MM-DD>`), and when manual runs happen (free text, "not set yet" in the template).
- `## Bugs`: bugs are Beads beads filed by `gin-qa cases bug`; whether an external tracker reference is required, and its pattern (for example `PROJ-NNNN`); "none" in the template.
- `## Automated types` keeps its current format and parser (`tests.py:22`).

`## Types` check in `gin-qa cases check`
- The section runs from the `## Types` line to the next `## ` heading. Lines that do not start with `- ` are prose and ignored.
- A `- ` line must match `` - `<type>` `` optionally followed by `:` and text, with `<type>` matching `^[a-z][a-z0-9-]*$` (`cases.TYPE`); otherwise the finding is `<guidelines>:<line>: '## Types' entry is not "- `<type>`: <description>"`.
- A section with no entry gives `<guidelines>:<line>: '## Types' lists no types`.
- Each case whose type is not listed gives `<case file>:<line>: <TC-ID>: type '<type>' is not listed under '## Types' in <guidelines>`. A flat-file case without a `Type:` field is not checked by this rule.
- No guidelines file, or no `## Types` section: the rule is skipped, so existing projects keep passing.
- The check runs in both layouts, before the legacy layout returns.

`/gin-qa:setup`
- Preconditions as in the other gin-qa skills: `gin-workflow` and `gin-qa` on `PATH`, `.agent-workflow/generated/effective-config.yaml` present; otherwise stop and name what to install or run.
- Paths: the guidelines file is `qa.guidelines` from `.agent-workflow/config.yaml` (default `qa/guidelines.md`); `README.md` sits next to it.
- It reads the existing guidelines, README, project skill, and `gin-qa cases export --format json`, and derives every answer it can: types from `## Types`, from a free-text type bullet, and from the case files on disk; automated types from `## Automated types`; the language from the `Language:` line.
- It asks, one question at a time and only for what is still unknown: the case types and what each covers; the language cases are written in; for each automated type other than `e2e` and `manual`, the `Tests:` globs and `Run:` command, proposed from the project's test runner as `/gin-qa:tests` step 3 does; the manual run reference and cadence; whether bugs need an external tracker reference and its pattern; when a report is made and who receives it.
- Managed parts: in the guidelines, the `Language:` line and the sections `Types`, `Automated types`, `Manual runs`, `Bugs`; in the README, `## Process`. For each managed part it shows the current and proposed text and writes only after the user confirms. Everything else in both files stays as it is. A free-text type bullet that `## Types` replaces is proposed for removal under the same confirmation.
- A type used by existing case files but left out of `## Types` is named to the user before writing, because `cases check` will report those cases.
- When the guidelines or README do not exist, they are created from `templates/guidelines.md` and `templates/qa-readme.md` with the answers filled in.
- `## Process` in the README states, for people: how cases are written (`/gin-qa:cases`), which skill builds the tests of each type (`/gin-qa:e2e`, `/gin-qa:tests --type <type>`), when manual runs happen (`/gin-qa:run`), how bugs are filed and referenced, and when a report is made and shared (`/gin-qa:report`).
- The project skill is `.claude/skills/<name>-qa/SKILL.md`, where `<name>` is the repository root's folder name in lower case with every run of characters outside `[a-z0-9]` replaced by `-` and leading or trailing `-` removed. It is written from `templates/project-skill.md`: a `name` and a description that triggers on testing or QA requests in this repository, the order of the gin-qa skills, the paths of the guidelines and README, and the rule that case data is read only through the gin-qa CLI (`gin-qa cases export --format json`). It copies no rule from the guidelines. An existing file is shown as current and proposed text and replaced only after confirmation.
- At the end it runs `gin-qa cases check`, and `gin-qa tests check` when `## Automated types` declares a type. A finding in a file setup wrote is fixed and the check rerun. A finding in an existing case file is reported, with the offer to add the missing type to `## Types`; setup does not edit case files.
- It reports the files created and changed and the check results. It does not commit.

Existing skills
- `cases`: the case type is one of the types listed under `## Types`. A case that needs a type not listed is written only after the user confirms adding the type to `## Types`. Without the section, the current rule (the type named in the guidelines) applies.
- `run`: the proposed run reference comes from `## Manual runs` when it names one, else `manual <YYYY-MM-DD>`. When `## Bugs` requires an external reference, a failed case asks for it and does not accept an empty answer, and the value is checked against the pattern when one is given; otherwise the reference stays optional.

OpenCode bundle
- `install.sh` and `install.ps1` rename gin-qa's `skills/setup` to `skills/gin-qa-setup` and its `name:` to `gin-qa-setup`, the way `report` is renamed today. gin-workflow's `setup` keeps its id.

## User Stories

### US-1: Set up QA in a new project
As a lead starting QA in a repository, I want one interview to write the guidelines, the README, and a project QA skill, so that the team and its agents follow the same process from the first case.

Acceptance criteria:
- In a repository with no `qa/` folder, `/gin-qa:setup` creates `qa/guidelines.md` with `Language:`, `## Types`, `## Automated types`, `## Manual runs`, and `## Bugs` filled from the answers.
- It creates `qa/README.md` with a `## Process` section naming the gin-qa skill for each step.
- It creates `.claude/skills/<name>-qa/SKILL.md` that points to the guidelines and README and copies none of their rules.
- `gin-qa cases check` exits 0 at the end.

### US-2: Bring an existing project up to date
As a lead whose repository already has `qa/guidelines.md`, I want setup to add only what is missing and show every change first, so that the rules the team wrote are kept.

Acceptance criteria:
- Answers already present in the files are not asked again.
- Each managed part is shown as current and proposed text, and nothing is written before the user confirms it.
- Sections setup does not manage, such as `## E2E specs`, are unchanged after setup.
- Case files are never edited by setup.

### US-3: Catch a case with an undeclared type
As a QA engineer, I want `gin-qa cases check` to report a case whose type the guidelines do not list, so that a misspelled suffix or an unagreed type is found before it is run.

Acceptance criteria:
- A case `TC-AUTH-001-login.ap.md` with `## Types` listing `api` and `manual` gives a finding naming the file, the TC-ID, and `ap`, and `check` exits 1.
- A malformed or empty `## Types` section gives a finding with the guidelines line.
- Guidelines without `## Types` give no type finding.

### US-4: Manual runs and bugs follow the team's rules
As a tester, I want `/gin-qa:run` to use the run reference and bug rules from the guidelines, so that every run and bug is named the way the team agreed.

Acceptance criteria:
- With `## Manual runs` naming a run reference format, `/gin-qa:run` proposes that reference instead of `manual <YYYY-MM-DD>`.
- With `## Bugs` requiring an external reference, a failed case is not filed until the tester gives one.

### US-5: Use setup in OpenCode without losing gin-workflow's setup
As an OpenCode user with both plugins installed, I want gin-qa's setup to have its own id, so that `@setup` still runs gin-workflow's setup.

Acceptance criteria:
- After `install.sh --plugin all` for OpenCode, gin-qa's skill is `gin-qa-setup` and gin-workflow's is `setup`.

## Errors and compatibility

- `cases check` keeps its exit codes: 0 ok, 1 findings, 2 usage or environment error. The `## Types` rule only adds findings, and only when the section exists, so current projects (gin-console has no `## Types`) keep passing.
- `cases export`, `e2e export`, `tests` output, and `report` are unchanged, so gin-console is not affected.
- Setup never writes a managed part without confirmation and never edits case files; a check finding in an existing case is reported, not fixed.
- The project skill holds process only; when plugin behavior changes, it still points to the plugin skills and CLI rather than to copied rules. That limits drift but does not prevent it: rerunning `/gin-qa:setup` shows the difference against the current template.
- gin-qa `VERSION` becomes `0.10` and the plugin `0.11.0`.

## Testing

`tests/gin_qa/` (the existing check tests, or a new `test_cases_types.py`):
- guidelines with `## Types` listing `e2e` and `manual`: a `.manual.md` case passes, a `.api.md` case gives the not-listed finding and exit 1;
- a `## Types` entry without backticks, and a section with only prose: one finding each, with the guidelines line;
- no `## Types` section, and no guidelines file: no type finding;
- a flat-file case without `Type:`: no type finding;
- the sdd layout reports the type finding together with the REQ findings.

`tests/gin_qa/test_packaging.py` lists the `setup` skill and the `project-skill.md` template; skill descriptions stay within the 1,000-character budget; `docs/reference/skills.md` names `setup`.

`tests/install_smoke_test.sh` and `tests/install_smoke_test.ps1`: the OpenCode install of gin-qa has `skills/gin-qa-setup/SKILL.md` with `name: gin-qa-setup`, and gin-workflow's `skills/setup` is untouched.
