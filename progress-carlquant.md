# CarlQuant Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **Milestone 2 (analysis pipeline split) COMPLETE.** Logic foundation done
(Milestone 1) and the main analysis flow (`run_carl_quant`) is now split: pure
per-specimen compute lives in `AnalysisService.analyze_specimen` (tkinter-free, tested),
and UI/threading orchestration moved to `app/view/carlquant/analysis_runner.py`.
Remaining panels still use legacy `CarlQuant/` imports — auditing/thinning + relocating
them to `app/view/carlquant/` is the next milestone.

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

### Tests (34 passing, 100% coverage; full suite green)

- [x] `test_carlquant_models.py` — RegionConfig buffers, SpecimenConfig, enum
- [x] `test_carlquant_interpolation.py` — single/multi keyframe, backfill, forward-fill,
      generic descriptor, AIR
- [x] `test_carlquant_analysis.py` — surface detection, no-region placeholder path, image
      loading, sequential iteration, progress callback, cancellation, region-config path,
      extract_regions/calculate_lesion_depth delegators
- [x] `test_carlquant_import_safety.py` — no tkinter in `app/logic/carlquant/`

Run (coverage): `& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -m pytest tests/ --cov=app.logic.carlquant --cov-report=term-missing`

## Milestone 2 — Analysis pipeline logic/view split (DONE)

- [x] `AnalysisService.analyze_specimen(...)` — pure, tkinter-free per-specimen pipeline
      (parallel via `ProcessPoolExecutor`/`process_slice_parallel` + sequential), result
      storage via `DataSaver`, optional persistence, status setting. UI is injected via
      `on_status` / `on_slice_done` / `on_mode` / `on_error` / `is_cancelled` callbacks.
      Returns `SpecimenAnalysisResult` (status: Completed/Partial/Cancelled).
- [x] `app/view/carlquant/analysis_runner.py` — `run_carl_quant(context)` thin UI/threading
      wrapper: builds `ProgressDialog`, runs the worker thread, maps service callbacks to
      dialog updates, updates the specimen table + status bar, handles skip choice and
      error popups. The pure compute is fully delegated to the service.
- [x] `CarlQuant/load_images_panel.py` rewired to import `run_carl_quant` from
      `app.view.carlquant.analysis_runner`.
- [x] `run_carl_quant` removed from `CarlQuant/carl_quant_core.py` (now pure compute +
      `process_slice_parallel` only).
- [x] Tests: `test_carlquant_specimen.py` (sequential, region-config path, result_lock,
      save-to-disk, parallel, cancellation, status callbacks). Full suite **439 passing**;
      `app/logic/carlquant` at **92%** (uncovered = parallel-cancellation timing branches).

## Next Milestone — Audit & relocate remaining panels (NOT started)

Panels under `CarlQuant/` to audit (per-panel checklist in `REFACTOR-PLAN.md`) then move to
`app/view/carlquant/`:

- [ ] `settings_panel.py` — UI + context state (region count, method, operator/measurement)
- [ ] `specimen_panel.py` — tksheet UI + DataLoader delegation
- [ ] `results_panel.py` — tksheet UI + DataLoader delegation
- [ ] `image_viewer_panel.py` — canvas UI + interpolation/annotation delegation
- [ ] `load_images_panel.py` — relocate (logic already delegated to runner/service)
- [ ] Relocate `progress_dialog.py`, `annotation_renderer.py`, `ascan_viewer.py` to view.
- [ ] Physically move pure logic (`specimen_model`, `carl_quant_core`, `data_io`,
      `interpolation`, `annotation_colors`) into `app/logic/carlquant/` and drop the
      transitional re-export imports; update `carlQuantTab.py`; remove old `CarlQuant/`.
- [ ] Integration test: `tests/integration/test_carlquant_analysis.py`
