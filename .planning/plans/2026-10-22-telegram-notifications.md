# Plan: Telegram notifications behind a config switch

Workflow: telegram-notifications
Spec: `.planning/specs/2026-10-22-telegram-notifications-design.md`

## Goal

One switch, `notifications.telegram` in `.agent-workflow/config.yaml` (default off), and one-way Telegram messages for exactly two situations: the agent needs the user's input (`needs_input`), or a long unattended run or a routed worker has finished (`run_finished`, `worker_finished`, `worker_failed`). One sender, `workflow_core.notify`, shared by gin-workflow and gin-orchestrator. `telegram.sh` and the `telegram-notify` skill go away.

## Architecture

- `workflow_core/notify.py`: `notify(root, event, message)` reads the effective config, posts to the Bot API with `urllib`, returns a warning instead of raising. `gin-workflow notify` wraps it and always exits 0 except on a usage error.
- Skills call the CLI: the shared stage contract (`needs_input`), `execute` (`run_finished`), the worker lifecycle reference (`worker_finished`/`worker_failed`).
- gin-orchestrator's `TelegramNotificationProvider` calls `workflow_core.ext.notify`; `WorkerScheduler` sends worker events through it.

## Tech Stack

Python 3 stdlib (`urllib.request`, `argparse`), PyYAML (already required), unittest, bash/PowerShell install scripts.

## Global Constraints

Copied from the spec:

- Delivery failures never fail a command or a stage: `notify` returns a warning, the CLI exits 0, and gin-orchestrator's provider returns an `unavailable` result as it does today.
- Credentials stay in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` and are never written to the config. The token never appears in a warning or in output.
- Existing configs stay valid: the key is optional in schema 2.8.
- Removing `notification.ask` and the reply fields changes gin-orchestrator's internal provider contract, not the CLI contract (still 2).
- Out of scope: two-way messages, other channels, per-event toggles, and notifications for closing a track or an epic, recording a gate, or shipping.

Repository constraints:

- gin-workflow never imports gin-orchestrator; gin-orchestrator imports gin-workflow only through `workflow_core.ext`.
- Every stage chain stays within `tests/workflow_core/test_token_budget.py` (12 000 characters; `quick` 8 000). `execute` is at 11 988 today.
- Versions are bumped once, in the last track.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: Telegram is opt-in by environment only, no stage calls it, its `ask` mode contradicts the stage contract, and the orchestrator provider is never used.
- Success criteria: spec requirements 1–11 and US-1..US-3 acceptance criteria hold; the full suite passes.
- Constraints: see Global Constraints.
- Non-goals: see the spec's out-of-scope list.

## Approach Options
### Option 1: CLI sender plus skill call sites, orchestrator through `ext` (A + C)
- Summary: as in Architecture.
- Pros: one sender and one switch; deterministic; works without gin-orchestrator.
- Cons: a new CLI subcommand.

### Option 2: skills call `telegram.sh` behind a config check
- Summary: each stage reads the switch and runs the script.
- Pros: no Python.
- Cons: agents forget; bash only; two senders once the orchestrator is involved.

### Recommended Approach
- Selected option: Option 1, confirmed in discuss.
- Reasoning: single sender, stdlib only, cross-platform, no-op when off.

## Scope
- In scope: spec requirements 1–11.
- Out of scope: the spec's out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Four dependent tracks; each builds on the previous one's interface.
```

## Tasks

### Track 1: Switch, sender, `gin-workflow notify`, doctor warning
- **Dependencies**: none
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/notify.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py` (`CONFIG_SCHEMA["properties"]`, next to `"clarify"`, ~line 208)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py` (`main`, lines 61–100: command tuple, usage string, dispatch)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/ext.py` (import and `__all__`)
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py` (`doctor`, after the `provider_mode == "multi"` block, ~line 495)
  - Modify `docs/reference/cli.md` (new `## \`gin-workflow notify\`` section before `## \`gin-workflow paths\``), `docs/reference/config.md` (new `### \`notifications\`` under Keys, after `### \`clarify\``)
  - Test: create `tests/workflow_core/test_notify.py`; modify `tests/workflow_core/test_schema_2_8.py`, `tests/workflow_core/test_setup_cli.py`
- **Interfaces produced**:
  - `workflow_core.notify.EVENTS: tuple[str, ...] = ("needs_input", "run_finished", "worker_finished", "worker_failed")`
  - `workflow_core.notify.notify(root: Path | str, event: str, message: str, *, environ: Mapping[str, str] | None = None, opener: Callable | None = None) -> str | None` — `None` when off or delivered; a warning string otherwise; `ValueError` for an unknown event.
  - `workflow_core.notify.credentials_warning(environ: Mapping[str, str]) -> str | None`
  - `workflow_core.notify.main(argv: Sequence[str]) -> int`
  - `workflow_core.ext.notify` (re-export)
  - CLI: `gin-workflow notify --event <event> [--repository PATH] MESSAGE`
