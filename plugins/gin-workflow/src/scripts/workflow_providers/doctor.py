from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from workflow_core.ext import (
    PROVIDER_DEFAULT,
    PROVIDER_DEFAULT_PROVIDERS,
    ProviderLocalConfigError,
    main_checkout,
    require_yaml,
    resolve_harness_executable,
)

from .antigravity_worker import antigravity_health
from .claude_worker import claude_health
from .codex_worker import codex_health
from .config import roles
from .local_config import LOCAL_FILE, validate_local_config
from .opencode_worker import opencode_health

HEALTH = {
    "claude": claude_health,
    "codex": codex_health,
    "antigravity": antigravity_health,
    "opencode": opencode_health,
}


def _inspect_required_providers(
    roles: Any,
    harness: str | None,
) -> tuple[set[str], bool]:
    required: set[str] = set()
    needs_main = False
    if not isinstance(roles, Mapping):
        return required, needs_main
    for role_entry in roles.values():
        if not isinstance(role_entry, Mapping):
            continue
        tiers = role_entry.get("by_tier")
        tier_lists = list(tiers.values()) if isinstance(tiers, Mapping) else []
        for items in (role_entry.get("preferred"), role_entry.get("fallback"), *tier_lists):
            candidates: list[str] = []
            if isinstance(items, (list, tuple)):
                candidates = [str(x) for x in items if x is not None]
            elif isinstance(items, str) and items:
                candidates = [items]
            for cand in candidates:
                if cand == "main_harness":
                    needs_main = True
                    if harness:
                        required.add(harness)
                else:
                    required.add(cand)
    return required, needs_main


def doctor_report(root: Path, config: Mapping[str, Any], *, probe: bool) -> dict[str, Any]:
    """Report provider mappings and, with probe, model health.

    `config` is the effective configuration; its `harness` must already be resolved
    (effective or detected), because `main_harness` roles are checked against it.
    """
    root = main_checkout(Path(root).resolve())
    yaml = require_yaml()
    detected_harness = config.get("harness")
    roles_map = roles(config)
    required_providers, needs_main_harness_check = _inspect_required_providers(roles_map, detected_harness)

    provider_details: dict[str, Any] = {}
    report: dict[str, Any] = {"providers": provider_details}

    providers_file = root / LOCAL_FILE
    if providers_file.is_file():
        try:
            p_data = yaml.safe_load(providers_file.read_text(encoding="utf-8")) or {}
            validate_local_config(p_data)
        except (OSError, UnicodeDecodeError, yaml.YAMLError, ProviderLocalConfigError) as error:
            report["providers_config"] = {"valid": False, "error": str(error)}
            p_data = {}
        providers_map = p_data.get("providers", {}) if isinstance(p_data, Mapping) else {}
        if required_providers or needs_main_harness_check:
            if needs_main_harness_check and (not detected_harness or detected_harness not in providers_map):
                provider_details[f"{detected_harness or 'main_harness'}.mapping"] = {
                    "available": False,
                    "reason": "missing_local_provider_mapping",
                }
            for p in sorted(required_providers):
                key = f"{p}.mapping"
                if key not in provider_details and p not in providers_map:
                    provider_details[key] = {
                        "available": False,
                        "reason": "missing_local_provider_mapping",
                    }
        if providers_map:
            if probe:
                for provider, pconfig in providers_map.items():
                    if not isinstance(pconfig, Mapping):
                        continue
                    configured_exe = str(pconfig.get("executable", ""))
                    resolved_exe = resolve_harness_executable(configured_exe, provider=provider)
                    if not resolved_exe:
                        provider_details[f"{provider}.executable"] = {
                            "available": False,
                            "reason": "executable_not_found",
                        }
                        continue
                    if provider not in HEALTH:
                        continue
                    probe_dir = root / ".agent-workflow/runtime/health-probe" / provider
                    probe_dir.mkdir(parents=True, exist_ok=True)
                    models = pconfig.get("models", {})
                    if isinstance(models, Mapping):
                        for tier, target in models.items():
                            model = target.get("model") if isinstance(target, Mapping) else str(target)
                            effort = target.get("effort") if isinstance(target, Mapping) else None
                            try:
                                builder = HEALTH[provider]
                                if provider in PROVIDER_DEFAULT_PROVIDERS and model == PROVIDER_DEFAULT:
                                    health = builder(resolved_exe)
                                else:
                                    kwargs: dict[str, Any] = {"model": model, "workspace": probe_dir}
                                    if provider == "codex":
                                        kwargs["effort"] = effort
                                    health = builder(resolved_exe, **kwargs)
                            except Exception as error:
                                health_avail = False
                                health_reason = str(error)
                            else:
                                health_avail = getattr(health, "available", False)
                                health_reason = getattr(health, "reason", "")
                            provider_details[f"{provider}.{tier}"] = {
                                "available": bool(health_avail),
                                "reason": health_reason,
                            }
            else:
                for provider, pconfig in providers_map.items():
                    if not isinstance(pconfig, Mapping):
                        continue
                    configured_exe = str(pconfig.get("executable", ""))
                    resolved_exe = resolve_harness_executable(configured_exe, provider=provider)
                    if not resolved_exe:
                        provider_details[f"{provider}.executable"] = {
                            "available": False,
                            "reason": "executable_not_found",
                        }
                    else:
                        provider_details[f"{provider}.executable"] = {
                            "available": True,
                            "reason": "executable_found",
                        }
    else:
        if required_providers or needs_main_harness_check:
            if needs_main_harness_check:
                provider_details[f"{detected_harness or 'main_harness'}.mapping"] = {
                    "available": False,
                    "reason": "missing_local_provider_mapping",
                }
            for p in sorted(required_providers):
                key = f"{p}.mapping"
                if key not in provider_details:
                    provider_details[key] = {
                        "available": False,
                        "reason": "missing_local_provider_mapping",
                    }

    return report
