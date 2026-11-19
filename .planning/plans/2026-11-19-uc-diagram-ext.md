# Plan: Use case diagram extensions: cross-capability includes, generalization, context diagram

Epic: gin-workflow-16jz
Workflow: gin-workflow-16jz
Spec: `.planning/specs/2026-11-19-uc-diagram-ext-design.md`

## Objective

Use cases can include, extend, and specialize use cases of other capabilities (`cap/slug`), actors can generalize other actors (`Is a` in `actors.md`), use cases can specialize others (`Specializes:`); lint checks the references and cycles; the use case diagram draws external use cases and `is a` edges; the SRS Actors section opens with a generated context diagram.

## Global Constraints

Copied from the spec:

- Actor generalization is declared once per project, in an optional `Is a` column of `<specs>/actors.md`; use case generalization by a `Specializes:` line in the specializing use case.
- `Includes:`, `Extends:`, and `Specializes:` take `slug` (same capability) or `cap/slug`; an activity diagram's `Use case:` stays same-capability.
- Generalization is drawn as `== is a ==>`.
- The context diagram is generated at export at the start of the Actors section: a system subgraph with one node per capability, actors outside with solid edges where primary and dashed edges where only secondary, plus `is a` edges; a one-capability export limits it to that capability.
- Files without the new forms lint and export as before; existing diagram outputs are unchanged when no new form is used.
- Out of scope: `/gin:explain`, data flows on the context diagram, the legacy layout.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: references stop at the capability boundary, generalization cannot be expressed, and the SRS has no system-level picture.
- Success criteria: US-1 to US-3 pass as tests; existing diagram outputs unchanged without the new forms; full suite green.
- Constraints: Global Constraints above.
- Non-goals: the out-of-scope list above.

## Approach Options
### Option 1: Extend the existing readers, lint, and diagram (confirmed at discuss)
- Summary: a reference resolver and a cycle finder in `specs.py`; parents of actors in `specs_matter`; `use_case_diagram` grows external subgraphs and `is a` edges; a new `context_diagram` in `specs_export`.
- Pros: one place per concern, reuses `actor_key`, `table_rows`, `line_values`.
- Cons: `use_case_diagram` takes two more inputs.

### Option 2: A separate relations file
- Summary: one `<specs>/relations.md` listing every include, extend, and is-a.
- Pros: one file to read.
- Cons: moves facts away from the use cases they describe; rejected at discuss.

### Recommended Approach
- Selected option: Option 1.