- **Steps**:
  1. Write `tests/workflow_core/test_notify.py` (setUp like `tests/workflow_core/test_routes_cli.py`: temp repo, `config.yaml` with `harness: claude`, `schema_version: '2.8'`, `refresh(root)`; a helper appends `notifications:\n  telegram: true\n` and refreshes). Cases:
     - off: a recording opener is never called; result `None`.
     - on, `environ={}`: result contains `telegram_credentials_missing`.
     - on, success: a fake opener returning a context manager with `status = 200` gets one request; `request.full_url == "https://api.telegram.org/botTOKEN/sendMessage"`; `urllib.parse.parse_qs(request.data.decode())` has `chat_id == ["42"]` and `text == [f"[{root.name}] needs_input: plan ready"]`; result `None`.
     - on, opener raises `urllib.error.HTTPError(url, 500, "boom", {}, None)`: warning contains `500`, not `TOKEN`.
     - on, opener raises `urllib.error.URLError("down")`: warning present, not `TOKEN`.
     - `notify(root, "bogus", "x")` raises `ValueError`.
     - CLI: `notify.main(["--event", "bogus", "x"])` raises `SystemExit` with code 2; with the switch on and `TELEGRAM_*` removed from `os.environ` (`patch.dict`), `main(["--event", "needs_input", "--repository", str(root), "hi"])` returns 0 and stderr contains `telegram_credentials_missing`.
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_notify` → fails (module missing).
  3. Create `notify.py`:
     ```python
     """`gin-workflow notify`: one-way Telegram messages behind `notifications.telegram`."""

     from __future__ import annotations

     import argparse
     import os
     from pathlib import Path
     import sys
     from typing import Any, Callable, Mapping, Sequence
     import urllib.error
     import urllib.parse
     import urllib.request

     from .checkout import main_checkout
     from .configuration import ConfigValidationError, load_effective_config

     EVENTS = ("needs_input", "run_finished", "worker_finished", "worker_failed")
     _API = "https://api.telegram.org/bot{token}/sendMessage"


     def _enabled(root: Path) -> bool:
         try:
             section = load_effective_config(root).get("notifications", {})
         except ConfigValidationError:
             return False
         return isinstance(section, Mapping) and section.get("telegram") is True


     def credentials_warning(environ: Mapping[str, str]) -> str | None:
         if environ.get("TELEGRAM_BOT_TOKEN") and environ.get("TELEGRAM_CHAT_ID"):
             return None
         return "telegram_credentials_missing: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"


     def notify(root: Path | str, event: str, message: str, *, environ: Mapping[str, str] | None = None,
                opener: Callable[..., Any] | None = None) -> str | None:
         """Send one message when the switch is on; a warning instead of raising, never the token."""
         if event not in EVENTS:
             raise ValueError(f"unknown event: {event}; expected one of {', '.join(EVENTS)}")
         root = Path(root).resolve()
         if not _enabled(root):
             return None
         env = os.environ if environ is None else environ
         if warning := credentials_warning(env):
             return warning
         text = f"[{main_checkout(root).name}] {event}: {message}"
         data = urllib.parse.urlencode({"chat_id": env["TELEGRAM_CHAT_ID"], "text": text}).encode()
         request = urllib.request.Request(_API.format(token=env["TELEGRAM_BOT_TOKEN"]), data=data)
         try:
             with (opener or urllib.request.urlopen)(request, timeout=10) as reply:
                 status = reply.status
         except urllib.error.HTTPError as error:
             return f"telegram delivery failed (HTTP {error.code})"
         except (urllib.error.URLError, OSError) as error:
             return f"telegram delivery failed ({type(error).__name__})"
         return None if 200 <= status < 300 else f"telegram delivery failed (HTTP {status})"


     def main(argv: Sequence[str]) -> int:
         parser = argparse.ArgumentParser(prog="gin-workflow notify")
         parser.add_argument("--event", required=True, choices=EVENTS)
         parser.add_argument("--repository", default=".")
         parser.add_argument("message")
         args = parser.parse_args(list(argv))
         if warning := notify(Path(args.repository), args.event, args.message):
             print(f"Warning: {warning}", file=sys.stderr)
         return 0
     ```
  4. `cli.py`: add `"notify"` to the command tuple and the usage string (after `routes`), and dispatch `if argv[0] == "notify": from .notify import main as notify_main; return notify_main(argv[1:])`.
  5. `ext.py`: `from .notify import notify` and `"notify"` in `__all__` (alphabetical).
  6. Run step 2's command → passes.
  7. Schema: in `test_schema_2_8.py` add `test_notifications_telegram_is_an_optional_boolean`: a migrated 2.8 config plus `{"notifications": {"telegram": True}}` passes `validate_portable_config`; `{"telegram": "yes"}` and `{"telegram": True, "slack": True}` raise `ConfigValidationError`. Run → fails. Add to `CONFIG_SCHEMA["properties"]`:
     ```python
     "notifications": {
         "type": "object",
         "properties": {"telegram": {"type": "boolean"}},
         "additionalProperties": False,
     },
     ```
     Run → passes.
  8. Doctor: in `test_setup_cli.py` add `test_doctor_warns_when_telegram_is_on_without_credentials` (pattern of `test_doctor_reports_orchestrator_missing_with_the_install_command`): `init`, then `configure --approve --set notifications.telegram=true`; `doctor` with an env lacking both variables → an `actions` entry contains `telegram_credentials_missing`; with both set → none; a repo without the key → none. Run → fails. In `doctor`, after the multi block:
     ```python
         if isinstance(effective.get("notifications"), Mapping) and effective["notifications"].get("telegram") is True:
             if warn := credentials_warning(os.environ):
                 actions.append(warn)
     ```
     with `from .notify import credentials_warning` at the top. Run → passes.
  9. Docs: `cli.md` section (usage line, the four events, exit codes 0/2, "no-op unless `notifications.telegram` is true", credentials from the two variables); `config.md` `### \`notifications\`` (key, default off, how to enable with `gin-workflow setup configure --set notifications.telegram=true --approve`, the doctor warning). Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage` → passes.
