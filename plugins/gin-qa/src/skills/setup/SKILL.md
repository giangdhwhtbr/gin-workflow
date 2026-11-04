---
name: setup
description: Set up QA for a project from one interview - guidelines, README, and a project QA process skill.
---

# QA Setup

`/gin-qa:setup`. Writes the QA rules and process of this repository. It writes no case, test, or spec, and edits no case file.

1. Preconditions: `gin-workflow` and `gin-qa` are on `PATH` and `.agent-workflow/generated/effective-config.yaml` exists. Otherwise stop and name what to install or run: `install.sh --plugin gin-qa` (or `--plugin all`) from a gin-workflow clone or through `remote-install.sh`, or `/setup`.
2. Paths: the guidelines file is `qa.guidelines` in `.agent-workflow/config.yaml` (default `qa/guidelines.md`), and `README.md` sits next to it. The project skill is `.claude/skills/<name>-qa/SKILL.md`. `<name>` is the repository root's folder name in lower case, with each run of characters outside `a-z0-9` replaced by `-` and leading and trailing `-` removed.
3. Read what exists: the guidelines, the README, the project skill, and `gin-qa cases export --format json`. Take every answer they already give:
   - the types: from `## Types`, from a bullet that names the types, and from the `type` of each exported case;
   - the automated types: from `## Automated types`;
   - the language: from the `Language:` line;
   - the run reference and cadence: from `## Manual runs`;
   - the bug rules: from `## Bugs`;
   - the process: from the README's `## Process`.
4. Ask only what is still unknown, one question per message:
   - the case types and what each covers (`e2e` and `manual` are built in; others are names such as `api` or `unit`);
   - the language cases are written in;
   - for each type other than `e2e` and `manual`, its `Tests:` globs and `Run:` command. Propose them from the project's test runner and existing tests, in the form and under the rules of `/gin-qa:tests` step 3 (`{junit}` required, `{files}` optional and a whole argument, globs relative to the repository root);
   - the manual run reference (default `manual <YYYY-MM-DD>`) and when manual runs happen;
   - whether a bug needs an external tracker reference (`none`, `optional`, `required`) and its pattern as a regular expression;
   - when a report is made and who receives it.
5. The managed parts are the guidelines' `Language:` line, its sections `## Types`, `## Automated types`, `## Manual runs`, and `## Bugs`, and the README's `## Process`. A missing file is created from [guidelines.md](../../templates/guidelines.md) or [qa-readme.md](../../templates/qa-readme.md) with the answers filled in.
   - For each managed part, show the current and the proposed text, and write it only after the user confirms. Leave every other line of both files as it is.
   - A bullet that names the types, now replaced by `## Types`, is proposed for removal under the same confirmation.
   - A type used by an existing case but left out of `## Types`: name those cases before writing, because `cases check` will report them.
   - Formats, as in the template: `## Types` has one `` - `<type>`: <what it covers> `` line per type; `## Automated types` has one `### <type>` per type, as `/gin-qa:tests` step 3 writes it; `## Manual runs` has `- Run reference:` and `- When:`; `## Bugs` has `- Tracker:` and `- External reference:`; `## Process` keeps the template's lines with the cadence, the bug rule, and the report expectations filled in.
6. Write the project skill from [project-skill.md](../../templates/project-skill.md). Replace `{{name}}`, `{{guidelines}}`, and `{{readme}}` (the two paths from step 2), and change nothing else; copy no rule from the guidelines into it. When the file exists and differs, show both versions and replace it only after the user confirms.
7. Run `gin-qa cases check`, and `gin-qa tests check` when `## Automated types` declares a type.
   - A finding in a file you wrote: fix it and run the check again.
   - A finding in an existing case file: report it, and offer to add its type to `## Types`. Never edit a case file.
   - End when both print `ok`, or list only findings the user chose to keep.
8. Report the files created and changed and the check output. The project skill is written for Claude Code only; for other harnesses, `docs/guides/qa.md` says where to copy it. Do not commit; the user reviews and commits.
