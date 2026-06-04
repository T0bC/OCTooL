# -*- coding: utf-8 -*-
"""
Backward-compatibility shim. ``HelpDialog`` now lives in
``app.view.shared.help_dialog``. Re-exported here so existing
``from utils.help_dialog import HelpDialog`` imports keep working during the refactor.
"""
from app.view.shared.help_dialog import HelpDialog  # noqa: F401

__all__ = ['HelpDialog']
