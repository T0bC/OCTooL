# -*- coding: utf-8 -*-
"""Backward-compatibility shim.

This panel was moved to `app.view.rexview.global_settings_panel`.
Import from there directly; this module re-exports for legacy imports.
"""
from app.view.rexview.global_settings_panel import globalSettingsPanel

__all__ = ["globalSettingsPanel"]
