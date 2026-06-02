"""
OCT Processing Functions

Pure functions for OCT file processing - no GUI dependencies.
This module is the canonical location for OCT processing logic.

For backward compatibility, these functions are re-exported from utils/oct_functions.py.
"""
# Re-export all functions from the original location during transition
# This allows gradual migration while maintaining backward compatibility
from utils.oct_functions import (
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
