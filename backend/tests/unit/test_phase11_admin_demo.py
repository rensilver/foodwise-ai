"""The admin verifier must record a failed prerequisite without leaving resources."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def test_admin_demo_failed_inventory_records_failure_and_removes_private_work(
    tmp_path, monkeypatch
):
    script = Path(__file__).parents[3] / "infra/verify_admin_demo.py"
    spec = importlib.util.spec_from_file_location("phase11_admin_demo", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
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
            "--pnpm",
            str(docker),
            "--output",
            str(output),
        ],
    )
    with pytest.raises(RuntimeError):
        module.main()
    report = json.loads(output.read_text())
    assert report["passed"] is False
    assert report["failure_type"] == "CalledProcessError"
    assert report["isolation"]["private_work_removed"] is True
    assert not list((tmp_path / ".local-tmp").glob("p11-05-*"))
