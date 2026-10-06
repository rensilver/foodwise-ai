"""Backup recovery must fail closed before touching a destination volume."""

import io
import tarfile
from pathlib import Path

import pytest
from scripts.backup_media import create_archive, restore_archive, volume_snapshot


def test_complete_volume_round_trip_includes_hidden_recovery_files(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".setup/downloads").mkdir(parents=True)
    (source / ".setup/downloads/original.bin").write_bytes(b"original")
    (source / "image.png").write_bytes(b"image")
    archive = tmp_path / "media.tar"
    create_archive(source, archive)
    destination = tmp_path / "destination"
    destination.mkdir()
    restore_archive(destination, archive)
    assert volume_snapshot(source) == volume_snapshot(destination)


@pytest.mark.parametrize("name", ["../escape", "/escape", "a/../../escape"])
def test_traversal_is_rejected_before_any_file_is_written(tmp_path: Path, name: str):
    archive = tmp_path / "media.tar"
    with tarfile.open(archive, "w") as tar:
        for entry in ("valid", name):
            member = tarfile.TarInfo(entry)
            member.size = 1
            tar.addfile(member, io.BytesIO(b"x"))
    destination = tmp_path / "destination"
    destination.mkdir()
    with pytest.raises(ValueError):
        restore_archive(destination, archive)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_links_and_special_files_are_rejected(tmp_path: Path, kind: bytes):
    archive = tmp_path / "media.tar"
    with tarfile.open(archive, "w") as tar:
        member = tarfile.TarInfo("entry")
        member.type = kind
        member.linkname = "outside"
        tar.addfile(member)
    destination = tmp_path / "destination"
    destination.mkdir()
    with pytest.raises(ValueError):
        restore_archive(destination, archive)
    assert list(destination.iterdir()) == []


def test_existing_destination_and_symlink_source_are_preserved(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    retained = source / "retained"
    retained.write_bytes(b"original")
    archive = tmp_path / "media.tar"
    create_archive(source, archive)
    with pytest.raises(ValueError):
        restore_archive(source, archive)
    assert retained.read_bytes() == b"original"
    (source / "link").symlink_to(retained)
    with pytest.raises(ValueError):
        create_archive(source, tmp_path / "unsafe.tar")


def test_archive_expansion_is_bounded(tmp_path: Path):
    archive = tmp_path / "media.tar"
    with tarfile.open(archive, "w") as tar:
        member = tarfile.TarInfo("large")
        member.size = 2
        tar.addfile(member, io.BytesIO(b"xx"))
    destination = tmp_path / "destination"
    destination.mkdir()
    with pytest.raises(ValueError):
        restore_archive(destination, archive, max_bytes=1)
    assert list(destination.iterdir()) == []


def test_duplicate_or_truncated_archives_leave_destination_empty(tmp_path: Path):
    destination = tmp_path / "destination"
    destination.mkdir()
    archive = tmp_path / "media.tar"
    with tarfile.open(archive, "w") as tar:
        for _ in range(2):
            member = tarfile.TarInfo("duplicate")
            member.size = 1
            tar.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(ValueError):
        restore_archive(destination, archive)
    assert list(destination.iterdir()) == []
    with tarfile.open(archive, "w") as tar:
        member = tarfile.TarInfo("truncated")
        member.size = 2048
        tar.addfile(member, io.BytesIO(b"x" * 2048))
    archive.write_bytes(archive.read_bytes()[:1536])
    with pytest.raises(tarfile.ReadError):
        restore_archive(destination, archive)
    assert list(destination.iterdir()) == []