- **Acceptance criteria**: the new tests pass; `gin-workflow notify` is listed in the CLI usage and documented; schema accepts only a boolean `notifications.telegram`; doctor warns only when on without credentials.

### Track 2: gin-orchestrator sends through `workflow_core.ext.notify`
- **Dependencies**: Track 1
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/contracts.py` (`NotificationRequest`, `NotificationReceipt`, lines 757–771)
  - Rewrite `plugins/gin-orchestrator/src/scripts/gin_orchestrator/notifications.py`
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/fakes.py` (`FakeNotificationProvider`, ~lines 508–526)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_scheduler.py` (`__init__` lines 84–107; `schedule` line 296)
  - Modify `plugins/gin-orchestrator/src/scripts/gin_orchestrator/registry.py` (`build_worker_scheduler`, lines 420–432)
  - Modify `plugins/gin-orchestrator/src/README.md` (drop the Telegram script from the copied-scripts sentence, line 21)
  - Test: modify `tests/gin_orchestrator/test_contracts.py` (lines 340–370), `tests/gin_orchestrator/test_worker_scheduler.py`, `tests/gin_orchestrator/test_registry.py` (line 629 area)
- **Interfaces consumed**: `workflow_core.ext.notify` (Track 1).
- **Interfaces produced**:
  - `NotificationRequest(event: str, message: str)`; `NotificationReceipt(event: str, delivered: bool)`
  - `TelegramNotificationProvider(repository_root: Path, *, sender: Callable[[Path, str, str], str | None] | None = None)`, capabilities `{"notification.send"}`
  - `WorkerScheduler(..., notifications: Any | None = None)`
- **Steps**:
  1. Tests first:
     - `test_contracts.py`: replace the runner-based Telegram cases with: a recording `sender` receives `(root, "worker_finished", "t1: completed")` and the result is success with `delivered=True`; a sender returning `"telegram delivery failed (HTTP 500)"` gives an `unavailable` result with that detail; a sender raising `ValueError` gives an `invalid` result; capabilities equal `{"notification.send"}`.
     - `test_worker_scheduler.py`: a scheduler built with `notifications=FakeNotificationProvider()` records one `worker_finished` request for a completed task and one `worker_failed` for a failed task; without `notifications` nothing is sent.
     - `test_registry.py`: `registry.build_worker_scheduler().notifications is registry.notifications`.
     Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.gin_orchestrator.test_contracts tests.gin_orchestrator.test_worker_scheduler tests.gin_orchestrator.test_registry` → fails.
  2. `contracts.py`: remove `wait_for_reply`, `timeout_seconds`, `session_id` from `NotificationRequest` and `reply` from `NotificationReceipt`.
  3. `notifications.py`:
     ```python
     """Telegram notifications through gin-workflow's single sender, `workflow_core.ext.notify`."""

     from __future__ import annotations

     from pathlib import Path
     from typing import Callable

     from workflow_core.ext import notify as workflow_notify

     from .contracts import NotificationReceipt, NotificationRequest, ProviderBase, ProviderResult

     Sender = Callable[[Path, str, str], "str | None"]


     class TelegramNotificationProvider(ProviderBase):
         provider_name = "telegram"
         provider_type = "notifications"
         capabilities = frozenset({"notification.send"})

         def __init__(self, repository_root: Path, *, sender: Sender | None = None) -> None:
             self.repository_root = Path(repository_root).resolve()
             self._send = sender or workflow_notify
             super().__init__(available=True, health_detail="")

         def notify(self, request: NotificationRequest, *, idempotency_key: str) -> ProviderResult[NotificationReceipt]:
             if guarded := self._guard():
                 return guarded
             if replay := self._replay("notify", idempotency_key, request):
                 return replay
             if not request.event.strip() or not request.message.strip() or not idempotency_key:
                 return ProviderResult.invalid("event, message, and idempotency_key are required")
             try:
                 warning = self._send(self.repository_root, request.event, request.message)
             except ValueError as error:
                 return ProviderResult.invalid(str(error))
             if warning:
                 return ProviderResult.unavailable(warning)
             receipt = NotificationReceipt(request.event, delivered=True)
             return self._remember("notify", idempotency_key, request, ProviderResult.success(receipt))
     ```
  4. `fakes.py`: capabilities `{"notification.send"}`; `NotificationReceipt(request.event, True)` stays valid.
  5. `worker_scheduler.py`: add the `notifications: Any | None = None` keyword to `__init__` (stored as `self.notifications`), add
     ```python
         def _run_and_notify(self, request: WorkerRequest) -> WorkerResult:
             result = self._run(request)
             if self.notifications is not None:
                 event = "worker_finished" if result.status == "completed" else "worker_failed"
                 self.notifications.notify(
                     NotificationRequest(event, f"{result.task_id}: {result.status}"),
                     idempotency_key=f"{result.task_id}:{event}",
                 )
             return result
     ```
     and use `executor.map(self._run_and_notify, selected)` in `schedule`. Import `NotificationRequest` from `.contracts`.
  6. `registry.py`: pass `notifications=self.notifications` in `build_worker_scheduler`.
  7. Run step 1's command → passes. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` → passes.
  8. README: the copied scripts are `worktree-create.sh` and `worktree-cleanup.sh` only.
