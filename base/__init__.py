# -*- coding: utf-8 -*-
"""
Base Module for OCTooL Application

This module provides base classes for common functionality across the application.

Created on Thu Oct 02 09:43:00 2025
@author: Tobias Meissner
"""

# Backward-compatibility shim. BaseCanvasPanel now lives in
# app/view/shared/base_canvas_panel.py. Re-exported here so existing
# `from base import BaseCanvasPanel` imports keep working during the refactor.
from app.view.shared.base_canvas_panel import BaseCanvasPanel

__all__ = ['BaseCanvasPanel']
