# Plan: Team workflow guide, milestones over sprints, default price catalog

Workflow: team-workflow-guide
Spec: .planning/specs/2026-11-01-team-workflow-guide-design.md

## Objective
A team can follow the rewritten brownfield walkthrough from a legacy Java JSP repository to a reviewed milestone 1; the only time-boxing concept is the milestone (`sprint:` labels are gone from skills, CLI and docs); `milestone close` records a reason and `milestone move` leaves a trace; `usage report` prices the common Claude, OpenAI and Gemini models without a repository price file.

## Goal
Copied from the spec:
- One guide (the brownfield walkthrough) with the prompt per stage, what it returns, the gate, and the mistakes to avoid, around a Java JSP modernization in a monorepo, with the stages missing today: repository strategy, roadmap overview, milestone planning, milestone review with spill-over.
- `sprint:<name>` is removed; milestones replace it in the roadmap skill, `usage report`, `progress` and `report`.
- `milestone close` requires a reason; `milestone move` appends a `milestone_moves` trace to the epic.
- The plugin ships a default price catalog; the repository file only overrides it; a dated model id prices as its undated prefix; each model reports `price_source`.

## Architecture
`S` = `plugins/gin-workflow/src`, `W` = `S/scripts/workflow_core`.
- `W/usage.py` owns prices (`Price`, `load_prices`, `cost`), per-model aggregation (`_by_model`), summaries and `report`. The default catalog is `W/usage_prices_default.yaml`, read by the same loader; `install.sh` already copies whole package directories (lines 506-509), so the YAML ships with no packaging change.
- `W/usage_cli.py` is the argparse front of `usage`; `UsageError` exits 2 (lines 82-87).
- `W/milestone_cli.py` owns milestone writes (`_move`, `_close`), the `bd` wrapper `_bd(root, argv, actor)`, and `_guard`, which returns the team member email as `actor` ("" outside team mode).
- Skills are Markdown under `S/skills/<name>/SKILL.md`; `dist/` is rebuilt by `install.sh`, never edited.
- Docs: `docs/starters/*.md` (walkthrough, strategy), `docs/reference/cli.md` (every command), `docs/guides/usage-report.md`, `docs/roles.md`, `docs/getting-started.md`.

## Tech Stack
Python 3 standard library plus the YAML loader already required by `usage.py` (`require_yaml`); `unittest` (`PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`); fake `bd` via `tests/workflow_core/team_fixtures.py` in `test_usage*.py`; real `bd` in `test_milestone_cli.py`; `tests/install_smoke_test.sh` checks built skills.

## Global Constraints
Copied from the spec:
- No change to the `gin-workflow milestone` schedule or JSON schema.
- No cross-repository dependency view; no gin-console change (analytics is `gin-console-unj`).
- No migration of existing `sprint:` labels; `--sprint` is removed, not aliased.
- `getting-started.md` changes only by a link to the walkthrough.
- No long-context, batch, fast-mode or regional price tiers in the catalog.
- The default catalog adds no dependency.
- A failed `milestone_moves` write never undoes a move.

## Route Rubric
| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | `haiku` | `low` |
| Bounded implementation with a clear spec | `sonnet` | `medium` |
| Cross-module change, security, migration, concurrency | `opus` | `high` |

## Requirement Analysis
- Problem statement: the walkthrough teaches a label-only sprint and a PHP scenario, has no repository, milestone or spill-over stage; `usage report` is blind without a hand-written price file; milestone close and move leave no reason or trace.
- Success criteria: spec US-1 to US-5 acceptance criteria.
- Constraints: Global Constraints above.
- Non-goals: spec "Out of scope".

