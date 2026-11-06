# gin-ba plugin: mockup and legacy capture skills

Epic: gin-workflow-ba-plugin
Status: draft for user review.

## Goal and scope

A BA prepares the inputs of a capability before `/gin:discuss` writes requirements. Since `gin-workflow-spec-iterations`, those inputs live in dated folders `<specs>/<cap>/assets/<YYYY-MM-DD>/` with a `description.md` from `gin specs template iteration.md` (`.planning/knowledge/spec-asset-iterations.md`). Nothing yet produces a mockup or describes a legacy screen, and the SDD discuss step only lists asset paths per capability: it does not read `description.md` or a mockup, and no requirement cites the input it came from (`plugins/gin-workflow/src/skills/sdd/SKILL.md`, discuss steps 1 and 3).

This spec adds:
- a new add-on plugin `gin-ba` with two skills, `gin-ba:mockup` and `gin-ba:capture`, and no CLI or launcher;
- installer support for an add-on without a launcher;
- a `Confirmed:` line in the `iteration.md` template, so a confirmed input can be told from a draft;
- SDD discuss reading the confirmed inputs of the affected capabilities and citing them per requirement with a `Source:` line;
- the BA guide and the reference entries for the new plugin.

Out of scope:
- A BA CLI, including `specs assets new`: a dated folder is a `mkdir` plus `gin specs template iteration.md`.
- A `gin-ba:change` skill: a new dated folder plus discuss covers a customer change.
- Figma or other design-tool import.
- A lint for unconfirmed inputs, for `Source:` lines, or for mockup size.
- The legacy (`.planning`) layout: dated asset folders exist only with the SDD layout.
- The full documentation pass, which belongs to `gin-workflow-docs-refresh`.

## Requirements

### R1. Plugin layout

`plugins/gin-ba/` follows `plugins/gin-qa/`:
- `plugin.meta.json`, `src/.claude-plugin/plugin.json`, and `src/.codex-plugin/plugin.json` agree on name `gin-ba`, version `0.1.0`, description, author, and repository.
- `src/skills/mockup/SKILL.md` and `src/skills/capture/SKILL.md`, each at most 6,000 characters; the plugin's skill descriptions total at most 1,000 characters (`workflow_core.budget.description_chars`).
- `src/skills/mockup/references/mockup-html.md`: the HTML guidance used when the `frontend-design` skill is not available.
- `src/skills/capture/references/legacy-description.md`: the structure of a legacy `description.md` (R6).
- No `scripts/` directory, no agents.

`.claude-plugin/marketplace.json` lists `gin-ba` with `path: plugins/gin-ba/src`, after `gin-qa`. The plugin is built for the same platforms as `gin-qa` (Claude Code, Codex, OpenCode, Copilot, Antigravity).

### R2. Installer support without a launcher

`install.sh` and `install.ps1`:
- accept `--plugin gin-ba` (`-Plugin gin-ba`), and `all` installs `gin-workflow gin-qa gin-orchestrator gin-ba`;
- build and register `gin-ba` for each selected platform like `gin-qa`;
- install no launcher for `gin-ba`: nothing is written to `~/.local/bin/gin-ba` or `~/.local/lib/gin-ba/`;
- print `Warning: gin is not installed; gin-ba needs it (./install.sh --plugin gin-workflow).` when `gin` is neither at `~/.local/bin/gin` nor on `PATH`, as for `gin-qa`;
- remove `plugins/gin-ba/dist` and the registered plugin on `--uninstall`.

The add-on refresh loop (commit 44b215d) stays limited to add-ons with a launcher; `gin-ba` has no library copy that calls `gin`.

### R3. Preconditions of both skills

Both skills start by checking, and stop with a message naming the fix when one fails:
- `gin` is on `PATH`;
- `gin state --format json` reports `project.layout: sdd`;
- the capability name normalizes to `[a-z][a-z0-9-]*`; a capability without a folder under `artifacts.specs` is created only after the user confirms the name, and a name that nearly matches an existing capability uses the existing one, as SDD discuss step 1 does.

### R4. Dated folder rules

