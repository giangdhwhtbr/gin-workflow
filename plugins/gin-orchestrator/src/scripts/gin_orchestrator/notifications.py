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
