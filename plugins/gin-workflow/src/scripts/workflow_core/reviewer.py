"""`gin-workflow reviewer` (agent-facing): the review tier and ordered reviewer routes; exit 2 when none."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any, Mapping, Sequence

from .assignments import AssignmentRequest, AssignmentResolutionError, resolve_assignment
from .configuration import ConfigValidationError, load_effective_config
from .models import EffectiveConfig
from .provider_config import (REASONING_TIERS, ProviderLocalConfigError, ProviderModelConfig,
                              load_provider_local_config)


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


def route(root: Path, base: str, *, tier: str, implementer: str, config: EffectiveConfig,
          local: Mapping[str, ProviderModelConfig]) -> dict[str, Any]:
    diff = subprocess.run(["git", "diff", "--name-only", "--no-renames", f"{base}...HEAD"], cwd=root,
                          capture_output=True, text=True, check=False)
    if diff.returncode != 0:
        raise ReviewerError(f"git diff {base}...HEAD failed: {diff.stderr.strip()}")
    tier, reason = review_tier(tier, diff.stdout.splitlines())
    try:
        candidates = resolve_assignment(
            AssignmentRequest("reviewer", "review", tier, config.harness or implementer), config, local)
    except AssignmentResolutionError as error:
        raise ReviewerError(str(error)) from error
    review = (config.get("routing") or {}).get("review") or {}
    independent = bool(review.get("require_independent", True)) and tier != "low"
    routes = [c for c in candidates if not independent or c.provider != implementer]
    if not routes and review.get("allow_self_review_fallback"):
        routes = list(candidates)
    if not routes:
        raise ReviewerError(f"no reviewer route independent of {implementer} at tier {tier}")
    return {"tier": tier, "reason": reason, "routes": [(c.provider, c.model, c.effort) for c in routes]}


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin-workflow reviewer")
    parser.add_argument("--base", required=True)
    parser.add_argument("--implementer", required=True)
    parser.add_argument("--tier", choices=REASONING_TIERS, default="medium")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args(list(arguments))
    root = args.repository.resolve()
    try:
        out = route(root, args.base, tier=args.tier, implementer=args.implementer,
                    config=load_effective_config(root), local=load_provider_local_config(root))
    except (ReviewerError, ConfigValidationError, ProviderLocalConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    lines = [f"tier {out['tier']}"] + ([f"reason: {out['reason']}"] if out["reason"] else [])
    lines += [" ".join(filter(None, item)) for item in out["routes"]]
    print("\n".join(lines))
    return 0
