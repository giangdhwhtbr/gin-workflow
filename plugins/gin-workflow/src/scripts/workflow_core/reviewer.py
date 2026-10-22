"""`gin-workflow reviewer` (agent-facing): the review tier and ordered reviewer routes; exit 2 when none."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any, Sequence
import uuid

from .configuration import ConfigValidationError, load_effective_config
from .models import EffectiveConfig
from .provider_config import (
    DEFAULT_HARNESS_MODELS,
    REASONING_TIERS,
    default_provider_model_config,
)


class ReviewerError(Exception):
    """The reviewer routes cannot be determined (exit 2)."""


def is_docs(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "skills" not in parts and (path.endswith(".md") or parts[:1] == ("docs",))


def review_tier(tier: str, changed: Sequence[str]) -> tuple[str, str | None]:
    """Raise a low tier to medium when the diff changes anything but documentation; never lower."""
    code = [path for path in changed if not is_docs(path)]
    if tier != "low" or not code:
        return tier, None
    return "medium", f"low track changes non-docs files: {', '.join(code[:3])}"


def route(
    root: Path,
    base: str,
    *,
    tier: str,
    implementer: str,
    config: EffectiveConfig,
) -> dict[str, Any]:
    diff = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if diff.returncode != 0:
        raise ReviewerError(f"git diff {base}...HEAD failed: {diff.stderr.strip()}")
    tier, reason = review_tier(tier, diff.stdout.splitlines())

    harness = config.harness or implementer
    if harness not in DEFAULT_HARNESS_MODELS:
        raise ReviewerError(f"unknown harness: {harness}")
    if tier not in REASONING_TIERS:
        raise ReviewerError(f"unknown reasoning tier: {tier}")

    target = default_provider_model_config(harness).models[tier]
    model = target.model
    effort = target.effort

    if harness != implementer:
        actor_id = f"reviewer:{harness}"
    else:
        actor_id = f"reviewer:{harness}:session-{uuid.uuid4().hex[:8]}"

    review = (config.get("routing") or {}).get("review") or {}
    independence = review.get("independence")
    warnings: list[str] = []
    if independence == "provider":
        warnings.append("routing.review.independence: provider requires gin-orchestrator; running on main harness in a fresh session")

    route_entry = {
        "provider": harness,
        "model": model,
        "effort": effort,
        "actor_id": actor_id,
    }
    return {
        "tier": tier,
        "reason": reason,
        "warnings": warnings,
        "routes": [route_entry],
    }


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin-workflow reviewer")
    parser.add_argument("--base", required=True)
    parser.add_argument("--implementer", required=True)
    parser.add_argument("--tier", choices=REASONING_TIERS, default="medium")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(arguments))
    root = args.repository.resolve()
    try:
        out = route(
            root,
            args.base,
            tier=args.tier,
            implementer=args.implementer,
            config=load_effective_config(root),
        )
    except (ReviewerError, ConfigValidationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(out))
        return 0

    for warning in out.get("warnings", []):
        print(f"warning: {warning}", file=sys.stderr)

    lines = [f"tier {out['tier']}"] + ([f"reason: {out['reason']}"] if out["reason"] else [])
    for r in out["routes"]:
        parts = [r["provider"], r["model"]]
        if r.get("effort"):
            parts.append(r["effort"])
        lines.append(" ".join(parts))
    print("\n".join(lines))
    return 0
