#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import-smoke tests for the tkinter view layer.

The ``app/view/**`` modules are tkinter-bound and are not unit-tested for
behaviour. These smoke tests simply import every view module to catch the most
common refactor regression: a broken import path. No widgets are instantiated
and no mainloop is started.

If the environment is headless (no display), tkinter import-time failures are
skipped rather than failed, since the goal here is import-path safety, not GUI
rendering.
"""
import importlib
from pathlib import Path

import pytest

VIEW_DIR = Path(__file__).resolve().parents[3] / "app" / "view"


def _view_modules():
    """Return dotted module names for every .py file under app/view/**."""
    modules = []
    for path in sorted(VIEW_DIR.rglob("*.py")):
        if path.name == "__init__.py":
            # Importing the package covers its __init__.
            rel = path.parent.relative_to(VIEW_DIR.parent.parent)
        else:
            rel = path.with_suffix("").relative_to(VIEW_DIR.parent.parent)
        modules.append(".".join(rel.parts))
    # De-duplicate while preserving order.
    seen = set()
    unique = []
    for m in modules:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


@pytest.mark.unit
@pytest.mark.parametrize("module_name", _view_modules())
def test_view_module_imports(module_name):
    """Every app/view module must import without raising an import error."""
    try:
        importlib.import_module(module_name)
    except ImportError as exc:
        pytest.fail(f"Failed to import {module_name}: {exc}")
    except Exception as exc:  # noqa: BLE001
        # Headless environments may raise TclError (or similar) at import time
        # if a module touches a display. That is not an import-path regression,
        # so skip rather than fail.
        if exc.__class__.__name__ in {"TclError"}:
            pytest.skip(f"{module_name} requires a display: {exc}")
        raise
