# -*- coding: utf-8 -*-
"""
Created on Thu Sep 11 12:16:39 2025

@author: Tobias Meissner
"""
# Backward-compatibility shim. AppContext now lives in
# app/view/shared/app_context.py and resource_path in app/logic/shared/paths.py.
# Re-exported here so existing `from utils.app_context import ...` imports keep
# working during the refactor.
from app.view.shared.app_context import AppContext  # noqa: F401
from app.logic.shared.paths import resource_path  # noqa: F401

__all__ = ['AppContext', 'resource_path']

