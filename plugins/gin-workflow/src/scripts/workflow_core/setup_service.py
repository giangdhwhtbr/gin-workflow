"""Side-effect-aware operations behind ``gin-workflow setup``."""

from __future__ import annotations

import difflib
import os
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping

from .atomic import atomic_write_many, atomic_write_bytes
from .bundles import export_bundle, verify_bundle
from .checkout import main_checkout
from .configuration import legacy_worker_routing, require_yaml, resolve_effective_config, validate_portable_config
from .project import preset_assignments, project_settings
from .project_detect import detect_project
from .migrations import (
    CURRENT_VERSION,
    apply_migration,
    migrate_config,
    propose_migration,
    rollback_migration,
)
from .executable_resolver import resolve_harness_executable
from .provider_config import DEFAULT_HARNESS_MODELS
from . import agents_block
from . import orchestrator_client
from .schemas import require_jsonschema


INIT_ACTIONS = [
    "create .agent-workflow/config.yaml",
    "create .agent-workflow/backups/",
    "create .agent-workflow/references/",
    "create .agent-workflow/runtime/evidence/",
    "generate .agent-workflow/generated/effective-config.yaml",
    "generate .agent-workflow/generated/config-provenance.yaml",
]


class SetupError(ValueError):
    """Raised for invalid or approval-gated setup operations."""

    def __init__(self, message: str, *, status: str = "error") -> None:
        super().__init__(message)
        self.status = status


def _agents_writes(root: Path, config: Mapping[str, Any], *, create: bool) -> dict[Path, bytes]:
    try:
        return agents_block.planned_writes(root, config, create=create)
    except agents_block.AgentsBlockError as error:
        raise SetupError(str(error)) from error


def _agents_actions(root: Path, writes: Mapping[Path, bytes]) -> list[str]:
    names = {
        root / "AGENTS.md": "write AGENTS.md gin-workflow block",
        root / "CLAUDE.md": "add @AGENTS.md to CLAUDE.md",
    }
    return [names[path] for path in writes if path in names]


def _dependencies() -> None:
    require_yaml()
    require_jsonschema()


def _minimal_config() -> dict[str, str]:
    return {
        "schema_version": CURRENT_VERSION,
        "setup_cli_version": CURRENT_VERSION,
        "workflow_version": CURRENT_VERSION,
    }


def _yaml_text(value: Mapping[str, Any]) -> str:
    yaml = require_yaml()
    return yaml.safe_dump(
        dict(value),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    )


def _merged_provider_gitignore(path: Path) -> bytes:
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = existing.splitlines()
    if "providers.local.yaml" not in lines:
        lines.append("providers.local.yaml")
    if "orchestrator.local.yaml" not in lines:
        lines.append("orchestrator.local.yaml")
    if "runtime/" not in lines:
        lines.append("runtime/")
    return (("\n".join(lines) + "\n") if lines else "providers.local.yaml\norchestrator.local.yaml\nruntime/\n").encode("utf-8")



def detect(repository: Path, *, harness: str | None = None, **_: Any) -> dict[str, Any]:
    root = Path(repository).resolve()
    detected = []
    for name, marker in (("claude", ".claude"), ("codex", ".codex"), ("antigravity", ".agents"), ("opencode", ".opencode")):
        if (root / marker).exists():
            detected.append(name)
    selected = harness or (detected[0] if len(detected) == 1 else None)
    return {
        "status": "detected",
        "repository": str(root),
        "initialized": (root / ".agent-workflow/config.yaml").is_file(),
        "detected_harnesses": detected,
        "harness": selected,
        "project": detect_project(root),
        "beads_installed": shutil.which("bd") is not None,
        "actions": [],
    }