- **Acceptance criteria**: no gin-orchestrator module references `telegram.sh`, `find_script("telegram.sh")`, `wait_for_reply` or `notification.ask`; the scheduler sends one worker event per completed dispatch when it has a notification provider; tests pass.

### Track 3: Call sites, removal of `telegram.sh` and `telegram-notify`, docs
- **Dependencies**: Track 2
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Estimated complexity**: medium
- **Files**:
  - Modify `plugins/gin-workflow/src/references/stage-contract.md` (new `## Notifications` section after `## Approval`)
  - Modify `plugins/gin-workflow/src/skills/execute/SKILL.md` (section 4 step 2, line 42)
  - Modify `plugins/gin-workflow/src/skills/execute/references/worker-lifecycle.md` (lines 3, 7, and the "Event identity…" paragraph)
  - Modify `plugins/gin-workflow/src/agents/bead-worker.md` (line 18)
  - Delete `plugins/gin-workflow/src/scripts/telegram.sh`, `plugins/gin-workflow/src/skills/telegram-notify/`
  - Modify `install.sh` (line 542 loop), `install.ps1` (line 426 loop)
  - Modify `tests/install_smoke_test.sh` (lines 263–264, 327, 337–338, 354, 377), `tests/install_smoke_test.ps1` (lines 132, 271–289), `tests/gin_orchestrator/test_harness_packaging.py` (lines 210–213)
  - Modify `docs/reference/skills.md` (line 51), `docs/reference/troubleshooting.md` (line 39), `docs/concepts/providers.md` (line 17)
  - Test: modify `tests/workflow_core/test_docs_coverage.py`
