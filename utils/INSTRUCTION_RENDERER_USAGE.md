# InstructionRenderer Usage Guide

## Overview

The `InstructionRenderer` class provides a centralized, consistent way to display instruction text across all panels in OCTexVIEW. It supports multi-column layouts, color-coded sections, and visual symbols.

## Quick Start

### 1. Import the Renderer

```python
from utils.instruction_renderer import InstructionRenderer
```

### 2. Basic Usage Pattern

```python
def show_instructions(self):
    """Display instructions on canvas when no data is loaded."""
    canvas_width = self.canvas.winfo_width()
    canvas_height = self.canvas.winfo_height()
    
    # Optional: Load logo
    logo_image = InstructionRenderer.load_logo("icons/WBM_UL_RGB_digital_Path.png")
    if logo_image:
        self.logo_ref = logo_image  # Keep reference to prevent garbage collection
    
    # Render instructions
    InstructionRenderer.render_[panel_type]_instructions(
        self.canvas, canvas_width, canvas_height, logo_image
    )
```

## Available Instruction Templates

### 1. Image Viewer Panel
**Method:** `render_image_viewer_instructions()`

**Features:**
- Two-column layout (Region Boundaries | AIR Regions)
- Navigation controls at bottom
- Color-coded headers (Yellow for regions, Cyan for AIR)

**Usage:**
```python
InstructionRenderer.render_image_viewer_instructions(
    canvas, canvas_width, canvas_height, logo_image
)
```

### 2. Load/Folder Selection Panel
**Method:** `render_load_panel_instructions()`

**Features:**
- Centered workflow layout
- Step-by-step numbered instructions
- Purple color theme for workflow

**Usage:**
```python
InstructionRenderer.render_load_panel_instructions(
    canvas, canvas_width, canvas_height, logo_image
)
```

### 3. Settings Panel
**Method:** `render_settings_panel_instructions()`

**Features:**
- Organized by setting categories
- Orange color theme
- Configuration guidance

**Usage:**
```python
InstructionRenderer.render_settings_panel_instructions(
    canvas, canvas_width, canvas_height, logo_image
)
```

## Integration Example: Load Images Panel

Here's how to add instructions to the `load_images_panel.py`:

```python
# In load_images_panel.py

from utils.instruction_renderer import InstructionRenderer

class loadImagePanel:
    def __init__(self, context):
        # ... existing initialization code ...
        
        # Add a canvas for instructions (if not already present)
        self.instruction_canvas = tk.Canvas(
            self.frame, 
            width=400, 
            height=300, 
            highlightthickness=0, 
            bg='#505050'
        )
        self.instruction_canvas.grid(row=2, column=0, sticky="nsew", pady=10)
        
        # Show instructions initially
        self.show_instructions()
    
    def show_instructions(self):
        """Display workflow instructions."""
        canvas_width = self.instruction_canvas.winfo_width()
        canvas_height = self.instruction_canvas.winfo_height()
        
        logo_image = InstructionRenderer.load_logo("icons/WBM_UL_RGB_digital_Path.png")
        if logo_image:
            self.logo_ref = logo_image
        
        InstructionRenderer.render_load_panel_instructions(
            self.instruction_canvas, canvas_width, canvas_height, logo_image
        )
    
    def hide_instructions(self):
        """Hide instructions when data is loaded."""
        self.instruction_canvas.delete("all")
```

## Creating Custom Instructions

If you need custom instructions for a specific panel, you can use the helper method:

```python
# Define your instruction content
instructions = [
    ("🔧", "Main instruction text"),
    ("", "  • Sub-point 1"),
    ("", "  • Sub-point 2"),
    ("", ""),  # Empty line for spacing
    ("📝", "Another main instruction"),
]

# Render at specific position
x = 20
y = 100
line_spacing = 22

final_y = InstructionRenderer._render_instruction_list(
    canvas, x, y, instructions, line_spacing
)
```

## Color Scheme

The renderer uses a consistent color scheme:

| Element | Color | Hex Code | Usage |
|---------|-------|----------|-------|
| Region Header | Gold | `#FFD700` | Region boundaries |
| AIR Header | Cyan | `#00E5FF` | AIR regions |
| Navigation Header | Green | `#A5D6A7` | Navigation controls |
| Workflow Header | Purple | `#CE93D8` | Workflow steps |
| Settings Header | Orange | `#FFAB91` | Settings/config |
| Symbols | Light Blue | `#90CAF9` | Icons/emojis |
| Primary Text | Light Gray | `#D0D0D0` | Main instructions |
| Secondary Text | Gray | `#B0B0B0` | Sub-text |
| Tertiary Text | Dark Gray | `#909090` | Hints/notes |

## Font Configuration

| Font Type | Specification | Usage |
|-----------|--------------|-------|
| Header | `Sans 12 bold` | Section headers |
| Text | `Sans 10` | Main instruction text |
| Symbol | `Sans 14` | Emojis/icons |
| Small | `Sans 9` | Fine print/hints |

## Best Practices

1. **Keep References:** Always store logo_image in an instance variable to prevent garbage collection
   ```python
   if logo_image:
       self.logo_ref = logo_image
   ```

2. **Clear Before Rendering:** The renderer automatically clears the canvas, but you can also call:
   ```python
   canvas.delete("all")
   ```

3. **Responsive Layout:** Get canvas dimensions dynamically:
   ```python
   canvas_width = self.canvas.winfo_width()
   canvas_height = self.canvas.winfo_height()
   ```

4. **Hide on Data Load:** Clear instructions when actual content is displayed:
   ```python
   def display_data(self):
       self.canvas.delete("all")
       # ... render actual content ...
   ```

## Adding New Instruction Templates

To add a new instruction template:

1. Add a new static method to `InstructionRenderer` class:
   ```python
   @staticmethod
   def render_your_panel_instructions(canvas, canvas_width, canvas_height, logo_image=None):
       canvas.delete("all")
       
       # Your custom layout here
       # Use InstructionRenderer.COLORS and InstructionRenderer.FONTS
       # Use _render_instruction_list() helper for consistent styling
   ```

2. Define your instruction content with symbols and text
3. Use the helper method `_render_instruction_list()` for consistent rendering
4. Document the new method in this guide

## Troubleshooting

**Issue:** Instructions not showing
- Check canvas dimensions: `canvas.winfo_width()` and `canvas.winfo_height()`
- Ensure canvas is properly gridded/packed in the layout
- Call `canvas.update_idletasks()` before getting dimensions

**Issue:** Logo not displaying
- Verify logo path is correct
- Check that logo file exists
- Ensure logo reference is stored in instance variable

**Issue:** Text overlapping
- Adjust `line_spacing` parameter
- Check canvas height is sufficient
- Consider multi-column layout for more content

## Future Enhancements

Potential improvements to consider:

- **Scrollable Instructions:** Add scrollbar for very long instruction lists
- **Animated Transitions:** Fade in/out effects for instructions
- **Interactive Elements:** Clickable links or expandable sections
- **Localization:** Support for multiple languages
- **Theme Support:** Light/dark mode variations
