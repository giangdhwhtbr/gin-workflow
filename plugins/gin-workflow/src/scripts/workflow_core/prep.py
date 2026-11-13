"""Prep tasks: pre-discuss work under an epic."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

PREP = "prep"
TYPES = ("capture", "mockup", "spike", "question", "other")


def is_prep(record: Mapping[str, Any]) -> bool:
    if not isinstance(record, Mapping):
        return False
    labels = record.get("labels") or []
    if not isinstance(labels, (list, tuple, set)):
        return False
    return (
        PREP in labels
        and not any(isinstance(lbl, str) and (lbl.startswith("track:") or lbl.startswith("req:")) for lbl in labels)
    )


def tracks_of(children: Sequence[Any]) -> list[Any]:
    return [
        child for child in children
        if not (isinstance(child, Mapping) and is_prep(child))
    ]
