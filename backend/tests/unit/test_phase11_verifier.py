"""A failed Docker prerequisite must not leave synthetic credentials behind."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_failed_initial_inventory_removes_credentials_and_records_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = Path(__file__).parents[3] / "infra/verify_persistence.py"
    spec = importlib.util.spec_from_file_location("phase11_verifier", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/synthetic-recipe-images.zip").write_bytes(b"fixture")
    docker = tmp_path / "docker"
    docker.write_text("#!/bin/sh\nexit 7\n")
    docker.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--minilm-root",
            str(tmp_path),
            "--clip-root",
            str(tmp_path),
            "--review-cache",
            str(tmp_path),
            "--output",
            str(output),
        ],
    )
    with pytest.raises(subprocess.CalledProcessError):
        module.main()
    assert not list(tmp_path.rglob("rehearsal.env"))
    report = json.loads(output.read_text())
    assert report["status"] == "failed"
    assert report["cleanup"]["temporary_credentials_removed"] is True
    assert report["failure_type"] == "CalledProcessError"
