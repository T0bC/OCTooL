# AnnoLyze Progress

Module-specific progress tracker. Pattern + process live in `REFACTOR-PLAN.md`.

Status: **not started.** Apply the canonical Service + Collector pattern after CarlQuant.

---

## Starting Notes

- `AnnoLyze/data_io.py` currently accesses `context.get_panel()` for saving — this context
  dependency must be removed so the logic is pure.

## Planned Logic (in `app/logic/annolyze/`)

- [ ] `models.py` — annotation + data models
- [ ] `annotation_service.py` — extract from `annotate_images_panel.py`
- [ ] `data_service.py` — extract from `data_io.py` (remove `context` dependency)
- [ ] Unit tests in `tests/unit/logic/test_annolyze_*.py`

## Panels to Audit & Wire (move to `app/view/annolyze/`)

Run the per-panel checklist from `REFACTOR-PLAN.md` for each panel file under `AnnoLyze/`:

- [ ] (list panels here as they are analyzed)

## Tests

- [ ] Unit tests for each service
- [ ] Integration test: `tests/integration/test_annotation_workflow.py`
- [ ] Import-safety test (no tkinter in `app/logic/annolyze/`)
