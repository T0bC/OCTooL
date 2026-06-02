#!/usr/bin/env python3
"""
Safe cross-platform refactor tool for renaming Python package directories.
Run this from the repo root (same folder as MainGui.py).
"""
import os
import re
import shutil
import sys
from pathlib import Path

# ============================================
# CONFIGURE YOUR RENAMES HERE
# ============================================
RENAME_MAP = {
    # old_folder_name: new_folder_name
    "export_frames": "RexView",
    # Add more here before running, e.g.:
    # "AnnoLyze": "AnalyzeView",
    # "CarlQuant": "CarlView",
}

# File extensions to scan for import references.
# Keep .py mandatory. Add .spec, .qmd, .html if you want docs/PyInstaller spec updated too.
EXTENSIONS = (".py", ".spec", ".qmd", ".html", ".md")

# Remove stale compiled caches so Python doesn't load old imports.
CLEAN_PYCACHE = True


def clean_pycache(root: Path) -> int:
    count = 0
    for pyc in root.rglob("__pycache__"):
        if pyc.is_dir():
            shutil.rmtree(pyc)
            count += 1
            print(f"  Removed {pyc.relative_to(root)}")
    return count


def rename_directories(root: Path, mapping: dict) -> None:
    for old, new in mapping.items():
        old_path = root / old
        new_path = root / new
        if not old_path.exists():
            print(f"SKIP : {old_path} does not exist.")
            continue
        if new_path.exists():
            print(f"ERROR: {new_path} already exists. Aborting to avoid data loss.")
            sys.exit(1)
        os.rename(old_path, new_path)
        print(f"RENAMED dir: {old} -> {new}")


def refactor_files(root: Path, mapping: dict) -> None:
    # Collect target files, ignoring .git
    files = [
        p
        for p in root.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and p.suffix in EXTENSIONS
    ]
    files.sort()

    for old, new in mapping.items():
        pattern = re.compile(rf"\b{re.escape(old)}\b")
        for fpath in files:
            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception as e:
                print(f"  WARN : Could not read {fpath.relative_to(root)}: {e}")
                continue
            new_text, num = pattern.subn(new, text)
            if num:
                fpath.write_text(new_text, encoding="utf-8")
                print(f"  UPDATED: {fpath.relative_to(root)} ({num} replacements)")


if __name__ == "__main__":
    project_root = Path(__file__).parent.resolve()
    print(f"Project root: {project_root}")

    print("\n--- Step 1: Rename directories ---")
    rename_directories(project_root, RENAME_MAP)

    print("\n--- Step 2: Refactor imports & references ---")
    refactor_files(project_root, RENAME_MAP)

    if CLEAN_PYCACHE:
        print("\n--- Step 3: Clean __pycache__ ---")
        n = clean_pycache(project_root)
        print(f"  Removed {n} __pycache__ directories.")

    print("\nDone.")
    print("Tip: If you also rename the top-level tab files (exportTab.py / annoLyzeTab.py / carlQuantTab.py),")
    print("     remember to update the matching `import ...` statements in MainGui.py manually.")