def initialize(
    repository: Path,
    *,
    dry_run: bool = False,
    harness: str | None = None,
    assignments: Iterable[str] = (),
    approve: bool = False,
    **_: Any,
) -> dict[str, Any]:
    _dependencies()
    root = Path(repository).resolve()
    workflow = root / ".agent-workflow"
    config_path = workflow / "config.yaml"
    if config_path.exists():
        generated = workflow / "generated/effective-config.yaml"
        provenance = workflow / "generated/config-provenance.yaml"
        missing_directories = [
            workflow / relative
            for relative in ("backups", "references", "runtime/evidence")
            if not (workflow / relative).is_dir()
        ]
        if not generated.is_file() or not provenance.is_file() or missing_directories:
            actions = ["repair incomplete one-time setup"]
            effective_result = resolve_effective_config(root, write=False)
            agents_writes = _agents_writes(root, effective_result.config.to_dict(), create=True)
            if dry_run:
                return {
                    "status": "would_repair",
                    "repository": str(root),
                    "actions": actions + _agents_actions(root, agents_writes),
                }
            if not approve:
                raise SetupError(
                    "setup repair requires explicit --approve before writing repository configuration",
                    status="approval_required",
                )
            resolve_effective_config(root)
            for path in missing_directories:
                path.mkdir(parents=True, exist_ok=True)
            agents_block.write(agents_writes)
            actions.extend(_agents_actions(root, agents_writes))
            return {
                "status": "repaired",
                "repository": str(root),
                "actions": actions,
            }
        effective_result = resolve_effective_config(root, write=False)
        agents_writes = _agents_writes(root, effective_result.config.to_dict(), create=True)
        if not agents_writes:
            return {"status": "already_initialized", "repository": str(root), "actions": []}
        agents_actions = _agents_actions(root, agents_writes)
        if dry_run:
            return {
                "status": "would_update",
                "repository": str(root),
                "actions": agents_actions,
            }
        if not approve:
            raise SetupError(
                "setup update requires explicit --approve before writing repository configuration",
                status="approval_required",
            )
        agents_block.write(agents_writes)
        return {
            "status": "updated",
            "repository": str(root),
            "actions": agents_actions,
        }

    changes = list(assignments)
    if not dry_run and not approve:
        raise SetupError(
            "initial setup requires explicit --approve before writing repository configuration",
            status="approval_required",
        )

    config: dict[str, Any] = _minimal_config()
    if harness:
        config["harness"] = harness
    for assignment in changes:
        path, value = _parse_assignment(assignment)
        _set_nested(config, path, value)
    validate_portable_config(config)
    resolved = resolve_effective_config(root, repository_config=config, write=False)
    agents_writes = _agents_writes(root, resolved.config.to_dict(), create=True)
    agents_actions = _agents_actions(root, agents_writes)
    config_text = _yaml_text(config)
    if dry_run:
        payload = {
            "status": "would_initialize",
            "repository": str(root),
            "actions": list(INIT_ACTIONS),
            "configuration": config,
        }
        payload["actions"].extend(agents_actions)
        return payload

    writes = {
        config_path: config_text.encode("utf-8"),
        resolved.effective_config_path: _yaml_text(resolved.config.to_dict()).encode("utf-8"),
        resolved.provenance_path: _yaml_text(resolved.provenance.to_dict()).encode("utf-8"),
    }
    atomic_write_many(writes)
    for relative in ("backups", "references", "runtime/evidence"):
        (workflow / relative).mkdir(parents=True, exist_ok=True)
    agents_block.write(agents_writes)
    actions = list(INIT_ACTIONS)
    actions.extend(agents_actions)
    return {"status": "initialized", "repository": str(root), "actions": actions}


def _parse_assignment(assignment: str) -> tuple[list[str], Any]:
    if "=" not in assignment:
        raise SetupError(f"configuration assignment must use KEY=VALUE: {assignment}")
    key, raw_value = assignment.split("=", 1)
    path = [part for part in key.split(".") if part]
    if not path:
        raise SetupError("configuration assignment key must not be empty")
    yaml = require_yaml()
    try:
        value = yaml.safe_load(raw_value)
    except yaml.YAMLError as error:
        raise SetupError(f"invalid configuration value for {key}: {error}") from error
    return path, value


