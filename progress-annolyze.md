# AnnoLyze Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **logic layer extracted, modeled, and fully tested (100% coverage, tkinter-free).**
View-layer wiring/move is next.

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

## Panels to Audit & Wire (move to `app/view/annolyze/`)

Run the per-panel checklist from `REFACTOR-PLAN.md` for each panel file under `AnnoLyze/`:

- [ ] `annotate_images_panel.py` → AnnotationService (geometry/serialize/color)
- [ ] `config_manager.py` → ConfigService (build/validate/parse), dialogs via shared
- [ ] `data_io.py` (DataLoader/DataSaver) → DataService (context-free)
- [ ] `key_binding_manager.py` → MeasurementService (value transforms)
- [ ] `results_panel.py` → DisplayService (luminance/font/width)
- [ ] `undo_panel.py` → DisplayService (dedup)
- [ ] `add_columns_panel.py` → MeasurementService.available_keys
- [ ] `metadata_panel.py`, `load_images_panel.py`, `keyboard_layout_viewer.py`, `instruction_panel.py` (mostly UI)
