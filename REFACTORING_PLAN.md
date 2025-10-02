# Canvas Panel Refactoring Plan

## Overview
This document outlines the refactoring strategy to centralize common canvas functionality across the OCTexVIEW application.

## Current State Analysis

### Common Functionality (All 3 Panels)
- ✅ Zoom (Ctrl+MouseWheel): 1.0 to 10.0x
- ✅ Pan (Ctrl+Drag): Move image when zoomed
- ✅ Navigation: Arrow keys, mouse wheel, slider
- ✅ Coordinate conversion: canvas ↔ image
- ✅ Image rendering with aspect ratio preservation
- ✅ Canvas resize handling
- ✅ Instruction text rendering via InstructionRenderer

### Specialized Functionality

#### analyze_frames/annotate_images_panel.py
- Point-based annotations (click to add points)
- Drag existing points to reposition
- Hover effects on points
- Right-click to delete points
- Spline curve fitting (F key)
- Toggle annotations visibility (H key)
- Overlay annotations for non-continuous data
- Save/load annotations as JSON

#### carlquant_frames/image_viewer_panel.py
- Region boundary selection (two-click vertical lines)
- AIR (Area of Interest Rectangle) drag selection
- Automatic mode detection (click vs drag)
- Region/AIR propagation logic
- Visual overlays for regions and AIR

#### export_frames/image_panel.py
- Different image loading (OCT file processing)
- No zoom/pan (simpler viewer)
- Scale bar insertion
- Refractive index correction
- Different navigation model

## Refactoring Strategy

### Phase 1: Base Class Creation ✅
**Status: COMPLETED & REVIEWED**

Created `base/base_canvas_panel.py` with:
- Common zoom/pan/navigation logic (Ctrl+MouseWheel, Ctrl+Drag)
- Coordinate conversion utilities (canvas ↔ image)
- Image rendering pipeline with aspect ratio preservation
- Hook methods for specialization:
  - `setup_specialized_bindings()` - called at end of __init__
  - `draw_specialized_overlays()` - called after image rendering
  - `get_instruction_key()` - returns instruction key for renderer
  - `get_image_list()` - returns list of images
  - `get_image_path(index)` - returns path to specific image
- Comprehensive documentation with usage examples
- Error handling for missing status_bar

### Phase 2: Refactor analyze_frames (CURRENT)
**Goal**: Make `annotate_images_panel` inherit from `BaseCanvasPanel`

**Steps**:
1. Import `BaseCanvasPanel`
2. Change class declaration to inherit from base
3. Call `super().__init__()` with proper parameters
4. Move annotation-specific state to after super() call
5. Implement hook methods:
   - `setup_specialized_bindings()` - annotation mouse/keyboard bindings
   - `get_instruction_key()` - return 'analyze_getting_started'
   - `get_image_list()` - return context.image_list
   - `draw_specialized_overlays()` - call draw_annotation() and draw_overlay_annotations()
6. Remove duplicate methods that now exist in base class:
   - `canvas_to_image_coords()`
   - `image_to_canvas_coords()`
   - `on_mouse_wheel_zoom()`
   - `start_pan()`, `do_pan()`, `end_pan()`
   - `on_arrow_left()`, `on_arrow_right()`
   - `on_mouse_wheel()`, `on_mouse_wheel_linux()`
   - `setup_scale_callback()`, `on_scale_change()`
   - `onResize()`
   - `render_zoomed_image()`
   - `display_image()` (modify to call super and add annotation drawing)
   - `instructionText()` (can use base implementation)

**Keep** (annotation-specific):
- All annotation drawing/editing methods
- Point dragging logic
- Hover effects
- Curve fitting
- Save/load annotations

### Phase 3: Refactor carlquant_frames
**Goal**: Make `image_viewer_panel` inherit from `BaseCanvasPanel`

Similar approach to Phase 2, but keep:
- Region selection logic
- AIR selection logic
- Automatic mode detection
- Propagation logic

### Phase 4: Testing
1. Test analyze_frames: Load images, annotate, zoom, pan, navigate
2. Test carlquant_frames: Load specimens, define regions, define AIR, zoom, pan
3. Test export_frames: Verify no regressions (not refactored yet)

### Phase 5: export_frames (Optional)
Decision: Keep export_frames separate for now since it has a fundamentally different
image loading mechanism and doesn't use zoom/pan. Can revisit later if needed.

## Benefits

1. **Code Reduction**: ~400-500 lines of duplicate code eliminated
2. **Maintainability**: Bug fixes in zoom/pan apply to all panels
3. **Consistency**: All panels behave identically for common operations
4. **Extensibility**: New canvas panels can easily inherit common functionality
5. **Testing**: Common functionality can be tested once in base class

## Risks & Mitigation

**Risk**: Breaking existing functionality during refactoring
**Mitigation**: 
- Careful step-by-step refactoring
- Test after each major change
- Keep git history clean for easy rollback
- Use error handlers to catch issues early

**Risk**: Performance degradation from extra method calls
**Mitigation**:
- Python method calls are cheap
- No noticeable performance impact expected
- Can profile if needed

## Implementation Notes

### Hook Method Pattern
The base class defines "hook methods" that subclasses override:
```python
def setup_specialized_bindings(self):
    """Override to add custom mouse/keyboard bindings"""
    pass

def draw_specialized_overlays(self):
    """Override to draw annotations, regions, etc."""
    pass
```

This allows the base class to control the overall flow while letting subclasses
customize specific behaviors.

### Coordinate Conversion
The base class handles zoom/pan calculations. Subclasses just call:
```python
img_x, img_y = self.canvas_to_image_coords(canvas_x, canvas_y)
canvas_x, canvas_y = self.image_to_canvas_coords(img_x, img_y)
```

### Image Source Abstraction
Base class calls `get_image_list()` and `get_image_path(index)` hooks,
allowing each subclass to define its own image source.

## Next Steps

1. ✅ Create base/base_canvas_panel.py
2. ✅ Create base/__init__.py
3. ⏳ Refactor analyze_frames/annotate_images_panel.py
4. ⏳ Test analyze_frames functionality
5. ⏳ Refactor carlquant_frames/image_viewer_panel.py
6. ⏳ Test carlquant_frames functionality
7. ⏳ Update documentation
8. ⏳ Create memory for future reference

## Status: PHASE 1 COMPLETE - READY FOR PHASE 2
Last updated: 2025-10-02 09:50

## Revision History
- 2025-10-02 09:43: Initial plan created, Phase 1 completed
- 2025-10-02 09:50: Base class reviewed and revised for alignment with plan
  - Removed unused hook methods (on_specialized_canvas_click, on_specialized_canvas_drag)
  - Added better error handling for missing status_bar
  - Enhanced documentation with usage examples
  - Added important note about initialization order for subclasses