Both skills take `<cap>` and an optional `--date YYYY-MM-DD` (default: today). The folder is `<specs>/<cap>/assets/<date>/`.
- When the folder does not exist, the skill creates it and writes `description.md` from `gin specs template iteration.md`, with `Kind:` set by the skill (R5, R6) and `Previous:` set to the latest earlier dated folder of the capability, or `none`.
- When the folder exists and its `description.md` has `Confirmed: <YYYY-MM-DD>`, the folder is frozen: the skill stops and asks for a new date. A later round of inputs always gets a new dated folder.
- When the folder exists and is not confirmed, the skill continues in it.

### R5. gin-ba:mockup

1. Inputs: the BA's description in the conversation; `description.md` and the mockup of earlier dated folders of the capability; the product's existing UI (design tokens, components, styles in the repository, and screenshots under any `legacy/` folder of the capability).
2. `Kind:` is `new` when the capability has no earlier dated folder, else `change`.
3. Output: `<date>/mockup/index.html`, one self-contained file: inline CSS and JavaScript, no network requests, fictional sample data. Each screen is a `<section id="<screen-id>">` reachable by URL hash, so a requirement can cite `mockup/index.html#<screen-id>`. Screens show their empty, error, and loading states where the feature has them. Large images are not embedded.
4. Visual source, in order: the product's existing UI when the repository has one; the `frontend-design` skill when there is no existing UI and the harness provides it; otherwise `references/mockup-html.md`.
5. The skill iterates on the BA's feedback until the BA explicitly confirms. Then it fills `## Summary`, `## Changes` (for `change`), and `## Files` (one line per screen with its id) and sets `Confirmed: <today>`.
6. The skill does not commit. It reports the file path and the next command, `/gin:discuss`.

### R6. gin-ba:capture

1. Inputs: the images under `<date>/legacy/` (png, jpg, jpeg, webp, gif) and, optionally, code paths the user names, read only to confirm fields and rules. With no image there, or with images outside the repository, the skill stops and asks the BA to place the screenshots under `<date>/legacy/` first; it never copies files from outside the repository.
2. `Kind:` is `legacy`.
3. `description.md` keeps the template header and sections and adds, per `references/legacy-description.md`:
   - `## As-is behaviour`, with one `### <Screen>` per screen: the screenshot file, the screen's purpose, a table `Field | Type | Required | Rule`, and the actions it offers;
   - `## Rules`: business rules seen across screens;
   - `## Open questions`: anything the screenshots and code do not settle. The skill never guesses a field type or rule.
   `## Changes` reads `none (as-is)`; `## Files` lists each file under `legacy/`.
4. After the BA explicitly confirms the description, the skill sets `Confirmed: <today>`. It does not commit.

### R7. Core: confirmation and citation

Core files never name `gin-ba` (the rule `test_core_never_refers_to_gin_qa` enforces for `gin-qa` extends to it); they describe the artifacts only.
- `plugins/gin-workflow/src/templates/iteration.md` gains `Confirmed: no` after `Previous:`, with the comment saying it becomes the ISO date the BA confirmed the inputs, after which the folder is frozen.
- `plugins/gin-workflow/src/templates/spec-delta.md`: the comment adds that a requirement taken from an input carries `Source:` with backticked paths, optionally with `#<screen-id>`.
- `plugins/gin-workflow/src/skills/sdd/SKILL.md`, discuss: before writing requirements, read `description.md` and the mockup of each dated folder of the affected capabilities; cite only inputs with `Confirmed: <date>`, and ask the user about an unconfirmed one (confirm or leave out); turn `## Open questions` into clarifying questions or listed assumptions; each requirement taken from an input gets `Source:` in its block. The file stays within 6,000 characters (5,332 today); detail that does not fit moves to a reference file.
- `specs archive` already copies the whole requirement block, so the `Source:` line reaches the living spec and `specs export`. `lint_block` accepts the extra line (it only restricts sub-headings).

### R8. Documentation

- `docs/guides/ba.md` and `docs/guides/ba.vi.md`: the BA flow capture, mockup, discuss, diagrams, SRS export, with the commands, the dated folder rules, and the fallback when `frontend-design` is missing; added to the `mkdocs.yml` nav after the QA add-on.
- `docs/guides/sdd.md` and `.vi.md`: the `Confirmed:` line and the `Source:` line.
- `docs/reference/skills.md`: the two `gin-ba` skills. `README.md`: `gin-ba` in the plugin table. `docs/contributing.md`: `--plugin gin-ba` for the installer. `docs/concepts/architecture.md`: four plugins build the same way.
- Every page follows `plugins/gin-workflow/src/references/docs-style.md`.