## Scope
- In scope: R1 to R5 of the spec.
- Out of scope: Global Constraints' out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Track 2 draws what Track 1 resolves and lints, and Track 3 documents both; they run one after another on feat/uc-diagram-ext.
```

## Tasks

### Track 1: References across capabilities, Specializes, actor Is a, and their lint (R1, R2, R3 lint)
- **Dependencies**: none
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs.py` (`use_case_ref`, `generalization_cycles`, `actor_parents`; `lint_references` around line 560; `lint_actors` around line 538; `lint_use_cases` around line 610)
  - Modify `plugins/gin-workflow/src/templates/use-case.md` (comment: `cap/slug`, `Specializes:`)
  - Test `tests/workflow_core/test_specs.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded lint rules in one module with exact messages from the spec; cycle detection is small but needs care.
- **Interfaces produced**:
  - `specs.use_case_ref(cap: str, value: str) -> tuple[str, str] | None`: `slug` → `(cap, slug)`, `other/slug` → `("other", "slug")`; None when the value has more than one `/` or an empty part.
  - `specs.generalization_cycles(parents: Mapping[str, list[str]]) -> list[list[str]]`: each cycle once, as its sorted members.
  - `specs.actor_parents(root, cfg) -> dict[str, str]`: `actor_key(child)` → parent label (spaces collapsed) from the `Is a` column of `<specs>/actors.md`; `{}` without the file or column.
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_specs.py` (`TestRepositoryCommands`; use `USE_CASE`, `AUTH_SPEC`, `write`):
     - Cross-capability: `docs/specs/orders/use-cases/pay.md` with `Includes: auth/sign-in` passes `lint_references` when `docs/specs/auth/use-cases/sign-in.md` exists; with `Includes: auth/verify-otp` it reports `docs/specs/orders/use-cases/pay.md: Includes names unknown use case 'auth/verify-otp'`; `Extends: orders/pay` in `pay.md` reports `... Extends names the use case itself`; `Includes: a/b/c` reports it as unknown.
     - `Specializes: sign-in` in `auth/use-cases/sign-in-sso.md` passes; `Specializes: nope` reports `... Specializes names unknown use case 'nope'`; `a.md` specializing `b` and `b.md` specializing `a` make `lint_use_cases` report `docs/specs/auth/use-cases/a.md: use case generalization cycle: auth/a, auth/b` (once).
     - `actors.md` with `| Actor | Description | Is a |` rows `| Admin | Manages users | User |` and a use case naming both passes `lint_actors`; `Is a` `Superuser` reports `docs/specs/actors.md:<line>: actor 'Admin' is a 'Superuser', which is no actor`; Admin is a User and User is an Admin report `docs/specs/actors.md: actor generalization cycle: Admin, User`; `specs.actor_parents` returns `{"admin": "User"}` for the valid table.
     - An existing `actors.md` with only `Actor` and `Description`, and use cases without these lines, give exactly the findings they gave before.
     In `TestSpecsCli`, the `use-case.md` template needles add `"Specializes:"` and `"cap/slug"`.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs.py -q`: the new tests fail.
  3. `specs.py`:
     ```python
     def use_case_ref(cap: str, value: str) -> tuple[str, str] | None:
         """The (capability, slug) a use case reference names: `slug` in `cap`, or `other/slug`."""
         parts = value.split("/")
         if len(parts) == 1 and parts[0]:
             return cap, parts[0]
         if len(parts) == 2 and all(parts):
             return parts[0], parts[1]
         return None


     def generalization_cycles(parents: Mapping[str, list[str]]) -> list[list[str]]:
         """Each cycle of a child -> parents graph once, as its sorted members."""
         cycles: list[list[str]] = []
         seen: set[tuple[str, ...]] = set()

         def visit(node: str, path: list[str]) -> None:
             if node in path:
                 cycle = sorted(path[path.index(node):])
                 if tuple(cycle) not in seen:
                     seen.add(tuple(cycle))
                     cycles.append(cycle)
                 return
             for parent in parents.get(node, ()):
                 visit(parent, [*path, node])

         for node in sorted(parents):
             visit(node, [])
         return cycles


     def actor_parents(root: Path, cfg: Mapping[str, Any]) -> dict[str, str]:
         """`actor_key(child)` -> parent label from the `Is a` column of `<specs>/actors.md`."""
         table = table_rows(read_text_or_none(specs_dir(root, cfg) / ACTORS_FILE) or "")
         return {actor_key(row["Actor"]): " ".join(row["Is a"].split())
                 for _, row in (table[1] if table else []) if row.get("Actor") and row.get("Is a")}
     ```
     - `lint_references`: loop over `("Includes", "Extends", "Specializes")`; for each value, `target = use_case_ref(cap.name, value)`; when `target == (cap.name, path.stem)` report `"{key} names the use case itself"`; when `target is None` or `base / target[0] / USE_CASES_DIR / f"{target[1]}.md"` is not a file, report `"{key} names unknown use case '{value}'"`. Keep the `Use case:` check of activity diagrams same-capability. Update the docstring.
     - `lint_use_cases`: build `parents = {f"{cap}/{slug}": [f"{c}/{s}" for c, s in (use_case_ref(cap, v) for v in line_values(text, "Specializes")) if c]}` over all use cases (skip None refs), and for each cycle from `generalization_cycles(parents)` append `f"{shown(root, first_member_path)}: use case generalization cycle: {', '.join(cycle)}"` where `first_member_path` is the file of `cycle[0]`. The `included` set used for the optional `Actor:` keeps reading `Includes:`: resolve its values with `use_case_ref` so `cap/slug` includes count for the included use case of another capability.
     - `lint_actors`: when the header has `Is a`, a row whose `Is a` value is neither an `Actor` of the table nor an actor named by a use case reports `f"{shown(root, path)}:{number}: actor '{row['Actor']}' is a '{row['Is a']}', which is no actor"`; then `generalization_cycles({actor_key(r["Actor"]): [actor_key(r["Is a"])] for _, r in rows if r.get("Is a")})` gives `f"{shown(root, path)}: actor generalization cycle: {', '.join(labels)}"` with the labels as written in the table, in the cycle's sorted-key order.
  4. `templates/use-case.md` comment: add that `Includes`, `Extends`, and `Specializes` take a slug of the same capability or `cap/slug` for another one, and the optional `Specializes: <slug>` line for a use case that is a special case of another; add `Specializes:` to the optional lines. No `--` inside the comment.
  5. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs.py tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs_export.py -q`: passes.
  6. Commit: `feat(specs): use cases reference other capabilities and specialize; actors generalize in actors.md; lint checks them (gin-workflow-16jz.1)`.
- **Acceptance criteria**: the lint criteria of US-1 and US-2; files without the new forms keep their findings.
- **Estimated complexity**: medium

