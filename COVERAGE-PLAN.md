# OCTooL Coverage Plan

Companion to `UTILS-REFACTOR-PLAN.md`. After the `utils/` + `base/` refactor, the full-app
coverage run (`--cov=app`) reports **28%** overall. This document decides which gaps are worth
closing and in what order.

Run the report with:

```pwsh
& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -m pytest tests/ --cov=app --cov-report=term-missing
```

---

## Diagnosis (where the 28% comes from)

The 28% is dominated by the **view layer**, not by missing logic tests.

- **`app/logic/*` is already strong.** `annolyze` and `rexview` logic are ~100%; `shared/models`,
  `shared/paths` are 100%. The remaining logic gaps are concentrated in **carlquant** plus two
  `shared` modules.
- **`app/view/*` is 0% across the board** (`MainGui`, all tabs, panels, dialogs, widgets). These
  are tkinter modules with no automated tests — expected for a desktop GUI, but they drag the
  global number down because `--cov=app` measures them.

So "fixing coverage" is really two separate decisions:
1. **Scope the coverage gate to the testable layer** so the headline number is meaningful.
2. **Close the genuinely cheap logic gaps**; treat the GUI with lightweight smoke tests only.

---

## Guiding Principle

- **Logic (`app/logic`) is pure and must be well-covered** (target **≥ 90%**). This is the layer
  the "no tkinter in logic" rule was designed to keep testable.
- **View (`app/view`) is tkinter-bound.** Chasing line coverage here means brittle widget tests
  with low value. Prefer **import/smoke tests** that catch import-time regressions (the kind the
  refactor could introduce) and leave deep interaction testing manual.
- **Do not weaken existing tests** or add `pragma: no cover` to hide untested *logic*; only use it
  for genuinely unreachable/debug branches.

---

## Coverage Targets

| Area | Current | Target | Approach |
|------|---------|--------|----------|
| `app/logic/annolyze` | ~100% | keep 100% | maintain |
| `app/logic/rexview` | 100% | keep 100% | maintain |
| `app/logic/shared/paths`, `models` | 100% | keep | maintain |
| `app/logic/shared/logging_utils` | 0% | ≥ 90% | new unit test (cheap) |
| `app/logic/shared/oct_functions` | 55% | ≥ 75% | unit + fixtures; pragma the heavy FFT path |
| `app/logic/carlquant/annotation_colors` | 76% | ≥ 95% | new unit test (cheap) |
| `app/logic/carlquant/interpolation` | 94% | ≥ 95% | 2 edge-case tests |
| `app/logic/carlquant/analysis_service` | 91% | ≥ 95% | error/edge branches |
| `app/logic/carlquant/carl_quant_core` | 76% | ≥ 85% | targeted numeric branches |
| `app/logic/carlquant/data_io` | 37% | ≥ 75% | tmp-file round-trip tests |
| `app/view/*` | 0% | import-smoke only | see Step 6 |

---

## Steps

Each step ends green and is independently shippable. Verify after each with:

```pwsh
& "C:\Users\meissnerto\AppData\Local\miniconda3\envs\octool\python.exe" -m pytest tests/ --cov=app.logic --cov-report=term-missing
```

### Step 1 — Decide the coverage policy (config, no new tests)
- [ ] Add a coverage gate scoped to logic in `pyproject.toml`, e.g. run CI/dev coverage with
      `--cov=app.logic` (the meaningful gate) and keep `--cov=app` available for the full picture.
- [ ] Optionally add `[tool.coverage.report] omit` entries for `app/view/*` when computing the
      gate, OR document that the gate is `--cov=app.logic`.
- [ ] (Optional) add `fail_under = 90` under `[tool.coverage.report]` once logic gaps are closed.
- [ ] No behavior change; this just makes the headline number reflect testable code.

### Step 2 — Close the cheap `shared` + carlquant gaps (high value, low effort)
- [ ] `tests/unit/logic/test_logging_utils.py`: call `log_error_to_file(...)` with a monkeypatched
      project root (or `tmp_path`) and assert the daily log file is created with the expected
      header/traceback content. Covers `logging_utils.py` (0% → ~100%).
- [ ] `tests/unit/logic/test_carlquant_annotation_colors.py`: exercise the color lookup/branches
      at lines 64-70, 83 (76% → ≥ 95%).
- [ ] Extend `test_carlquant_interpolation.py` for the missing edges (159, 230-233).
- [ ] Run `--cov=app.logic.shared --cov=app.logic.carlquant`.

### Step 3 — carlquant `data_io` round-trip tests (biggest logic gap: 243 missing)
- [ ] Add `tests/unit/logic/test_carlquant_data_io.py` using `tmp_path`:
      - `DataSaver` writes JSON + Excel (openpyxl) → `DataLoader` reads them back → assert
        round-trip equality for `Specimen`/`SliceResult`/`RegionStats`/`LesionDepth`/`Surface`.
      - cover the load/save error branches (missing file, malformed JSON, empty workbook).
- [ ] Target the large missing ranges (71-208, 218-371, 508-629) via realistic fixtures.
- [ ] `data_io.py` 37% → ≥ 75%.

### Step 4 — carlquant `carl_quant_core` numeric branches (138 missing)
- [ ] Add focused tests for the fitting/detection helpers (`fit_exp2_to_profile`,
      `detect_depth_sigmoid_fit`, spline smoothing) with small synthetic profiles.
- [ ] Cover the guarded error/fallback branches (empty input, non-convergence) rather than every
      numeric line. 76% → ≥ 85%.
- [ ] Mark any genuinely slow fits with `@pytest.mark.slow`.

### Step 5 — `oct_functions` testable paths + pragma the heavy raw path
- [ ] Cover the small helper branches still missing (151-152, 163-164, 167-170, 221-222, 249-252).
- [ ] For `createImageFromRaw` / `createVideoImageFromRaw` (309-504): either
      (a) add a tiny synthetic `.oct`-like zip fixture exercising the **Processed** branch, or
      (b) `# pragma: no cover` the raw-spectral FFT path that needs real instrument data, with a
      comment pointing to the integration test that exercises it on real files.
- [ ] 55% → ≥ 75%.

### Step 6 — View layer: import-smoke tests only (cheap regression guard)
- [ ] Add `tests/unit/view/test_view_import_safety.py` mirroring the existing
      `*_import_safety.py` pattern: import every `app/view/**` module and assert no import error
      (no widget instantiation, no mainloop).
- [ ] This raises many 0% files to "import covered", and—more importantly—catches the exact class
      of breakage the refactor risked (bad import paths) on every CI run.
- [ ] Explicitly **out of scope:** deep tkinter interaction tests. Document GUI behavior as
      manually verified.

### Step 7 — Re-baseline and document
- [ ] Re-run full `--cov=app` and `--cov=app.logic`; record the new numbers.
- [ ] Confirm the logic gate meets target; mark this plan complete.

---

## Risk / Notes

- **GUI coverage is intentionally low.** Do not add fragile widget tests just to move the global
  number — scope the gate to `app.logic` (Step 1) instead.
- **`oct_functions` raw path** genuinely needs real `.oct` data; prefer an integration fixture or a
  documented `pragma: no cover` over fake data that doesn't represent the instrument format.
- **`data_io` Excel tests** depend on `openpyxl`; round-trip via `tmp_path` to avoid touching real
  project data.
- Keep every step green; never delete or weaken existing passing tests to raise coverage.
