# -*- coding: utf-8 -*-
"""Backward-compatibility shim.

This panel was moved to `app.view.rexview.image_panel`.
Import from there directly; this module re-exports for legacy imports.
"""
from app.view.rexview.image_panel import imagePanel

__all__ = ["imagePanel"]
