"""The admin verifier must record a failed prerequisite without leaving resources."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image


def test_portfolio_requires_complete_decodable_pngs_before_export(tmp_path):
    script = Path(__file__).parents[3] / "infra/verify_admin_demo.py"
    spec = importlib.util.spec_from_file_location("portfolio_demo", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError):
        module.portfolio_assets(tmp_path)
    for name in module.PORTFOLIO_FILES:
        Image.new("RGB", (390, 844), "white").save(tmp_path / name)
    assets = module.portfolio_assets(tmp_path)
    assert len(assets) == 7
    assert all(a["width"] == 390 and a["height"] == 844 for a in assets)
    assert all(len(a["sha256"]) == 64 for a in assets)
    (tmp_path / module.PORTFOLIO_FILES[0]).write_bytes(b"invalid")
    with pytest.raises(ValueError):
        module.portfolio_assets(tmp_path)


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