def _set_nested(config: dict[str, Any], path: list[str], value: Any) -> None:
    current = config
    for component in path[:-1]:
        child = current.get(component)
        if child is None:
            child = {}
            current[component] = child
        elif isinstance(child, str):
            child = {"model": child}
            current[component] = child
        elif not isinstance(child, dict):
            raise SetupError(f"cannot set nested value below non-mapping field {component}")
        current = child
    current[path[-1]] = value


def configure(
    repository: Path,
    *,
    assignments: Iterable[str] = (),
    approve: bool = False,
    dry_run: bool = False,
    harness: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    _dependencies()
    root = Path(repository).resolve()
    config_path = root / ".agent-workflow/config.yaml"
    if not config_path.is_file():
        raise SetupError("repository is not initialized")
    yaml = require_yaml()
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise SetupError(f"invalid YAML in {config_path}: {error}") from error
    if not isinstance(loaded, Mapping):
        raise SetupError("repository configuration must contain a YAML mapping")
    config = {str(key): value for key, value in loaded.items()}
    changes = list(assignments)
    for assignment in changes:
        path, value = _parse_assignment(assignment)
        _set_nested(config, path, value)
    if harness:
        config["harness"] = harness
        changes.append(f"harness={harness}")
    if not changes:
        return {"status": "no_changes", "repository": str(root), "actions": []}
    validate_portable_config(config)
    resolved = resolve_effective_config(root, repository_config=config, write=False)
    actions = ["update .agent-workflow/config.yaml", "refresh generated configuration"]
    if dry_run:
        return {"status": "would_configure", "repository": str(root), "actions": actions}
    if not approve:
        raise SetupError(
            "configure requires explicit --approve before changing user-authored configuration",
            status="approval_required",
        )
    writes = {
        config_path: _yaml_text(config).encode("utf-8"),
        resolved.effective_config_path: _yaml_text(resolved.config.to_dict()).encode("utf-8"),
        resolved.provenance_path: _yaml_text(resolved.provenance.to_dict()).encode("utf-8"),
    }
    atomic_write_many(writes)
    return {"status": "configured", "repository": str(root), "actions": actions}


def refresh(repository: Path, *, dry_run: bool = False, **_: Any) -> dict[str, Any]:
    _dependencies()
    root = Path(repository).resolve()
    result = resolve_effective_config(root, write=False)
    writes = _agents_writes(root, result.config.to_dict(), create=False)  # broken markers fail before any write
    if not dry_run:
        result = resolve_effective_config(root, write=True)
    agents_state = (
        "updated"
        if writes
        else ("unchanged" if agents_block.status(root, result.config.to_dict()) == "ok" else "absent")
    )
    if writes and not dry_run:
        agents_block.write(writes)
    actions = [
        "generate .agent-workflow/generated/effective-config.yaml",
        "generate .agent-workflow/generated/config-provenance.yaml",
    ]
    if writes:
        actions.append("update AGENTS.md gin-workflow block")
    return {
        "status": "would_refresh" if dry_run else "refreshed",
        "repository": str(root),
        "actions": actions,
        "effective_config": str(result.effective_config_path),
        "provenance": str(result.provenance_path),
        "agents_block": agents_state,
    }


def status(repository: Path, **_: Any) -> dict[str, Any]:
    root = Path(repository).resolve()
    workflow = root / ".agent-workflow"
    config = workflow / "config.yaml"
    generated = [
        workflow / "generated/effective-config.yaml",
        workflow / "generated/config-provenance.yaml",
    ]
    return {
        "status": "initialized" if config.is_file() else "not_initialized",
        "repository": str(root),
        "config": str(config),
        "generated": all(path.is_file() for path in generated),
        "actions": [],
    }


def doctor(repository: Path, *, probe: bool = False, **_: Any) -> dict[str, Any]:
    _dependencies()
    root = Path(repository).resolve()
    checks: dict[str, bool] = {"repository": root.is_dir(), "initialized": False, "configuration": False}
    checks_details: dict[str, Any] = {}
    config = root / ".agent-workflow/config.yaml"
    checks["initialized"] = config.is_file()
    effective_cfg: dict[str, Any] = {}
    backend_actions: list[str] = []
    if config.is_file():
        effective_cfg = resolve_effective_config(root, write=False).config.to_dict()
        checks["configuration"] = True
        user_cfg = require_yaml().safe_load(config.read_text(encoding="utf-8")) or {}
        providers_block = user_cfg.get("providers")
        backend_unset = not (isinstance(providers_block, Mapping) and "task_tracking" in providers_block)
        if (root / ".beads").is_dir() and backend_unset and "team" not in user_cfg:
            backend_actions.append(
                ".beads exists but providers.task_tracking is unset, so tasks use markdown; to keep Beads run "
                "gin-workflow setup configure --set providers.task_tracking=beads --approve"
            )
        if str(user_cfg.get("schema_version", "")) != "2.8" and legacy_worker_routing(user_cfg):
            backend_actions.append(
                "worker routing under routing: is ignored; run gin-workflow setup update --to-version 2.8 --approve"
            )

    h = effective_cfg.get("harness") or detect(root).get("harness")
    h_exe = None
    if h and h in DEFAULT_HARNESS_MODELS:
        h_exe = resolve_harness_executable(DEFAULT_HARNESS_MODELS[h]["executable"], provider=h)
    checks["harness"] = bool(h_exe)
    checks_details["harness"] = {"name": h, "executable": h_exe}
    if not h_exe:
        backend_actions.append(
            f"main harness {h}: executable not found on PATH" if h else "main harness is not configured; run gin-workflow setup init"
        )

    hook_actions: list[str] = []
    if checks["configuration"]:
        settings = project_settings(effective_cfg)
        missing = [k for k in ("lint", "typecheck", "test", "build") if not settings.verify_commands.get(k)]
        checks_details["verify_commands"] = {"missing": missing}
        if settings.verify_commands:
            from .hooks import status as hooks_status

            states = hooks_status(root)
            checks_details["hooks"] = states
            hook_actions = [f"hooks: {name} is missing; run gin-workflow hooks install" if state == "missing" else
                            f"hooks: {name} is occupied; chain `exec gin-workflow hooks run {name}` into it"
                            for name, state in states.items() if state != "ok"]
        detected = detect_project(root)
        if settings.stage == "greenfield" and detected["stage"] == "brownfield":
            checks_details["project_stage"] = {"suggestion": "project now has a manifest/sources; run /setup configure to set project.stage=brownfield"}
        graph = dict(detected["codegraph"])
        if not graph["installed"]:
            graph["suggestion"] = ("codegraph is not installed (optional); see "
                                   "https://github.com/giangdhwhtbr/gin-workflow/blob/master/docs/guides/recommended-tools.md")
        elif graph["stale"]:
            graph["suggestion"] = "codegraph index is older than HEAD; run `codegraph sync`"
        checks_details["codegraph"] = graph

    actions: list[str] = [*backend_actions, *hook_actions]
    checks["review_ledgers"] = True
    planning_dir = root / ".planning"
    if planning_dir.is_dir():
        try:
            from review_ledger.cleanup import cleanup_review_ledgers
            preview = cleanup_review_ledgers(root, all_closed=True, dry_run=True)
            stale_cleaned = preview.get("cleaned", [])
            stale_count = len(stale_cleaned)
            if stale_count > 0:
                checks["review_ledgers"] = False
                checks_details["review_ledgers"] = {
                    "stale_count": stale_count,
                    "stale_beads": [item["bead_id"] for item in stale_cleaned],
                    "remedy": "Run 'python3 review-ledger.py cleanup --all-closed' to remove stale review ledgers.",
                }
                actions.append(
                    f"Run 'python3 review-ledger.py cleanup --all-closed' to remove {stale_count} stale review ledger(s)."
                )
        except Exception:
            checks["review_ledgers"] = True

    if checks["configuration"]:
        from .rules_checks import rules_doctor

        effective = effective_cfg
        rules_detail = rules_doctor(root, effective)
        checks_details["rules"] = rules_detail
        for item in rules_detail.get("tool_checks", []):
            if item["status"] == "missing":
                actions.append(f"rules: add {item['id']} for pack {item['pack']} (suggestion in checks_details.rules)")
        for item in rules_detail.get("conflicts", []):
            actions.append(f"rules: {item['file']} says '{item['project_conflict']}', pack {item['pack']} says "
                           f"'{item['pack_says']}'; the project wins, record the divergence")

        state = agents_block.status(root, effective)
        checks_details["agents_block"] = state
        if state == "stale":
            actions.append("agents: AGENTS.md block is stale; run gin-workflow setup refresh")
        elif state == "invalid":
            actions.append("agents: AGENTS.md block cannot be updated (broken markers or a symbolic link); fix it by hand")

        from .specs import sdd_config
        from .specs_migrate import sdd_report

        sdd_detail = sdd_report(root, effective, sdd_config(effective))
        checks_details["sdd"] = sdd_detail
        if "suggestion" in sdd_detail:
            actions.append(f"sdd: {sdd_detail['suggestion']}")
        if "conflict" in sdd_detail:
            actions.append(f"sdd: {sdd_detail['conflict']['path']} holds non-SDD files; "
                           f"{sdd_detail['conflict']['suggestion']}")

        from .team import load_team

        team = load_team(effective)
        if team is not None:
            from .team_init import doctor_report

            team_detail = doctor_report(root, team, effective)
            checks_details["team"] = team_detail
            checks["team"] = all(team_detail["checks"].values())
            actions.extend(f"team: {action}" for action in team_detail["actions"])

        if effective.get("provider_mode") == "multi":
            checks_details["orchestrator"] = orchestrator_client.status()
            if probe and orchestrator_client.delegates(effective, "doctor"):
                try:
                    providers = orchestrator_client.call(["doctor", "--repository", str(root)])["providers"]
                    checks_details["providers"] = providers
                    checks["providers"] = all(v["available"] for v in providers.values())
                except (orchestrator_client.OrchestratorError, KeyError, TypeError, AttributeError):
                    checks["providers"] = False
                    checks_details["providers"] = {"reason": orchestrator_client.FAILED}
            if not checks_details["orchestrator"].get("available"):
                warn = orchestrator_client.warning(effective)
                if warn:
                    actions.append(warn)

    healthy = all(checks.values())
    payload: dict[str, Any] = {
        "status": "healthy" if healthy else "issues_found",
        "repository": str(root),
        "checks": checks,
        "actions": actions,
    }
    if checks_details:
        payload["checks_details"] = checks_details
    return payload


def diff(repository: Path, **_: Any) -> dict[str, Any]:
    _dependencies()
    root = Path(repository).resolve()
    result = resolve_effective_config(root, write=False)
    expected = {
        result.effective_config_path: _yaml_text(result.config.to_dict()),
        result.provenance_path: _yaml_text(result.provenance.to_dict()),
    }
    changes: dict[str, str] = {}
    for path, wanted in expected.items():
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        rendered = "".join(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                wanted.splitlines(keepends=True),
                fromfile=str(path),
                tofile=f"{path} (expected)",
            )
        )
        if rendered:
            changes[str(path.relative_to(root))] = rendered
    return {
        "status": "clean" if not changes else "changes",
        "repository": str(root),
        "diff": changes,
        "actions": [],
    }


