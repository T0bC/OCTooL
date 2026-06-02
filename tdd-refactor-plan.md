# TDD Refactoring Plan: GUI/Logic Separation for OCTooL

Incrementally refactor OCTooL to separate GUI from business logic, starting with RexView as pilot, enabling comprehensive pytest-based testing with pydantic models.

---

## Current State Analysis

**Problem**: Panel classes (`executionPanel`, `imagePanel`, etc.) instantiate tkinter widgets in `__init__` and read widget states directly in business logic methods, making unit testing impossible without the full GUI.

**Already Testable**:
- `utils/oct_functions.py` - pure zipfile/XML/image processing
- `CarlQuant/carl_quant_core.py` - pure algorithms (surface detection, region extraction)
- `CarlQuant/interpolation.py` - pure math functions

**Tightly Coupled** (needs refactoring):
- `RexView/execution_panel.py` - reads `treeView.getValue()`, `globalSettingsFrame.ScaleBox.state()`
- `RexView/image_panel.py` - mixes display logic with OCT processing
- `AnnoLyze/data_io.py` - accesses `context.get_panel()` for saving

---

## Target Directory Structure

```
OCTooL/
├── app/
│   ├── __init__.py
│   ├── logic/
│   │   ├── __init__.py
│   │   ├── shared/                    # Shared utilities (from utils/)
│   │   │   ├── __init__.py
│   │   │   ├── oct_functions.py       # Move from utils/
│   │   │   └── models.py              # Pydantic models for OCT metadata
│   │   ├── rexview/
│   │   │   ├── __init__.py
│   │   │   ├── export_service.py      # Pure export logic
│   │   │   ├── image_processor.py     # Image processing pipeline
│   │   │   └── models.py              # Pydantic: ExportConfig, SliceParams
│   │   ├── annolyze/
│   │   │   ├── __init__.py
│   │   │   ├── annotation_service.py
│   │   │   ├── data_service.py
│   │   │   └── models.py
│   │   └── carlquant/
│   │       ├── __init__.py
│   │       ├── analysis_service.py    # Move from carl_quant_core.py
│   │       ├── surface_detection.py
│   │       └── models.py
│   └── view/
│       ├── __init__.py
│       ├── shared/
│       │   ├── __init__.py
│       │   ├── app_context.py         # Keep UI coordination
│       │   ├── base_canvas_panel.py
│       │   └── widgets/               # Reusable UI components
│       ├── rexview/
│       │   ├── __init__.py
│       │   ├── execution_panel.py     # Thin UI wrapper
│       │   ├── image_panel.py
│       │   └── settings_panels.py
│       ├── annolyze/
│       │   └── ...
│       └── carlquant/
│           └── ...
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── logic/
│   │   │   ├── test_oct_functions.py
│   │   │   ├── test_rexview_export.py
│   │   │   └── test_carlquant_analysis.py
│   │   └── models/
│   │       └── test_pydantic_models.py
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_export_pipeline.py
│   └── fixtures/
│       ├── sample_oct_files/          # Small test OCT files
│       └── expected_outputs/
├── MainGui.py                         # Entry point (unchanged)
├── OCTooL.py                          # Main app (unchanged)
└── requirements.txt                   # Add pytest, pydantic
```

---

## Phase 1: Foundation (Week 1)

### 1.1 Setup Test Infrastructure
- [ ] Create `tests/` directory structure
- [ ] Add `pytest`, `pydantic`, `pytest-cov` to `requirements.txt`
- [ ] Create `tests/conftest.py` with shared fixtures
- [ ] Create `pyproject.toml` or `pytest.ini` for pytest config

### 1.2 Create Pydantic Models for RexView
- [ ] Create `app/logic/rexview/models.py`:
  ```python
  from pydantic import BaseModel
  from typing import Literal, Optional, Tuple
  
  class ExportConfig(BaseModel):
      resize_enabled: bool = True
      prefer_raw: bool = True
      advanced_filter: bool = False
      export_format: Literal['.png', '.tiff'] = '.tiff'
      averaging: Literal['none', 'incoherent', 'coherent'] = 'coherent'
      tukey_window_size: float = 0.9
      scale_enabled: bool = True
      scale_length_um: int = 500
      scale_font_size: int = 30
  
  class SliceExportParams(BaseModel):
      file_path: str
      name: str
      first_slice: int
      last_slice: int
      num_slices: int
      slice_direction: Literal['XZ', 'YZ', 'XY']
      db_min: int
      db_max: int
      refractive_index: float = 1.0
      dispersion: Tuple[str, str] = ('None', '0')
  
  class OCTMetadata(BaseModel):
      """Pydantic model for OCT file metadata (from xmlDict)"""
      data_type: str
      dim_x: int
      dim_y: int
      dim_z: int
      img_size_mm_x: Optional[float]
      img_size_mm_y: Optional[float]
      img_size_mm_z: Optional[float]
      spacing_x: float
      spacing_y: float
      spacing_z: float
      exp_number: int
      # ... etc
  ```

