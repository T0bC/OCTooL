# -*- coding: utf-8 -*-
"""Backward-compatibility shim.

This panel was moved to `app.view.rexview.pick_files_panel`.
Import from there directly; this module re-exports for legacy imports.
"""
from app.view.rexview.pick_files_panel import pickFilesPanel

__all__ = ["pickFilesPanel"]
