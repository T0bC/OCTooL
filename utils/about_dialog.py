# -*- coding: utf-8 -*-
"""
Backward-compatibility shim. ``AboutDialog`` now lives in
``app.view.shared.about_dialog``. Re-exported here so existing
``from utils.about_dialog import AboutDialog`` imports keep working during the refactor.
"""
from app.view.shared.about_dialog import AboutDialog  # noqa: F401

__all__ = ['AboutDialog']