- **Steps**:
  1. `test_docs_coverage.py`: add `test_no_doc_mentions_telegram_sh`, scanning `pages()` plus `plugins/*/src/skills/**/*.md`, `plugins/*/src/agents/*.md`, `install.sh` and `install.ps1` for `telegram.sh` or `telegram-notify`. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage` → fails.
  2. `stage-contract.md`, new section:
     ```markdown
     ## Notifications
     Before stopping to wait for the user (a confirmation, an approval, a choice, `human_decision_required`, a blocker), run `gin-workflow notify --event needs_input "<what you need>"`. It does nothing unless `notifications.telegram` is on, and a message is never approval.
     ```
  3. `execute/SKILL.md` section 4 step 2, append: `If `gin-workflow state --workflow-id <id>` now shows `implementation_complete` satisfied, run `gin-workflow notify --event run_finished "<epic>: all tracks closed"`.`
  4. `worker-lifecycle.md`:
     - delete line 3 ("The dispatcher exposes `dispatch(request)`…") and the paragraph starting "Event identity includes the workflow…"; both describe gin-orchestrator's dispatcher internals, not steps the agent takes. This keeps the `execute` chain within 12 000.
     - line 7, append: `When it exits, run `gin-workflow notify --event worker_finished "<track>: <provider>"` (`worker_failed` on failure).`
  5. `bead-worker.md` line 18: replace "send a `work_blocked` notification when `telegram-notify` is configured" with "run `gin-workflow notify --event needs_input "<blocker>"`".
  6. `git rm -r plugins/gin-workflow/src/scripts/telegram.sh plugins/gin-workflow/src/skills/telegram-notify`.
  7. `install.sh` / `install.ps1`: drop `telegram.sh` from the copied-script lists. Smoke tests and `test_harness_packaging.py`: drop the `telegram-notify` and `telegram.sh` assertions; keep the `${PLUGIN_ROOT}` rewrite assertions only where another file still carries the token (none of the skills do after this change, so remove those two assertions too).
  8. Docs: `skills.md` drop the `telegram-notify` row; `troubleshooting.md` drop the Copilot Telegram bullet; `providers.md` line 17 → `optional delivery only (\`gin-workflow notify\`, behind \`notifications.telegram\`)`.
  9. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage tests.workflow_core.test_token_budget tests.gin_orchestrator.test_harness_packaging` → passes; `bash tests/install_smoke_test.sh` → exit 0.
- **Acceptance criteria**: every stage reaches `needs_input` through the stage contract; `execute` sends `run_finished` and the worker events; no file outside `.planning/` mentions `telegram.sh` or `telegram-notify`; stage chains within budget; smoke test passes.

### Track 4: Release: gin-workflow 2.1.0, gin-orchestrator 0.2.0
- **Dependencies**: Track 3
- **Provider role**: `general`
- **Reasoning**: `low`
- **Estimated complexity**: low
- **Files**:
  - Modify `plugins/gin-workflow/plugin.meta.json`, `plugins/gin-workflow/src/.claude-plugin/plugin.json`, `plugins/gin-workflow/src/.codex-plugin/plugin.json` (2.0.0 → 2.1.0)
  - Modify `plugins/gin-orchestrator/plugin.meta.json`, its two `plugin.json` files, and `ORCHESTRATOR_VERSION` in `plugins/gin-orchestrator/src/scripts/gin_orchestrator/__init__.py` (0.1.0 → 0.2.0)
  - Create `docs/reference/upgrade-2.1.md`; link it from `docs/reference/upgrade-2.0.md` and wherever `upgrade-2.0.md` is linked
  - Modify the version assertions found by `git grep -n '2\.0\.0\|0\.1\.0' -- tests` that refer to these manifests
- **Steps**:
  1. `git grep -n '"2.0.0"\|"0.1.0"\|ORCHESTRATOR_VERSION' -- plugins tests` and update every hit for the two plugins (the schema/CLI/launcher version stays 2.8).
  2. `upgrade-2.1.md`: Telegram is now off unless `notifications.telegram: true`; enable with `gin-workflow setup configure --set notifications.telegram=true --approve`; the `telegram-notify` skill and `telegram.sh` are gone; messages are one-way, never approval.
  3. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` and `bash tests/install_smoke_test.sh` → both pass.
- **Acceptance criteria**: both plugins publish the new versions consistently; upgrade notes exist and are linked; full suite and smoke test pass.

## Integration
- **Branch**: `feat/telegram-notifications` (worktree `.planning/worktrees/telegram-notifications`)
- **Merge strategy**: sequential

## Validation
- [ ] All tests pass (`PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`)
- [ ] `bash tests/install_smoke_test.sh` exits 0
- [ ] Manual: with the switch on and both variables set, `gin-workflow notify --event needs_input "manual check"` delivers one message; with it off, nothing arrives

## Notes
- Parent bead (epic) stays open until the human-confirmed merge; track beads close after tests and review pass.
- Concrete providers and models are resolved at orchestration; none belong here.
