# RexView Module Separation Plan

Gradually separate RexView into pure logic (`app/logic/rexview/`) and thin UI wrappers (`app/view/rexview/`), enabling comprehensive pytest-based testing without tkinter dependencies.

---

## Overview

This plan covers the complete RexView module refactoring as part of the broader TDD refactor (see `tdd-refactor-plan.md`).

**Goal**: Transform 7 tightly-coupled panel files into:
- `app/logic/rexview/` - Pure business logic, fully testable
- `app/view/rexview/` - Thin UI wrappers that delegate to logic layer

---

## Current State

### Completed (Phase 2.1-2.2)

- **ExportService** (`app/logic/rexview/export_service.py`): Complete with `prepare_export()`, `load_image_stack()`, `process_slice()`, `run_export()`, etc.
- **Models** (`app/logic/rexview/models.py`): `ExportConfig`, `SliceExportParams`, `ExportProgress`
- **execution_panel.py**: Wired to use ExportService (Steps 1-5 complete)
- **Tests**: 65+ unit tests passing, 13 integration tests

### Remaining RexView Panels

| Panel | File | Logic to Extract |
|-------|------|------------------|
| Image Panel | `image_panel.py` | OCT preview rendering, slice navigation |
| Global Settings | `global_settings_panel.py` | Settings validation, defaults |
| Custom Settings | `custom_settings_panel.py` | Dispersion, custom params |
| Tree View | `tree_view_panel.py` | Queue management, item validation |
| Pick Files | `pick_files_panel.py` | File discovery, metadata extraction |
| Instructions | `instruction_panel.py` | Static (no logic extraction needed) |

---

## Phase A: ExportService Wiring (COMPLETED)

Wired `execution_panel.py` to delegate to `ExportService`.

- [x] Wire `prepare_export()` - slice calculation, data type
- [x] Wire `load_image_stack()` - image loading
- [x] Wire `process_slice()` - slice processing
- [x] Wire `export_video_image()` - video export
- [x] Add integration tests

---

## Phase B: Image Panel Refactoring (COMPLETED)

Extract preview rendering logic from `image_panel.py`.

### B.1 Create ImageService

Created `app/logic/rexview/image_service.py`:

- [x] `load_oct_file()` - Load OCT file and extract metadata
- [x] `load_processed_stack()` - Load full image stack for processed data
- [x] `create_raw_slice()` - Create single slice from raw data
- [x] `extract_slice()` - Extract 2D slice from 3D stack
- [x] `apply_resize_correction()` - Apply aspect ratio correction
- [x] `apply_refractive_index_correction()` - Apply refractive index correction
- [x] `add_scale_bar()` - Add scale bar to image
- [x] `resize_to_fit_canvas()` - Resize image to fit canvas
- [x] `calculate_canvas_position()` - Calculate centered position
- [x] `process_preview_image()` - Main method combining all processing
- [x] `navigate_slice()` - Calculate slice index for navigation
- [x] `get_middle_slice_index()` - Get middle slice index

### B.2 Create ImageDisplayConfig Model

Added to `app/logic/rexview/models.py`:

- [x] `ImageDisplayConfig` with all display-related settings
- [x] `from_gui_state()` factory method for widget state conversion

### B.3 Wire image_panel.py

- [x] Add `_collect_display_config()` helper
- [x] Delegate preview loading to `ImageService`
- [x] Keep canvas rendering in UI layer

### B.4 Tests

- [x] Unit tests for `ImageService` methods (36 tests)
- [ ] Integration test for preview pipeline (optional)

---

## Phase C: Settings Panels Refactoring

Extract validation and defaults from settings panels.

### C.1 Create SettingsService

Create `app/logic/rexview/settings_service.py`:

- `validate_export_config()` - Validate settings combinations
- `get_defaults()` - Return default configuration
- `parse_dispersion()` - Parse dispersion parameters

### C.2 Wire Settings Panels

- [ ] `global_settings_panel.py` → thin wrapper
- [ ] `custom_settings_panel.py` → thin wrapper
- [ ] Settings validation in logic layer

---

## Phase D: Queue Management Refactoring

