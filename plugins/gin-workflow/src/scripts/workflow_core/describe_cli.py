"""`gin-workflow describe` command line interface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .atomic import atomic_write_text
from .describe import DescribeError, GraphTooLarge, collect, layout, render, template


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gin-workflow describe")
    parser.add_argument("id", help="Bead ID to describe")
    parser.add_argument("--out", type=Path, help="Output HTML file path")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(arguments: Sequence[str]) -> int:
    args = _parser().parse_args(list(arguments))
    repo = args.repository.resolve()
    target_id = args.id

    if args.out:
        out_path = args.out if args.out.is_absolute() else (Path.cwd() / args.out).resolve()
    else:
        out_path = repo / f".agent-workflow/runtime/describe/{target_id}.html"

    try:
        graph = collect(repo, target_id)
        graph = layout(graph)
        html_content = render(graph, template())

        out_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out_path, html_content, mode=0o644)

        node_count = len(graph["nodes"])
        edge_count = len(graph["edges"])

        if args.format == "json":
            payload = {
                "status": "ok",
                "path": str(out_path),
                "nodes": node_count,
                "edges": edge_count,
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"{out_path}  ({node_count} nodes, {edge_count} edges)")
        return 0
    except GraphTooLarge as error:
        print(f"error: {error}", file=sys.stderr)
        return 3
    except DescribeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
