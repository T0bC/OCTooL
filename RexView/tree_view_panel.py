# -*- coding: utf-8 -*-
"""Backward-compatibility shim.

This panel was moved to `app.view.rexview.tree_view_panel`.
Import from there directly; this module re-exports for legacy imports.
"""
from app.view.rexview.tree_view_panel import treeViewPanel

__all__ = ["treeViewPanel"]
