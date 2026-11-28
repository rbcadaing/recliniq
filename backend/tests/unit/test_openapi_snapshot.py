"""The committed OpenAPI snapshot matches the backend (US-00.4 API contract check)."""

from pathlib import Path

import pytest

from scripts.export_openapi import SNAPSHOT_PATH, main


def test_committed_snapshot_is_up_to_date() -> None:
    assert main(["--check"]) == 0, "run `uv run python -m scripts.export_openapi` and commit"


def test_check_fails_for_a_stale_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    stale = tmp_path / "openapi.json"
    stale.write_text(SNAPSHOT_PATH.read_text(encoding="utf-8").replace("email", "e_mail"))
    assert main(["--check", "--output", str(stale)]) == 1
    assert "scripts.export_openapi" in capsys.readouterr().err


def test_export_writes_the_snapshot(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "openapi.json"
    assert main(["--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == SNAPSHOT_PATH.read_text(encoding="utf-8")
