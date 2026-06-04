# -*- coding: utf-8 -*-
"""
Backward-compatibility shim. ``Tooltip`` now lives in
``app.view.shared.tool_tip``. Re-exported here so existing
``from utils.tool_tip import Tooltip`` imports keep working during the refactor.
"""
from app.view.shared.tool_tip import Tooltip  # noqa: F401

__all__ = ['Tooltip']
