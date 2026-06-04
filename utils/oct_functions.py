# -*- coding: utf-8 -*-
"""
Backward-compatibility shim.

The real OCT processing functions now live in ``app.logic.shared.oct_functions``.
This module re-exports them so existing ``from utils import oct_functions`` and
``from utils.oct_functions import ...`` imports keep working during the refactor.
"""
from app.logic.shared.oct_functions import (
    insertScale,
    unzipOCTData,
    getXMLvalue,
    readXMLContent,
    getXMLAttributes,
    createVideoImageFromRaw,
    createImageFromRaw,
    octToGV,
    octToGV_legacy,
    smooth,
)

__all__ = [
    'insertScale',
    'unzipOCTData',
    'getXMLvalue',
    'readXMLContent',
    'getXMLAttributes',
    'createVideoImageFromRaw',
    'createImageFromRaw',
    'octToGV',
    'octToGV_legacy',
    'smooth',
]
