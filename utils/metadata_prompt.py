# -*- coding: utf-8 -*-
"""
Backward-compatibility shim. The metadata prompt helpers now live in
``app.view.shared.metadata_prompt``. Re-exported here so existing
``from utils.metadata_prompt import ...`` imports keep working during the refactor.
"""
from app.view.shared.metadata_prompt import (  # noqa: F401
    prompt_for_metadata,
    get_metadata_from_context,
    ensure_metadata_set,
)

__all__ = [
    'prompt_for_metadata',
    'get_metadata_from_context',
    'ensure_metadata_set',
]