def update(
    repository: Path,
    *,
    target_version: str = CURRENT_VERSION,
    approve: bool = False,
    dry_run: bool = False,
    assignments: Iterable[str] = (),
    **_: Any,
) -> dict[str, Any]:
    _dependencies()
    root = Path(repository).resolve()
    config_path = root / ".agent-workflow/config.yaml"
    yaml = require_yaml()
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise SetupError(f"invalid repository configuration: {error}") from error
    if not isinstance(loaded, Mapping):
        raise SetupError("repository configuration must contain a YAML mapping")
    migrated = migrate_config({str(key): value for key, value in loaded.items()}, target_version)
    for assignment in assignments:
        path, value = _parse_assignment(assignment)
        _set_nested(migrated, path, value)
    validate_portable_config(migrated)
    resolved = resolve_effective_config(root, repository_config=migrated, write=False)

    proposal = propose_migration(root, target_version=target_version)
    main = main_checkout(root)
    local_dir = main / ".agent-workflow"
    old_local, new_local = local_dir / "providers.local.yaml", local_dir / "orchestrator.local.yaml"
    rename_local = target_version == "2.8" and old_local.is_file() and not new_local.exists()
    if rename_local:
        proposal["actions"] = [*proposal.get("actions", ()), f"rename {old_local.relative_to(main)} to {new_local.name}"]
    payload = {**proposal, "configuration": migrated}
    if dry_run or not approve:
        return payload
    additional_writes: dict[Path, bytes] = {
        resolved.effective_config_path: _yaml_text(resolved.config.to_dict()).encode("utf-8"),
        resolved.provenance_path: _yaml_text(resolved.provenance.to_dict()).encode("utf-8"),
    }
    res = apply_migration(
        root,
        target_version=target_version,
        prepared_config=migrated,
        additional_writes=additional_writes,
    )
    if rename_local:
        os.replace(old_local, new_local)
        res.setdefault("actions", []).append(f"rename {old_local.relative_to(main)} to {new_local.name}")
        ignore_path = root / ".agent-workflow/.gitignore"
        atomic_write_bytes(ignore_path, _merged_provider_gitignore(ignore_path))
    return res