Extract queue logic from `tree_view_panel.py` and `pick_files_panel.py`.

### D.1 Create QueueService

Create `app/logic/rexview/queue_service.py`:

- `add_item()` - Validate and add item to queue
- `remove_item()` - Remove item from queue
- `validate_item()` - Check item parameters
- `reorder_items()` - Handle queue reordering

### D.2 Create FileDiscoveryService

Create `app/logic/rexview/file_discovery_service.py`:

- `scan_directory()` - Find OCT files in directory
- `extract_metadata()` - Read OCT file metadata
- `validate_file()` - Check file is valid OCT

### D.3 Wire Panels

- [ ] `tree_view_panel.py` → uses QueueService
- [ ] `pick_files_panel.py` → uses FileDiscoveryService

---

## Phase E: Move UI Files to app/view/rexview/

After all logic is extracted, relocate UI files.

### E.1 Create View Directory Structure

```
app/view/rexview/
├── __init__.py
├── execution_panel.py      # Thin UI wrapper
├── image_panel.py
├── global_settings_panel.py
├── custom_settings_panel.py
├── tree_view_panel.py
├── pick_files_panel.py
└── instruction_panel.py
```

### E.2 Update Imports

- [ ] Update `rexViewTab.py` to import from `app.view.rexview`
- [ ] Keep `RexView/` as deprecated re-exports for backward compatibility

### E.3 Final Cleanup

- [ ] Remove deprecated code from old panel files
- [ ] Update all import paths
- [ ] Verify all tests pass

---

## Target File Structure (End State)

```
app/
├── logic/
│   └── rexview/
│       ├── __init__.py
│       ├── export_service.py       # ✓ Complete
│       ├── image_service.py        # Phase B
│       ├── settings_service.py     # Phase C
│       ├── queue_service.py        # Phase D
│       ├── file_discovery_service.py  # Phase D
│       └── models.py               # ✓ Complete + additions
└── view/
    └── rexview/
        ├── __init__.py
        ├── execution_panel.py      # Phase E
        ├── image_panel.py          # Phase E
        ├── global_settings_panel.py
        ├── custom_settings_panel.py
        ├── tree_view_panel.py
        ├── pick_files_panel.py
        └── instruction_panel.py
```

---

## Progress Tracking

### Phase A: ExportService (COMPLETED)

- [x] Create ExportService with all methods
- [x] Create ExportConfig, SliceExportParams models
- [x] Wire execution_panel.py
- [x] Add unit and integration tests

### Phase B: ImageService (COMPLETED)

- [x] Create ImageService
- [x] Create ImageDisplayConfig model
- [x] Wire image_panel.py
- [x] Add tests (36 unit tests)

### Phase C: SettingsService

- [ ] Create SettingsService
- [ ] Wire global_settings_panel.py
- [ ] Wire custom_settings_panel.py
- [ ] Add tests

### Phase D: QueueService & FileDiscoveryService

- [ ] Create QueueService
- [ ] Create FileDiscoveryService
- [ ] Wire tree_view_panel.py
- [ ] Wire pick_files_panel.py
- [ ] Add tests

### Phase E: UI File Migration

- [ ] Create app/view/rexview/ directory
- [ ] Move UI files
- [ ] Update imports
- [ ] Add backward compatibility re-exports
- [ ] Final cleanup and verification

---

## RexView Completion Criteria

Before moving to AnnoLyze/CarlQuant, RexView must be:

- [ ] **Fully functional**: All export features work identically to before
- [ ] **Fully tested**: 90%+ coverage on `app/logic/rexview/`
- [ ] **Fully separated**: All logic in `app/logic/rexview/`, all UI in `app/view/rexview/`
- [ ] **Documented**: This plan updated with lessons learned
- [ ] **Standalone testable**: `pytest tests/unit/logic/test_rexview_*.py` runs without tkinter

---

## Replication Guide for Other Modules

This section documents the **process** used for RexView so it can be applied to AnnoLyze and CarlQuant.

### Step-by-Step Process

#### 1. Analyze the Panel Files

For each panel file in the module:

