"""
Unit tests for app/logic/shared/json_io.py (UTF-8, atomic JSON file I/O).
"""

import pytest

from app.logic.shared.json_io import read_json, write_json_atomic


@pytest.mark.unit
def test_round_trip(tmp_path):
    """GIVEN data, WHEN written then read, THEN the data is identical."""
    path = tmp_path / "data.json"
    data = {"a": 1, "b": [1.5, 2, None], "c": {"nested": True}}

    write_json_atomic(path, data)

    assert read_json(path) == data


@pytest.mark.unit
def test_non_ascii_written_raw_when_ensure_ascii_false(tmp_path):
    """GIVEN non-ASCII text, WHEN ensure_ascii=False, THEN raw UTF-8 is stored and read back."""
    path = tmp_path / "data.json"
    data = {"operator": "Müller"}

    write_json_atomic(path, data, ensure_ascii=False)

    assert "Müller".encode() in path.read_bytes()
    assert read_json(path) == data


@pytest.mark.unit
def test_non_ascii_escaped_when_ensure_ascii_true(tmp_path):
    """GIVEN non-ASCII text, WHEN ensure_ascii=True (default), THEN the file is pure ASCII."""
    path = tmp_path / "data.json"
    data = {"operator": "Müller"}

    write_json_atomic(path, data)

    raw = path.read_bytes()
    assert raw.isascii()
    assert b"\\u00fc" in raw
    assert read_json(path) == data


@pytest.mark.unit
def test_creates_parent_directories(tmp_path):
    """GIVEN a missing parent folder chain, WHEN writing, THEN it is created."""
    path = tmp_path / "a" / "b" / "data.json"

    write_json_atomic(path, {"x": 1})

    assert read_json(path) == {"x": 1}


@pytest.mark.unit
def test_failed_dump_keeps_existing_file_and_leaves_no_temp(tmp_path):
    """GIVEN an existing file, WHEN dump fails, THEN the file is unchanged and no .tmp remains."""
    path = tmp_path / "data.json"
    write_json_atomic(path, {"keep": "me"})
    before = path.read_bytes()

    with pytest.raises(TypeError):
        write_json_atomic(path, {"bad": object()})

    assert path.read_bytes() == before
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.unit
def test_returns_path(tmp_path):
    """GIVEN a str path, WHEN writing, THEN a Path to the written file is returned."""
    path = tmp_path / "data.json"

    result = write_json_atomic(str(path), {"x": 1})

    assert result == path
    assert result.is_file()
