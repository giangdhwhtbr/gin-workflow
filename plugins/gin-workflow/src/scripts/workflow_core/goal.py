"""`gin goal`: a Claude Code /goal over the epic tracks the agent can finish unattended.

A track labelled `human-gate` needs a person (credentials, production access, a manual or third-party
approval). The goal leaves it out, together with every open track that depends on it, so an unattended
run stops before work it cannot finish instead of looping on the Stop hook.
"""

from __future__ import annotations

import argparse
from graphlib import TopologicalSorter
from pathlib import Path
import sys
from typing import Any, Sequence

from .prep import tracks_of
from .tasks import query
from . import workspace

HUMAN_GATE = "human-gate"


def goal_text(epic: str, tracks: Sequence[dict[str, Any]], workflow_id: str, review_ledger: bool) -> str:
    """The /goal line for the open tracks the agent can finish, or a line saying why there is none.

    The review clause is part of the condition only when the review ledger is on; otherwise no ledger
    exists and no waiver is recorded, so the clause could never be met.
    """
    found = {track["id"]: track for track in tracks if track.get("status") != "closed"}
    blockers = {bead: {dep.get("depends_on_id") for dep in track.get("dependencies") or []
                       if dep.get("type", "blocks") == "blocks"} & found.keys()
                for bead, track in found.items()}
    open_tracks = {bead: found[bead] for bead in TopologicalSorter(blockers).static_order()}
    held: set[str] = set()
    for bead, track in open_tracks.items():
        if HUMAN_GATE in (track.get("labels") or []) or blockers[bead] & held:
            held.add(bead)
    gates = [bead for bead, track in open_tracks.items() if HUMAN_GATE in (track.get("labels") or [])]
    runnable = [bead for bead in open_tracks if bead not in held]
    if not open_tracks:
        return f"No goal: every track of epic {epic} is closed."
    if not runnable:
        named = ", ".join(f"{bead} ({open_tracks[bead].get('title', '')})" for bead in gates)
        return f"No goal: every open track of epic {epic} waits on a human: {named}."
    text = (f"/goal tracks {', '.join(runnable)} of epic {epic} are closed in Beads (`gin task show`), "
            f"`gin state --workflow-id {workflow_id} --format json` shows `implementation_complete` satisfied")
    if review_ledger:
        text += (", and for each of those tracks `python3 review-ledger.py status --bead-id <id>` shows an approved "
                 "state (`review-approved` or later) or the track is listed in `review_waivers`")
    text += "."
    if held:
        text += f" Do not start {', '.join(bead for bead in open_tracks if bead in held)}: they need a human."
    return text


def main(argv: Sequence[str]) -> int:
    from .checkout import main_checkout
    from .configuration import resolve_effective_config
    from .project import project_settings
    from .lifecycle_cli import _get_event_store, _recorded_epic

    parser = argparse.ArgumentParser(prog="gin goal")
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--repository", type=Path, default=None)
    args = parser.parse_args(argv)
    args.repository = workspace.repository_root(args.repository)
    epic = _recorded_epic(_get_event_store(args.repository).read_all(), args.workflow_id)
    if not epic:
        print(f"error: no epic recorded for {args.workflow_id}; run /gin:orchestrate first", file=sys.stderr)
        return 1
    tracks = query(args.repository, ["list", "--parent", epic, "--all", "--limit", "0"])
    if isinstance(tracks, list):
        tracks = tracks_of(tracks)
    if tracks == []:
        tracks = query(args.repository, ["show", epic])
    if not isinstance(tracks, list):
        print("error: the task backend is unavailable", file=sys.stderr)
        return 1
    config = resolve_effective_config(main_checkout(args.repository), write=False).config.to_dict()
    print(goal_text(epic, tracks, args.workflow_id, project_settings(config).review_ledger))
    return 0
