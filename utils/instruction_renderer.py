# -*- coding: utf-8 -*-
"""
Backward-compatibility shim. ``InstructionRenderer`` now lives in
``app.view.shared.instruction_renderer``. Re-exported here so existing
``from utils.instruction_renderer import InstructionRenderer`` imports keep
working during the refactor.
"""
from app.view.shared.instruction_renderer import InstructionRenderer  # noqa: F401

__all__ = ['InstructionRenderer']
