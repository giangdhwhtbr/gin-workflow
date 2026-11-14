"""AI usage summaries per bead: tokens and estimated cost per model and stage, plus quality signals.

`collect` reads local logs and writes the summary into the bead's metadata (`ai_usage`);
`report` reads the summaries back from Beads and never reads logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping, Sequence

from .checkout import main_checkout
from .events import WorkflowEventStore
from .configuration import ConfigValidationError, require_yaml, resolve_effective_config
from .executables import tool
from .prep import is_prep
from .usage_attribution import (
    UNATTRIBUTED, BeadSpan, Worktree, attribute, gates_from_events, review_intervals, worktrees,
)
from .usage_logs import UsageRecord, claude_code_records, codex_records, parse_ts

PRICES_FILE = ".agent-workflow/usage-prices.yaml"
DEFAULT_PRICES = Path(__file__).with_name("usage_prices_default.yaml")
EVENTS_FILE = ".agent-workflow/runtime/events.jsonl"
_TOKENS = ("input", "output", "cache_read", "cache_write")
_SEVERITIES = ("critical", "important", "minor", "suggestion")
# Budget statuses: `warn` from WARN_RATIO of the budget, `stop` from STOP_RATIO; the margin
# above 1.0 covers the error of time-span attribution.
WARN_RATIO = 0.8
STOP_RATIO = 1.2


class UsageError(Exception):
    """A real failure: missing bd, a failing bd call, or an invalid price list."""


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float
    cache_write: float
    source: str = "repo"


def _parse_prices(text: str, label: str, source: str) -> dict[str, Price]:
    try:
        loaded = require_yaml().safe_load(text) or {}
    except Exception as error:  # yaml.YAMLError without importing yaml here
        raise UsageError(f"{label}: {error}") from error
    prices = loaded.get("prices", {}) if isinstance(loaded, Mapping) else None
    if not isinstance(prices, Mapping):
        raise UsageError(f"{label}: expected 'prices:' mapping model names to prices")
    result: dict[str, Price] = {}
    for model, entry in prices.items():
        values = [entry.get(key) if isinstance(entry, Mapping) else None for key in _TOKENS]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 for value in values):
            raise UsageError(f"{label}: {model} needs non-negative numbers for {', '.join(_TOKENS)}")
        result[str(model)] = Price(*(float(value) for value in values), source)
    return result


def load_prices(repo: Path) -> dict[str, Price]:
    """The shipped catalog, overridden by the repository file where both name a model."""
    prices = _parse_prices(DEFAULT_PRICES.read_text(encoding="utf-8"), DEFAULT_PRICES.name, "default")
    path = Path(repo) / PRICES_FILE
    if path.is_file():
        prices.update(_parse_prices(path.read_text(encoding="utf-8"), PRICES_FILE, "repo"))
    return prices


def price_for(prices: Mapping[str, Price], model: str) -> Price | None:
    """Exact id, else the longest key that the id extends with `-<suffix>` (dated Claude ids)."""
    if model in prices:
        return prices[model]
    keys = [key for key in prices if model.startswith(key + "-")]
    return prices[max(keys, key=len)] if keys else None


def cost(totals: Mapping[str, int], price: Price | None) -> float | None:
    if price is None:
        return None
    return round(sum(totals.get(key, 0) * getattr(price, key) for key in _TOKENS) / 1_000_000, 4)


def budget_usd(repo: Path) -> float | None:
    """`usage.budget_usd` from the main checkout's live config; None when unset."""
    try:
        config = resolve_effective_config(main_checkout(Path(repo).resolve()), write=False).config.to_dict()
    except ConfigValidationError as error:
        raise UsageError(f"invalid configuration: {error}") from error
    value = (config.get("usage") or {}).get("budget_usd")
    return None if value is None else float(value)


def budget_status(cost: float | None, unpriced: Sequence[str], budget: float) -> str:
    if unpriced:
        return "unenforceable"
    ratio = (cost or 0.0) / budget
    if ratio >= STOP_RATIO:
        return "stop"
    return "warn" if ratio >= WARN_RATIO else "ok"


