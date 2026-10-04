"""Best-practice rule packs: parse, select by file scope, order by precedence, trim to budget."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from .configuration import require_yaml, resolve_effective_config

TIERS = ("core", "language", "framework")
IMPACTS = ("critical", "high", "medium")
TASK_BUDGET = 4_000
DEFAULT_BODY_LIMIT = 1_500
DEFAULT_PACKS = ("core", "lean")
BODY_LIMITS = {"core": 1_000, "lean": 1_000}
_TIER_RANK = {"project": 0, "framework": 1, "language": 2, "core": 3}
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
_BULLET = re.compile(r"^- (?:\[([a-z]+)\] )?`([a-z0-9][a-z0-9-]*)`: (\S.*)$")
_WHY_LINE = re.compile(r"^- `([a-z0-9][a-z0-9-]*)`: (\S.*)$")
_WHY_HEADING = "## Why"


class RulesError(ValueError):
    """Raised when a rule pack or project rule file is malformed."""


@dataclass(frozen=True)
class Bullet:
    anchor: str
    impact: str
    line: str


@dataclass(frozen=True)
class Pack:
    id: str
    tier: str
    source: str
    applies_to: tuple[str, ...]
    requires: tuple[str, ...]
    bullets: tuple[Bullet, ...]
    why: Mapping[str, str]
    meta: Mapping[str, Any]
    path: Path

    @property
    def body_chars(self) -> int:
        return len("\n".join(bullet.line for bullet in self.bullets))

    @property
    def body_limit(self) -> int:
        return BODY_LIMITS.get(self.id, DEFAULT_BODY_LIMIT) if self.source == "plugin" else DEFAULT_BODY_LIMIT


def _string_list(value: Any, *, path: Path, key: str, required: bool) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value) or not all(isinstance(v, str) and v for v in value):
        raise RulesError(f"{path}: {key} must be a {'non-empty ' if required else ''}list of strings")
    return tuple(value)


def parse_pack(path: Path, *, source: str) -> Pack:
    text = Path(path).read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        raise RulesError(f"{path}: missing YAML frontmatter")
    meta = require_yaml().safe_load(match.group(1)) or {}
    if not isinstance(meta, Mapping):
        raise RulesError(f"{path}: frontmatter must be a mapping")
    lines = text[match.end():].splitlines()
    split = lines.index(_WHY_HEADING) if _WHY_HEADING in lines else len(lines)
    bullets: list[Bullet] = []
    for line in lines[:split]:
        if not line.strip():
            continue
        found = _BULLET.match(line)
        if not found or (found.group(1) or "medium") not in IMPACTS:
            raise RulesError(f"{path}: not a rule bullet: {line!r}")
        bullets.append(Bullet(anchor=found.group(2), impact=found.group(1) or "medium", line=line))
    anchors = [bullet.anchor for bullet in bullets]
    duplicates = sorted({anchor for anchor in anchors if anchors.count(anchor) > 1})
    if duplicates:
        raise RulesError(f"{path}: duplicate anchors {duplicates}")
    why: dict[str, str] = {}
    for line in lines[split + 1:]:
        if not line.strip():
            continue
        found = _WHY_LINE.match(line)
        if not found or found.group(1) not in anchors or found.group(1) in why:
            raise RulesError(f"{path}: invalid ## Why line {line!r}")
        why[found.group(1)] = found.group(2)
    if source == "plugin":
        if meta.get("id") != path.stem:
            raise RulesError(f"{path}: id must equal the file stem {path.stem!r}")
        if meta.get("tier") not in TIERS:
            raise RulesError(f"{path}: tier must be one of {TIERS}")
    return Pack(
        id=str(meta.get("id") or path.stem),
        tier="project" if source == "project" else str(meta["tier"]),
        source=source,
        applies_to=_string_list(meta.get("applies_to"), path=path, key="applies_to", required=True),
        requires=_string_list(meta.get("requires"), path=path, key="requires", required=False),
        bullets=tuple(bullets),
        why=why,
        meta=dict(meta),
        path=Path(path),
    )


def plugin_rules_dir() -> Path:
    """Launcher layout ships `rules/` beside `workflow_core/`; plugin trees have it two levels up."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "rules", here.parent.parent / "rules"):
        if candidate.is_dir():
            return candidate
    raise RulesError("plugin rules directory not found next to workflow_core")


def load_plugin_packs(directory: Path) -> dict[str, Pack]:
    return {path.stem: parse_pack(path, source="plugin")
            for path in sorted(Path(directory).glob("*.md")) if path.name != "README.md"}


def load_project_rules(repository: Path) -> list[Pack]:
    return [parse_pack(path, source="project")
            for path in sorted((Path(repository) / ".agent-workflow/rules").glob("*.md"))]


def rules_config(config: Mapping[str, Any]) -> tuple[list[str], set[str]]:
    section = config.get("rules") if isinstance(config.get("rules"), Mapping) else {}
    packs = [str(item) for item in (section.get("packs") or ["core"])]
    return packs, {str(item) for item in (section.get("disabled") or ())}


def _glob_regex(pattern: str) -> re.Pattern[str]:
    parts, index = [], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(parts) + r"\Z")


def _matches(pack: Pack, files: Sequence[str]) -> bool:
    return any(_glob_regex(pattern).match(path) for pattern in pack.applies_to for path in files)


