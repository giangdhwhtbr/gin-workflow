# Workflow Token Optimization (Sub-project A) Implementation Plan

> **For agentic workers:** Use the `execute` stage per track. Authoritative task state is tracked via Beads; checkboxes give the visual step breakdown. Do not commit or push unless explicitly authorized.

**Goal:** Cut the per-stage instruction load of gin-workflow to ≤ 12,000 chars by collapsing command → skill → methodology layers into thin commands plus self-contained stage skills that share one stage contract, and give agents a real CLI for gate evidence.

**Architecture:** Commands become thin entry points; each lifecycle stage skill absorbs its methodology skill and points to `references/stage-contract.md`. Abstract Python contracts in prose are replaced by `gin-workflow state|record|unblock`. A token budget test locks the result.

**Tech Stack:** Markdown skills/commands/agents; Python 3 stdlib `unittest`; bash install smoke test.

**Spec:** `.planning/specs/2026-10-01-workflow-token-optimization-design.md`

## Global Constraints

- Test command (repo root): `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` — baseline 2026-10-01: `Ran 535 tests … OK`.
- Install smoke test: `bash tests/install_smoke_test.sh`.
- `plugins/*/dist/` is gitignored and rebuilt by `install.sh`; never edit `dist/` by hand.
- `docs/<name>.md` and `plugins/gin-workflow/src/references/<name>.md` pairs in `CANONICAL_REFERENCE_PAIRS` must stay byte-identical (`test_canonical_references_are_packaged_without_drift`). This plan does **not** modify any pair; skills simply stop linking them.
- `docs/use-cases/*.md` assertions (`test_t8_*`) must keep passing; lifecycle semantics are unchanged.
- Banned tokens in `commands/*.md` and `skills/**/SKILL.md` at the end: `ContextManifest`, `ArtifactRegistry`, `ApprovalDecision`, `load_effective_config`.
- Budgets (chars): stage chain ≤ 12,000; `commands/*.md` ≤ 1,200; `gin-*` skill ≤ 6,000; `agents/*.md` ≤ 4,000; sum of frontmatter `description` ≤ 4,000.
- Plan-level `Reasoning: low` already dispatches at `cheap_simple` (`workflow_providers/worker_dispatch.py:394`); no new code for the spec's "complexity: low ⇒ cheap_simple" rule — only document it in `plan`.
- Commit/push only with explicit user authorization.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: brainstorm `high_reasoning`; design `high_reasoning`; plan `standard_impl`; implement `standard_impl`; verify `standard_impl`; review `high_reasoning`; docs `cheap_simple`
- `override_rule`: Use `high_reasoning` only for Track 4/5 content consolidation where behavior must be preserved while text shrinks.

## Requirement Analysis
- Problem: 3+ instruction layers per stage, 16 duplicated wrapper paragraphs, abstract contracts agents cannot call, no CLI to write gate events, oversized forked superpowers skills, expensive tier defaults.
- Success: budget test passes; `gin-workflow record` makes gates `satisfied`; full suite + smoke tests green; before/after table in handoff.
- Constraints: lifecycle stages/gates unchanged; existing configs untouched; Codex/Antigravity keep working without superpowers.
- Non-goals: lifecycle merging, fast path, project profiles, rules (sub-projects B+C, D).

## Approach Options
### Option 1: Thin command + self-contained stage skill + shared contract (selected)
- Pros: 2 layers, measurable budget, skills still auto-triggerable. Cons: many files change; packaging tests need updates.
### Option 2: Fat commands, no stage skills
- Cons: loses skill auto-invocation that Codex/Antigravity rely on.
### Recommended Approach
- Option 1, as confirmed in discovery.

