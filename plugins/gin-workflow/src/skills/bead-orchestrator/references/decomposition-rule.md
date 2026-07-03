# Decomposition Rules

How the orchestrator converts a plan markdown into bd issues, dependencies, and
execution tracks. Corresponds to Phase 2 of the orchestrator protocol.

---

## H2 → bd issue

For each H2 task in the plan (in document order):

```bash
# 1. Create the issue — use --silent to capture ID cleanly
bid=$(bd create "<H2 title>" -t task -p <priority> --silent --actor "$COORDINATOR_NAME")

# 2. Set the body (verbatim from plan body)
bd update "$bid" --description "<body verbatim>" --actor "$COORDINATOR_NAME"

# 3. Link to epic (child of epic)
#    ARGUMENT ORDER: dependent first (bid), target second (epic_id)
bd dep add "$bid" "$epic_id" -t parent-child

# 4. For each "Depends on:" entry, resolve to previously-created bid and add blocks dep
bd dep add "$bid" "$dep_bid" -t blocks
```

**Priority mapping:**

| Risk in plan | bd priority |
|---|---|
| HIGH         | P1          |
| MEDIUM       | P2          |
| LOW (default)| P3          |

**Sequential default:** when `Depends on:` is absent, task N automatically depends on
task N-1 (by index in document order). This is applied before `bv --robot-plan` is run.
Override with `Depends on: none` to opt out of this chain.

After all issues created: `bd export -o .beads/issues.jsonl` to export DB → JSONL.

---

## Risk → spike beads (deferred to v2)

**v1 behavior:** emit warning only; do NOT create a spike bead.

```
WARN: task "<title>" marked HIGH risk; spike bead deferred to v2 (see spec §15).
```

v2 will activate full spike-bead behavior per spec §15: a `type=spike` issue
is prepended before each HIGH-risk task, with its own `File scope` and `Depends on`
inherited from the parent task.

---

## File scope inference (when missing)

When a task has no explicit `File scope:` line, apply heuristics in order:

**Heuristic 1 — Explicit paths in body:** aggregate paths mentioned in code blocks or
backticks into a minimal glob set covering all of them. If multiple paths share a common
prefix (e.g. all under `packages/sdk/`), collapse to `<prefix>/**`.
Example: `` `packages/sdk/index.ts` `` and `` `packages/sdk/types.ts` `` → `packages/sdk/**`.

**Heuristic 2 — Title names a package or module:**
If the title references a named package/module (e.g. "Update SDK exports"),
infer `<package_path>/**` using the closest matching directory. Example:
"Refactor CLI utils" → `packages/cli/**` if that path exists in the repo.

**Heuristic 3 — Fallback:**
If neither heuristic yields a concrete scope, set `file_scope = ["**"]` (whole repo) and
force this task into its own isolated track. It cannot safely parallelize with any other task.

**Important:** workers treat `file_scope` as a strict edit boundary regardless of whether
the scope came from an explicit `File scope:` line or inference. They MUST NOT edit files
outside the inferred globs.

---

## Track grouping (after all beads created)

Executed after Phase 2 step 4 (`bd export -o .beads/issues.jsonl`), before spawning workers.

### Step 1 — Get bv's dependency-aware plan

```bash
bv --robot-plan 2>/dev/null > exec-plan.json
```

Each `.plan.tracks[]` in the output is an independent execution lane. Use `track_id`
to label parallel-dispatched workers.

### Step 2 — Compute file-scope unions per track

For each track, compute the union of `file_scope` globs across all its member beads.
This represents the total filesystem footprint of that track.

### Step 3 — Reconcile overlapping tracks

If two tracks have overlapping file-scope unions (any glob in one overlaps any glob
in the other), the track with MORE beads absorbs the smaller track:
- Append the smaller track's `items[]` to the larger track's `items[]`.
- Deduplicate the combined `file_scope` glob set.
- Remove the absorbed track from `exec-plan.tracks`.

If the counts are equal, absorb the later track (by index in `exec-plan.tracks`) into
the earlier one.

### Step 4 — Enforce max-tracks limit

If track count > `--max-tracks` (default: 4), merge the two smallest tracks (by bead
count) into one, repeating until track count ≤ max.

### Step 5 — Assign agent names and write exec-plan

```bash
# Assign adjective+noun names (random, per track): BlueLake, RedFox, GreenMist, ...
# Write final exec-plan to state dir
cat exec-plan.json > .beads/orchestrator-runs/<epic_id>/exec-plan.json
```

The `exec-plan.tracks` order is authoritative for Phase 6 merge order. Iterate in
this order for determinism — `bv --robot-plan` respects bd cross-track dependencies
via topological sort over the issue graph.
