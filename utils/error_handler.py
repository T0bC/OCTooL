# -*- coding: utf-8 -*-
"""
Created on Thu Aug 14 10:37:54 2025

@author: Tobias Meissner
"""

# Backward-compatibility shim. The tkinter error-surfacing code now lives in
# app/view/shared/error_handler.py and log_error_to_file in
# app/logic/shared/logging_utils.py. Re-exported here so existing
# `from utils.error_handler import ...` imports keep working during the refactor.
from app.view.shared.error_handler import (  # noqa: F401
    show_error_popup,
    install_tk_exception_handler,
    handle_errors,
)
from app.logic.shared.logging_utils import log_error_to_file  # noqa: F401

__all__ = [
    'show_error_popup',
    'install_tk_exception_handler',
    'handle_errors',
    'log_error_to_file',
]


