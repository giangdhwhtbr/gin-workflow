"""Telegram notification adapter using only the existing telegram.sh integration."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Callable, Mapping, Sequence

from .contracts import (
    NotificationReceipt,
    NotificationRequest,
    ProviderBase,
    ProviderResult,
)


Runner = Callable[[Sequence[str], Path, Mapping[str, str]], subprocess.CompletedProcess[str]]


def _default_runner(
    argv: Sequence[str], cwd: Path, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, env=dict(env), text=True, capture_output=True, check=False)


class TelegramNotificationProvider(ProviderBase):
    provider_name = "telegram"
    provider_type = "notifications"
    capabilities = frozenset({"notification.send", "notification.ask"})

    def __init__(
        self,
        repository_root: Path,
        *,
        script_path: Path | None = None,
        environment: Mapping[str, str] | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        scripts = Path(__file__).resolve().parent.parent
        self.script_path = Path(script_path or scripts / "telegram.sh")
        self.environment = dict(os.environ if environment is None else environment)
        self._runner = runner or _default_runner
        configured = bool(
            self.environment.get("TELEGRAM_BOT_TOKEN")
            and self.environment.get("TELEGRAM_CHAT_ID")
        )
        available = runner is not None or (self.script_path.is_file() and configured)
        if not self.script_path.is_file():
            detail = "telegram.sh was not found"
        elif not configured and runner is None:
            detail = "Telegram opt-in credentials are not configured"
        else:
            detail = ""
        super().__init__(available=available, health_detail=detail)

    def notify(self, request: NotificationRequest, *, idempotency_key: str) -> ProviderResult[NotificationReceipt]:
        if guarded := self._guard():
            return guarded
        if replay := self._replay("notify", idempotency_key, request):
            return replay
        if not request.event.strip() or not request.message.strip() or not idempotency_key:
            return ProviderResult.invalid("event, message, and idempotency_key are required")
        if request.timeout_seconds < 1:
            return ProviderResult.invalid("timeout_seconds must be positive")
        argv = [str(self.script_path), "ask" if request.wait_for_reply else "send", request.message]
        if request.wait_for_reply:
            argv.extend(["--timeout", str(request.timeout_seconds)])
            if request.session_id:
                argv.extend(["--session-id", request.session_id])
        try:
            completed = self._runner(argv, self.repository_root, self.environment)
        except (OSError, subprocess.SubprocessError) as error:
            return ProviderResult.unavailable(f"Telegram unavailable: {error}")
        if completed.returncode:
            detail = completed.stderr.strip() or "Telegram integration failed"
            return ProviderResult.unavailable(detail)
        receipt = NotificationReceipt(
            request.event,
            delivered=True,
            reply=completed.stdout.strip() if request.wait_for_reply else "",
        )
        return self._remember("notify", idempotency_key, request, ProviderResult.success(receipt))
