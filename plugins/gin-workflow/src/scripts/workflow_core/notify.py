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
