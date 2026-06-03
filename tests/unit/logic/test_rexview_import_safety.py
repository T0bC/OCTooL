#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import-safety tests enforcing the logic/view boundary for RexView.

The ``app/logic/rexview`` package must never import tkinter, so it can be
imported and unit-tested headlessly (no display).
"""

import ast
import importlib
import sys
from pathlib import Path

import pytest

LOGIC_DIR = Path(__file__).resolve().parents[3] / "app" / "logic" / "rexview"


def _logic_modules():
    return sorted(p for p in LOGIC_DIR.glob("*.py") if p.name != "__init__.py")


@pytest.mark.unit
def test_logic_package_imports_without_tkinter():
    """Importing app.logic.rexview must not pull tkinter into sys.modules."""
    for mod in list(sys.modules):
        if mod == "tkinter" or mod.startswith("tkinter."):
            del sys.modules[mod]

    importlib.import_module("app.logic.rexview")

    assert "tkinter" not in sys.modules, (
        "app.logic.rexview imported tkinter; logic layer must stay GUI-free."
    )


@pytest.mark.unit
@pytest.mark.parametrize("module_path", _logic_modules(), ids=lambda p: p.name)
def test_logic_module_has_no_tkinter_import(module_path):
    """No source file under app/logic/rexview may import tkinter."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
            assert not any(n == "tkinter" or n.startswith("tkinter.") for n in names), (
                f"{module_path.name} imports tkinter"
            )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not (mod == "tkinter" or mod.startswith("tkinter.")), (
                f"{module_path.name} imports from tkinter"
            )