### Track 2: Diagrams and the actor catalogue (R1, R2, R3 drawing, R4)
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_export.py` (`use_case_diagram` around line 220; new `context_diagram`; `_chapter` call around line 262; `_matter` actors around line 376)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/specs_matter.py` (`actors` rows gain `is_a`)
  - Test `tests/workflow_core/test_specs_export.py`, `tests/workflow_core/test_specs_matter.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** diagram text built from data Track 1 resolves; the subtle parts are keeping today's output byte-for-byte without the new forms and the edge kinds of the context diagram.
- **Interfaces consumed**: `specs.use_case_ref`, `specs.actor_parents`, `specs.actor_key`.
- **Interfaces produced**:
  - `use_case_diagram(capability: str, folder: Path, parents: Mapping[str, str] | None = None) -> str` (the cap's own folder; other capabilities are read from `folder.parent`).
  - `context_diagram(title: str, capabilities: list[tuple[str, str]], actors: list[dict], parents: Mapping[str, str]) -> str` (`capabilities` as `(cap, title)`; `actors` as `specs_matter.actors` rows).
  - `specs_matter.actors` rows gain `is_a` (parent label or `""`).
- **Steps**:
  1. Failing tests:
     - `test_specs_export.py`: existing diagram tests keep passing unchanged (they pin today's output). New: `orders/use-cases/pay.md` with `Includes: auth/sign-in` gives an orders diagram with `subgraph ext1["Auth"]` (dashed via `style ext1 stroke-dasharray: 5 5`), a node for Sign in inside it, and `ucN -. «include» .-> xN`; `Specializes: sign-in` in `sign-in-sso.md` gives `uc… == is a ==> uc…`; with `actors.md` `Is a` Admin → User and a use case whose actor is Admin, the diagram has an Admin node, a User node, and `aX == is a ==> aY`, and the `class` line lists both.
     - Context diagram: `gin specs export --all` with auth (Customer primary of sign-in, Mail service secondary) and billing (Accountant primary) shows `<section class="context-diagram" id="context-diagram">` before the actor table inside the Actors section, a `subgraph system[...]` with two capability nodes, `Customer --> auth`, `Mail service -.-> auth`, `Accountant --> billing` (by node ids), and no section without use cases; `export auth` has no billing node.
     - `test_specs_matter.py`: actor rows carry `is_a` (`"User"` for Admin, `""` otherwise).
     - The SRS actor table has an "Is a" column after Actor.
  2. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_export.py tests/workflow_core/test_specs_matter.py -q`: fails.
  3. `specs_matter.actors`: after reading descriptions, set `row["is_a"] = specs.actor_parents(root, cfg).get(key, "")` for each row (initialise `"is_a": ""` in `setdefault`).
  4. `use_case_diagram(capability, folder, parents=None)`:
     - Keep the current code path; collect references with `specs.use_case_ref(folder.name, value)` for `Includes`, `Extends`, and `Specializes`. A target in this capability uses `ids[slug]` as today (skip unknown and self). A target in another capability gets a node `x<n>` registered once per `(cap, slug)` in `externals[cap]`, labelled with the `# ` title of `folder.parent / cap / "use-cases" / f"{slug}.md"` (skip when the file is missing).
     - Edge texts: `«include»`, `«extend»` as today; `Specializes` gives `  {child} == is a ==> {parent}`.
     - Actor generalization: after the use case loop, walk the actor keys present (`actors` dict) and for each with a parent in `parents or {}`, register the parent with `actor(parent_label)` and append `  {child_id} == is a ==> {parent_id}`; repeat until no new parent is added (a chain), guarding against cycles with a seen set.
     - Output order: the current lines, then for each external capability (sorted) `  subgraph ext<n>[<title quoted>]`, its nodes, `  end`, `  style ext<n> stroke-dasharray: 5 5`, inserted after the system subgraph's `end` and before the edges; generalization edges after the existing edges; the `class` line last. With no external target and no parents, the output must equal today's.
     - In `_chapter`, pass `specs.actor_parents(root, cfg)`; `_chapter` needs `cfg`: thread it from `export` (add a parameter).
  5. `context_diagram(title, capabilities, actors, parents)`:
     ```python
     def context_diagram(title: str, capabilities: list[tuple[str, str]], actors: list[dict[str, Any]],
                         parents: Mapping[str, str]) -> str:
         """Mermaid flowchart of the system: capabilities inside, actors outside, primary solid, secondary dashed."""
         wanted = {cap for cap, _ in capabilities}
         rows = [row for row in actors if any(u["ref"].split("/", 1)[0] in wanted for u in row["use_cases"])]
         if not rows:
             return ""
         caps = {cap: f"c{number}" for number, (cap, _) in enumerate(capabilities, 1)}
         nodes: dict[str, tuple[str, str]] = {}

         def actor(name: str) -> str:
             label = " ".join(name.split())
             return nodes.setdefault(specs.actor_key(name), (f"a{len(nodes) + 1}", label))[0]

         edges: list[str] = []
         for row in rows:
             node = actor(row["actor"])
             primary = {u["ref"].split("/", 1)[0] for u in row["use_cases"] if not u["secondary"]}
             secondary = {u["ref"].split("/", 1)[0] for u in row["use_cases"] if u["secondary"]} - primary
             edges += [f"  {node} --> {caps[cap]}" for cap in sorted(primary & wanted)]
             edges += [f"  {node} -.-> {caps[cap]}" for cap in sorted(secondary & wanted)]
         for key in list(nodes):
             child, seen = key, set()
             while child in parents and child not in seen:
                 seen.add(child)
                 parent = actor(parents[child])
                 edges.append(f"  {nodes[child][0]} == is a ==> {parent}")
                 child = specs.actor_key(parents[child])
         lines = ["flowchart LR", "  classDef actor fill:none,stroke-width:3px",
                  *(f"  {node}[{_quoted(label)}]" for node, label in nodes.values()),
                  f"  subgraph system[{_quoted(title)}]",
                  *(f"    {caps[cap]}([{_quoted(name)}])" for cap, name in capabilities), "  end", *edges,
                  f"  class {','.join(node for node, _ in nodes.values())} actor"]
         return "\n".join(lines)
     ```
     Deduplicate repeated `is a` edges (a parent shared by two children is walked twice): keep a set of emitted edges.
  6. `_matter`: build `capabilities = [(name, _title(living[name].read_text(...), name)) for name in caps]` (pass `living` in from `export`), compute `diagram = context_diagram(<document title>, capabilities, rows, specs.actor_parents(root, cfg))`, and prefix the actors table with `<section class="context-diagram" id="context-diagram"><pre class="mermaid">{escape(diagram)}</pre></section>` when it is not empty. Add the "Is a" column after "Actor" (`escape(a["is_a"])`).
  7. Run `timeout 300 python3 -m pytest tests/workflow_core/test_specs_export.py tests/workflow_core/test_specs_matter.py tests/workflow_core/test_specs.py -q`: passes.
  8. Render check: export a scratch SDD repo with two capabilities, a cross-capability include, a `Specializes:`, and an `Is a`, open it in Chromium (`NODE_PATH=/home/gin/scotty/node_modules node <script>`, scratch files under `/tmp/claude-1002/-home-gin-gin-fam-gin-workflow/06b4f8ac-7dbf-4dd5-95e7-c8ff3f98bfa4/scratchpad/`), and check every Mermaid block renders without a syntax error; save `srs-uc-ext.png` there.
  9. Commit: `feat(specs): diagrams draw cross-capability use cases and is-a edges; the SRS opens Actors with a context diagram (gin-workflow-16jz.2)`.
