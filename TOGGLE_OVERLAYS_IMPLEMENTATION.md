# Toggle Overlays Implementation Summary

## Overview
Implemented a unified overlay toggle system that works consistently across both the analyze and carlquant panels, with special handling for the annotation flash behavior.

## Changes Made

### 1. Base Class (`base/base_canvas_panel.py`)
- **Added**: `overlays_visible` state flag (default: `True`)
- **Added**: `toggle_overlays()` method that:
  - Toggles the visibility flag
  - Clears all overlay-related canvas items (annotations, regions, AIR)
  - Triggers a redraw via `render_zoomed_image()`
  - Updates status bar with visibility state

### 2. Analyze Panel (`analyze_frames/annotate_images_panel.py`)
- **Removed**: Local `annotations_visible` attribute (now uses `overlays_visible` from base)
- **Updated**: Bindings to use `<h>` (just the 'h' key, no modifiers)
- **Added**: Binding on both `window` and `canvas` for better event capture
- **Updated**: `draw_specialized_overlays()` to check `overlays_visible` before drawing
- **Updated**: `draw_annotation()` to always show current annotation being edited
- **Fixed**: `flash_annotation()` workflow to avoid redundant drawing
- **Fixed**: `_hide_annotations_if_not_toggled()` to use `render_zoomed_image()` for proper cleanup
- **Removed**: Old `toggle_annotations()` method

### 3. Carl Quant Panel (`carlquant_frames/image_viewer_panel.py`)
- **Removed**: Local `annotations_visible` attribute
- **Updated**: Bindings to use `<h>` (just the 'h' key, no modifiers)
- **Added**: Binding on both `window` and `canvas` for better event capture
- **Updated**: `draw_specialized_overlays()` to check `overlays_visible` before drawing
- **Removed**: Broken `toggle_annotations()` method that was causing the AttributeError

## Key Features

### Unified Toggle Behavior
- **Keyboard Shortcut**: Press `h` key to toggle overlay visibility in both panels
- **When Visible**: All overlays (annotations, regions, AIR) are drawn
- **When Hidden**: All overlays are cleared from canvas
- **Status Feedback**: Status bar shows "Overlays visible" or "Overlays hidden"

### Annotation Flash Behavior (Analyze Panel Only)
After committing an annotation:
1. **Flash Phase** (800ms): Overlays become visible to show the user what was just committed
2. **Auto-Hide Phase**: After 800ms, overlays automatically hide to give a clear view
3. **User Override**: If the user manually toggles visibility during the flash, auto-hide is cancelled

This provides visual feedback while maintaining a clean workspace.

## Why It Works Now

### Problem 1: Key Binding Format
- **Before**: Used `<KeyPress-h>` which is verbose and less reliable
- **After**: Uses `<h>` which is the standard Tkinter binding for a simple key press
- **Benefit**: Simpler, more reliable key binding

### Problem 2: Single Binding Point
- **Before**: Only bound to `self.window`
- **After**: Bound to both `self.window` and `self.canvas`
- **Benefit**: More reliable event capture regardless of focus state

### Problem 3: Inconsistent State Management
- **Before**: Each panel had its own `annotations_visible` flag
- **After**: Both panels use `overlays_visible` from base class
- **Benefit**: Consistent behavior and easier maintenance

### Problem 4: Flash Behavior Cleanup
- **Before**: Manually deleted canvas items, could leave orphaned state
- **After**: Uses `render_zoomed_image()` for complete redraw
- **Benefit**: Ensures clean state after auto-hide

## Testing Recommendations

1. **Test 'h' key in Analyze Panel**: 
   - Load images
   - Create annotations
   - Press 'h' to toggle visibility

2. **Test 'h' key in CarlQuant Panel**:
   - Load specimen
   - Define regions and AIR
   - Press 'h' to toggle visibility
   - Verify regions and AIR show/hide

### How It Works Now

1. **Manual Toggle**: Press `h` to show/hide all overlays
2. **Auto-Flash**: When you commit an annotation:
   - Overlays become visible (flash)
   - After 800ms, they auto-hide for a clear view
   - If you press `h` during the flash, auto-hide is cancelled

4. **Test Current Annotation**:
   - Start creating a new annotation (don't commit)
   - Press 'h'
   - Verify the current (uncommitted) annotation remains visible even when overlays are hidden
{{ ... }}

## Architecture Benefits

- **DRY Principle**: Single implementation in base class
- **Extensibility**: New panel types automatically get toggle functionality
- **Maintainability**: Changes to toggle behavior only need to be made in one place
- **Consistency**: Same keyboard shortcut and behavior across all panels
