"""Read-only rule-pack support for setup and doctor: proposals, tool checks, conflict warnings."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
from typing import Any, Mapping, Sequence

from .project_detect import _mentions, _read_json, _workspace_dirs, _workspace_globs
from .rules import Pack, RulesError, load_plugin_packs, plugin_rules_dir, rules_config

_TIER_ORDER = ("core", "language", "framework")
_ESLINT_FILES = ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs", "eslint.config.ts",
                 ".eslintrc", ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.yml", ".eslintrc.yaml")
_JSONC_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
_CONFLICT_FILES = ("CLAUDE.md", "AGENTS.md")


def _js_deps(root: Path) -> set[str]:
    deps: set[str] = set()
    for directory in [root, *_workspace_dirs(root, _workspace_globs(root))]:
        manifest = _read_json(directory / "package.json")
        for key in ("dependencies", "devDependencies"):
            if isinstance(manifest.get(key), dict):
                deps |= set(manifest[key])
    return deps


def _py_text(root: Path) -> str:
    return "".join((root / name).read_text(encoding="utf-8", errors="replace").lower()
                   for name in ("pyproject.toml", "requirements.txt") if (root / name).is_file())


def _with_requires(chosen: set[str], plugin: Mapping[str, Pack]) -> set[str]:
    pending = list(chosen)
    while pending:
        for name in plugin[pending.pop()].requires:
            if name in plugin and name not in chosen:
                chosen.add(name)
                pending.append(name)
    return chosen


def propose_packs(root: Path, plugin: Mapping[str, Pack], *, stack_intent: str = "") -> list[str]:
    root = Path(root).resolve()
    deps, py_text, intent = _js_deps(root), _py_text(root), stack_intent.lower()
    chosen = {"core"} & set(plugin)
    for pack in plugin.values():
        detect = pack.meta.get("detect") or {}
        js_names = [str(n) for n in detect.get("package_json_deps", [])]
        py_names = [str(n) for n in detect.get("pyproject_deps", [])]
        if (any(name in deps for name in js_names)
                or any(_mentions(py_text, name) for name in py_names)
                or any((root / str(name)).exists() for name in detect.get("files_exist", []))
                or (intent and any(_mentions(intent, name.lower()) for name in (pack.id, *js_names, *py_names)))):
            chosen.add(pack.id)
    return sorted(_with_requires(chosen, plugin), key=lambda name: (_TIER_ORDER.index(plugin[name].tier), name))


def _jsonc(text: str) -> Any:
    stripped = _JSONC_TOKENS.sub(lambda m: m.group(0) if m.group(0).startswith('"') else "", text)
    return json.loads(_TRAILING_COMMA.sub(r"\1", stripped))


def check_tool(root: Path, check: Mapping[str, Any]) -> str:
    """`present` | `missing` | `unknown`; never raises on unreadable or unparseable config."""
    root = Path(root)
    kind, value = next(iter(check.items()))
    if kind == "file_exists":
        return "present" if (root / str(value)).exists() else "missing"
    if kind == "tsconfig_option":
        path = root / "tsconfig.json"
        if not path.is_file():
            return "missing"
        try:
            data = _jsonc(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            return "unknown"
        options = data.get("compilerOptions", {}) if isinstance(data, dict) else None
        if not isinstance(options, dict):
            return "unknown"
        for key, expected in dict(value).items():
            if key not in options:
                return "unknown" if "extends" in data else "missing"
            if options[key] != expected:
                return "missing"
        return "present"
    if kind == "eslint_rule":
        texts = []
        for name in _ESLINT_FILES:
            if (root / name).is_file():
                try:
                    texts.append((root / name).read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    return "unknown"
        package_config = _read_json(root / "package.json").get("eslintConfig")
        if package_config:
            texts.append(json.dumps(package_config))
        if not texts:
            return "missing"
        plugin_name = str(value).split("/")[0]
        return "present" if any(str(value) in text or plugin_name in text for text in texts) else "missing"
    if kind == "pyproject_tool":
        path = root / "pyproject.toml"
        if not path.is_file():
            return "missing"
        try:
            node: Any = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
            return "unknown"
        for part in str(value).split("."):
            if not isinstance(node, dict) or part not in node:
                return "missing"
            node = node[part]
        return "present"
    return "unknown"


def tool_check_report(root: Path, packs: Sequence[Pack]) -> list[dict[str, str]]:
    return [{"pack": pack.id, "id": str(item["id"]), "status": check_tool(root, item["check"]),
             "suggest": str(item.get("suggest", ""))}
            for pack in packs for item in (pack.meta.get("tool_checks") or [])]


def conflict_warnings(root: Path, packs: Sequence[Pack]) -> list[dict[str, str]]:
    warnings = []
    for name in _CONFLICT_FILES:
        path = Path(root) / name
        text = path.read_text(encoding="utf-8", errors="replace").lower() if path.is_file() else ""
        for pack in packs:
            for item in pack.meta.get("conflict_keywords") or []:
                if text and str(item["project_conflict"]).lower() in text:
                    warnings.append({"pack": pack.id, "pack_says": str(item["pack_says"]),
                                     "project_conflict": str(item["project_conflict"]), "file": name})
    return warnings


def rules_doctor(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    try:
        plugin = load_plugin_packs(plugin_rules_dir())
    except RulesError as error:
        return {"error": str(error)}
    names, disabled = rules_config(config)
    chosen = _with_requires({n for n in ("core", *names) if n in plugin and n not in disabled}, plugin) - disabled
    packs = [plugin[name] for name in sorted(chosen, key=lambda n: (_TIER_ORDER.index(plugin[n].tier), n))]
    return {"packs": [pack.id for pack in packs], "tool_checks": tool_check_report(root, packs),
            "conflicts": conflict_warnings(root, packs)}
