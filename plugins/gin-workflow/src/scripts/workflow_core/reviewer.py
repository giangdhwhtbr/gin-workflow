"""`gin-workflow reviewer` (agent-facing): the review route and ordered reviewer routes; exit 2 when none."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import uuid
from typing import Any

from .catalog import Catalog, DEFAULT_CATALOGS, catalog_for, map_route, route_diagnostics, tier_of
from .configuration import ConfigValidationError, load_effective_config
from .models import EffectiveConfig
from . import orchestrator_client


class ReviewerError(Exception):
    """The reviewer routes cannot be determined (exit 2)."""


def is_docs(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "skills" not in parts and (path.endswith(".md") or parts[:1] == ("docs",))


def review_route(
    catalog: Catalog,
    model: str,
    effort: str | None,
    changed: Sequence[str],
) -> tuple[str, str | None, str | None]:
    """Raise a low model to the next model when the diff changes anything but documentation."""
    code = [path for path in changed if not is_docs(path)]
    if tier_of(catalog, model) == "low" and code and len(catalog.models) > 1:
        return (catalog.models[1], effort, "non-docs files changed")
    return (model, effort, None)


def route(
    root: Path,
    base: str,
    *,
    model: str,
    effort: str | None = None,
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

    warnings: list[str] = []
    config_dict = config.to_dict() if hasattr(config, "to_dict") else dict(config)
    harness = config.harness or implementer
    for name in (harness, implementer):
        if name not in DEFAULT_CATALOGS:
            raise ReviewerError(f"unknown harness: {name}")
    # --model/--effort are the implementer's route, in the implementer's catalog.
    catalog = catalog_for(config_dict, implementer)
    diagnostics = route_diagnostics(catalog, model, effort)
    if diagnostics:
        raise ReviewerError("; ".join(diagnostics))

    model, effort, reason = review_route(catalog, model, effort, diff.stdout.splitlines())

    if orchestrator_client.delegates(config_dict, "reviewer"):
        cmd = [
            "reviewer",
            "--base", base,
            "--implementer", implementer,
            "--model", model,
            "--repository", str(root),
        ]
        if effort is not None:
            cmd.extend(["--effort", effort])
        try:
            orch_routes = orchestrator_client.call(cmd)
        except orchestrator_client.OrchestratorError as error:
            warnings.append(f"gin-orchestrator failed ({error}); reviewing on the main harness")
            orch_routes = None
        if orch_routes is not None and not (
            isinstance(orch_routes, list) and all(isinstance(r, Mapping) for r in orch_routes)
        ):
            warnings.append(f"gin-orchestrator failed ({orchestrator_client.FAILED}); reviewing on the main harness")
            orch_routes = None

        if orch_routes is not None:
            if not orch_routes:
                raise ReviewerError("no reviewer routes available from orchestrator")
            return {
                "model": model,
                "effort": effort,
                "reason": reason,
                "warnings": warnings,
                "routes": list(orch_routes),
            }
    else:
        warn = orchestrator_client.warning(config_dict)
        if warn is not None:
            warnings.append(warn)

    independence = (
        config_dict.get("routing", {}).get("review", {}).get("independence", "session")
        if isinstance(config_dict.get("routing"), Mapping)
        else "session"
    )
    if independence == "provider" and not orchestrator_client.delegates(config_dict, "reviewer"):
        warnings.append(
            "routing.review.independence: provider requires gin-orchestrator; falling back to same-provider session isolation"
        )

    actor_id = (
        f"reviewer:{harness}:session-{uuid.uuid4().hex[:8]}"
        if implementer == harness
        else f"reviewer:{harness}"
    )
    route_model, route_effort = (
        (model, effort)
        if harness == implementer
        else map_route(catalog, catalog_for(config_dict, harness), model, effort)
    )
    routes = [
        {
            "provider": harness,
            "model": route_model,
            "effort": route_effort,
            "actor_id": actor_id,
        }
    ]
    return {
        "model": model,
        "effort": effort,
        "reason": reason,
        "warnings": warnings,
        "routes": routes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gin-workflow reviewer")
    parser.add_argument("--base", required=True)
    parser.add_argument("--implementer", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", default=None)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")

    try:
        args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    root = args.repository.resolve()
    try:
        config = load_effective_config(root)
    except (OSError, ConfigValidationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    try:
        payload = route(
            root,
            args.base,
            model=args.model,
            effort=args.effort,
            implementer=args.implementer,
            config=config,
        )
    except ReviewerError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
