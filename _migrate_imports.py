"""Temporary Step H migration: repoint utils/base imports to app.*.shared homes."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent

# Ordered substring replacements. The combined app_context import must come
# before the single-symbol variants so it is handled correctly.
REPLACEMENTS = [
    ("from utils.app_context import AppContext, resource_path",
     "from app.view.shared.app_context import AppContext\nfrom app.logic.shared.paths import resource_path"),
    ("from utils.app_context import resource_path",
     "from app.logic.shared.paths import resource_path"),
    ("from utils.app_context import AppContext",
     "from app.view.shared.app_context import AppContext"),
    ("from utils.status_bar import", "from app.view.shared.status_bar import"),
    ("from utils.error_handler import", "from app.view.shared.error_handler import"),
    ("from utils.help_dialog import", "from app.view.shared.help_dialog import"),
    ("from utils.about_dialog import", "from app.view.shared.about_dialog import"),
    ("from utils.tool_tip import", "from app.view.shared.tool_tip import"),
    ("from utils.instruction_renderer import", "from app.view.shared.instruction_renderer import"),
    ("from utils.metadata_prompt import", "from app.view.shared.metadata_prompt import"),
    ("from utils import oct_functions", "from app.logic.shared import oct_functions"),
    ("from base import BaseCanvasPanel",
     "from app.view.shared.base_canvas_panel import BaseCanvasPanel"),
]

# Directories that contain the shims / new homes themselves - skip them so we
# don't rewrite the intentional `from app...` shims or new modules.
SKIP_DIRS = {ROOT / "utils", ROOT / "base", ROOT / ".git"}

changed = []
for path in ROOT.rglob("*.py"):
    if path.name == "_migrate_imports.py":
        continue
    if any(skip in path.parents or skip == path.parent for skip in SKIP_DIRS):
        continue
    text = path.read_text(encoding="utf-8")
    new = text
    for old, repl in REPLACEMENTS:
        new = new.replace(old, repl)
    if new != text:
        path.write_text(new, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))

print("Changed files:")
for c in changed:
    print(" ", c)