```
1. List all methods in the panel class
2. Categorize each method:
   - UI-only (widget creation, event binding) → stays in view
   - Logic (calculations, data processing) → extract to service
   - Mixed (reads widget state, does logic) → split into collector + service call
3. Identify data flowing between methods → becomes Pydantic model
```

#### 2. Create Pydantic Models First

```python
# Pattern: app/logic/<module>/models.py

class <Feature>Config(BaseModel):
    """Configuration gathered from UI widgets."""
    # Fields match what the logic needs, not widget structure
    
class <Feature>Params(BaseModel):
    """Parameters for a single operation."""
    # Includes validation via Pydantic validators
    
class <Feature>Result(BaseModel):
    """Result returned from service to UI."""
    # What the UI needs to display
```

#### 3. Create Service Class with Pure Logic

```python
# Pattern: app/logic/<module>/<feature>_service.py

class <Feature>Service:
    """Pure business logic - no tkinter imports."""
    
    def __init__(self):
        # No GUI references
        pass
    
    def prepare_<operation>(self, params: Params, config: Config) -> dict:
        """Validate and prepare for operation."""
        pass
    
    def execute_<operation>(self, ...) -> Result:
        """Execute the core logic."""
        pass
```

#### 4. Write Unit Tests for Service

```python
# Pattern: tests/unit/logic/test_<module>_<feature>.py

class Test<Feature>Service:
    
    @pytest.fixture
    def service(self):
        return <Feature>Service()
    
    def test_<method>_<scenario>(self, service, ...):
        # GIVEN
        params = <Params>(...)
        
        # WHEN
        result = service.<method>(params)
        
        # THEN
        assert result.<field> == expected
```

#### 5. Add Collector Methods to Panel

```python
# Pattern: In existing panel class

def _collect_<feature>_config(self) -> <Feature>Config:
    """Gather current UI state into config object."""
    return <Feature>Config.from_gui_state(
        field1=self.widget1.get(),
        field2=self.widget2.state(),
        # ...
    )
```

#### 6. Wire Panel to Service

```python
# Pattern: Replace inline logic with service delegation

# Before (inline logic):
def some_action(self):
    value = self.widget.get()
    result = complex_calculation(value)  # Logic mixed with UI
    self.other_widget.set(result)

# After (delegated):
def some_action(self):
    config = self._collect_config()
    result = self.service.calculate(config)  # Pure logic call
    self.other_widget.set(result.display_value)
```

#### 7. Add Integration Tests

```python
# Pattern: tests/integration/test_<module>_pipeline.py

def test_<feature>_end_to_end(self, ...):
    """Test config collection → service → result chain."""
    # Uses real service, mocked file I/O
```

#### 8. Move UI Files (Final Step)

```
1. Create app/view/<module>/ directory
2. Copy panel files to new location
3. Update imports in panel files
4. Update imports in tab file (<module>Tab.py)
5. Add re-exports in old location for backward compatibility
6. Run all tests
7. Manual verification
```

### Key Lessons from RexView

1. **Start with the most complex panel** - `execution_panel.py` had the most logic, extracting it first established patterns

2. **Models before services** - Define data structures first, they clarify what the service interface should be

3. **Incremental wiring** - Replace one method at a time, test after each change

4. **Keep collectors in UI layer** - `_collect_*()` methods stay in panel, they know about widgets

5. **Service methods take models, not primitives** - Pass `ExportConfig` not individual fields

6. **Progress callbacks for long operations** - Service accepts `Callable` for UI updates

7. **Factory methods on models** - `Config.from_gui_state()` handles widget-to-Python conversion

### Files Created for RexView (Reference)

```
app/logic/rexview/
├── __init__.py              # Exports public API
├── export_service.py        # ~380 lines, 8 public methods
├── image_service.py         # ~320 lines, 12 public methods
└── models.py                # ~310 lines, 4 models

tests/unit/logic/
├── test_rexview_export.py   # ~350 lines, 65 tests
├── test_rexview_image.py    # ~520 lines, 36 tests

tests/integration/
└── test_export_pipeline.py  # ~260 lines, 13 tests
```
