# Plan: {title}

## Objective
{What success looks like}

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
- Problem statement: ...
- Success criteria: ...
- Constraints: ...
- Non-goals: ...

## Approach Options
### Option 1: {name}
- Summary: ...
- Pros: ...
- Cons: ...

### Option 2: {name}
- Summary: ...
- Pros: ...
- Cons: ...

### Recommended Approach
- Selected option: ...
- Rationale: ...

## Scope
- In scope: ...
- Out of scope: ...

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Concrete reason for the selected mode
```

- Valid pairings are only `direct` with `workers.mode: sequential`, and `worker` with `workers.mode: parallel`.
- Use `direct` / `sequential` for sequential work, explicitly one-agent work, work with three or fewer tasks, or work without a qualifying worker condition.
- Use `worker` / `parallel` only for more than three independent parallel tasks, long-running work, specialized work, or an independent review.
- `workers.mode` declares scheduling behavior only. It never contains provider model names, commands, credentials, or implementation methodology.

## Tasks
### Track 1: {name}
- **Dependencies**: none | Track N
- **Files**: one entry per file, indented under this label. `team check-plan` reads files only from this block: the leading backticked paths of each entry (comma-separated), after an optional `Create`, `Modify`, `Test`, or `Delete`; notes after them are ignored.
  - Create `path/to/new_file.py`
  - Modify `path/to/existing.py:10-40` (what changes)
  - Test `tests/path/test_file.py`
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded change to one module with a clear spec; edge cases listed in the spec.
- **Human gate**: omit, or what a person must do (credentials, production access, a manual or third-party approval); `/goal` runs stop before this track and its dependents
- **Acceptance criteria**: ...
- **Estimated complexity**: low | medium | high

### Track 2: {name}
...

## Integration
- **Branch**: {integration-branch-name}
- **Merge strategy**: sequential | parallel-then-merge

## Validation
- [ ] All tests pass
- [ ] Type checks clean
- [ ] Manual verification steps

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric.
- Omit `Effort:` when the catalog lists no efforts.
- Unclear requirements never raise the model or effort; ask the user or return to `discuss`.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- Deliverable merge-holds (e.g. "remain open until human-confirmed merge") apply exclusively to the Parent Bead. Individual track beads must close upon passing tests and code review to unblock downstream dependent tracks.
