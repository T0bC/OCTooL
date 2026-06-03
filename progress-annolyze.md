# AnnoLyze Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **logic layer extracted + 100% tested (tkinter-free); panels wired in place to
delegate to the services.** File relocation to `app/view/annolyze/` is the remaining
optional step.

---

## Starting Notes

- `AnnoLyze/data_io.py` accessed `context.get_panel()` for saving — the new
  `data_service.py` is context-free (takes plain data) per the plan.

## Logic (in `app/logic/annolyze/`) — DONE

| File | Status |
|------|--------|
| `models.py` (Annotation, MetadataConfig, ColumnSpec, AnnotationConfig, UndoAction) | Done |
| `annotation_service.py` — geometry (polyline/spline length), hex→RGBA, (de)serialization | Done |
| `config_service.py` — build/validate/parse config, column map, file I/O | Done |
| `data_service.py` — file discovery + annotation/results/config I/O (context-free) | Done |
| `measurement_service.py` — per-type cell transforms, parsing, key filtering | Done |
| `display_service.py` — luminance, font color, column width (dedup results/undo) | Done |
| `__init__.py` exports | Done |

## Tests — DONE (100% coverage on `app/logic/annolyze/`)

- [x] `test_annolyze_annotation.py`
- [x] `test_annolyze_config.py`
- [x] `test_annolyze_data.py`
- [x] `test_annolyze_measurement.py`
- [x] `test_annolyze_display.py`
- [x] `test_annolyze_models.py`
- [x] `test_annolyze_import_safety.py` (no tkinter in `app/logic/annolyze/`)

Run: `pytest tests/unit/logic -k annolyze --cov=app.logic.annolyze --cov-report=term-missing`

## Panels Wired (in place under `AnnoLyze/`) — DONE

Pure/duplicated logic in each panel now delegates to the new services:

- [x] `annotate_images_panel.py` → AnnotationService (`annotation_length`, `spline_points`,
  `make_annotation_id`, `hex_to_rgba`, `deserialize_annotations`) + DataService
  (`save_annotations`). Removed dead `numpy`/`scipy`/`json` imports.
- [x] `config_manager.py` → ConfigService (`default_config`, `build_config`,
  `validate_config`, `build_column_map`, `get_data_type_for_column`, file I/O) via
  `_collect_metadata`/`_collect_columns` collectors. Removed dead `json`/`datetime` imports.
- [x] `data_io.py` (DataLoader/DataSaver) → DataService (`find_file`, `load_results`,
  `build_data_folder`, `save_config/annotations/results`). Removed dead `csv`/`datetime`.
- [x] `key_binding_manager.py` → MeasurementService (`apply_continuous`, `toggle_boolean`,
  `increment_percentage/categorical/ordinal`, `parse_integer/float/text`,
  `feature_from_annotation_id`).
- [x] `results_panel.py` → DisplayService (luminance/font/width).
- [x] `undo_panel.py` → DisplayService (dedup).
- [x] `add_columns_panel.py` → MeasurementService.available_keys. Removed dead `string`.
- [x] `metadata_panel.py`, `load_images_panel.py`, `keyboard_layout_viewer.py`,
  `instruction_panel.py` — UI-only, no logic to extract.

Verification: `pytest tests/` all pass; `app/logic/annolyze` at 100% coverage;
all edited panels `py_compile` clean.

## Remaining (optional)

- [ ] Relocate panels to `app/view/annolyze/`, update `annoLyzeTab.py` imports, remove
  old `AnnoLyze/` folder (mirrors the RexView end state).
- [ ] Route view-layer messageboxes through `app/view/shared/dialogs.py`.
