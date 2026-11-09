"""Registry of git host adapters: one module per host, imported on first use."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import HostAdapter

HOSTS = ("github", "gitlab", "gitea", "codecommit")
DEFAULT_HOST = "github"


def adapter(host: str) -> HostAdapter:
    """The adapter module's ADAPTER; ValueError for an unknown host."""
    if host not in HOSTS:
        raise ValueError(f"unknown team.host {host!r}; expected one of {', '.join(HOSTS)}")
    return importlib.import_module(f".{host}", __name__).ADAPTER
