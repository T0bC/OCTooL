# CarlQuant Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **Milestone 1 (logic foundation) COMPLETE.** `app/logic/carlquant/` exists,
is tkinter-free, and is unit-tested (29 tests). Panels still use legacy `CarlQuant/`
imports — wiring + relocation to `app/view/carlquant/` is the next milestone.

---

## Starting Notes

- `CarlQuant/carl_quant_core.py` and `CarlQuant/interpolation.py` already contain pure
  functions (surface detection, region extraction, math) — good extraction candidates.
- `CarlQuant/specimen_model.py` (dataclasses) and `CarlQuant/data_io.py` (Excel/JSON/PIL
  I/O) are already tkinter-free.
- `carl_quant_core.py` was tkinter-tainted only via `progress_dialog` + `utils.error_handler`,
  both used solely inside `run_carl_quant`. Those imports are now **lazy** (inside
  `run_carl_quant`), so the module imports headlessly and its pure compute functions are
  reusable by the logic layer.

## Milestone 1 — Logic foundation (DONE)

Logic package `app/logic/carlquant/` (tkinter-free, verified by import-safety test):

| File | Contents | Status |
|------|----------|--------|
| `models.py` | Surfaces the pure boundary models (`RegionConfig`, `AirConfig`, `SpecimenConfig`, `RegionStats`, `Surface`, `LesionDepth`, `SliceResult`, `Specimen`) + `DepthDetectionMethod` from the canonical `CarlQuant.specimen_model` / core | Done |
| `analysis_service.py` | `AnalysisService` (`detect_surface`, `extract_regions`, `calculate_lesion_depth` delegators) + the extracted pure per-slice pipeline `analyze_slice` / `analyze_image` / `analyze_slices` (progress-callback + cancellation, **no tkinter**) and `SliceAnalysis` result | Done |
| `interpolation_service.py` | `InterpolationService` wrapping the keyframe engine (regions/AIR) | Done |
| `data_service.py` | Surfaces `DataLoader` / `DataSaver` + helpers | Done |
| `__init__.py` | Package exports | Done |

### Tests (29 passing; full suite 425 passing)

- [x] `test_carlquant_models.py` — RegionConfig buffers, SpecimenConfig, enum
- [x] `test_carlquant_interpolation.py` — single/multi keyframe, backfill, forward-fill, AIR
- [x] `test_carlquant_analysis.py` — surface detection, no-region placeholder path, image
      loading, sequential iteration, progress callback, cancellation
- [x] `test_carlquant_import_safety.py` — no tkinter in `app/logic/carlquant/`

Run: `& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -m pytest tests/unit/logic -k carlquant -q`

## Next Milestone — Wire & relocate panels (NOT started)

Panels under `CarlQuant/` to audit (per-panel checklist in `REFACTOR-PLAN.md`) then move to
`app/view/carlquant/`:

- [ ] `settings_panel.py` — UI + context state (region count, method, operator/measurement)
- [ ] `load_images_panel.py` — calls `run_carl_quant`; wire to a callback-based service
- [ ] `specimen_panel.py` — tksheet UI + DataLoader delegation
- [ ] `results_panel.py` — tksheet UI + DataLoader delegation
- [ ] `image_viewer_panel.py` — canvas UI + interpolation/annotation delegation
- [ ] Extract `run_carl_quant` UI/threading orchestration into the view layer, delegating
      per-slice compute to `AnalysisService.analyze_slices(progress_callback=...)`.
- [ ] Update `carlQuantTab.py` imports; remove duplicated logic from `CarlQuant/`.
- [ ] Integration test: `tests/integration/test_carlquant_analysis.py`
