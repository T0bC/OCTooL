# -*- coding: utf-8 -*-
"""
Backward-compatibility shim. ``StatusBar`` now lives in
``app.view.shared.status_bar``. Re-exported here so existing
``from utils.status_bar import StatusBar`` imports keep working during the refactor.
"""
from app.view.shared.status_bar import StatusBar  # noqa: F401

__all__ = ['StatusBar']
