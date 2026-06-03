# -*- coding: utf-8 -*-
"""Backward-compatibility shim.

This panel was moved to `app.view.rexview.execution_panel`.
Import from there directly; this module re-exports for legacy imports.
"""
from app.view.rexview.execution_panel import executionPanel

__all__ = ["executionPanel"]