## Scope
- In: `plugins/gin-workflow/src/{commands,skills,agents,references/stage-contract.md,scripts/workflow_core,examples}`, tests under `tests/`.
- Out: `docs/**` content, root `review.md`/`Plan.md` (listed in handoff only), router semantics.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Tracks share skill/agent files and packaging tests; sequential execution avoids merge conflicts in Markdown consolidation.
```

## File Structure

| Path | Responsibility |
|---|---|
| `scripts/workflow_core/budget.py` (new) | Measure stage load chains and description totals; `--report` table |
| `scripts/workflow_core/lifecycle_cli.py` | Add `record` subcommand |
| `scripts/workflow_core/cli.py` | Route `record` to lifecycle CLI |
| `scripts/workflow_core/configuration.py` | `verify` tier default → `standard_impl` |
| `scripts/workflow_core/review_coordinator.py` | `max_cycles` default 3 → 2 |
| `examples/config.full.yaml` | `max_cycles: 2` |
| `references/stage-contract.md` (new) | Shared stage rules + CLI |
| `commands/*.md` | Thin entries |
| `skills/<stage>/SKILL.md` | Self-contained stage skills |
| `skills/execute/references/{worker-lifecycle,delegation-policy,result-contract}.md` | Moved from `worker-dispatch` |
| `skills/review/SKILL.md` (new) | Merged review skill |
| `skills/gin-{debugging,worktrees,review-response,parallel-agents,knowledge}/SKILL.md` (new) | Compact shared skills |
| `agents/*.md` | Point to stage skills; ≤ 4,000 |
| `tests/workflow_core/test_token_budget.py` (new) | Budget assertions |
| `tests/workflow_core/test_lifecycle_cli.py` | `record` tests |
| `tests/workflow_providers/test_harness_packaging.py`, `tests/install_smoke_test.sh`, `tests/workflow_providers/test_routed_worker.py`, `tests/workflow_core/test_config_examples.py` | Updated paths/defaults |

## Tasks

### Track 1: Budget measurement module and baseline

**Metadata:**
- Dependencies: none
- Provider role: general
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: low

**Files:**
- Create: `plugins/gin-workflow/src/scripts/workflow_core/budget.py`
- Create: `tests/workflow_core/test_token_budget.py`

**Interfaces:**
- Produces: `STAGES: tuple[str, ...]`; `stage_chain(src: Path, stage: str) -> list[Path]`; `stage_chars(src: Path, stage: str) -> int`; `description_chars(src: Path) -> int`; `report(src: Path) -> str`; `python3 -m workflow_core.budget --report [--src PATH]`.

- [ ] **Step 1: Write failing tests for the measurement logic (not budgets yet)**

```python
"""Token budget measurement and limits for packaged gin-workflow instructions."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workflow_core.budget import description_chars, stage_chain, stage_chars

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "plugins/gin-workflow/src"


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestBudgetMeasurement(unittest.TestCase):
    def test_chain_includes_command_skill_and_linked_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write(src, "commands/execute.md", "---\ndescription: x\n---\nUse the `execute` skill.\n")
            _write(src, "skills/execute/SKILL.md", "Follow references/stage-contract.md.\nSee [w](references/worker-lifecycle.md).\n")
            _write(src, "references/stage-contract.md", "contract")
            _write(src, "skills/execute/references/worker-lifecycle.md", "lifecycle")
            _write(src, "references/unrelated.md", "unused")
            names = sorted(p.relative_to(src).as_posix() for p in stage_chain(src, "execute"))
            self.assertEqual(
                [
                    "commands/execute.md",
                    "references/stage-contract.md",
                    "skills/execute/SKILL.md",
                    "skills/execute/references/worker-lifecycle.md",
                ],
                names,
            )
            self.assertEqual(sum(len(p.read_text()) for p in stage_chain(src, "execute")), stage_chars(src, "execute"))

    def test_description_chars_sums_frontmatter_descriptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write(src, "skills/a/SKILL.md", "---\nname: a\ndescription: abcd\n---\n")
            _write(src, "agents/b.md", "---\nname: b\ndescription: ef\n---\n")
            _write(src, "commands/c.md", "---\ndescription: g\n---\n")
            self.assertEqual(7, description_chars(src))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and confirm failure**

Run: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_token_budget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'workflow_core.budget'`

- [ ] **Step 3: Implement `budget.py`**

```python
"""Measure instruction size loaded per lifecycle stage (chars; ~4 chars ≈ 1 token)."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

STAGES = ("discuss", "plan", "orchestrate", "execute", "verify", "ship", "review", "workflow", "progress")

_REFERENCE = re.compile(r"(?<![\w/.-])((?:references/)[\w./-]+\.md)")
_DESCRIPTION = re.compile(r"^description:\s*(.*)$", re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _linked(src: Path, owner: Path) -> list[Path]:
    found = []
    for relative in _REFERENCE.findall(owner.read_text(encoding="utf-8")):
        for base in (owner.parent, src):
            candidate = (base / relative).resolve()
            if candidate.is_file() and candidate.is_relative_to(src.resolve()):
                found.append(candidate)
                break
    return found


def stage_chain(src: Path, stage: str) -> list[Path]:
    src = Path(src)
    roots = [p for p in (src / f"commands/{stage}.md", src / f"skills/{stage}/SKILL.md") if p.is_file()]
    chain: dict[Path, None] = {p.resolve(): None for p in roots}
    for owner in roots:
        for linked in _linked(src, owner):
            chain.setdefault(linked, None)
    return list(chain)


def stage_chars(src: Path, stage: str) -> int:
    return sum(len(p.read_text(encoding="utf-8")) for p in stage_chain(src, stage))


def description_chars(src: Path) -> int:
    src = Path(src)
    files = [*src.glob("skills/*/SKILL.md"), *src.glob("agents/*.md"), *src.glob("commands/*.md")]
    total = 0
    for path in files:
        header = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        match = _DESCRIPTION.search(header.group(1)) if header else None
        total += len(match.group(1).strip()) if match else 0
    return total


def report(src: Path) -> str:
    lines = ["| Stage | Chars |", "|---|---|"]
    lines += [f"| {stage} | {stage_chars(src, stage):,} |" for stage in STAGES]
    lines.append(f"| descriptions | {description_chars(src):,} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workflow_core.budget")
    parser.add_argument("--report", action="store_true", required=True)
    parser.add_argument("--src", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    print(report(args.src))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_token_budget.py -v`

- [ ] **Step 5: Record baseline**

Run: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.budget --report > .agent-workflow/runtime/evidence/token-budget-baseline.md` and keep the table for the handoff. (Numbers may differ from the spec's throwaway-script table; this report is authoritative.)

### Track 2: `gin-workflow record` gate writer

**Metadata:**
- Dependencies: none
- Provider role: backend
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: low

**Files:**
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py` (`main`, new `_record_command`)
- Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py:61-65` (allow `record`)
- Test: `tests/workflow_core/test_lifecycle_cli.py`

**Interfaces:**
- Produces: `gin-workflow record {requirement-confirmed,plan-approved,orchestration-ready} --evidence TEXT --actor ID [--workflow-id ID] [--repository PATH] [--format text|json]`; writes events read by `_process_gate_state`.

- [ ] **Step 1: Write failing tests** (append to `TestLifecycleCLI`)

```python
    def _state_gates(self, workflow_id="default-workflow"):
        import io
        from unittest.mock import patch

        with patch("sys.stdout", new=io.StringIO()) as out:
            lifecycle_main(["state", "--repository", str(self.repo_path), "--format", "json", "--workflow-id", workflow_id])
        return json.loads(out.getvalue())["gates"]

    def test_record_marks_each_process_gate_satisfied(self):
        for gate in ("requirement-confirmed", "plan-approved", "orchestration-ready"):
            exit_code = cli_main([
                "record", gate,
                "--repository", str(self.repo_path),
                "--evidence", ".planning/specs/x.md",
                "--actor", "user",
            ])
            self.assertEqual(0, exit_code)
        gates = self._state_gates()
        for gate in ("requirement_confirmed", "plan_approved", "orchestration_ready"):
            self.assertEqual("satisfied", gates[gate])

    def test_record_is_scoped_to_workflow_id(self):
        cli_main(["record", "requirement-confirmed", "--repository", str(self.repo_path),
                  "--evidence", "spec.md", "--actor", "user", "--workflow-id", "other"])
        self.assertEqual("unmet", self._state_gates()["requirement_confirmed"])
        self.assertEqual("satisfied", self._state_gates("other")["requirement_confirmed"])

    def test_record_rejects_unknown_gate_and_missing_evidence(self):
        self.assertEqual(2, cli_main(["record", "shipped", "--repository", str(self.repo_path),
                                      "--evidence", "x", "--actor", "user"]))
        self.assertEqual(2, cli_main(["record", "plan-approved", "--repository", str(self.repo_path),
                                      "--actor", "user"]))
```

- [ ] **Step 2: Run and confirm failure**

Run: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/workflow_core/test_lifecycle_cli.py -v`
Expected: FAIL — `record` returns 2 (`usage: gin-workflow {setup,state,unblock}`).

- [ ] **Step 3: Implement**

In `cli.py` `main`, replace the allowlist and lifecycle dispatch:

```python
    if not argv or argv[0] not in ("setup", "state", "unblock", "record"):
        print("usage: gin-workflow {setup,state,unblock,record} <command>", file=sys.stderr)
        return 2
    if argv[0] in ("state", "unblock", "record"):
```

In `lifecycle_cli.py`, add near `_process_gate_state`:

```python
_RECORDABLE_GATES = {
    "requirement-confirmed": ("requirement.confirmed", {}),
    "plan-approved": ("approval.recorded", {"action": "plan_approved", "decision": {"status": "approved"}}),
    "orchestration-ready": ("orchestration.ready", {}),
}


def _record_command(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    event_type, base_payload = _RECORDABLE_GATES[args.gate]
    store = _get_event_store(Path(args.repository).resolve())
    event = WorkflowEvent.create(
        event_type=event_type,
        workflow_id=args.workflow_id,
        actor=args.actor,
        payload={**base_payload, "evidence": args.evidence},
        idempotency_key=f"{args.workflow_id}:{args.gate}:{args.evidence}",
    )
    appended = store.append(event)
    return {
        "status": "recorded" if appended else "already_recorded",
        "gate": args.gate,
        "event_type": event_type,
        "workflow_id": args.workflow_id,
        "message": f"{args.gate} recorded for {args.workflow_id}",
    }, 0
```

In `lifecycle_cli.main`: change both allowlists to `("state", "unblock", "record")` (usage text `{state,unblock,record}`), and before the final `return 2` add:

```python
    if command == "record":
        parser.add_argument("gate", choices=tuple(_RECORDABLE_GATES))
        parser.add_argument("--evidence", required=True)
        parser.add_argument("--actor", required=True)
        try:
            args = parser.parse_args(argv[1:])
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else 2
        payload, exit_code = _record_command(args)
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(payload["message"])
        return exit_code
```

- [ ] **Step 4: Run tests — expect PASS**, then full suite (Global Constraints command) — expect OK.

### Track 3: Stage contract and thin commands

**Metadata:**
- Dependencies: Track 2
- Provider role: docs
- Reasoning: medium
- Model guidance: standard_impl
- Estimated complexity: medium

**Files:**
- Create: `plugins/gin-workflow/src/references/stage-contract.md`
- Modify: all `plugins/gin-workflow/src/commands/*.md`

**Interfaces:**
- Produces: `references/stage-contract.md` — every stage skill's first body line is `Follow references/stage-contract.md.`

- [ ] **Step 1: Write `references/stage-contract.md` (≤ 1,600 chars)** with exactly these sections:
  - `## Configuration` — If `.agent-workflow/generated/effective-config.yaml` is missing, stop and tell the user to run `/setup` once. `capabilities: {}` is valid (all capabilities enabled). Never run setup from a lifecycle stage.
  - `## State and gates` — `gin-workflow state --format json [--workflow-id ID]`; `gin-workflow record <requirement-confirmed|plan-approved|orchestration-ready> --evidence <path|ids> --actor <id> [--workflow-id ID]`; `gin-workflow unblock --gate GATE --reason TEXT --actor ID [--follow-up TASK_ID]`. Later gates come from Beads, review-ledger, and git.
  - `## Evidence` — valid: test/command output, review-ledger state, bead IDs, spec/plan paths. Never: self-assessment, summaries, notification delivery.
  - `## Approval` — explicit user confirmation in the harness before `plan-approved`, production-impacting parallel work, disabling worktree isolation, or execution-strategy/scope changes; record it before acting.
  - `## Context` — load only the requirement, file scope, and validation intent; look up symbols/tests/knowledge on demand; use `codegraph explore` when `.codegraph/` exists, else grep/read.
  - `## Git` — commit/push only with explicit authorization.
- [ ] **Step 2: Rewrite each `commands/<name>.md`** to ≤ 1,200 chars: keep frontmatter (`name`, `description` ≤ 100 chars), one-paragraph purpose, `Use the \`<name>\` skill.`, and any command-specific stop rule (e.g. `/discuss` never plans; `/execute` handles one unit). Remove the Wrapper boundary paragraph and banned tokens. `commands/setup.md` keeps the CLI subcommand list (it is outside the lifecycle and does not link the contract).
- [ ] **Step 3: Verify** — `grep -lE 'ContextManifest|ArtifactRegistry|ApprovalDecision|load_effective_config' plugins/gin-workflow/src/commands/*.md` prints nothing; `wc -c plugins/gin-workflow/src/commands/*.md` all ≤ 1,200; full suite OK.

### Track 4: Self-contained lifecycle stage skills

**Metadata:**
- Dependencies: Track 3
- Provider role: docs
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: high

**Files:**
- Modify: `skills/{discuss,plan,orchestrate,execute,verify,ship,workflow,progress,setup,tech-doc}/SKILL.md`
- Create: `skills/review/SKILL.md`
- Move: `skills/worker-dispatch/references/*.md` → `skills/execute/references/` (content unchanged)
- Move: `skills/writing-plans/plan-schema.md` → `skills/plan/plan-schema.md` (content unchanged)
- Delete: `skills/{discovering-work,writing-plans,bead-orchestrator,executing-plans,bead-worker,worker-dispatch,verification-before-completion,finishing-a-development-branch,cross-agent-code-review,requesting-code-review,approval-manager,evidence-manager,context-manager,context-retrieval}/`
- Modify: `tests/workflow_providers/test_harness_packaging.py` (`REQUIRED_ARTIFACTS`), `tests/install_smoke_test.sh` (`required`), `tests/workflow_providers/test_routed_worker.py:514-525` (paths)

Absorption map and behavior that must survive (verbatim phrases are asserted by tests or reviewers):

| Skill | Absorbs | Must keep |
|---|---|---|
| `discuss` | `discovering-work` | one question at a time; 2–3 approaches; spec to `.planning/specs/YYYY-MM-DD-<topic>-design.md`; self-review; explicit confirmation then `gin-workflow record requirement-confirmed`; no plan/beads |
| `plan` | `writing-plans` | link `plan-schema.md`; tracks with provider role + reasoning (`low` ⇒ `cheap_simple`); `validate_plan_assignments` via CLI-free instruction "every track has a configured role and low/medium/high reasoning"; no placeholders; approval then `gin-workflow record plan-approved` |
| `orchestrate` | `bead-orchestrator` | parent vs track beads; merge-hold only on parent; `gin-workflow record orchestration-ready --evidence <bead-ids>` |
| `execute` | `executing-plans`, `bead-worker`, `worker-dispatch` | one ready unit; phrases "provider role and reasoning" and "never downgrade the requested reasoning"; links `references/worker-lifecycle.md`, `references/delegation-policy.md`, `references/result-contract.md` (relative to the skill); handoff two options when no commit authority |
| `verify` | `verification-before-completion` | run verification commands fresh and cite output before claiming; failures route to `gin-debugging` |
| `ship` | `finishing-a-development-branch` | present merge/PR/keep/discard options; `python3 review-ledger.py cleanup --bead-id <bead-id>`; no auto commit/push |
| `review` | `cross-agent-code-review`, `requesting-code-review` | review-ledger commands (`start-review`, `add-finding`, `verify-finding`, `reopen-finding`, `checkpoint`, `approve`); independent reviewer; `max_cycles` from config |

- [ ] **Step 1:** Update the three test files first so they point at the new locations (`skills/execute/SKILL.md`, `skills/execute/references/*.md`, `skills/review/SKILL.md`, `skills/plan/plan-schema.md`, `references/stage-contract.md`; drop deleted skills). Run the suite — expect FAIL on missing files.
- [ ] **Step 2:** Write each stage skill: frontmatter `name`, `description` (≤ 120 chars); first body line `Follow references/stage-contract.md.`; then stage-specific numbered steps covering the "Must keep" column; no rationale essays, no anti-rationalization tables, no banned tokens.
- [ ] **Step 3:** Move/delete per Files list; `grep -rn` the src tree for every deleted skill name and update remaining links (agents are handled in Track 5 — leave them if only agents reference a deleted name, and list them).
- [ ] **Step 4:** Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m workflow_core.budget --report` — every stage ≤ 12,000; trim until true. Run full suite — expect OK (except agent link checks fixed in Track 5, if any; list them).

### Track 5: Shared `gin-*` skills and agents

**Metadata:**
- Dependencies: Track 4
- Provider role: docs
- Reasoning: high
- Model guidance: high_reasoning
- Estimated complexity: medium

**Files:**
- Create: `skills/gin-debugging/SKILL.md` (+ keep `find-polluter.sh`; fold `root-cause-tracing.md` essentials inline), `skills/gin-worktrees/SKILL.md`, `skills/gin-review-response/SKILL.md`, `skills/gin-parallel-agents/SKILL.md`, `skills/gin-knowledge/SKILL.md`
- Delete: `skills/{systematic-debugging,using-git-worktrees,receiving-code-review,dispatching-parallel-agents,knowledge-capture,knowledge-reconciliation}/`
- Modify: `agents/*.md`; `skills/telegram-notify/SKILL.md`, `skills/beads-migration/SKILL.md` (only links/banned tokens; add "load only when configured or explicitly invoked")

- [ ] **Step 1:** Write each `gin-*` skill ≤ 6,000 chars keeping gin-specific behavior: debugging = root cause before fix, reproduce, one hypothesis at a time, `find-polluter.sh`; worktrees = `scripts/worktree-create.sh`/`worktree-cleanup.sh`, `.planning/worktrees`, approval to disable isolation; review-response = review-ledger `fix-finding`/`dispute-finding`/`propose-deferral`/`provide-clarification`/`change-scope`/`checkpoint`; parallel-agents = only independent units, one scope per agent; knowledge = capture decisions/risks to `.planning/knowledge` and reconcile at ship.
- [ ] **Step 2:** Rewrite `agents/*.md` to ≤ 4,000 chars each: role, inputs, "follow the `<stage>` skill", output contract. Remove references to deleted skills.
- [ ] **Step 3:** `grep -rn` src for every deleted skill name — no hits outside the absorption notes. Budget report: `description` total ≤ 4,000. Full suite OK.

### Track 6: Defaults, budget assertions, packaging verification

**Metadata:**
- Dependencies: Track 5
- Provider role: backend
- Reasoning: low
- Model guidance: standard_impl
- Estimated complexity: low

**Files:**
- Modify: `scripts/workflow_core/configuration.py:47` (`"verify": "standard_impl"`)
- Modify: `scripts/workflow_core/review_coordinator.py:111` (`max_cycles: int = 2`)
- Modify: `examples/config.full.yaml` (`max_cycles: 2`), `tests/workflow_core/test_config_examples.py:33` (expect 2)
- Modify: `skills/setup/SKILL.md` (question 9 suggests 2 cycles)
- Modify: `tests/workflow_core/test_token_budget.py` (add `TestBudgetLimits`)

- [ ] **Step 1: Add failing budget limits**

```python
from workflow_core.budget import STAGES

BANNED = ("ContextManifest", "ArtifactRegistry", "ApprovalDecision", "load_effective_config")


class TestBudgetLimits(unittest.TestCase):
    def test_each_stage_chain_within_budget(self):
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertLessEqual(stage_chars(SRC, stage), 12_000)

    def test_commands_agents_and_shared_skills_within_budget(self):
        limits = [("commands/*.md", 1_200), ("agents/*.md", 4_000), ("skills/gin-*/SKILL.md", 6_000)]
        for pattern, limit in limits:
            for path in SRC.glob(pattern):
                with self.subTest(path=path.name):
                    self.assertLessEqual(len(path.read_text(encoding="utf-8")), limit)

    def test_descriptions_within_budget(self):
        self.assertLessEqual(description_chars(SRC), 4_000)

    def test_no_abstract_contract_tokens(self):
        for path in [*SRC.glob("commands/*.md"), *SRC.glob("skills/**/SKILL.md")]:
            text = path.read_text(encoding="utf-8")
            for token in BANNED:
                with self.subTest(path=str(path.relative_to(SRC)), token=token):
                    self.assertNotIn(token, text)
