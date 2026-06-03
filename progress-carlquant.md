# CarlQuant Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **not started.** Apply the canonical Service + Collector pattern after RexView Phase F.

---

## Starting Notes

- `CarlQuant/carl_quant_core.py` and `CarlQuant/interpolation.py` already contain pure
  functions (surface detection, region extraction, math) — good extraction candidates.
- Main remaining work is modeling + wrapping in services and thinning the panels.

## Planned Logic (in `app/logic/carlquant/`)

- [ ] `models.py` — `RegionConfig`, `AIRConfig`, `SpecimenConfig`
- [ ] `analysis_service.py` — wrap `carl_quant_core.py` functions
- [ ] `surface_detection.py` — surface detection logic
- [ ] Unit tests in `tests/unit/logic/test_carlquant_*.py`

## Panels to Audit & Wire (move to `app/view/carlquant/`)

Run the per-panel checklist from `REFACTOR-PLAN.md` for each panel file under `CarlQuant/`:

- [ ] (list panels here as they are analyzed)

## Tests

- [ ] Unit tests for each service
- [ ] Integration test: `tests/integration/test_carlquant_analysis.py`
- [ ] Import-safety test (no tkinter in `app/logic/carlquant/`)