def rollback(repository: Path, *, backup: Path | None, dry_run: bool = False, **_: Any) -> dict[str, Any]:
    _dependencies()
    if backup is None:
        raise SetupError("rollback requires an explicit --backup target")
    result = rollback_migration(repository, backup, dry_run=dry_run)
    root = Path(repository).resolve()
    main = main_checkout(root)
    local_dir = main / ".agent-workflow"
    old_local, new_local = local_dir / "providers.local.yaml", local_dir / "orchestrator.local.yaml"
    if str(result.get("restored_version", "")) != "2.8" and new_local.is_file() and not old_local.exists():
        if not dry_run:
            os.replace(new_local, old_local)
        result.setdefault("actions", []).append(f"rename {new_local.relative_to(main)} to {old_local.name}")
    return result


def export(repository: Path, *, output: Path | None, dry_run: bool = False, **_: Any) -> dict[str, Any]:
    if output is None:
        output = Path(repository).resolve() / "gin-workflow-bundle.json"
    return export_bundle(repository, output, dry_run=dry_run)


def verify(*, bundle: Path | None, **_: Any) -> dict[str, Any]:
    if bundle is None:
        raise SetupError("verify-bundle requires an explicit --bundle target")
    return verify_bundle(bundle)


def harness_override(
    repository: Path,
    *,
    harness: str | None = None,
    reset: bool = False,
    clear: bool = False,
    dry_run: bool = False,
    **_: Any,
) -> dict[str, Any]:
    runtime_dir = main_checkout(Path(repository).resolve()) / ".agent-workflow" / "runtime"
    override_file = runtime_dir / "session-harness.override"

    should_reset = reset or clear

    if should_reset:
        if harness:
            raise SetupError("cannot specify both --harness and --reset/--clear")
        if dry_run:
            return {
                "status": "dry_run",
                "message": "would clear session harness override",
                "actions": [f"delete {override_file}"],
            }
        if override_file.exists():
            override_file.unlink()
            return {
                "status": "success",
                "message": "cleared session main harness override",
                "actions": [f"deleted {override_file}"],
            }
        return {
            "status": "success",
            "message": "no active session main harness override file to clear",
            "actions": [],
        }

    if not harness:
        if override_file.is_file():
            current = override_file.read_text(encoding="utf-8").strip()
            return {
                "status": "success",
                "message": f"active session main harness override: '{current}'",
                "actions": [],
                "harness": current,
            }
        return {
            "status": "success",
            "message": "no session main harness override active",
            "actions": [],
        }

    selected = harness.strip().lower()
    from .configuration import SUPPORTED_HARNESSES

    if selected not in SUPPORTED_HARNESSES:
        raise SetupError(
            f"invalid harness '{harness}'; expected one of: {', '.join(SUPPORTED_HARNESSES)}"
        )

    if dry_run:
        return {
            "status": "dry_run",
            "message": f"would set session main harness override to '{selected}'",
            "actions": [f"write '{selected}' to {override_file}"],
            "harness": selected,
        }

    runtime_dir.mkdir(parents=True, exist_ok=True)
    override_file.write_text(selected, encoding="utf-8")
    return {
        "status": "success",
        "message": f"set session main harness override to '{selected}'",
        "actions": [f"wrote '{selected}' to {override_file}"],
        "harness": selected,
    }


