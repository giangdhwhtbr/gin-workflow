"""`gin goal`: a Claude Code /goal over the epic tracks the agent can finish unattended.

A track labelled `human-gate` needs a person (credentials, production access, a manual or third-party
approval). The goal leaves it out, together with every open track that depends on it, so an unattended
run stops before work it cannot finish instead of looping on the Stop hook.
"""

from __future__ import annotations

import argparse
from graphlib import TopologicalSorter
from pathlib import Path
import re
import sys
from typing import Any, Sequence

from .prep import tracks_of
from .tasks import query
from .team_pending import lane_bead, track_lane
from . import team as team_core
from . import workspace

HUMAN_GATE = "human-gate"
_EXTERNAL = re.compile(r"^external: ")


def goal_text(epic: str, tracks: Sequence[dict[str, Any]], workflow_id: str, review_ledger: bool, *,
              member: str | None = None, lane: str | None = None, waiting: frozenset[str] = frozenset()) -> str:
    """The /goal line for the open tracks the agent can finish, or a line saying why there is none.

    The review clause is part of the condition only when the review ledger is on; otherwise no ledger
    exists and no waiver is recorded, so the clause could never be met. With `member` (team mode) the goal
    covers that member's tracks, or with `lane` the member's and unassigned tracks of the lane; a track that
    depends on a bead in `waiting` (a lane not merged yet) is left out like a human gate. A lane bead
    (`Plan: <path>, Lane <name>`) is never a track; when the member's only open beads are lane beads, one line
    per lane says to plan it.
    """
    planning = {track["id"]: (found_lane[1], track) for track in tracks if track.get("status") != "closed"
                and (found_lane := lane_bead(str(track.get("description") or ""))) is not None}
    found = {track["id"]: track for track in tracks
             if track.get("status") != "closed" and not _EXTERNAL.match(track.get("title") or "")
             and track["id"] not in planning}
    blockers = {bead: {dep.get("depends_on_id") for dep in track.get("dependencies") or []
                       if dep.get("type", "blocks") == "blocks"} & found.keys()
                for bead, track in found.items()}
    open_tracks = {bead: found[bead] for bead in TopologicalSorter(blockers).static_order()}
    held: set[str] = set()   # needs a human, or depends on such a track
    late: set[str] = set()   # waits for another lane to merge, or depends on such a track
    for bead, track in open_tracks.items():
        deps = {dep.get("depends_on_id") for dep in track.get("dependencies") or []
                if dep.get("type", "blocks") == "blocks"}
        if HUMAN_GATE in (track.get("labels") or []) or blockers[bead] & held:
            held.add(bead)
        elif deps & waiting or blockers[bead] & late:
            late.add(bead)

    def mine(track: dict[str, Any], name: str | None) -> bool:
        assignee = (track.get("assignee") or "").lower()
        return (lane is None or name == lane) and (assignee == member or (lane is not None and not assignee))

    def lane_name(track: dict[str, Any]) -> str | None:
        found_lane = track_lane(str(track.get("description") or ""))
        return found_lane[2] if found_lane else None

    covered = open_tracks if member is None else {bead: t for bead, t in open_tracks.items() if mine(t, lane_name(t))}
    gates = [bead for bead, track in covered.items() if HUMAN_GATE in (track.get("labels") or [])]
    runnable = [bead for bead in covered if bead not in held and bead not in late]
    to_plan = [name for name, track in planning.values() if member is not None and mine(track, name)]
    if member is not None and not covered and to_plan:
        return "\n".join(f"No goal: lane {name} has no tracks yet; run /plan for it." for name in dict.fromkeys(to_plan))
    if not open_tracks and (member is None or not planning):
        return f"No goal: every track of epic {epic} is closed."
    if member is not None and not covered:
        where = f"lane {lane} of epic {epic}" if lane else f"epic {epic}"
        return f"No goal: {member} has no open track in {where}."
    if not runnable:
        if not any(bead in late for bead in covered):
            named = ", ".join(f"{bead} ({covered[bead].get('title', '')})" for bead in gates)
            return f"No goal: every open track of epic {epic} waits on a human: {named}."
        return (f"No goal: every open track of epic {epic} assigned to {member} waits on a human or on "
                f"another lane to merge: {', '.join(covered)}.")
    text = f"/goal tracks {', '.join(runnable)} of epic {epic} are closed in Beads (`gin task show`)"
    if member is None:
        # implementation_complete needs every track closed, so it is left out while a held track stays open
        if len(runnable) == len(covered):
            text += f", `gin state --workflow-id {workflow_id} --format json` shows `implementation_complete` satisfied"
    else:
        text += ", and in each lane's worktree `git status -sb` shows the branch is not ahead of `origin`"
    if review_ledger:
        text += (", and for each of those tracks `python3 review-ledger.py status --bead-id <id>` shows an approved "
                 "state (`review-approved` or later) or the track is listed in `review_waivers`")
    text += "."
    if any(bead in held for bead in covered):
        text += f" Do not start {', '.join(bead for bead in covered if bead in held)}: they need a human."
    if any(bead in late for bead in covered):
        text += f" Do not start {', '.join(bead for bead in covered if bead in late)}: they wait for another lane to merge."
    return text


def main(argv: Sequence[str]) -> int:
    from .checkout import main_checkout
    from .configuration import resolve_effective_config
    from .project import project_settings
    from .lifecycle_cli import _get_event_store, _recorded_epic

    parser = argparse.ArgumentParser(prog="gin goal")
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--repository", type=Path, default=None)
    parser.add_argument("--lane")
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
    checkout = main_checkout(args.repository)
    config = resolve_effective_config(checkout, write=False).config.to_dict()
    member, waiting = None, frozenset()
    team = team_core.load_team(config)
    if team is None and args.lane:
        print("error: --lane needs team mode", file=sys.stderr)
        return 1
    if team is not None:
        who = team_core.current_member(checkout, team)
        if who is None:
            print("error: git user.email is not in team.members", file=sys.stderr)
            return 1
        member = who.email
        rows = query(args.repository, ["list", "--status", "open", "--limit", "0"])
        waiting = frozenset(row["id"] for row in rows or [] if _EXTERNAL.match(row.get("title", "")))
    print(goal_text(epic, tracks, args.workflow_id, project_settings(config).review_ledger,
                    member=member, lane=args.lane, waiting=waiting))
    return 0
