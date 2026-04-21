"""Catalog-driven registry.

Single authority: the packaged catalog.yaml. For each entry we import the
module, read SPEC, validate name match, and finalize schemas. Stale user
overrides (pointing at removed tools) emit a warning and are ignored.
"""

from __future__ import annotations

import importlib
import importlib.resources as resources
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from .config import UserConfig
from .spec import ToolSpec, finalize_spec


@dataclass(frozen=True)
class ResolvedTool:
    spec: ToolSpec
    enabled: bool
    catalog_entry: dict


def _read_catalog_text(catalog_path: Optional[Path] = None) -> str:
    if catalog_path is not None:
        return Path(catalog_path).read_text(encoding="utf-8")
    # Packaged data file; resources.files is 3.9+ and handles both installed & editable layouts.
    return resources.files("bwkit").joinpath("catalog.yaml").read_text(encoding="utf-8")


def load_registry(
    *,
    catalog_path: Optional[Path] = None,
    config: Optional[UserConfig] = None,
) -> dict[str, ResolvedTool]:
    raw = yaml.safe_load(_read_catalog_text(catalog_path)) or {}
    entries = raw.get("tools") or []
    cfg_overrides = config.overrides if config else {}

    resolved: dict[str, ResolvedTool] = {}
    seen_names: set[str] = set()

    for entry in entries:
        name = entry["name"]
        module_name = entry["module"]
        try:
            mod = importlib.import_module(module_name)
        except Exception as e:
            warnings.warn(
                f"bwkit: skipping tool '{name}': failed to import {module_name}: {e}",
                stacklevel=2,
            )
            continue

        spec = getattr(mod, "SPEC", None)
        if spec is None:
            factory = getattr(mod, "get_spec", None)
            if factory is None:
                warnings.warn(
                    f"bwkit: skipping tool '{name}': module {module_name} exports neither SPEC nor get_spec()",
                    stacklevel=2,
                )
                continue
            spec = factory()

        if spec.name != name:
            raise RuntimeError(
                f"catalog/spec name drift: catalog entry '{name}' imports {module_name} "
                f"which exports SPEC.name={spec.name!r}"
            )

        spec = finalize_spec(spec)
        enabled = cfg_overrides.get(name, bool(entry.get("default_enabled", True)))
        resolved[name] = ResolvedTool(spec=spec, enabled=enabled, catalog_entry=entry)
        seen_names.add(name)

    # Stale overrides → warn, don't raise.
    for stale in sorted(set(cfg_overrides) - seen_names):
        warnings.warn(
            f"bwkit: config override for unknown tool '{stale}' is ignored "
            f"(removed from catalog)",
            stacklevel=2,
        )

    return resolved
