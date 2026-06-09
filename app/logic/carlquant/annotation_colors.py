# -*- coding: utf-8 -*-
"""
Centralized Annotation Color Configuration.

Defines all colours used for annotations throughout the application. Import these constants to ensure consistent colours in both the GUI (Tkinter canvas) and exported images (PIL ImageDraw). All colours are optimised for visibility on grayscale images with a dark UI theme.

This file is part of OCTooL.
OCTooL is an open source software for export, analysis and quantification of
Optical Coherence Tomography (OCT) images.
Copyright (C) 2019-2026 Tobias Meissner

OCTooL is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see http://www.gnu.org/licenses/.

****
Author: Tobias Meissner
****
"""



# ============================================================================
# ANNOTATION COLOR SCHEME - Centralized color definitions
# ============================================================================

# Surface Detection Colors
# High contrast colors that work on both bright (white) and dark (gray) backgrounds
INTERPOLATED_SURFACE_COLOR = '#e600e6'       # Bright magenta - visible on light and dark areas
ACTUAL_SURFACE_COLOR = '#00b0e6'             # Bright cyan/blue - distinct from red lesion depth, visible on gray

# Lesion Depth Detection Colors
LESION_DEPTH_PRIMARY_COLOR = '#f71134'       # Bright red - main lesion depth result (thick line)

# Component Detection Method Colors (shown when enabled in A-Scan viewer)
KNEE_POINT_COLOR = 'yellow'                  # Knee point detection method
INFLECTION_POINT_COLOR = 'cyan'              # Sigmoid inflection point method
SHOULDER_POINT_COLOR = 'magenta'             # Sigmoid shoulder point method

# Extraction Region Colors
EXTRACTION_REGION_COLOR = '#00FF88'          # Bright mint green for sound region boundaries
EXTRACTION_REGION_LESION_COLOR = '#f71134'   # Color for lesion (non-sound) region boundaries
EXTRACTION_REGION_TEXT_COLOR = '#00FF88'     # Text color for region numbers

# Region Boundary Colors (vertical lines for region definition)
# Named constants for clarity - specimen boundaries vs lesion boundaries
SPECIMEN_BOUNDARY_COLOR = '#4CAF50'          # Bootstrap success green - specimen start/end
LESION_BOUNDARY_COLOR = '#FFD700'            # Gold/yellow - lesion start/end (distinct from red)

# AIR Reference Color
AIR_REGION_COLOR = '#37bfe9'                 # Bright cyan - AIR reference area

# Results Panel Row Highlighting Colors
ROW_HIGHLIGHT_NAVIGATION_COLOR = '#2d5016'   # Dark green - normal navigation highlighting
ROW_HIGHLIGHT_ASCAN_COLOR = '#6a4c93'        # Purple/lavender - A-Scan viewer active highlighting

# ============================================================================
# Color Conversion Utilities (if needed for different rendering contexts)
# ============================================================================

def hex_to_rgb(hex_color):
    """
    Convert hex color string to RGB tuple.
    
    Args:
        hex_color: Color in hex format (e.g., '#FF0000' or 'red')
    
    Returns:
        tuple: (R, G, B) values (0-255)
    """
    # Handle named colors by returning them as-is (PIL supports them)
    if not hex_color.startswith('#'):
        # For named colors like 'red', 'cyan', etc., PIL can handle them directly
        # But if you need RGB values, you'd need a color name lookup table
        return hex_color
    
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """
    Convert RGB tuple to hex color string.
    
    Args:
        r, g, b: Red, green, blue values (0-255)
    
    Returns:
        str: Hex color string (e.g., '#FF0000')
    """
    return f'#{r:02x}{g:02x}{b:02x}'
