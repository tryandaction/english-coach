from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Callable

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


def package_dir(package: str) -> Path:
    spec = importlib.util.find_spec(package)
    if spec is None:
        raise RuntimeError(f"Package not found: {package}")
    if spec.submodule_search_locations:
        return Path(next(iter(spec.submodule_search_locations))).resolve()
    if spec.origin:
        return Path(spec.origin).resolve().parent
    raise RuntimeError(f"Cannot resolve package directory: {package}")


def collect_package_datas(package: str) -> list[tuple[str, str]]:
    return collect_data_files(package)


def collect_package_binaries(package: str) -> list[tuple[str, str]]:
    return collect_dynamic_libs(package)


def collect_package_hiddenimports(
    package: str,
    *,
    filter_fn: Callable[[str], bool] | None = None,
) -> list[str]:
    if filter_fn is None:
        filter_fn = lambda _name: True
    return collect_submodules(package, filter=filter_fn, on_error="ignore")
