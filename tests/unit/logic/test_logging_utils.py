"""
Unit tests for app/logic/shared/logging_utils.py.

Exercises log_error_to_file with a monkeypatched project root so the daily log
file is written under tmp_path rather than the real project directory.
"""
import os

import pytest

from app.logic.shared import logging_utils


@pytest.mark.unit
def test_log_error_creates_daily_file(tmp_path, monkeypatch):
    """GIVEN a temp project root, WHEN logging an error, THEN a daily log file is written."""
    monkeypatch.setattr(logging_utils, "_project_root", lambda: str(tmp_path))

    logging_utils.log_error_to_file(
        function_name="do_thing",
        args=(1, "abc"),
        kwargs={"flag": True},
        custom_message="Something failed",
        traceback_text="Traceback (most recent call last): ...",
    )

    logs_dir = tmp_path / "logs"
    assert logs_dir.is_dir()

    log_files = list(logs_dir.glob("error_log_*.txt"))
    assert len(log_files) == 1

    content = log_files[0].read_text(encoding="utf-8")
    assert "do_thing" in content
    assert "Something failed" in content
    assert "Traceback (most recent call last): ..." in content
    assert "flag=True" in content
    assert "'abc'" in content


@pytest.mark.unit
def test_log_error_appends_to_existing_file(tmp_path, monkeypatch):
    """GIVEN two errors on the same day, WHEN logging, THEN both entries append to one file."""
    monkeypatch.setattr(logging_utils, "_project_root", lambda: str(tmp_path))

    logging_utils.log_error_to_file("f1", (), {}, "first", "tb1")
    logging_utils.log_error_to_file("f2", (), {}, "second", "tb2")

    log_files = list((tmp_path / "logs").glob("error_log_*.txt"))
    assert len(log_files) == 1

    content = log_files[0].read_text(encoding="utf-8")
    assert "f1" in content and "f2" in content
    assert content.count("=" * 80) >= 2


@pytest.mark.unit
def test_log_error_default_message_when_none(tmp_path, monkeypatch):
    """GIVEN no custom message, WHEN logging, THEN the default message is used."""
    monkeypatch.setattr(logging_utils, "_project_root", lambda: str(tmp_path))

    logging_utils.log_error_to_file("f", (), {}, None, "tb")

    content = next((tmp_path / "logs").glob("error_log_*.txt")).read_text(encoding="utf-8")
    assert "Unhandled exception" in content


@pytest.mark.unit
def test_project_root_points_above_app(tmp_path):
    """The computed project root must be four levels above the module file."""
    root = logging_utils._project_root()
    # logging_utils lives at <root>/app/logic/shared/logging_utils.py
    assert os.path.isdir(os.path.join(root, "app", "logic", "shared"))