def _depth(pack: Pack, plugin: Mapping[str, Pack], seen: tuple[str, ...] = ()) -> int:
    required = [plugin[name] for name in pack.requires if name in plugin and name not in seen]
    return 1 + max((_depth(item, plugin, (*seen, pack.id)) for item in required), default=0)


def select_packs(plugin: Mapping[str, Pack], project: Sequence[Pack], config: Mapping[str, Any],
                 files: Sequence[str]) -> tuple[list[Pack], list[str]]:
    """Enabled packs matching `files` (+ core and lean, + requires), highest precedence first."""
    packs, disabled = rules_config(config)
    warnings = [f"unknown rule pack {name!r} ignored" for name in packs if name not in plugin]
    enabled = {name for name in (*DEFAULT_PACKS, *packs) if name in plugin and name not in disabled}
    chosen = {name for name in enabled if name == "core" or _matches(plugin[name], files)}
    pending = list(chosen)
    while pending:
        for name in plugin[pending.pop()].requires:
            if name in plugin and name not in disabled and name not in chosen:
                chosen.add(name)
                pending.append(name)
    selected = [plugin[name] for name in chosen]
    selected += [rule for rule in project if rule.id not in disabled and _matches(rule, files)]
    selected.sort(key=lambda pack: (_TIER_RANK[pack.tier], -_depth(pack, plugin), pack.id))
    return selected, warnings


def _render(packs: Sequence[Pack], kept: Sequence[list[Bullet]]) -> str:
    blocks = [f"## {pack.id} ({pack.source})\n" + "\n".join(bullet.line for bullet in bullets)
              for pack, bullets in zip(packs, kept) if bullets]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def build_rules(packs: Sequence[Pack], budget: int = TASK_BUDGET) -> dict[str, Any]:
    """Render packs; over budget, drop medium then high bullets, lowest precedence first; never critical."""
    kept = [list(pack.bullets) for pack in packs]
    text = _render(packs, kept)
    trimmed: list[str] = []
    warnings: list[str] = []
    for impact in ("medium", "high"):
        step: list[str] = []
        for index in reversed(range(len(packs))):
            for bullet in reversed(list(kept[index])):
                if len(text) <= budget:
                    break
                if bullet.impact == impact:
                    kept[index].remove(bullet)
                    step.append(f"{packs[index].id}#{bullet.anchor}")
                    text = _render(packs, kept)
        if step:
            trimmed += step
            warnings.append(f"rules over {budget} chars: trimmed {impact} " + ", ".join(step))
    if len(text) > budget:
        warnings.append(f"critical rules exceed budget: {len(text)} > {budget} chars")
    return {
        "text": text,
        "chars": len(text),
        "budget": budget,
        "trimmed": trimmed,
        "warnings": warnings,
        "packs": [{"id": pack.id, "source": pack.source, "tier": pack.tier,
                   "bullets": [{"anchor": b.anchor, "impact": b.impact, "text": b.line} for b in bullets],
                   "trimmed": [b.anchor for b in pack.bullets if b not in bullets]}
                  for pack, bullets in zip(packs, kept)],
    }


def list_packs(plugin: Mapping[str, Pack], project: Sequence[Pack], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    packs, disabled = rules_config(config)
    enabled = [plugin[name] for name in dict.fromkeys((*DEFAULT_PACKS, *packs)) if name in plugin and name not in disabled]
    rows = [rule for rule in project if rule.id not in disabled] + enabled
    return [{"id": pack.id, "source": pack.source, "tier": pack.tier, "chars": pack.body_chars,
             "limit": pack.body_limit, "over_limit": pack.body_chars > pack.body_limit,
             "impacts": {impact: sum(b.impact == impact for b in pack.bullets) for impact in IMPACTS}}
            for pack in rows]


def _load_config(repository: Path) -> Mapping[str, Any]:
    if not (repository / ".agent-workflow/config.yaml").is_file():
        return {}
    return resolve_effective_config(repository, write=False).config.to_dict()


def _relative(repository: Path, raw: str) -> str:
    path = Path(raw)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(repository)
        except ValueError:
            pass
    return path.as_posix().removeprefix("./")


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="gin-workflow rules")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("text", "json"), default="text")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--files", nargs="+")
    mode.add_argument("--list", action="store_true")
    try:
        args = parser.parse_args(list(arguments))
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 2
    repository = args.repository.resolve()
    try:
        config = _load_config(repository)
        plugin = load_plugin_packs(plugin_rules_dir())
        project = load_project_rules(repository)
    except (RulesError, ValueError) as error:
        print(f"rules error: {error}", file=sys.stderr)
        return 2
    if args.list:
        rows = list_packs(plugin, project, config)
        if args.format == "json":
            print(json.dumps({"packs": rows}, indent=2, sort_keys=True))
        else:
            for row in rows:
                counts = " ".join(f"{k}={v}" for k, v in row["impacts"].items())
                flag = " OVER LIMIT" if row["over_limit"] else ""
                print(f"{row['id']} ({row['source']}, {row['tier']}): {row['chars']}/{row['limit']} chars; {counts}{flag}")
        return 0
    packs, warnings = select_packs(plugin, project, config, [_relative(repository, f) for f in args.files])
    result = build_rules(packs)
    for warning in [*warnings, *result["warnings"]]:
        print(f"warning: {warning}", file=sys.stderr)
    if args.format == "json":
        print(json.dumps({**result, "warnings": [*warnings, *result["warnings"]]}, indent=2, sort_keys=True))
    else:
        sys.stdout.write(result["text"])
    return 0
