"""A failed Docker prerequisite must not leave synthetic credentials behind."""

import argparse
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


def load_backup_verifier():
    script = Path(__file__).parents[3] / "infra/verify_backup_restore.py"
    spec = importlib.util.spec_from_file_location("phase11_backup_verifier", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backup_pair_rejects_missing_corrupt_and_symlink_files(tmp_path: Path):
    module = load_backup_verifier()
    for name in ("database.dump", "media.tar"):
        (tmp_path / name).write_bytes(b"fixture")
    manifest = {
        name: module.file_identity(tmp_path / name)
        for name in ("database.dump", "media.tar")
    }
    module.verify_pair(tmp_path, manifest)
    (tmp_path / "media.tar").write_bytes(b"changed")
    with pytest.raises(ValueError):
        module.verify_pair(tmp_path, manifest)
    (tmp_path / "media.tar").unlink()
    with pytest.raises(ValueError):
        module.verify_pair(tmp_path, manifest)
    (tmp_path / "media.tar").symlink_to(tmp_path / "database.dump")
    with pytest.raises(ValueError):
        module.verify_pair(tmp_path, manifest)


def test_backup_verifier_initial_failure_cleans_secrets_and_backups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    module = load_backup_verifier()
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
            "verifier",
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
    with pytest.raises(RuntimeError):
        module.main()
    assert not list(tmp_path.rglob("*.env"))
    report = json.loads(output.read_text())
    assert report["status"] == "failed"
    assert report["cleanup"]["temporary_credentials_removed"] is True
    assert report["cleanup"]["raw_backups_removed"] is True


def test_backup_transfer_uses_binary_pipes_for_docker(tmp_path: Path, monkeypatch):
    module = load_backup_verifier()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    args = argparse.Namespace(
        minilm_root=tmp_path, clip_root=tmp_path, review_cache=tmp_path
    )
    report = {"steps": []}
    rehearsal = module.Rehearsal(args, report)
    executable = tmp_path / "binary-copy"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import os, stat, sys\n"
        "assert stat.S_ISFIFO(os.fstat(0).st_mode)\n"
        "assert stat.S_ISFIFO(os.fstat(1).st_mode)\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n"
    )
    executable.chmod(0o700)
    source = tmp_path / "source.bin"
    source.write_bytes(bytes(range(256)) * 4096)
    destination = tmp_path / "destination.bin"
    rehearsal.run("copy", [str(executable)], input_file=source, output_file=destination)
    assert destination.read_bytes() == source.read_bytes()
    assert destination.stat().st_mode & 0o777 == 0o600
    assert (rehearsal.work / "copy.log").read_text() == ""
