"""Side-effect-aware operations behind ``gin-workflow setup``."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any, Iterable, Mapping

from .atomic import atomic_write_many
from .bundles import export_bundle, verify_bundle
from .configuration import require_yaml, resolve_effective_config, validate_portable_config
from .migrations import (
    CURRENT_VERSION,
    apply_migration,
    migrate_config,
    propose_migration,
    rollback_migration,
)
from .provider_config import validate_provider_local_config
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
    return (("\n".join(lines) + "\n") if lines else "providers.local.yaml\n").encode("utf-8")


def detect(repository: Path, *, harness: str | None = None, **_: Any) -> dict[str, Any]:
    root = Path(repository).resolve()
    detected = []
    for name, marker in (("claude", ".claude"), ("codex", ".codex"), ("antigravity", ".agents")):
        if (root / marker).exists():
            detected.append(name)
    selected = harness or (detected[0] if len(detected) == 1 else None)
    return {
        "status": "detected",
        "repository": str(root),
        "initialized": (root / ".agent-workflow/config.yaml").is_file(),
        "detected_harnesses": detected,
        "harness": selected,
        "actions": [],
    }


def initialize(
    repository: Path,
    *,
    dry_run: bool = False,
    harness: str | None = None,
    assignments: Iterable[str] = (),
    provider_assignments: Iterable[str] = (),
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
            if dry_run:
                return {
                    "status": "would_repair",
                    "repository": str(root),
                    "actions": actions,
                }
            if not approve:
                raise SetupError(
                    "setup repair requires explicit --approve before writing repository configuration",
                    status="approval_required",
                )
            resolve_effective_config(root)
            for path in missing_directories:
                path.mkdir(parents=True, exist_ok=True)
            return {
                "status": "repaired",
                "repository": str(root),
                "actions": actions,
            }
        return {"status": "already_initialized", "repository": str(root), "actions": []}

    changes = list(assignments)
    provider_changes = list(provider_assignments)
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
    provider_config: dict[str, Any] | None = None
    if provider_changes:
        provider_config = {"schema_version": CURRENT_VERSION, "providers": {}}
        for assignment in provider_changes:
            path, value = _parse_assignment(assignment)
            _set_nested(provider_config, path, value)
        validate_provider_local_config(provider_config)
    resolved = resolve_effective_config(root, repository_config=config, write=False)
    config_text = _yaml_text(config)
    if dry_run:
        payload = {
            "status": "would_initialize",
            "repository": str(root),
            "actions": list(INIT_ACTIONS),
            "configuration": config,
        }
        if provider_config is not None:
            payload["provider_configuration"] = provider_config
            payload["actions"].extend(
                [
                    "create .agent-workflow/providers.local.yaml",
                    "create .agent-workflow/.gitignore",
                ]
            )
        return payload

    writes = {
        config_path: config_text.encode("utf-8"),
        resolved.effective_config_path: _yaml_text(resolved.config.to_dict()).encode("utf-8"),
        resolved.provenance_path: _yaml_text(resolved.provenance.to_dict()).encode("utf-8"),
    }
    if provider_config is not None:
        writes[workflow / "providers.local.yaml"] = _yaml_text(provider_config).encode("utf-8")
        writes[workflow / ".gitignore"] = _merged_provider_gitignore(workflow / ".gitignore")
    atomic_write_many(writes)
    for relative in ("backups", "references", "runtime/evidence"):
        (workflow / relative).mkdir(parents=True, exist_ok=True)
    actions = list(INIT_ACTIONS)
    if provider_config is not None:
        actions.extend(
            [
                "create .agent-workflow/providers.local.yaml",
                "create .agent-workflow/.gitignore",
            ]
        )
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
        if not isinstance(child, dict):
            raise SetupError(f"cannot set nested value below non-mapping field {component}")
        current = child
    current[path[-1]] = value


def configure(
    repository: Path,
    *,
    assignments: Iterable[str] = (),
    provider_assignments: Iterable[str] = (),
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
    provider_changes = list(provider_assignments)
    for assignment in changes:
        path, value = _parse_assignment(assignment)
        _set_nested(config, path, value)
    if harness:
        config["harness"] = harness
        changes.append(f"harness={harness}")
    if not changes and not provider_changes:
        return {"status": "no_changes", "repository": str(root), "actions": []}
    validate_portable_config(config)
    resolved = resolve_effective_config(root, repository_config=config, write=False)
    provider_config: dict[str, Any] | None = None
    if provider_changes:
        provider_path = root / ".agent-workflow/providers.local.yaml"
        if provider_path.is_file():
            try:
                current_provider = yaml.safe_load(provider_path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, yaml.YAMLError) as error:
                raise SetupError(f"invalid provider local configuration: {error}") from error
            if not isinstance(current_provider, Mapping):
                raise SetupError("provider local configuration must contain a YAML mapping")
            provider_config = {str(key): value for key, value in current_provider.items()}
        else:
            provider_config = {"schema_version": CURRENT_VERSION, "providers": {}}
        for assignment in provider_changes:
            path, value = _parse_assignment(assignment)
            _set_nested(provider_config, path, value)
        validate_provider_local_config(provider_config)
    actions = ["update .agent-workflow/config.yaml", "refresh generated configuration"]
    if provider_config is not None:
        actions.extend(
            [
                "update .agent-workflow/providers.local.yaml",
                "update .agent-workflow/.gitignore",
            ]
        )
    if dry_run:
        payload = {"status": "would_configure", "repository": str(root), "actions": actions}
        if provider_config is not None:
            payload["provider_configuration"] = provider_config
        return payload
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
    if provider_config is not None:
        writes[root / ".agent-workflow/providers.local.yaml"] = _yaml_text(provider_config).encode("utf-8")
        ignore_path = root / ".agent-workflow/.gitignore"
        writes[ignore_path] = _merged_provider_gitignore(ignore_path)
    atomic_write_many(writes)
    return {"status": "configured", "repository": str(root), "actions": actions}


def refresh(repository: Path, *, dry_run: bool = False, **_: Any) -> dict[str, Any]:
    _dependencies()
    root = Path(repository).resolve()
    result = resolve_effective_config(root, write=not dry_run)
    return {
        "status": "would_refresh" if dry_run else "refreshed",
        "repository": str(root),
        "actions": [
            "generate .agent-workflow/generated/effective-config.yaml",
            "generate .agent-workflow/generated/config-provenance.yaml",
        ],
        "effective_config": str(result.effective_config_path),
        "provenance": str(result.provenance_path),
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


def doctor(repository: Path, **_: Any) -> dict[str, Any]:
    _dependencies()
    root = Path(repository).resolve()
    checks = {"repository": root.is_dir(), "initialized": False, "configuration": False}
    config = root / ".agent-workflow/config.yaml"
    checks["initialized"] = config.is_file()
    if config.is_file():
        resolve_effective_config(root, write=False)
        checks["configuration"] = True
    healthy = all(checks.values())
    return {
        "status": "healthy" if healthy else "issues_found",
        "repository": str(root),
        "checks": checks,
        "actions": [],
    }


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
    provider_assignments: Iterable[str] = (),
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

    provider_config: dict[str, Any] | None = None
    provider_changes = list(provider_assignments)
    if provider_changes:
        provider_path = root / ".agent-workflow/providers.local.yaml"
        if provider_path.is_file():
            try:
                current = yaml.safe_load(provider_path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, yaml.YAMLError) as error:
                raise SetupError(f"invalid provider local configuration: {error}") from error
            if not isinstance(current, Mapping):
                raise SetupError("provider local configuration must contain a YAML mapping")
            provider_config = {str(key): value for key, value in current.items()}
        else:
            provider_config = {"schema_version": target_version, "providers": {}}
        for assignment in provider_changes:
            path, value = _parse_assignment(assignment)
            _set_nested(provider_config, path, value)
        validate_provider_local_config(provider_config)

    proposal = propose_migration(root, target_version=target_version)
    payload = {**proposal, "configuration": migrated}
    if provider_config is not None:
        payload["provider_configuration"] = provider_config
    if dry_run or not approve:
        return payload
    additional_writes: dict[Path, bytes] = {
        resolved.effective_config_path: _yaml_text(resolved.config.to_dict()).encode("utf-8"),
        resolved.provenance_path: _yaml_text(resolved.provenance.to_dict()).encode("utf-8"),
    }
    if provider_config is not None:
        additional_writes[root / ".agent-workflow/providers.local.yaml"] = _yaml_text(provider_config).encode("utf-8")
        ignore_path = root / ".agent-workflow/.gitignore"
        additional_writes[ignore_path] = _merged_provider_gitignore(ignore_path)
    return apply_migration(
        root,
        target_version=target_version,
        prepared_config=migrated,
        additional_writes=additional_writes,
    )


def rollback(repository: Path, *, backup: Path | None, dry_run: bool = False, **_: Any) -> dict[str, Any]:
    _dependencies()
    if backup is None:
        raise SetupError("rollback requires an explicit --backup target")
    return rollback_migration(repository, backup, dry_run=dry_run)


def export(repository: Path, *, output: Path | None, dry_run: bool = False, **_: Any) -> dict[str, Any]:
    if output is None:
        output = Path(repository).resolve() / "gin-workflow-bundle.json"
    return export_bundle(repository, output, dry_run=dry_run)


def verify(*, bundle: Path | None, **_: Any) -> dict[str, Any]:
    if bundle is None:
        raise SetupError("verify-bundle requires an explicit --bundle target")
    return verify_bundle(bundle)


COMMANDS = {
    "detect": detect,
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
}
