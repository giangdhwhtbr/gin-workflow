# Plan: `describe` skill — HTML view of a bead or epic

**Goal:** `gin-workflow describe <id>` writes one self-contained HTML file with a fixed two-column template: the bead's graph on the left (parent-child tree, `blocks` edges, `discovered-from` bugs), the full Beads detail of the selected bead on the right. A thin read-only `describe` skill calls it.

**Architecture:** One core module `workflow_core/describe.py` with three pure-ish steps (`collect` reads `bd`, `layout` assigns tidy-tree coordinates, `render` fills the fixed template), a CLI module `describe_cli.py` registered in `cli.py`, a fixed template `templates/describe.html` (inline CSS and JS, one data placeholder), and `skills/describe/SKILL.md`. Follows the `usage` / `report` pattern.

**Tech Stack:** Python 3.12 stdlib; `bd` CLI; `unittest` with the fake `bd` from `tests/workflow_core/team_fixtures.py`; vanilla HTML/CSS/JS (no libraries); Markdown skill; bash/PowerShell smoke tests.

**Spec:** `.planning/specs/2026-10-05-describe-skill-design.md` @ `02f5561` (workflow id `describe-skill`, `requirement_confirmed` recorded).

## Global Constraints

Copied verbatim from the spec:

- Data comes from Beads only. Review-ledger state, gate state, waivers, spec/plan evidence, and `ai_usage` are out of scope.
- The fixed template ... Located with `plugin_templates_dir()`; no project override.
- `describe.py` has its own small `_bd()` helper (same shape as `usage.py`, not imported from it).
- Text fields (description, design, acceptance criteria, notes, comments) are shown as plain text with `white-space: pre-wrap`; no markdown rendering.
- Safety: the JSON is serialized with `</` escaped as `<\/` before substitution; the JS writes bead data only via `textContent` / SVG text nodes, never `innerHTML`.
- No external resources: no CDN, fonts, or images by URL.
- Default path: `.agent-workflow/runtime/describe/<id>.html` (already git-ignored via `.agent-workflow/.gitignore`). `--out PATH` overrides it.