def over_budget(repo: Path, workflow_id: str) -> dict[str, Any] | None:
    """The stop payload once the epic's stored cost reaches STOP_RATIO of the budget; None otherwise."""
    budget = budget_usd(repo)
    if budget is None:
        return None
    root = main_checkout(Path(repo).resolve())
    epic = gates_from_events(_events(root))[1].get(workflow_id, workflow_id)
    stored = _usage_of(_show(root, epic)) or {}
    if budget_status(stored.get("cost"), stored.get("unpriced") or [], budget) != "stop":
        return None
    return {"status": "over_budget", "epic": epic, "cost": stored["cost"], "budget_usd": budget}


def _bd(repo: Path, argv: list[str]) -> Any:
    from .configuration import ConfigValidationError
    from .tasks import backend

    try:
        name = backend(repo)
    except ConfigValidationError as error:
        raise UsageError(str(error)) from error
    if name == "markdown":
        raise UsageError("AI usage tracking requires Beads (providers.task_tracking: beads)")
    executable = tool("bd", repo)
    if executable is None:
        raise UsageError("bd is not installed")
    try:
        done = subprocess.run([executable, *argv], cwd=repo, text=True, capture_output=True, check=False,
                              timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise UsageError(f"bd {argv[0]} failed: {error}") from error
    if done.returncode != 0:
        raise UsageError(f"bd {' '.join(argv[:2])} failed: {(done.stderr or done.stdout).strip()}")
    if "--json" not in argv:
        return None
    try:
        return json.loads(done.stdout or "null")
    except json.JSONDecodeError as error:
        raise UsageError(f"bd {argv[0]} printed invalid JSON") from error


def _show(repo: Path, bead: str) -> dict[str, Any]:
    data = _bd(repo, ["show", bead, "--json"])
    data = data[0] if isinstance(data, list) and data else data
    if not isinstance(data, dict):
        raise UsageError(f"bd show {bead}: no such bead")
    return data


def _row(by_id: Mapping[str, Any], bead: str) -> dict[str, Any]:
    row = by_id.get(bead)
    if not isinstance(row, dict):
        raise UsageError(f"bd show {bead}: no such bead")
    return row


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _ts(value: Any) -> datetime | None:
    try:
        return parse_ts(value) if isinstance(value, str) and value else None
    except ValueError:
        return None


def _ledger(repo: Path, bead: str) -> Mapping[str, Any] | None:
    roots = [Path(repo)] + [tree.path for tree in worktrees(repo)]
    for root in roots:
        for relative in (f".planning/reviews/{bead}/review.json", f".planning/{bead}/review.json"):
            path = root / relative
            if path.is_file():
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(loaded, Mapping):
                    return loaded
    return None


def _events(repo: Path) -> list:
    path = Path(repo) / EVENTS_FILE
    return WorkflowEventStore(path).read_all() if path.is_file() else []


def empty_quality() -> dict[str, Any]:
    return {"reopens": 0, "bugs": 0, "review_cycles": 0, "rejections": 0,
            "findings": {severity: 0 for severity in _SEVERITIES}, "waivers": 0}


def quality(repo: Path, bead: str, *, workflows: set[str], events: Sequence | None = None,
            history: Sequence[Mapping[str, Any]] | None = None,
            rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    result = empty_quality()
    hist = _list(_bd(repo, ["history", bead, "--json"])) if history is None else _list(history)
    statuses = [(row.get("Issue") or {}).get("status") for row in reversed(hist)]
    result["reopens"] = sum(1 for before, after in zip(statuses, statuses[1:]) if before == "closed" != after)
    if rows is not None:
        result["bugs"] = sum(1 for row in rows if row.get("issue_type") == "bug" and any(
            dep.get("depends_on_id") == bead and dep.get("type") == "discovered-from"
            for dep in row.get("dependencies") or ()))
    else:
        found = _list(_bd(repo, ["dep", "list", bead, "--direction=up", "--type", "discovered-from", "--json"]))
        result["bugs"] = sum(1 for item in found if item.get("issue_type") == "bug")
    ledger = _ledger(repo, bead)
    if ledger is not None:
        actions = [entry.get("action") for entry in ledger.get("events") or () if isinstance(entry, Mapping)]
        result["review_cycles"] = actions.count("review-started")
        result["rejections"] = actions.count("changes-requested") + actions.count("review-approval-invalidated")
        for finding in (ledger.get("findings") or {}).values():
            severity = str(finding.get("severity", "")).lower() if isinstance(finding, Mapping) else ""
            if severity in result["findings"]:
                result["findings"][severity] += 1
    events = _events(repo) if events is None else events
    result["waivers"] = sum(1 for event in events
                            if event.event_type == "gate.waived" and event.workflow_id in workflows)
    return result


def _add_quality(total: dict[str, Any], part: Mapping[str, Any]) -> None:
    for key, value in part.items():
        if key == "findings":
            for severity, count in value.items():
                total["findings"][severity] = total["findings"].get(severity, 0) + count
        else:
            total[key] = total.get(key, 0) + value


def _totals(records: Iterable[UsageRecord]) -> dict[str, int]:
    totals = {key: 0 for key in _TOKENS}
    for record in records:
        for key in _TOKENS:
            totals[key] += getattr(record, key)
    return totals


def _priced_cost(records: Sequence[UsageRecord], prices: Mapping[str, Price]) -> float | None:
    by_model: dict[str, list[UsageRecord]] = {}
    for record in records:
        by_model.setdefault(record.model, []).append(record)
    costs = [cost(_totals(items), price_for(prices, model)) for model, items in by_model.items()]
    known = [value for value in costs if value is not None]
    return round(sum(known), 4) if known else None


def _by_model(records: Sequence[UsageRecord], prices: Mapping[str, Price]) -> dict[str, dict[str, Any]]:
    by_model: dict[str, dict[str, Any]] = {}
    for model in sorted({record.model for record in records}):
        totals = _totals(record for record in records if record.model == model)
        price = price_for(prices, model)
        by_model[model] = {**totals, "cost": cost(totals, price), "price_source": price.source if price else "none"}
    return by_model


def summarize(by_stage: Mapping[str, Sequence[UsageRecord]], prices: Mapping[str, Price],
              quality: Mapping[str, Any], sources: Mapping[str, str], skipped: int, now: datetime,
              unattributed: Sequence[UsageRecord] | None = None) -> dict[str, Any]:
    everything = [record for records in by_stage.values() for record in records]
    models = _by_model(everything, prices)
    roles = {role: _by_model([record for record in everything if record.role == role], prices)
             for role in sorted({record.role for record in everything})}
    stages = {stage: {"tokens": sum(_totals(records).values()), "cost": _priced_cost(records, prices)}
              for stage, records in sorted(by_stage.items()) if records}
    priced = [entry["cost"] for entry in models.values() if entry["cost"] is not None]
    document: dict[str, Any] = {
        "version": 1,
        "collected_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "models": models,
        "roles": roles,
        "stages": stages,
        "cost": round(sum(priced), 4) if priced or not models else None,
        "unpriced": sorted(model for model, entry in models.items() if entry["cost"] is None),
        "quality": dict(quality),
        "sources": dict(sources),
        "skipped_lines": skipped,
    }
    if unattributed is not None:
        document["unattributed"] = {"tokens": sum(_totals(unattributed).values()),
                                    "cost": _priced_cost(unattributed, prices) if unattributed else 0.0}
    return document


def _span(repo: Path, bead: str, shown: Mapping[str, Any], now: datetime,
          history: Sequence[Mapping[str, Any]] | None = None) -> BeadSpan:
    hist = _list(_bd(repo, ["history", bead, "--json"])) if history is None else _list(history)
    starts = [_ts((row.get("Issue") or {}).get("started_at")) for row in hist] + [_ts(shown.get("started_at"))]
    starts = [value for value in starts if value is not None]
    ledger = _ledger(repo, bead)
    return BeadSpan(bead, shown.get("parent") or None, min(starts) if starts else None,
                    _ts(shown.get("closed_at")), review_intervals(ledger, now=now) if ledger else (),
                    prep=is_prep(shown))


def collect(repo: Path, bead: str, *, now: datetime | None = None, claude_root: Path | None = None,
            codex_root: Path | None = None) -> dict[str, Any]:
    # Logs, gate events, and worktrees all belong to the main checkout, wherever collect runs.
    repo = main_checkout(Path(repo).resolve())
    now = now or datetime.now(timezone.utc)
    prices = load_prices(repo)
    rows = _list(_bd(repo, ["list", "--all", "-n", "0", "--json"]))
    by_id = {row["id"]: row for row in rows if "id" in row}
    shown = _row(by_id, bead)
    is_epic = shown.get("issue_type") == "epic"
    epic = bead if is_epic else (shown.get("parent") or None)
    children = sorted(str(row["id"]) for row in rows if row.get("parent") == epic and row.get("id")) if epic else []
    histories: dict[str, list[dict[str, Any]]] = {}

    def get_history(target: str) -> list[dict[str, Any]]:
        if target not in histories:
            histories[target] = _list(_bd(repo, ["history", target, "--json"]))
        return histories[target]

    spans = {bead: _span(repo, bead, shown, now, history=get_history(bead))}
    for other in ([epic] if epic and epic != bead else []) + children:
        if other not in spans:
            other_shown = _row(by_id, other)
            spans[other] = _span(repo, other, other_shown, now, history=get_history(other))
    events = _events(repo)
    gates, epic_of = gates_from_events(events)
    scans = {"claude_code": claude_code_records(repo, claude_root), "codex": codex_records(repo, codex_root)}
    records = [record for scan in scans.values() for record in scan.records]
    trees = worktrees(repo)
    # A worktree removed after ship is no longer listed by git; its path still names its bead.
    listed = {tree.path.name for tree in trees}
    trees += [Worktree(repo / ".planning" / "worktrees" / name, "") for name in sorted(spans) if name not in listed]
    groups = attribute(records, repo=repo, spans=spans, trees=trees, gates=gates, epic_of=epic_of,
                       collecting=bead if is_epic else None, now=now)
    members = {bead, *children} if is_epic else {bead}
    by_stage: dict[str, list[UsageRecord]] = {}
    for (owner, stage), items in groups.items():
        if owner in members:
            by_stage.setdefault(stage, []).extend(items)
    owned_workflows = {bead} | {workflow for workflow, owner in epic_of.items() if owner == bead}
    total_quality = quality(repo, bead, workflows=owned_workflows, events=events, history=get_history(bead), rows=rows)
    unattributed = None
    if is_epic:
        for child in children:
            if is_prep(_row(by_id, child)):
                continue
            _add_quality(total_quality,
                         quality(repo, child, workflows={child}, events=events, history=get_history(child), rows=rows))
        own_gates = [gate.ts for gate in gates if epic_of.get(gate.workflow_id, gate.workflow_id) == bead]
        start = min(own_gates) if own_gates else spans[bead].start
        end = spans[bead].end or now
        unattributed = [record for record in groups.get((UNATTRIBUTED, ""), [])
                        if start is not None and start <= record.ts <= end]
    document = summarize(by_stage, prices, total_quality, {name: scan.status for name, scan in scans.items()},
                         sum(scan.skipped_lines for scan in scans.values()), now, unattributed)
    if is_epic:
        document["children"] = children
        budget = budget_usd(repo)
        if budget is not None:
            document["budget"] = {"budget_usd": budget, "cost": document["cost"],
                                  "status": budget_status(document["cost"], document["unpriced"], budget)}
    text = json.dumps(document, sort_keys=True, separators=(",", ":"))
    _bd(repo, ["update", bead, "--set-metadata", f"ai_usage={text}"])
    return document


def _usage_of(row: Mapping[str, Any]) -> dict[str, Any] | None:
    value = (row.get("metadata") or {}).get("ai_usage") if isinstance(row.get("metadata"), Mapping) else None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _add_models(slots: dict[str, dict[str, Any]], by_model: Mapping[str, Mapping[str, Any]]) -> None:
    for name, values in by_model.items():
        slot = slots.setdefault(name, {key: 0 for key in _TOKENS} | {"cost": None})
        for key in _TOKENS:
            slot[key] += values.get(key, 0)
        if values.get("cost") is not None:
            slot["cost"] = round((slot["cost"] or 0) + values["cost"], 4)


def report(repo: Path, *, bead: str | None = None, epic: str | None = None, since: date | None = None,
           milestone: str | None = None) -> dict[str, Any]:
    rows = _list(_bd(Path(repo), ["list", "--all", "-n", "0", "--json"]))
    if bead:
        selected = [row for row in rows if row.get("id") == bead]
    elif epic:
        selected = [row for row in rows if row.get("id") == epic or row.get("parent") == epic]
    elif milestone is not None:
        target = next((row for row in rows if row.get("id") == milestone), None)
        if target is None or target.get("issue_type") != "milestone":
            raise UsageError(f"{milestone} is not a milestone")
        epics = {row["id"] for row in rows if row.get("issue_type") == "epic" and row.get("parent") == milestone}
        selected = [row for row in rows if row.get("id") in epics or row.get("parent") in epics]
    else:
        selected = [row for row in rows if since is None or
                    ((_ts(row.get("closed_at")) or datetime.min.replace(tzinfo=timezone.utc)).date() >= since)]
        if since is None:
            selected = [row for row in selected if _usage_of(row) is not None or row.get("status") == "closed"]
    collected = [(row, _usage_of(row)) for row in selected]
    beads = [{"bead": row["id"], "title": row.get("title", ""), "type": row.get("issue_type", ""),
              "parent": row.get("parent") or None, **doc} for row, doc in collected if doc is not None]
    ids = {entry["bead"] for entry in beads}
    top = [entry for entry in beads if entry["parent"] not in ids]  # an epic's summary already holds its children
    models: dict[str, dict[str, Any]] = {}
    roles: dict[str, dict[str, Any]] = {}
    stages: dict[str, dict[str, Any]] = {}
    for entry in top:
        _add_models(models, entry.get("models") or {})
        for role, by_model in (entry.get("roles") or {}).items():
            _add_models(roles.setdefault(role, {}), by_model)
        for name, values in (entry.get("stages") or {}).items():
            slot = stages.setdefault(name, {"tokens": 0, "cost": None})
            slot["tokens"] += values.get("tokens", 0)
            if values.get("cost") is not None:
                slot["cost"] = round((slot["cost"] or 0) + values["cost"], 4)
    costs = [entry["cost"] for entry in top if entry.get("cost") is not None]
    parts = [entry.get("unattributed") or {} for entry in top]
    tokens = sum(part.get("tokens", 0) for part in parts)
    priced = [part["cost"] for part in parts if part.get("cost") is not None]
    unattributed = {"tokens": tokens, "cost": round(sum(priced), 4) if priced or not tokens else None}
    unpriced = sorted({name for entry in top for name in entry.get("unpriced") or ()})
    not_collected = [row["id"] for row, doc in collected if doc is None]
    docs = [doc for _, doc in collected if doc is not None]
    has_doc_ids = {row["id"] for row, doc in collected if doc is not None and "id" in row}
    reasons: set[str] = set()
    if any(row.get("parent") in has_doc_ids for row, doc in collected if doc is not None and row.get("parent")):
        reasons.add("children_not_merged")
    if not_collected:
        reasons.add("not_collected")
    if unattributed["tokens"] > 0:
        reasons.add("unattributed")
    if any(any(status != "ok" for status in (doc.get("sources") or {}).values()) or
           (doc.get("skipped_lines") or 0) > 0 for doc in docs):
        reasons.add("log_sources")
    for row, doc in collected:
        if doc is None:
            continue
        cat = _ts(doc.get("collected_at"))
        if cat is None:
            continue
        child_closed = [_ts(c.get("closed_at")) for c in selected if c.get("parent") == row.get("id")]
        valid_closed = [ts for ts in child_closed if ts is not None]
        if valid_closed and cat < max(valid_closed):
            reasons.add("stale")
    if unpriced:
        reasons.add("unpriced")
    partial_reasons = sorted(reasons)
    return {
        "beads": beads,
        "totals": {"cost": round(sum(costs), 4) if costs or not models else None, "models": models, "roles": roles,
                   "stages": stages},
        "unpriced": unpriced,
        "unattributed": unattributed,
        "not_collected": not_collected,
        "partial": bool(partial_reasons),
        "partial_reasons": partial_reasons,
    }
