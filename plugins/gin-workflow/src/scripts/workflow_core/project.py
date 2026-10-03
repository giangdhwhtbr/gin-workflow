"""Resolved project profile: stage x shape, rigor presets, verify commands (schema 2.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping, Sequence

STAGES = ("greenfield", "brownfield", "legacy")
SHAPES = ("frontend", "backend", "fullstack", "library")
RIGORS = ("easy", "standard", "strict")
VERIFY_KEYS = ("lint", "typecheck", "test", "build", "e2e")
RIGOR_PRESETS: dict[str, dict[str, Any]] = {
    "easy": {"worktree": "never", "review": "self_check", "review_ledger": False, "max_cycles": 2},
    "standard": {"worktree": "parallel", "review": "independent", "review_ledger": False, "max_cycles": 2},
    "strict": {"worktree": "always", "review": "independent", "review_ledger": True, "max_cycles": 2},
}


@dataclass(frozen=True)
class ProjectSettings:
    stage: str = "brownfield"
    shape: str = "fullstack"
    monorepo: bool = False
    rigor: str = "standard"
    stack_intent: str = ""
    packages: tuple[Mapping[str, Any], ...] = ()
    provider_mode: str = "multi"
    verify_commands: Mapping[str, str] = field(default_factory=dict)
    independence: str = "provider"
    worktree: str = "parallel"
    review: str = "independent"
    review_ledger: bool = False
    max_cycles: int = 2
    quick_max_files: int = 5
    layout: str = "legacy"
    spec_review: str = "chat"

    def to_dict(self) -> dict[str, Any]:
        return {name: (list(value) if isinstance(value, tuple) else dict(value) if isinstance(value, Mapping) else value)
                for name, value in self.__dict__.items()}


def _section(config: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = config
    for key in keys:
        current = current.get(key, {}) if isinstance(current, Mapping) else {}
    return current if isinstance(current, Mapping) else {}


def project_settings(config: Mapping[str, Any]) -> ProjectSettings:
    """Resolve the project block; a config without `project:` keeps pre-2.4 behavior."""
    project = _section(config, "project")
    review = _section(config, "routing", "review")
    rigor = str(project.get("rigor", "standard"))
    preset = RIGOR_PRESETS.get(rigor, RIGOR_PRESETS["standard"])
    commands = {k: str(v) for k, v in _section(config, "verify", "checks").items() if k in VERIFY_KEYS and str(v).strip()}
    return ProjectSettings(
        stage=str(project.get("stage", "brownfield")),
        shape=str(project.get("shape", "fullstack")),
        monorepo=bool(project.get("monorepo", False)),
        rigor=rigor,
        stack_intent=str(project.get("stack_intent", "")),
        packages=tuple(project.get("packages", ()) or ()),
        provider_mode=str(config.get("provider_mode", "multi")),
        verify_commands=commands,
        independence=str(review.get("independence", "provider")),
        worktree=str(project.get("worktree", preset["worktree"])),
        review=str(project.get("review", preset["review"])),
        review_ledger=bool(project.get("review_ledger", preset["review_ledger"])),
        max_cycles=int(review.get("max_cycles", preset["max_cycles"])),
        quick_max_files=int(_section(config, "quick").get("max_files", 5)),
        layout=str(_section(config, "artifacts").get("layout", "legacy")),
        spec_review=str(_section(config, "artifacts").get("spec_review", "chat")),
    )


ROLES_BY_SHAPE = {
    "frontend": ("frontend", "review", "docs", "general"),
    "backend": ("backend", "review", "docs", "general"),
    "fullstack": ("frontend", "backend", "review", "docs", "general"),
    "library": ("frontend", "backend", "review", "docs", "general"),
}


def preset_assignments(*, stage: str, shape: str, rigor: str, provider_mode: str, monorepo: bool = False,
                       stack_intent: str = "", verify_commands: Mapping[str, str] | None = None,
                       packages: tuple[Mapping[str, Any], ...] | list = (),
                       rule_packs: Sequence[str] = (), layout: str = "") -> list[str]:
    """Explicit `--set` assignments for setup; skills never infer presets at runtime."""
    if stage not in STAGES or shape not in SHAPES or rigor not in RIGORS or provider_mode not in ("single", "multi"):
        raise ValueError(f"invalid project preset: {stage=} {shape=} {rigor=} {provider_mode=}")
    preset = RIGOR_PRESETS[rigor]
    values: dict[str, Any] = {
        "project.stage": stage, "project.shape": shape, "project.monorepo": monorepo, "project.rigor": rigor,
        "project.worktree": preset["worktree"], "project.review": preset["review"],
        "project.review_ledger": preset["review_ledger"], "provider_mode": provider_mode,
        "routing.review.max_cycles": preset["max_cycles"],
        "routing.review.independence": "session" if provider_mode == "single" else "provider",
        "quick.max_files": 5,
    }
    if stack_intent:
        values["project.stack_intent"] = stack_intent
    if packages:
        values["project.packages"] = [dict(package) for package in packages]
    if rule_packs:
        values["rules.packs"] = list(rule_packs)
    if layout:
        values["artifacts.layout"] = layout
    for key in VERIFY_KEYS:
        values[f"verify.checks.{key}"] = str((verify_commands or {}).get(key, ""))
    if provider_mode == "single":
        for role in ROLES_BY_SHAPE[shape]:
            values[f"routing.roles.{role}"] = {"preferred": ["main_harness"]}
        values["routing.review.role"] = "review"
        values["routing.review.require_independent"] = True
        values["routing.review.allow_self_review_fallback"] = False
    return [f"{key}={json.dumps(value)}" for key, value in values.items()]