## Approach Options
### Option 1: Four code/skill tracks, then one docs track
- Summary: catalog and milestone report in `usage.py` (two tracks on disjoint ranges), milestone CLI track, roadmap skill track, then the walkthrough rewrite once every command it cites exists.
- Pros: each track has its own test cycle; the docs reviewer checks commands against a finished `cli.md`.
- Cons: five reviews.
### Option 2: One code track and one docs track
- Summary: all `usage.py`, `usage_cli.py`, `milestone_cli.py` and skill changes in one track.
- Pros: two reviews.
- Cons: a reviewer rejecting the trace format blocks the price catalog; one worker holds four unrelated contexts.
### Recommended Approach
- Selected option: Option 1.
- Rationale: independent rejection per concern; the two `usage.py` tracks edit disjoint ranges (`load_prices`/`_by_model` versus `report`).

## Scope
- In scope: spec R1-R16.
- Out of scope: spec "Out of scope".

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks 1 and 2 edit usage.py and test_usage.py; sequential dispatch keeps one merge order and lets the docs track cite a finished cli.md.
```

## Tasks

### Track 1: Default price catalog, prefix match, price_source
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/usage_prices_default.yaml`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/usage.py:25-26` (constant), `:40-64` (`Price.source`, `load_prices`, `price_for`), `:225-230` (`_by_model`)
  - Modify `docs/guides/usage-report.md:36-45` (Prices section)
  - Test `tests/workflow_core/test_usage.py:41-52` (`test_load_prices`), `:61-77` (document shape)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change in one module with a clear spec; the prefix rule and override order have listed edge cases.
- **Acceptance criteria**: spec US-5; R13-R16.
- **Estimated complexity**: medium

Steps:
1. Write the catalog file from the table in spec R13, one row per model id (expand the grouped rows: `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`, `claude-opus-4-5`, `claude-sonnet-4-6`, `claude-sonnet-4-5`, `gemini-3.8-flash`, `gemini-3.6-flash`, `gpt-5.1`, `gpt-5`). Header comment: `# Default price catalog, USD per million tokens, standard tier, checked on 2026-11-01 against the vendor pages named per row. .agent-workflow/usage-prices.yaml overrides by model id.` Each row ends with `# <source URL>` plus the note from the table where one exists. Shape per row: `claude-opus-5-5: {input: 4, output: 20, cache_read: 0.2, cache_write: 5}`.
2. Failing tests in `test_load_prices` (replace the body):
   ```python
   def test_load_prices(self):
       with tempfile.TemporaryDirectory() as tmp:
           repo = Path(tmp)
           defaults = usage.load_prices(repo)
           self.assertEqual(usage.Price(4, 20, 0.2, 5, "default"), defaults["claude-opus-5-5"])
           for model in ("claude-fable-5-1", "claude-haiku-5-5", "gpt-5.6-sol", "gpt-6-astra", "gemini-2.5-pro"):
               self.assertEqual("default", defaults[model].source, model)
           write(repo, usage.PRICES_FILE, "prices:\n  claude-opus-5-5: {input: 3, output: 15, cache_read: 0.3, cache_write: 3.75}\n  m1: {input: 1, output: 2, cache_read: 0, cache_write: 0}\n")
           prices = usage.load_prices(repo)
           self.assertEqual(usage.Price(3, 15, 0.3, 3.75, "repo"), prices["claude-opus-5-5"])
           self.assertEqual("repo", prices["m1"].source)
           self.assertEqual(prices["claude-sonnet-4-5"], usage.price_for(prices, "claude-sonnet-4-5-20250929"))
           self.assertEqual(prices["m1"], usage.price_for(prices, "m1-2"))
           self.assertIsNone(usage.price_for(prices, "m10"))
           self.assertIsNone(usage.price_for(prices, "codex-auto-review"))
           write(repo, usage.PRICES_FILE, "prices:\n  m1: {input: lots, output: 15, cache_read: 0, cache_write: 0}\n")
           with self.assertRaises(usage.UsageError):
               usage.load_prices(repo)
           write(repo, usage.PRICES_FILE, "- not a mapping\n")
           with self.assertRaises(usage.UsageError):
               usage.load_prices(repo)
   ```
   In `test_document_shape_and_unpriced_models` add `self.assertEqual("none", doc["models"]["m2"]["price_source"])` and, for the priced model of that test, `self.assertEqual("repo", doc["models"]["m1"]["price_source"])` (that test writes a repository price for `m1`; keep it). Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_usage -k load_prices -k document_shape`: fails on `Price(..., "default")` and `price_for`.
3. Code in `usage.py`:
   ```python
   PRICES_FILE = ".agent-workflow/usage-prices.yaml"
   DEFAULT_PRICES = Path(__file__).with_name("usage_prices_default.yaml")

   @dataclass(frozen=True)
   class Price:
       input: float
       output: float
       cache_read: float
       cache_write: float
       source: str = "repo"

   def _parse_prices(text: str, label: str, source: str) -> dict[str, Price]:
       try:
           loaded = require_yaml().safe_load(text) or {}
       except Exception as error:  # yaml.YAMLError without importing yaml here
           raise UsageError(f"{label}: {error}") from error
       prices = loaded.get("prices", {}) if isinstance(loaded, Mapping) else None
       if not isinstance(prices, Mapping):
           raise UsageError(f"{label}: expected 'prices:' mapping model names to prices")
       result: dict[str, Price] = {}
       for model, entry in prices.items():
           values = [entry.get(key) if isinstance(entry, Mapping) else None for key in _TOKENS]
           if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 for value in values):
               raise UsageError(f"{label}: {model} needs non-negative numbers for {', '.join(_TOKENS)}")
           result[str(model)] = Price(*(float(value) for value in values), source)
       return result

   def load_prices(repo: Path) -> dict[str, Price]:
       """The shipped catalog, overridden by the repository file where both name a model."""
       prices = _parse_prices(DEFAULT_PRICES.read_text(encoding="utf-8"), DEFAULT_PRICES.name, "default")
       path = Path(repo) / PRICES_FILE
       if path.is_file():
           prices.update(_parse_prices(path.read_text(encoding="utf-8"), PRICES_FILE, "repo"))
       return prices

   def price_for(prices: Mapping[str, Price], model: str) -> Price | None:
       """Exact id, else the longest key that the id extends with `-<suffix>` (dated Claude ids)."""
       if model in prices:
           return prices[model]
       keys = [key for key in prices if model.startswith(key + "-")]
       return prices[max(keys, key=len)] if keys else None
   ```
   In `_by_model`: `price = price_for(prices, model)` then `by_model[model] = {**totals, "cost": cost(totals, price), "price_source": price.source if price else "none"}`. Every other `prices.get(model)` call in the file (grep) becomes `price_for(prices, model)`.
4. Run the two tests (pass), then `python3 -m unittest tests.workflow_core.test_usage tests.workflow_core.test_usage_cli` (pass; a test that asserts an exact per-model dict gains `"price_source"`).
5. Docs `usage-report.md` Prices section: the plugin ships a catalog (`workflow_core/usage_prices_default.yaml`, checked on 2026-11-01, standard tier, Anthropic 5-minute cache writes, OpenAI cache writes at 1.25x input, Google cache writes 0); the repository file overrides by model id and adds models; the prefix rule with the `claude-sonnet-4-5-20250929` example; `price_source` values `default`, `repo`, `none`; prices change and the catalog is an estimate, not a billing source. Commit: `feat(usage): default price catalog with repo override, prefix match and price_source`.

### Track 2: usage report, progress and report by milestone
- **Dependencies**: Track 1 (same files; merge order)
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/usage.py:347-357` (`report` signature and selection)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/usage_cli.py:36` and `:80`
  - Modify `plugins/gin-workflow/src/skills/progress/SKILL.md:14`, `plugins/gin-workflow/src/skills/report/SKILL.md:14`
  - Modify `docs/reference/cli.md:342-345`, `docs/reference/skills.md` (the `progress` and `report` rows)
  - Modify `tests/install_smoke_test.sh:181`
  - Test `tests/workflow_core/test_usage.py:277-292`, `tests/workflow_core/test_usage_cli.py:101-108`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded replacement of one selector with a clear spec and an existing test to mirror.
- **Acceptance criteria**: spec US-4; R9, R10, the `cli.md`/`skills.md` parts of R5.
- **Estimated complexity**: low

Steps:
1. Failing test: rename `test_sprint_report_covers_labelled_epics_and_their_tracks` to `test_milestone_report_covers_its_epics_and_their_tracks`:
   ```python
   rows = self.rows()
   rows.append({"id": "m1", "title": "M1", "issue_type": "milestone", "status": "open", "labels": None})
   rows[0]["parent"] = "m1"
   rows.append({"id": "ep2", "title": "Next", "issue_type": "epic", "status": "open", "parent": "m2"})
   rows.append({"id": "ep4", "title": "Unassigned", "issue_type": "epic", "status": "open"})
   self.rules[0]["stdout"] = rows
   fake_cli(self.bin, "bd", self.rules)
   out = usage.report(self.repo, milestone="m1")
   self.assertEqual(["ep1", "ep1.1"], [row["bead"] for row in out["beads"]])
   self.assertEqual(["ep1.2"], out["not_collected"])
   self.assertEqual(3.0, out["totals"]["cost"])
   with self.assertRaisesRegex(usage.UsageError, "ep4 is not a milestone"):
       usage.report(self.repo, milestone="ep4")
   with self.assertRaisesRegex(usage.UsageError, "m9 is not a milestone"):
       usage.report(self.repo, milestone="m9")
   ```
   In `test_usage_cli.py:104` replace `--sprint s1` with `--milestone m1` (still exits 2 with `--epic`), and add `done = run_cli(self.repo, "usage", "report", "--sprint", "s1", env=self.env); self.assertEqual(done.returncode, 2); self.assertIn("--milestone", done.stderr)` (argparse prints the usage line, which names `--milestone`).
2. Code, `usage.py`:
   ```python
   def report(repo: Path, *, bead: str | None = None, epic: str | None = None, since: date | None = None,
              milestone: str | None = None) -> dict[str, Any]:
   ...
       elif milestone is not None:
           target = next((row for row in rows if row.get("id") == milestone), None)
           if target is None or target.get("issue_type") != "milestone":
               raise UsageError(f"{milestone} is not a milestone")
           epics = {row["id"] for row in rows if row.get("issue_type") == "epic" and row.get("parent") == milestone}
           selected = [row for row in rows if row.get("id") in epics or row.get("parent") in epics]
   ```
   `usage_cli.py:36` → `scope.add_argument("--milestone", metavar="ID")`; line 80 → `milestone=args.milestone`.
3. Run `tests.workflow_core.test_usage tests.workflow_core.test_usage_cli` (pass).
4. Skills: `progress/SKILL.md:14` → "For a milestone: `gin-workflow task list --parent <milestone-id> --all --json` gives the epics; `gin-workflow task list --parent <epic> --all --json` gives each one's tracks." `report/SKILL.md:14` → "a milestone's epics and their tracks (`--milestone <id>`)". `install_smoke_test.sh:181` → `assert_contains ".../progress/SKILL.md" "--parent <milestone-id>"`; add `assert_not_contains ".../progress/SKILL.md" "sprint:"`.
5. Docs: `cli.md:342` synopsis `--milestone ID`; `:345` "`--milestone ID` covers the epics under that milestone and their tracks; a non-milestone id exits 2." `skills.md`: `progress`/`report` rows mention `--milestone <id>`. Run `bash tests/install_smoke_test.sh` (pass). Commit: `feat(usage): report, progress and report skills scope by milestone; drop sprint labels`.

### Track 3: milestone close reason and move trace
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/milestone_cli.py:54` (argparse), `:168-190` (`_move`), `:204-210` (`_close`)
  - Modify `docs/reference/cli.md:200` (synopsis `close ID --reason TEXT`), `:212` and `:214` (table rows)
  - Test `tests/workflow_core/test_milestone_cli.py:248-265` (`test_req_005_move`), `:293-300` (`test_req_010_close`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change with real `bd` in tests; the metadata append and the best-effort warning have listed edge cases.
- **Acceptance criteria**: spec US-3 (CLI parts); R11, R12.
- **Estimated complexity**: medium

Steps:
1. Failing tests. In `test_req_010_close`: `self.assertEqual(2, self.run_cli("close", "t-m1")[0])` before the refused call, then use `self.run_cli("close", "t-m1", "--reason", "catalog shipped")` for the success path and assert `self.show("t-m1")["close_reason"] == "catalog shipped"` (`bd show --json` prints `close_reason`). In `test_req_005_move`, after the first move: `moves = json.loads(self.show("t-a")["metadata"]["milestone_moves"])` if `bd` returns metadata values as strings, else read the list directly; assert `moves[-1]["from"] is None`, `moves[-1]["to"] == "t-m2"`, `moves[-1]["actor"] == "unknown"`, and `moves[-1]["at"]` matches `r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"`; after `--to none`: `len(moves) == 2` and `moves[-1]["from"] == "t-m2"`, `moves[-1]["to"] is None`. Run `python3 -m unittest tests.workflow_core.test_milestone_cli -k move -k close` (fails).
2. Code:
   ```python
   item = sub.add_parser("close", parents=[common])
   item.add_argument("id")
   item.add_argument("--reason", required=True)
   ```
   `_close`: `_bd(root, ["close", args.id, "--reason", args.reason], actor)`.
   `_move`, inside the loop after the parent update succeeds:
   ```python
   done.append(epic)
   warnings.extend(_trace_move(root, bead, epic, args.to, actor))
   ```
   with
   ```python
   def _trace_move(root: Path, bead: Mapping[str, Any], epic: str, to: str, actor: str) -> list[str]:
       """Append {from, to, at, actor} to the epic's `milestone_moves` metadata; a failure is a warning, never a rollback."""
       stored = (bead.get("metadata") or {}).get("milestone_moves") if isinstance(bead.get("metadata"), Mapping) else None
       moves = json.loads(stored) if isinstance(stored, str) else list(stored or [])  # bd returns metadata parsed or as a string
       moves.append({"from": bead.get("parent") or None, "to": None if to == "none" else to,
                     "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor or "unknown"})
       try:
           _bd(root, ["update", epic, "--set-metadata", f"milestone_moves={json.dumps(moves)}"], actor)
       except MilestoneError as error:
           return [f"warning: {epic} moved but milestone_moves not recorded: {error}"]
       return []
   ```
   (`team_beads.metadata_json(issue, key)` exists but returns a dict, so it does not fit a list value.) `_move` returns `("moved ...", "membership")` as today; print each warning to stderr in `_write` (extend `WRITES` functions to return an optional third element, or collect warnings on a module list; pick the smaller diff and keep the two-tuple contract for the other commands).
3. Run the two tests (pass), then the whole `tests.workflow_core.test_milestone_cli` (pass).
4. Docs `cli.md`: synopsis line 200 → `gin-workflow milestone close ID --reason TEXT`; `move` row adds "and appends `{from, to, at, actor}` to each epic's `milestone_moves` metadata (a failed append prints a warning and keeps the move)"; `close` row → "Close a milestone with a reason (`bd close --reason`); refused while it has open epics; `--reason` missing is a usage error". Commit: `feat(milestone): close requires a reason; move records milestone_moves on the epic`.

### Track 4: roadmap skill: no sprint label, estimates without pace, adoption by dependency layer
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/roadmap/SKILL.md:17-18` (`--milestone` steps 2 and 3), `:38` (delete step 7, renumber 8 → 7)
  - Test `tests/install_smoke_test.sh:176-177` (add one `assert_contains` for the new adoption sentence and one `assert_not_contains` for `sprint:`)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** three sentences of behaviour rules in a skill; wording must match the CLI exactly, but the logic is specified.
- **Acceptance criteria**: spec US-2; R6-R8.
- **Estimated complexity**: low

Steps:
1. Smoke test first: `assert_contains ".../roadmap/SKILL.md" "no open blocker first"` and `assert_not_contains ".../roadmap/SKILL.md" "sprint:"`; run `bash tests/install_smoke_test.sh` (fails).
2. Step 2 of `## With --milestone <id>` gains, after the rounding sentence: "When that list has no epic (no measured pace), ask the PM for one day value per size, small, medium and large, assign one size per epic, and mark each resulting `Estimate:` line `(assumed)` in the roadmap file."
3. Step 3 (Adoption) gains: "Propose by dependency layer: epics with no open blocker first; an epic with an open blocker only when that blocker is proposed too; stop when the sum of estimates reaches the milestone's working days from `gin-workflow milestone show <id> --json`. Name the epics left out and why (blocked, or over capacity)."
4. Delete step 7 (`sprint:` label); renumber step 8 to 7. Run the smoke test (passes). Commit: `docs(roadmap): adoption by dependency layer, estimates without pace, no sprint label`.

### Track 5: Repository strategy and the Java JSP monorepo walkthrough
- **Dependencies**: Track 2, Track 3, Track 4 (every command and skill flag the walkthrough cites must exist in `docs/reference/cli.md` and the skills)
- **Files**:
  - Modify `docs/starters/brownfield-modernize.md:55` (insert `## Repository strategy` before `## Related`)
  - Modify `docs/starters/brownfield-walkthrough.md:1-233` (rewrite)
  - Modify `docs/roles.md:18`, `docs/getting-started.md:88-94`, `docs/guides/team.md:47-55` (the `execute` and `ship` rows name claims, leases and the epic gate proof; one sentence each, pointing at the walkthrough)
  - Create `tests/workflow_core/test_walkthrough_docs.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** documentation, but every claim must be checked against the CLI and skills across the repository and the scenario needs consistent names across twelve stages; the weakest model loses that thread.
- **Acceptance criteria**: spec US-1, US-3 (walkthrough stage); R1-R5.
- **Estimated complexity**: medium

Steps:
1. Failing test `tests/workflow_core/test_walkthrough_docs.py`:
   ```python
   """The walkthrough cites only documented gin-workflow commands."""
   import re, unittest
   from pathlib import Path
   ROOT = Path(__file__).resolve().parents[2]
   class TestWalkthroughCommands(unittest.TestCase):
       def test_every_cited_command_is_in_the_cli_reference(self):
           cli = (ROOT / "docs/reference/cli.md").read_text(encoding="utf-8")
           text = (ROOT / "docs/starters/brownfield-walkthrough.md").read_text(encoding="utf-8")
           cited = set(re.findall(r"gin-workflow ((?:[a-z]+(?: [a-z-]+)?))", text))
           missing = sorted(token for token in cited if f"gin-workflow {token}" not in cli)
           self.assertEqual([], missing)
       def test_walkthrough_has_the_milestone_stages(self):
           text = (ROOT / "docs/starters/brownfield-walkthrough.md").read_text(encoding="utf-8")
           for heading in ("## Repository and workspace setup", "## Roadmap overview", "## Milestone planning",
                           "## Milestone review and spill-over"):
               self.assertIn(heading, text)
           self.assertNotIn("sprint", text.lower())
   ```
   `tests/test_all.py` discovers `tests/*/test_*.py` by glob, so no registration is needed. Run it (fails on headings).
2. `brownfield-modernize.md`: `## Repository strategy` with the subtree commands, the submodule reason (one sentence), when a legacy repository stays separate, `monorepo`/`packages` and per-package `verify.checks` (cite `docs/reference/config.md`), `team.areas` by path. Four short paragraphs and one fenced block:
   ```bash
   git subtree add --prefix=legacy/shop git@github.com:acme/shop-legacy.git main
   git subtree pull --prefix=legacy/shop git@github.com:acme/shop-legacy.git main   # later vendor fixes
   ```
3. Rewrite `brownfield-walkthrough.md` per spec R2-R4: title "Brownfield walkthrough: from a legacy JSP monolith to milestone delivery"; scenario table with Lan `pm`, An `ba`, Binh `be_lead`, Em `be_dev`, Hoa `fe_dev`, Chi `qe`; the `team:` block with areas `legacy: {paths: ["legacy/**"], lead: be_lead, roles: [be_dev]}`, `api: {paths: ["services/api/**", "qa/api/**"], lead: be_lead, roles: [be_dev]}`, `web: {paths: ["apps/web/**", "qa/web/**"], lead: be_lead, roles: [fe_dev]}` and the approvals of today's file plus `permissions: {milestone: [pm]}`; mermaid flow with the new stages; then the stages in the order of R3, each with Who, Prompt, Put in the prompt, You get, Gate or approval, Common mistakes. Prompts to include verbatim:
   - Repository setup: the subtree block above, `/gin-workflow:setup` answers (`stage: brownfield`, `shape: fullstack`, `monorepo: true`).
   - Survey: `/gin-workflow:tech-doc whole repository` with "Put in the prompt: the entry points you know (`web.xml`, the Struts config), the database, and the modules you plan to replace first."
   - Roadmap overview: `/gin-workflow:roadmap Goal: replace the catalog, cart and checkout JSP flows with the REST API and the React SPA within two quarters; the Oracle schema stays; no downtime. Non-goals: reporting screens.` then `gin-workflow task graph --all` and the gin-console Dependencies page.
   - Milestone planning: `gin-workflow milestone create "M1 Catalog read path" --start 2026-11-10 --end 2026-11-28`, `/gin-workflow:roadmap --milestone <id>` with "Capacity: 2 developers, 1 QE, 15 working days. Sizes: S=3 M=6 L=10 days. Pick only epics with no open blockers; the API facade lands first.", then `gin-workflow milestone kickstart <id> --date 2026-11-10` and `gin-workflow milestone show <id>`.
   - Execute: `gin-workflow team ready`, `gin-workflow team claim <bead>` (lease of `team.claim_ttl_hours`, renew by claiming again), `gin-workflow team reassign <bead> <email>`.
   - Ship: `/gin-workflow:ship`; "You get" names the PR proof written to the epic bead's `gates` metadata and visible to teammates in `gin-workflow state`.
   - Milestone review and spill-over: the command block of spec R4 with `/gin-workflow:report --milestone <id>` and `/gin-workflow:progress --milestone <id>`.
   Keep "Customizing outputs" and "Solo variant" (solo: `milestone` commands work the same; no `permissions`).
4. `roles.md:18` → "The Roadmap overview, Milestone planning, and Milestone review sections of the brownfield walkthrough"; `getting-started.md:91` adds "then the [brownfield walkthrough](starters/brownfield-walkthrough.md) for the team flow"; `team.md` `execute`/`ship` rows: one sentence each linking the walkthrough stage.
5. Run `gin-workflow rules --files docs/starters/brownfield-walkthrough.md docs/starters/brownfield-modernize.md` and apply the docs pack (no em dashes, no bold-label bullets, one home). Run the new test and `python3 -m unittest tests.test_all` (pass). Commit: `docs(starters): Java JSP monorepo walkthrough with milestones and spill-over; repository strategy`.

## Integration
- **Branch**: `feat/team-workflow-guide`
- **Merge strategy**: sequential (1 → 2, then 3, 4, then 5; `usage.py` and `test_usage.py` are edited by 1 and 2 in disjoint ranges; `cli.md` by 2 and 3 in different sections; `install_smoke_test.sh` by 2 and 4 on neighbouring lines)

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes
- [ ] `bash tests/install_smoke_test.sh` passes
- [ ] After `./install.sh`: `gin-workflow usage report --since 2026-10-01` on this repository prices `claude-opus-5-5`, `claude-fable-5-1`, `claude-haiku-5-5`, the `gpt-5.6-*` rows, and lists `codex-auto-review` under `unpriced`
- [ ] `gin-workflow milestone close <id>` without `--reason` exits 2 in a scratch Beads repository

## Notes
- `Model:` and `Effort:` come from the main harness catalog (`claude`: `haiku`, `sonnet`, `opus`; efforts `low` to `max`).
- Track 3 writes `actor` from the team roster email that `_guard` returns, or `unknown` outside team mode; the spec's "git user.email" is read as that value, since `milestone_cli` has no other identity source.
- The parent bead is the workflow `team-workflow-guide`; tracks close after tests and review.