```

- [ ] **Step 2:** Run `test_token_budget.py` — expect PASS if Tracks 3–5 met budgets; any failure is fixed in the offending file, never by raising a limit.
- [ ] **Step 3:** Apply default changes; update `test_config_examples.py`; run `test_configuration.py`, `test_review_coordinator.py`, `test_end_to_end.py` and fix assertions that encoded `max_cycles=3` defaults only where they relied on the default (explicit configs stay 3).
- [ ] **Step 4:** Full suite OK; `bash tests/install_smoke_test.sh` OK; `bash install.sh --dry-run` builds all three harness layouts.
- [ ] **Step 5:** Produce handoff table: baseline (Track 1 evidence) vs `python3 -m workflow_core.budget --report`; list `docs/*` duplicates, root `review.md`, `Plan.md` for user decision.

## Integration
- **Branch**: `feat/token-optimization` (create only when execution starts; worktree per `gin-worktrees`)
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` — OK
- [ ] `bash tests/install_smoke_test.sh` — OK
- [ ] Budget report: all stages ≤ 12,000; descriptions ≤ 4,000
- [ ] `gin-workflow record …` then `gin-workflow state --format json` shows gate `satisfied`
- [ ] Manual: run `/discuss` in a scratch repo on Claude Code and confirm the skill loads and references `stage-contract.md`

## Risks
- Behavior lost during consolidation → "Must keep" table + reviewer checks each row (Track 4/5 review at `high_reasoning`).
- Hidden text assertions in tests → run full suite after every track; Track 4 Step 1 updates known path assertions first.
- `install.sh` may enumerate skill dirs → covered by smoke test in Track 6.
- Existing consumer repos referencing deleted skill names in their own docs → release note lists renames.

## Notes
- Model guidance is planning metadata, not Beads state.
- Parent bead: "Sub-project A: token optimization" stays open until human-confirmed merge; track beads close on tests + review.