Repository constraints:
- Test command (repo root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`. Baseline on `master` `78bf124`: see Validation (recorded before Track 1).
- Install smoke test: `bash tests/install_smoke_test.sh` exits 0 after Track 3. The PowerShell smoke test cannot run here (no `pwsh`); keep it consistent by reading.
- Core never names `gin-qa`. Skills ≤ 6,000 chars each.
- Git: commit/push on `feat/describe-skill`; never commit to `master`.

## Verified `bd` behavior (bd on this machine, 2026-10-05)

- `bd show A B ... --json [--include-comments]` → JSON array, one object per id. Fields used: `id`, `title`, `issue_type`, `status`, `priority`, `assignee`, `owner`, `labels`, `description`, `design`, `acceptance_criteria`, `notes`, `close_reason`, `created_at`, `updated_at`, `closed_at`, `metadata` (object), `parent` (id or absent), `dependencies` (array of issue objects with `id`, `title`, `status`, `dependency_type`: `parent-child` | `blocks` | `discovered-from` | `related` | ...), `comments` (with `--include-comments`: `[{id, author, text, created_at}]`). Absent fields are simply missing.
- Unknown id: exit 1, stderr `Error fetching <id>: no issue found matching "<id>"`.
- `bd dep list A B ... --direction=up --type <t> --json` → flat array of the dependent issues across all ids (batch supported), each with `dependency_type`; it does not say which input id each row came from.
- A `dependencies` entry `{id: X, dependency_type: "blocks"}` on bead N means X blocks N; `discovered-from` on bug B means B was discovered from X; `parent-child` on child C means X is C's parent.

## Deviations from the spec

- Collection batches `bd dep list` per tree level (and once for bugs) instead of per node: `bd show` costs ~0.4 s per call, so a 300-node graph would otherwise need ~600 calls. Same data, fewer processes. The "one `bd show` per level" test becomes "one `bd show` and one `bd dep list` per level".
- Any issue linked by `discovered-from` (one hop) is added with role `bug`; the node still shows its real `issue_type`. In this repository those are bugs.
- JSON escaping is stricter than the spec's `</` → `<\/`: every `<`, `>`, `&` is written as `\u003c`, `\u003e`, `\u0026` (covers `</script>` and `<!--`).
- The detail column also shows `owner` and `close_reason` (Beads fields the spec's list omitted; "all information" was the requirement).

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `cheap_simple`
- `override_rule`: none needed; boundaries and data shapes are settled.

## Requirement Analysis
- Problem: there is no single view of an epic or bead with its hierarchy, dependencies, bugs, metadata, and comments.
- Success: spec §Testing and §Error Handling; the Validation list below.
- Constraints: Global Constraints above; read-only; offline HTML.
- Non-goals (spec §Out of Scope): ledger/gate/waiver/spec/`ai_usage` data, markdown rendering, external-blocker nodes, multi-hop bugs, ancestor siblings, `--depth`, template overrides, auto-opening a browser, sharing `_bd()`.

## Approach Options
### Option 1: CLI computes data and layout, template JS only draws (selected in discuss)
- Pros: deterministic, layout tested in Python, thin skill.
- Cons: own layout code.
### Option 2: JS computes layout
- Cons: untested in this repo (no JS test harness).
### Recommended Approach
- Option 1, as confirmed.

## Scope
- In: `plugins/gin-workflow/src/scripts/workflow_core/describe.py`, `describe_cli.py`, `cli.py`; `plugins/gin-workflow/src/templates/describe.html`; `plugins/gin-workflow/src/skills/describe/SKILL.md`; `tests/workflow_core/test_describe.py`, `test_describe_cli.py`; `tests/workflow_providers/test_harness_packaging.py`; `tests/install_smoke_test.sh`, `.ps1`; `README.md`, `docs/reference/skills.md`, `docs/reference/cli.md`; regenerated `plugins/gin-workflow/dist/`.
- Out: other skills, config schema, gates, `gin-qa`, version bump (done at ship).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three tracks in a strict chain (collect -> layout/render/template -> CLI/skill/docs); each consumes the previous track's interfaces.
```

## Tasks

### Track 1: Collect the graph from Beads (`describe.py` — collect)
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/describe.py`
  - Test: `tests/workflow_core/test_describe.py` (class `CollectTests`)
- **Interfaces (produced)**:
  ```python
  MAX_NODES = 300
  DETAIL_FIELDS = ("description", "design", "acceptance_criteria", "notes", "close_reason", "assignee", "owner",
                   "labels", "created_at", "updated_at", "closed_at", "metadata")

  class DescribeError(Exception): ...                       # CLI exit 2
  class GraphTooLarge(DescribeError):                       # CLI exit 3
      def __init__(self, count: int, limit: int) -> None    # attributes .count, .limit; message
          # f"graph has more than {limit} nodes (reached {count}); describe a child bead instead"

  def collect(repo: Path, root_id: str, *, max_nodes: int = MAX_NODES,
              now: datetime | None = None) -> dict
  # returns {"meta": {"root": str, "generated_at": "YYYY-MM-DDTHH:MM:SSZ", "repo": repo.name},
  #          "nodes": [ {"id", "title", "type", "status", "priority",
  #                      "role": "root"|"ancestor"|"descendant"|"bug",
  #                      "detail": {<DETAIL_FIELDS present in bd output>, "comments": [{"author","text","created_at"}],
  #                                 "external_blockers": [{"id","title","status"}]}} ... ]  sorted by id,
  #          "edges": [ {"from", "to", "kind": "parent"|"blocks"|"discovered"} ... ]  sorted by (kind, from, to)}
  ```
- **Steps**:
  1. Tests first in `CollectTests`, each with `fake_cli(self.bin, "bd", rules)` and `mock.patch.dict(os.environ, path_with(self.bin))` (pattern of `tests/workflow_core/test_usage.py`). Fixture: epic `e` (parent `p`, which has parent `g`; `g` also has another child `s` that must not appear); `e` children `e.1`, `e.2`; `e.1` child `e.1.1`; `e.2` has a `blocks` dependency on `e.1` (in graph) and on `x` (outside); bug `b1` has `discovered-from` `e.1.1`; bug `b2` has `discovered-from` both `e.1` and `e.2`. Rules (ids always sorted in batched argv):
     - `["show","e","--json","--include-comments"]`, `["show","p",...]`, `["show","g",...]`, `["show","e.1","e.2",...]`, `["show","e.1.1",...]`, `["show","b1","b2",...]`
     - `["dep","list","e","--direction=up","--type","parent-child","--json"]` → `e.1`, `e.2`; `["dep","list","e.1","e.2",...]` → `e.1.1`; `["dep","list","e.1.1",...]` → `[]`
     - `["dep","list","e","e.1","e.1.1","e.2","--direction=up","--type","discovered-from","--json"]` → `b1`, `b2`
     Assertions:
     - node ids == `{g, p, e, e.1, e.2, e.1.1, b1, b2}`; `s` and `x` absent; roles: `g`,`p` ancestor, `e` root, `e.*` descendant, `b*` bug.
     - edges include `parent` `g→p`, `p→e`, `e→e.1`, `e→e.2`, `e.1→e.1.1`; `blocks` `e.1→e.2`; `discovered` `e.1.1→b1`, `e.1→b2`, `e.2→b2`.
     - `e.2` detail `external_blockers == [{"id":"x","title":"X","status":"open"}]`; comments reduced to `author/text/created_at`; absent fields absent from `detail`.
     - `calls.log`: exactly one `show` and one parent-child `dep list` per descendant level, one `discovered-from` `dep list` in total; no call for `s`.
     - Cycle (variant fixture: the `["dep","list","e.1.1",...,"parent-child",...]` rule returns `e`) → no revisit, terminates, `e` keeps role `root`.
     - `max_nodes=4` → `GraphTooLarge` with `.count > 4`, `.limit == 4`, and no `show` call for the level that overflowed.
     - Unknown root (`show` rule exit 1, stderr `Error fetching zz: no issue found matching "zz"`) → `DescribeError("bd show zz: no such bead")`; `bd` absent from PATH → `DescribeError("bd is not installed")`; invalid JSON → `DescribeError` containing `printed invalid JSON`.
     - Single bead with no parent, children, or bugs → one node, no edges.
     - `meta.generated_at` uses `now` (`datetime(2026,10,5,tzinfo=timezone.utc)` → `"2026-10-05T00:00:00Z"`).
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_describe.py` → fails (module missing).
  3. Implement:
     - `_bd(repo, argv)`: same shape as `usage._bd` (`shutil.which("bd")`, `subprocess.run(..., cwd=repo, text=True, capture_output=True, timeout=120)`, non-zero → `DescribeError(f"bd {' '.join(argv[:2])} failed: {stderr or stdout}")`, JSON parse error → `DescribeError(f"bd {argv[0]} printed invalid JSON")`).
     - `_show(repo, ids)` → `_bd(repo, ["show", *sorted(ids), "--json", "--include-comments"])` as a list.
     - Root: call `_show`; on `DescribeError` whose text contains `no issue found`, or an empty result, raise `DescribeError(f"bd show {root_id}: no such bead")`.
     - Ancestors: follow `parent` from the root while the id is unseen, one `_show` each.
     - Descendants: `level = [root_id]`; loop: `kids = sorted({row["id"] for row in dep list up parent-child over level} - seen)`; empty → stop; if `len(seen) + len(kids) > max_nodes` raise `GraphTooLarge`; `_show(kids)`; role `descendant`; `level = kids`. Track `tree` = root + descendants.
     - Bugs: one `dep list up discovered-from` over sorted `tree`; new ids → same size check → `_show` → role `bug`.
     - Edges from each node's `dependencies`: both ends in graph → `parent-child`→`parent`, `blocks`→`blocks`, `discovered-from`→`discovered`, each `{"from": dep["id"], "to": node_id}`; `blocks` with an outside end → `external_blockers` (sorted by id); other types ignored.
     - Node: `type = issue_type`; `detail` keeps `DETAIL_FIELDS` that are present and not `None`, plus `comments` and `external_blockers` only when non-empty.
  4. Run the test → passes; full suite → OK. Commit `feat(describe): collect a bead's graph from Beads`.
- **Acceptance criteria**: every assertion above passes; full suite OK; independent review approved.

### Track 2: Layout, render, and the fixed template (`describe.py` — layout/render, `describe.html`)
- **Dependencies**: Track 1
- **Provider role**: `frontend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/describe.py` (append)
  - Create: `plugins/gin-workflow/src/templates/describe.html`
  - Test: `tests/workflow_core/test_describe.py` (classes `LayoutTests`, `RenderTests`)
- **Interfaces (consumed)**: `collect` graph shape, `DescribeError` (Track 1); `workflow_core.specs.plugin_templates_dir()`, `SpecsError`.
- **Interfaces (produced)**:
  ```python
  PLACEHOLDER = "/*__DESCRIBE_DATA__*/"
  def layout(graph: dict) -> dict          # same dict, every node gains "x": float (slot) and "y": int (row; root 0, ancestors < 0)
  def template() -> str                    # plugin_templates_dir() / "describe.html"; SpecsError or missing file -> DescribeError
  def render(graph: dict, template_text: str) -> str
      # template_text must contain PLACEHOLDER exactly once, else DescribeError("describe template must contain the data placeholder once")
      # payload = json.dumps(graph, ensure_ascii=False, sort_keys=True) with "<" ">" "&" -> "\\u003c" "\\u003e" "\\u0026"
  ```
- **Steps**:
  1. Tests first (pure data, graphs built in the test):
     - `layout` on the Track 1 fixture shape: calling twice gives identical `(id, x, y)`; every parent's `x` equals the mean of its first and last layout child's `x`; no two nodes share `(x, y)`; `b1.y == e.1.1.y + 1`; `b2` sits under `e.1` (smallest discoverer id); ancestors `g.y == -2`, `p.y == -1`, both with `x == e.x`; single node → `x == 0`, `y == 0`.
     - `render`: result contains no `/*__DESCRIBE_DATA__*/`; a node title `</script><img src=x onerror=alert(1)>` appears only as `\u003c/script\u003e...`; the raw string `</script><img` does not occur; template without the placeholder, or with it twice → `DescribeError`.
     - Template file: `template()` returns text containing `PLACEHOLDER` once; it matches no `(?:src|href)\s*=\s*["']?https?:`, no `@import`, no `url\(\s*["']?https?:`, and no `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`.
  2. Run → fails.
  3. Implement `layout`: layout parent of a descendant = its `parent` edge source; of a bug = smallest-id discoverer among `discovered` edge sources that are root/descendant (a bug that is also a descendant keeps its tree parent). Children ordered: descendants by id, then bugs by id. Post-order: leaf → next integer slot; parent → `(first.x + last.x) / 2`. Rows: root 0, child = parent + 1. Ancestors: walk the `parent` edges up from the root, `y = -1, -2, ...`, `x = root.x`.
  4. Write `describe.html` (fixed, self-contained):
     - Layout: CSS grid two columns (`minmax(0,3fr) minmax(320px,2fr)`), full height; left pane scrollable `<svg id="graph">`; right pane `<aside id="detail">`; header bar with the root id, `generated_at`, a legend (status colors, edge kinds), and a `Back to root` button.
     - `<script>const DATA = /*__DESCRIBE_DATA__*/;</script>` then the app script.
     - Drawing: pixel `px = x * 200 + 110`, `py = (y - minY) * 110 + 50`; node = rounded `rect` 180×56 with the id and the title truncated to 26 chars (full title in an SVG `<title>`), fill by status (`open` #3b82f6, `in_progress` #f59e0b, `blocked` #ef4444, `closed` #22c55e, `deferred` #a3a3a3, other #94a3b8), role `bug` red border, role `root` thick dark border, selected node outlined. Edges drawn under nodes: `parent` straight grey line; `blocks` orange cubic curve with an arrow marker; `discovered` red dashed line. All elements via `document.createElementNS`; text via `textContent`.
     - Detail: `show(id)` clears `#detail` with `replaceChildren()` and builds: header (id, title, type, status, priority, assignee, owner, role); sections Description, Design, Acceptance criteria, Notes, Close reason (each `<pre class="text">` with `white-space: pre-wrap`); Labels; Dates; Metadata (two-column table, non-string values `JSON.stringify(v, null, 2)` in `<pre>`); Comments (author, created_at, text); Children (`parent` edges from it); Blocked by / Blocks (`blocks` edges, plus `external_blockers` as plain non-clickable rows); Bugs (`discovered` edges from it). A section is not created when its value is empty. Ids of graph nodes are buttons that call `show(id)`. Clicking a node calls `show(id)`; `Back to root` calls `show(DATA.meta.root)`; initial view `show(DATA.meta.root)`.
  5. Run the tests → pass; full suite → OK. Commit `feat(describe): lay out the graph and render the fixed HTML template`.
- **Acceptance criteria**: tests above pass; template has no external resource and no HTML-string sinks; full suite OK; independent review approved.

### Track 3: CLI, skill, docs, packaging
- **Dependencies**: Track 2
- **Provider role**: `backend`
- **Reasoning**: `low`
- **Estimated complexity**: low
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/describe_cli.py`, `plugins/gin-workflow/src/skills/describe/SKILL.md`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py:69-84` (add `describe` to the accepted commands, the usage line, and a dispatch block like `usage`); `tests/workflow_providers/test_harness_packaging.py:99-103` (`REQUIRED_ARTIFACTS` adds `skills/describe/SKILL.md`, `scripts/workflow_core/describe.py`, `scripts/workflow_core/describe_cli.py`, `templates/describe.html`); `tests/install_smoke_test.sh:143,207,226` (assert `skills/describe/SKILL.md` in the claude-code, codex, antigravity dist); `tests/install_smoke_test.ps1:83-84` (`.claude` and `.codex` `skills/describe/SKILL.md`); `README.md:85` (row `| \`describe\` | HTML view of a bead or epic: graph and details |`); `docs/reference/skills.md:26` (row after `report`: `| \`describe\` | Write a self-contained HTML page for a bead or epic: graph of children, blockers, and bugs beside its full details, without changing anything |`); `docs/reference/cli.md:174` (new section `## \`gin-workflow describe\`` before `## \`review-ledger.py\``).
  - Regenerate: `plugins/gin-workflow/dist/` via the installer the smoke test runs.
  - Test: `tests/workflow_core/test_describe_cli.py`
- **Interfaces (consumed)**: `collect`, `layout`, `render`, `template`, `DescribeError`, `GraphTooLarge`, `MAX_NODES` (Tracks 1–2); `workflow_core.atomic.atomic_write_text(path, text, mode=...)`.
- **Interfaces (produced)**:
  `gin-workflow describe ID [--out PATH] [--repository P] [--format text|json]`. Default out: `<repository>/.agent-workflow/runtime/describe/<ID>.html`; relative `--out` resolved against the current directory. Writes with `atomic_write_text(path, html, mode=0o644)` after `path.parent.mkdir(parents=True, exist_ok=True)`. Text output: `<path>  (<n> nodes, <m> edges)`; JSON: `{"status": "ok", "path": "<abs path>", "nodes": n, "edges": m}`. Exit 0 ok; 2 `DescribeError` (`error: <message>` on stderr); 3 `GraphTooLarge` (`error: <message>`). No file written on error.
- **Steps**:
  1. Tests first (`run_cli` from `team_fixtures`, fake `bd` with a root `t1` that has one child `t1.1`):
     - default path exists after the run, contains `t1.1`, and `--format json` returns the shape above with `nodes == 2`, `edges == 1`; `--out <tmp>/x/y.html` creates parent dirs; a second run overwrites.
     - unknown id → exit 2, stderr `error: bd show zz: no such bead`, no file; `bd` missing → exit 2.
     - exit 3: patch is not possible across a subprocess, so build a fake `bd` whose root has 301 children (one `dep list` rule returning 301 rows) → exit 3, stderr contains `more than 300 nodes`, no file.
     - `gin-workflow` with no args lists `describe` in the usage line.
     Add the packaging and smoke assertions. Run → fail.
  2. Implement `describe_cli.py` (argparse `prog="gin-workflow describe"`, positional `id`, catch `GraphTooLarge` before `DescribeError`) and the `cli.py` dispatch.
  3. `skills/describe/SKILL.md`: frontmatter `name: describe`, `description: Write a self-contained HTML page for a bead or epic — its graph of children, blockers, and discovered bugs beside full details, metadata, and comments — without mutating anything.`; the shared "Before you start" block (copy from `skills/report/SKILL.md:6-8`); steps: take the bead id from the request (ask if missing); run `gin-workflow describe <id> --format json` (`--out` only if the user gave a path); exit 2 → show the error and stop; exit 3 → say the graph is too large and suggest describing a child bead; otherwise report the path and node/edge counts and that it is a snapshot of Beads at that moment. Never open a browser, change beads, or chain into another stage.
  4. Docs: README and skills rows above; `cli.md` section with the usage block, the default path, a sentence on the graph scope (parent chain, all descendants, one hop of `discovered-from`, `blocks` between drawn beads, outside blockers listed in details), the 300-node limit, and `Exit codes: 0 ok; 2 error; 3 graph too large.`
  5. Run `bash tests/install_smoke_test.sh` (regenerates `dist/`), packaging tests, `test_docs_coverage.py`, and the full suite → OK, exit 0. Commit `feat(describe): describe CLI, skill, and docs` including the regenerated `dist/`.
- **Acceptance criteria**: CLI tests pass; skill ≤ 6,000 chars; packaging, docs-coverage, and smoke assertions pass on every harness layout; full suite OK; independent review approved.

## Integration
- **Branch**: `feat/describe-skill`
- **Merge strategy**: sequential

## Validation
- [ ] Baseline full suite on `78bf124` recorded before Track 1; full suite OK and smoke test exit 0 at the final track.
- [ ] Manual: `gin-workflow describe gin-workflow-a0j` (epic with 6 tracks and `blocks` edges) and `gin-workflow describe gin-workflow-qik` (has `discovered-from` bugs `gin-workflow-xs4`, `gin-workflow-m6l` on a child); open both HTML files offline, click several nodes, check the detail column switches and `Back to root` works; screenshot as evidence.
- [ ] Spec §Error Handling rows and §Testing bullets checked line by line.

## Notes
- The Parent Bead (epic) remains open until the human-confirmed merge; track beads close after tests and review pass.
- Version bump happens at ship, as in previous releases.
