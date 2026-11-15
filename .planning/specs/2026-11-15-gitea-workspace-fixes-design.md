# Gitea host and workspace clone fixes

Workflow: gitea-workspace-fixes
Kind: technical
Status: confirmed by the user on 2026-11-15.

## Goal and scope

Fix the bug reports still open on `master` (`b07d6a87`): three Gitea host defects that block or silently disable team mode on Gitea, and `gin workspace clone` on an empty remote.

In scope:

- B5. `gt api` pagination: `hosts/gitea.py` `_PAGES` sends `-f limit=50` with `--paginate`; gt 1.2.0 then treats the request as one with a body and refuses it (`--paginate requires a body-free GET request`). Every Gitea gate that reads PR approvals, `specs status`, the closed-PR search, and the branch PR list fail.
- B2. Spec-review evidence: the `sdd` skill (`discuss` step 5, `pr`) asks for evidence `<pr url> <merge commit>`; in team mode `authorize_record` passes the whole string to the host as one PR URL and Gitea's `_pull_ref` rejects it. The error text `_EXPECTED` says `https://` although `http://` is accepted.
- B4. Gitea CODEOWNERS: `team_init.codeowners()` writes GitHub-style globs (`/src/**`, `/docs/specs/`) for every host. Gitea 1.27 reads each pattern as an anchored `regexp2` expression (leading `!` and `/` removed, `\` dropped by the tokenizer, `#` starts a comment, whitespace splits tokens), so `/**` lines are invalid and directory lines never match: no rule takes effect.
- B1. `workspace_cli.clone` always runs `git clone --branch <default_branch>`, which fails on a remote with no refs. `workspace.ensure_gitignore` appends a new path after a blank line at the end of `.gitignore` instead of inside the block under its header.
- The user docs that describe these behaviours.

Out of scope:

- Items of the same bug reports already fixed on `master`: the `fcntl` locks (`locking.py`), `atomic._fsync_directory` on Windows, the bash worktree scripts (`gin worktree create`), the `team claim`/`task close` actor (`tasks._bd_env`), the `check-plan` file-list false positive, the `record` failure message, and the `orchestrate` routes order.
- Renaming either `"stage"` key of `gin state --format json` (out of scope in earlier specs too; gin-console parses that JSON).
- `scripts/merge-integration.sh` (referenced nowhere; left untouched as in earlier specs).
- A `gin setup doctor` check for a `workspace.repos` remote with no default branch (it would need a network call on every doctor run).
- CODEOWNERS output for GitHub, GitLab, and CodeCommit.

## Approach

### A. Gitea host (`plugins/gin-workflow/src/scripts/workflow_core/hosts/gitea.py`, `team.py`, `team_init.py`, `hosts/base.py`, `skills/sdd/SKILL.md`)

B5:

- `_PAGES = ["-X", "GET", "-f", "limit=50", "--paginate", "--slurp"]`. All four callers (PR reviews, PR files, closed-PR search, branch PR list) use `_PAGES`, so no call site changes.

B2:

- `team.authorize_record`: when `evidence` is a single string, the PR URL to verify is its first whitespace-separated token. The recorded evidence string stays as given. `shipped` with several `--evidence` values is unchanged.
- `skills/sdd/SKILL.md`, `discuss` step 5 (`pr`): in team mode the `requirement-confirmed` evidence is `<pr url>` (the PR proof stores the merge commit); otherwise `<pr url> <merge commit>` as today. The file stays within its token budget.
- `_EXPECTED = "http(s)://<host>[/<subpath>]/<owner>/<repo>/pulls/<n>"`.

B4:

- `HostFiles` gains `codeowners_syntax: str = "glob"` as its last field, so existing adapters need no change. `Gitea.files` sets `"regex"`.
- `team_init.regex_pattern(glob: str) -> str`, a pure function that translates one CODEOWNERS glob as gin writes it into a Gitea pattern:
  - drop the leading `/`;
  - `**` → `.*`, `*` → `[^/]*`, `?` → `[^/]`;
  - a glob bracket expression `[...]` is kept as is;
  - each regex metacharacter `. + ( ) { } | $` becomes a one-character class (`[.]`), never a backslash escape, because Gitea's tokenizer drops `\`;
  - a trailing `/` (a directory) becomes `/.*`; the lone root pattern (`/**` from `reroot`) becomes `.*`.
  - A glob containing whitespace, `#`, `\`, or `^` raises `TeamError` naming the glob: Gitea's tokenizer splits on whitespace, treats `#` as a comment, and drops `\`, and a literal `^` has no backslash-free form.
- `team_init.codeowners()` passes every pattern it writes (area globs, rerooted child globs, the plans directory, the spec directories) through `regex_pattern` when the host's `codeowners_syntax` is `"regex"`. The header line and the owner lists are unchanged.
- `team codeowners --check` and `codeowners_drift` compare against the new output, so a file written by an older gin reports drift until `gin team init` runs again. A file whose marker line was removed by hand is not overwritten without `--force`, as today.

### B. Workspace clone (`workspace_cli.py`, `workspace.py`)

- `clone`: the first attempt is unchanged (`git clone --branch <default_branch> [--depth 1] <url> <target>`). Only when it fails, run `git ls-remote --heads <url>`. When that succeeds with empty output (the remote has no branches):
  1. `git clone <url> <target>` without `--branch` or `--depth`;
  2. `git -C <target> symbolic-ref HEAD refs/heads/<default_branch>`;
  3. the row is `{"path": ..., "status": "cloned", "empty": true}`, and `notes` gains `<path>: empty remote; the first commit on <default_branch> creates the branch`.
  The repository then goes through the same hook installation and `.gitignore` step as any clone. In every other case (`ls-remote` fails, or the remote has refs but not `default_branch`) the original clone error is raised, with the existing `cloned so far` suffix. A fallback clone or `symbolic-ref` that fails raises its own stderr the same way.
- `workspace.branch`: when `rev-parse --abbrev-ref HEAD` fails (an unborn `HEAD`), return the branch `git symbolic-ref --short HEAD` names, so `workspace status` shows `default_branch` for an empty clone.
- `ensure_gitignore`: when the header is already in the file, insert the missing lines right after the last non-blank line of the header's block (the block ends at the first blank line after the header, or at the end of the file); text after the block keeps its place. Without the header, keep today's behaviour (blank line, header, lines at the end).

### C. Docs

- `docs/guides/team.md` and `.vi.md`, Gitea host section: `team init` writes `.gitea/CODEOWNERS` as Gitea regular expressions; Gitea only requests reviews from code owners (1.27 has no "require code owner approval"); after upgrading, rerun `gin team init` (with `--force` when the marker line was removed).
- `docs/guides/workspace.md` and `.vi.md`: `gin workspace clone` accepts an empty remote, points `HEAD` at `default_branch`, and the first commit pushed creates that branch.
- `docs/reference/cli.md`: the `workspace clone` row mentions the `empty` field.

## Risks and rollback

- B5 depends on gt honouring `-X GET` with `-f` fields as query parameters; verified by hand in both reports (`gt api -X GET ... -f limit=50 --paginate --slurp` returns `[[...]]`).
- B4 changes generated output: Gitea teams see `team codeowners --check` drift (and the CI step from `templates/team/gitea-ci.yml` fails) until they rerun `gin team init`. That failure is the intended signal; the docs say so.
- B4 is checked with Python `re`, not .NET `regexp2`. The constructs emitted (`.*`, `[^/]*`, `[^/]`, `[x]`, literal text) mean the same in both, and both reject `**`.
- B1 adds one `ls-remote` network call only after a failed clone; a successful clone costs nothing extra.
- Rollback: revert the merge commit; no stored data or config format changes.

## Testing

- `tests/workflow_core/test_hosts_gitea.py`: the argv of reviews, files, closed-PR search, and branch PR list contains `-X GET` before `--paginate`; `_pull_ref` error text contains `http(s)://`.
- `tests/workflow_core/test_team_gates.py`: single evidence `"<pr url> <sha>"` verifies the URL alone and records the full string; an evidence whose first token is not a PR URL is still refused.
- `tests/workflow_core/test_team_init.py`:
  - `regex_pattern` table: `src/**` → `src/.*`, `docs/specs/` → `docs/specs/.*`, `.planning/plans/` → `[.]planning/plans/.*`, `src/*.py` → `src/[^/]*[.]py`, `a?b` → `a[^/]b`, `[ab]c` kept, `/**` → `.*`; whitespace, `#`, `\`, or `^` raises `TeamError`.
  - For a Gitea team (root and `child`), every non-comment line's pattern compiles as `^<pattern>$` with `re`, contains no `\` or `#`, matches `src/a.txt`, `docs/specs/x.md`, `.planning/plans/p.md` where expected, and does not match `xplanning/plans/p.md`.
  - GitHub and GitLab output is byte-identical to today's.
- `tests/workflow_core/test_workspace_cli.py`, with a local bare remote (`git init --bare`):
  - an empty remote clones, `HEAD` is `refs/heads/master`, the row has `"empty": true`, the note is printed, the path is in `.gitignore`, and `workspace status` reports it present;
  - a non-empty remote with a wrong `default_branch` still raises the original clone error.
- `tests/workflow_core/test_workspace.py`: `ensure_gitignore` with the header followed by other entries inserts the new line inside the block; without the header it appends as today.
- `sdd` skill needle for the team-mode evidence sentence; `test_token_budget.py`, docs tests, and `python3 -m pytest -n auto` pass at ship.

## Open Technical Questions