- **Acceptance criteria**: the drawing criteria of US-1 and US-2, US-3; existing diagram outputs unchanged; browser render without Mermaid errors.
- **Estimated complexity**: medium

### Track 3: Documentation (R5)
- **Dependencies**: Track 2
- **Files**:
  - Modify `docs/guides/sdd.md`, `docs/guides/sdd.vi.md`, `docs/guides/ba.md`, `docs/guides/ba.vi.md`
  - Modify `docs/reference/cli.md`
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `low`
- **Why:** documentation of behaviour built in Tracks 1 and 2, checked against the code.
- **Steps**:
  1. Read `specs.py` (`use_case_ref`, `generalization_cycles`, `actor_parents`, `lint_references`, `lint_actors`, `lint_use_cases`), `specs_export.py` (`use_case_diagram`, `context_diagram`, `_matter`), `specs_matter.actors`, and `templates/use-case.md`.
  2. `sdd.md` (and `.vi.md`): `cap/slug` references, `Specializes:`, the `Is a` column, the lint messages, how the use case diagram shows external use cases and `is a`, and the context diagram at the start of the SRS Actors section.
  3. `ba.md` (and `.vi.md`): when to share a use case across capabilities, when to declare `Is a` and `Specializes:`, one example each; link to sdd.md for the rules.
  4. `cli.md`: the new lint findings in the `lint` row; the context diagram and the "Is a" column in the `export` row.
  5. Run `gin docs check docs/guides/sdd.md docs/guides/sdd.vi.md docs/guides/ba.md docs/guides/ba.vi.md docs/reference/cli.md` and `timeout 300 python3 -m pytest tests/workflow_core/test_docs*.py -q`: pass.
  6. Commit: `docs(specs): cross-capability use cases, generalization, and the context diagram (gin-workflow-16jz.3)`.
- **Acceptance criteria**: R5; every claim matches the code; docs check exits 0.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/uc-diagram-ext`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes (pre-push hook).
- [ ] `gin docs check` on the changed pages exits 0.
- [ ] Manual: the browser render of Track 2 step 8.

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead `gin-workflow-16jz`; track beads close when their tests and review pass.
- Track IDs in commit messages (`gin-workflow-16jz.N`) are the beads orchestrate creates; use the real IDs.