## User Stories

### US-1: Mockup before requirements
As a BA, I want an interactive mockup of a capability that looks like our product, so that the customer confirms the screens before requirements are written.

Acceptance criteria:
- `gin-ba:mockup reports` in an SDD project writes `docs/specs/reports/assets/<today>/mockup/index.html` and a `description.md` with `Kind: new` and `Previous: none`.
- The mockup opens offline in a browser and each screen is reachable by `#<screen-id>`.
- After the BA confirms, `description.md` lists the screens with their ids and reads `Confirmed: <today>`.
- Running the skill again for that date stops and asks for a new date.

### US-2: Describe a legacy feature
As a BA on a legacy project, I want the existing screens described from screenshots, so that requirements for the rebuild start from what the system does today.

Acceptance criteria:
- With screenshots under `docs/specs/orders/assets/<date>/legacy/`, `gin-ba:capture orders --date <date>` writes `description.md` with `Kind: legacy`, one `### <Screen>` per screen with a fields table, `## Rules`, and `## Open questions`.
- With no image under `legacy/`, the skill stops and asks for screenshots.
- After the BA confirms, `description.md` reads `Confirmed: <today>`.

### US-3: Requirements cite their inputs
As a reviewer, I want each requirement to name the input it came from, so that I can check it against the mockup or the legacy description.

Acceptance criteria:
- SDD discuss on a capability with a confirmed dated folder writes requirement blocks with `Source:` lines naming `assets/<date>/...` paths.
- An input whose `description.md` reads `Confirmed: no` is not cited until the user confirms it.
- After `specs archive`, the living `spec.md` keeps the `Source:` lines.

### US-4: Install the add-on
As a developer, I want to install `gin-ba` like the other add-ons, so that the BA skills are available on every platform I use.

Acceptance criteria:
- `./install.sh --plugin gin-ba` registers the plugin and creates no `~/.local/bin/gin-ba`.
- Without `gin` installed, the installer prints the `gin-ba needs it` warning.
- `./install.sh --plugin all` includes `gin-ba`, and `--uninstall` removes `plugins/gin-ba/dist`.

## Errors and compatibility

- A project with the legacy layout: both skills stop and say the BA skills need `project.layout: sdd`.
- A frozen (confirmed) dated folder: the skill stops and asks for a new date; it never edits the folder.
- No `frontend-design` skill: the mockup follows the existing UI or `references/mockup-html.md`; this is not an error.
- Existing `description.md` files without a `Confirmed:` line: discuss treats them as unconfirmed and asks the user, so older folders keep working.
- A requirement block with a `Source:` line passes `specs lint` and `specs hash`; a `MODIFIED` block's base hash is taken from the living block as before.
- `gin-ba` installs without changing `gin` or its launcher; uninstalling it leaves the other plugins untouched.
- Risk: the `sdd` skill has 668 characters of budget left; the discuss text must stay short or move to a reference.
- Risk: a mockup can grow large; the skill keeps images out of it, and no lint enforces a size.

## Testing

- `tests/gin_ba/test_packaging.py`: the three manifests agree; the description and skill character budgets; the reference links of each skill equal the expected list and resolve; no `scripts/` directory; no file under `plugins/gin-workflow/src` contains `gin-ba`.
- The marketplace maps in `test_manifests_agree` of `tests/gin_qa/test_packaging.py` and `tests/gin_orchestrator/test_orchestrator_packaging.py` include `gin-ba`.
- A core test that `gin specs template iteration.md` prints `Confirmed: no`.
- The core skill budget test keeps `sdd/SKILL.md` within 6,000 characters.
- `tests/install_smoke_test.sh` and `tests/install_smoke_test.ps1`, with a temporary `HOME`: `--plugin gin-ba` builds `plugins/gin-ba/dist/claude-code` with both skills; no `~/.local/bin/gin-ba`; the warning with `gin` hidden from `PATH`; `all` includes `gin-ba`; `--uninstall` removes its dist.
- Review evidence, manual: in a temporary SDD project, run `gin-ba:capture` on two sample screenshots and `gin-ba:mockup` on one capability, confirm both, then run SDD discuss and show the `Source:` lines in the change folder's `02-spec-delta.md`.