def preset(repository: Path, *, project_stage: str | None = None, project_shape: str | None = None,
           rigor: str | None = None, task_tracking: str | None = None, monorepo: bool = False,
           stack_intent: str = "", **_: Any) -> dict[str, Any]:
    from .rules import load_plugin_packs, plugin_rules_dir
    from .rules_checks import propose_packs, tool_check_report
    from .specs import SDD_DEFAULTS
    from .specs_migrate import sdd_report

    root = Path(repository).resolve()
    detected = detect_project(root)
    plugin = load_plugin_packs(plugin_rules_dir())
    rule_packs = propose_packs(root, plugin, stack_intent=stack_intent)
    stage = project_stage or detected["stage"]
    layout = "sdd" if stage == "greenfield" else ""
    try:
        assignments = preset_assignments(
            stage=stage, shape=project_shape or detected["shape"],
            rigor=rigor or detected["suggested_rigor"], task_tracking=task_tracking or "markdown",
            monorepo=monorepo or detected["monorepo"], stack_intent=stack_intent,
            verify_commands=detected["verify_commands"], packages=tuple(detected["packages"]),
            rule_packs=rule_packs, layout=layout)
    except ValueError as error:
        raise SetupError(str(error)) from error
    missing = [key for key, value in detected["verify_commands"].items() if not value and key != "e2e"]
    tool_checks = [item for item in tool_check_report(root, [plugin[name] for name in rule_packs])
                   if item["status"] != "present"]
    sdd = sdd_report(root, {}, dict(SDD_DEFAULTS), proposed=bool(layout)) if layout else {"layout": "legacy"}
    return {"status": "proposed", "assignments": assignments, "detected": detected,
            "rule_packs": rule_packs, "rule_tool_checks": tool_checks, "sdd": sdd,
            "warnings": [f"no {key} command detected" for key in missing], "actions": []}


def models(repository: Path, *, provider: str | None = None, **_: Any) -> dict[str, Any]:
    if not provider:
        raise SetupError("--provider is required")
    from . import orchestrator_client

    listed = orchestrator_client.models(provider)
    return {"status": "listed", "provider": provider, "models": listed, "manual_entry": True, "actions": []}


COMMANDS = {
    "detect": detect,
    "preset": preset,
    "models": models,
    "init": initialize,
    "configure": configure,
    "refresh": refresh,
    "update": update,
    "doctor": doctor,
    "status": status,
    "diff": diff,
    "rollback": rollback,
    "export-bundle": export,
    "verify-bundle": verify,
    "harness-override": harness_override,
}

