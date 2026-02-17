"""Load existing profiling logic from compiled modules in __pycache__."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import ModuleType

MODULE_ORDER = (
    "profile_schema",
    "stats_calculator",
    "base_profiler",
    "run_profiler",
)

BASE_DIR = Path(__file__).resolve().parent
PYCACHE_DIR = BASE_DIR / "__pycache__"
PYC_PATTERN = "{module}.cpython-*.pyc"


def _ensure_namespace_packages() -> None:
    if "services" not in sys.modules:
        services_mod = types.ModuleType("services")
        services_mod.__path__ = [str(BASE_DIR.parent)]
        sys.modules["services"] = services_mod

    if "services.profiling" not in sys.modules:
        profiling_mod = types.ModuleType("services.profiling")
        profiling_mod.__path__ = [str(BASE_DIR)]
        sys.modules["services.profiling"] = profiling_mod


def _resolve_compiled_path(module_name: str) -> Path:
    matches = sorted(PYCACHE_DIR.glob(PYC_PATTERN.format(module=module_name)))
    if not matches:
        raise FileNotFoundError(
            f"Compiled profiling module not found for '{module_name}' in {PYCACHE_DIR}"
        )
    return matches[0]


def load_compiled_profiling_modules() -> dict[str, ModuleType]:
    _ensure_namespace_packages()
    loaded: dict[str, ModuleType] = {}

    for short_name in MODULE_ORDER:
        full_name = f"services.profiling.{short_name}"
        existing = sys.modules.get(full_name)
        if existing is not None:
            loaded[short_name] = existing
            continue

        module_path = _resolve_compiled_path(short_name)
        spec = importlib.util.spec_from_file_location(full_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Failed to load module spec for {full_name}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)
        loaded[short_name] = module

    return loaded


def get_profile_schema_module() -> ModuleType:
    modules = load_compiled_profiling_modules()
    return modules["profile_schema"]


def get_run_profiler_module() -> ModuleType:
    modules = load_compiled_profiling_modules()
    return modules["run_profiler"]


def get_profile_model_class():
    schema_module = get_profile_schema_module()

    table_profile = getattr(schema_module, "TableProfile", None)
    if table_profile is not None:
        return table_profile

    dataset_profile = getattr(schema_module, "DatasetProfile", None)
    if dataset_profile is not None:
        return dataset_profile

    raise AttributeError(
        "No TableProfile or DatasetProfile model was found in services.profiling.profile_schema."
    )
