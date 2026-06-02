# RexView ExportService Wiring Plan

Gradually wire `mainRoutines()` in `execution_panel.py` to delegate to `ExportService`, replacing inline logic one method at a time while maintaining backward compatibility and testability.

---

## Current State

- **ExportService** (`app/logic/rexview/export_service.py`): Complete with `prepare_export()`, `load_image_stack()`, `process_slice()`, `run_export()`, etc.
- **Models** (`app/logic/rexview/models.py`): `ExportConfig`, `SliceExportParams`, `ExportProgress`
- **Helper methods** in `execution_panel.py`: `_collect_export_config()`, `_collect_slice_params()` already exist
- **Tests**: 65 unit tests passing, covering ExportService methods
- **Problem**: `mainRoutines()` still has all inline logic (~100 lines) - doesn't use ExportService

---

## Incremental Wiring Strategy

Each step replaces one logical block, is independently testable, and can be paused/resumed.

### Step 1: Wire `prepare_export()` for slice calculation and data type selection
**Replace**: Lines 126-143 (slice calculation, data type selection)
**Keep**: Everything else inline
**Test**: Verify export still works, slices calculated correctly

### Step 2: Wire `load_image_stack()` for image loading
**Replace**: Lines 150-163 (createImageFromRaw call)
**Keep**: Slice processing inline
**Test**: Verify image loading produces same results

### Step 3: Wire `process_slice()` for slice processing
**Replace**: Lines 166-201 (prepareImageSlice, DPI calc, save)
**Keep**: Outer loop, status updates
**Test**: Verify exported images identical

### Step 4: Wire full `run_export()` per-item
**Replace**: Entire per-item processing block
**Keep**: TreeView iteration, GUI callbacks
**Test**: Full export workflow

### Step 5: Add integration tests
**Add**: Tests that verify panel → service → output chain
**Cleanup**: Remove deprecated inline methods

---

## Step 1 Details (First Increment)

### 1.1 Changes to `mainRoutines()`

Replace slice calculation and data type selection with:

```python
# Collect config and params using existing helpers
config = self._collect_export_config()
params = self._collect_slice_params(item[1])

# Use ExportService for preparation
metadata = OCTMetadata.from_xml_dict(self.xmlDict)
prep = self.export_service.prepare_export(params, config, metadata)

# Use prepared values
self.selectedSliceNumber = prep['selected_slices']
self.slicesToLoadAndProcess = prep['slices_to_load']
self.selDataType = prep['sel_data_type']
```

### 1.2 Test Verification

After this change:
1. Run existing unit tests: `pytest tests/unit/ -v`
2. Manual test: Export a sample OCT file, verify output matches previous behavior
3. Add integration test for config collection → prepare_export flow

### 1.3 Success Criteria

- [ ] All 65 existing tests pass
- [ ] Export produces identical output to before
- [ ] `prepare_export()` is called instead of inline calculation

---

## Files to Modify

| File | Changes |
|------|---------|
| `RexView/execution_panel.py` | Wire `mainRoutines()` to use ExportService methods |
| `tests/integration/test_export_pipeline.py` | Add integration tests for wiring |

---

## Rollback Strategy

Each step preserves the original logic in comments until verified. If issues arise:
1. Uncomment original code
2. Comment out service delegation
3. Run tests to confirm rollback works

---

## After Each Step

1. Run `pytest tests/ -v` to verify no regressions
2. Manual test with real OCT file
3. Update this plan with completion status and any adjustments
4. Commit changes with descriptive message

---

## Progress Tracking

- [ ] **Step 1**: Wire `prepare_export()` - slice calculation, data type
- [ ] **Step 2**: Wire `load_image_stack()` - image loading
- [ ] **Step 3**: Wire `process_slice()` - slice processing
- [ ] **Step 4**: Wire full `run_export()` per-item
- [ ] **Step 5**: Integration tests and cleanup