### 1.3 Write First Tests for Existing Pure Functions
- [ ] Create `tests/unit/logic/test_oct_functions.py`:
  - Test `unzipOCTData()` with sample OCT file
  - Test `readXMLContent()` 
  - Test `getXMLAttributes()` returns valid dict
  - Test `insertScale()` with mock image
  - Test `octToGV()` with synthetic data

---

## Phase 2: RexView Logic Extraction (Week 2)

### 2.1 Extract Export Service
- [ ] Create `app/logic/rexview/export_service.py`:
  ```python
  from app.logic.rexview.models import ExportConfig, SliceExportParams, OCTMetadata
  from app.logic.shared import oct_functions as octF
  
  class ExportService:
      """Pure business logic for OCT export - no tkinter dependencies"""
      
      def prepare_export(self, params: SliceExportParams, config: ExportConfig) -> dict:
          """Validate and prepare export parameters"""
          ...
      
      def process_slice(self, image_stack, slice_idx: int, 
                        params: SliceExportParams, config: ExportConfig,
                        metadata: OCTMetadata) -> Image:
          """Process a single slice - resize, scale bar, etc."""
          ...
      
      def run_export(self, params: SliceExportParams, config: ExportConfig,
                     progress_callback=None) -> list[Path]:
          """Execute full export pipeline"""
          ...
  ```

### 2.2 Refactor execution_panel.py
- [ ] Keep `executionPanel` as thin UI wrapper
- [ ] Extract widget state into `ExportConfig` and `SliceExportParams`
- [ ] Delegate to `ExportService` for actual processing
- [ ] Pattern:
  ```python
  class executionPanel:
      def __init__(self, context):
          self.export_service = ExportService()
          # ... UI setup unchanged
      
      def _collect_config(self) -> ExportConfig:
          """Gather current UI state into config object"""
          return ExportConfig(
              resize_enabled=self.globalSettingsFrame.getResizeState() == 'selected',
              # ...
          )
      
      def mainRoutine(self):
          config = self._collect_config()
          params = self._collect_params_from_treeview()
          self.export_service.run_export(params, config, 
                                         progress_callback=self._update_status)
  ```

### 2.3 Write Tests for Export Service
- [ ] `tests/unit/logic/test_rexview_export.py`:
  - Test `ExportService.prepare_export()` validates params
  - Test `ExportService.process_slice()` with synthetic image
  - Test slice selection logic
  - Test scale bar insertion
  - Test refractive index correction

---

## Phase 3: Shared Logic Migration (Week 3)

### 3.1 Move oct_functions.py
- [ ] Create `app/logic/shared/oct_functions.py` (copy)
- [ ] Update imports in refactored modules
- [ ] Keep `utils/oct_functions.py` as re-export for backward compatibility:
  ```python
  # utils/oct_functions.py (deprecated wrapper)
  from app.logic.shared.oct_functions import *
  ```

### 3.2 Create Shared Models
- [ ] `app/logic/shared/models.py` - common pydantic models
- [ ] Migrate `OCTMetadata` parsing to return pydantic model

---

## Phase 4: AnnoLyze & CarlQuant (Weeks 4-5)

Apply same pattern:
1. Create pydantic models in `app/logic/<module>/models.py`
2. Extract service classes with pure logic
3. Refactor panels to thin UI wrappers
4. Write unit tests for services

**CarlQuant** is partially done - `carl_quant_core.py` already has pure functions. Main work:
- Create pydantic models for `RegionConfig`, `AIRConfig`, `SpecimenConfig`
- Wrap existing functions in service class

**AnnoLyze**:
- Extract `AnnotationService` from `annotate_images_panel.py`
- Extract `DataService` from `data_io.py` (remove context dependency)

---

## Phase 5: Integration Tests (Week 6)

- [ ] `tests/integration/test_export_pipeline.py` - full export with real OCT file
- [ ] `tests/integration/test_annotation_workflow.py`
- [ ] `tests/integration/test_carlquant_analysis.py`

---

## Testing Guidelines (from Modern TDD)

1. **GIVEN-WHEN-THEN** structure for all tests
2. **Test behavior, not implementation** - don't mock internal methods
3. **One behavior per test** - single assertion focus
4. **Test pyramid**: 50% unit, 30% integration, 20% e2e
5. **Mock only external resources** (file I/O, network) - not internal classes
6. **Pydantic for validation** - models validate at construction time

---

## Backward Compatibility Strategy

- Old import paths continue to work via re-exports
- `AppContext` remains the coordination hub
- Panel `__init__` signatures unchanged
- Gradual migration - both patterns coexist during transition

---

## Success Criteria

- [ ] `pytest tests/unit/` runs without tkinter
- [ ] 80%+ coverage on `app/logic/` modules
- [ ] RexView export works identically before/after refactor
- [ ] New features can be developed test-first
- [ ] CI can run tests headlessly

---

## Estimated Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1 | 3-4 days | Test infra + first unit tests |
| 2 | 5-7 days | RexView fully refactored |
| 3 | 2-3 days | Shared logic migrated |
| 4 | 7-10 days | AnnoLyze + CarlQuant |
| 5 | 3-4 days | Integration tests |

**Total: ~4-5 weeks** for full refactor with tests
