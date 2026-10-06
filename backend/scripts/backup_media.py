"""Offline media-volume backup/restore; source writers must already be stopped.

CLI archives travel over stdin/stdout, keeping host backup files private without
mounting a host directory writable by the container. Restore requires an empty
volume and rejects links, special files, traversal and excessive expansion.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

MAX_BYTES = 4 * 1024**3
MAX_ENTRIES = 10000


def volume_snapshot(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Media root must be a real directory")
    digest = hashlib.sha256()
    count = size = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Media volume contains a link or special file")
        name = path.relative_to(root).as_posix()
        digest.update(name.encode() + b"\0")
        if path.is_file():
            with path.open("rb") as handle:
                digest.update(hashlib.file_digest(handle, "sha256").digest())
            size += path.stat().st_size
            count += 1
    return {"files": count, "bytes": size, "sha256": digest.hexdigest()}


def create_archive(root: Path, archive: Path) -> None:
    if archive.resolve().is_relative_to(root.resolve()):
        raise ValueError("Archive must be outside the media volume")
    volume_snapshot(root)  # Reject unsafe sources before creating an archive.
    with tarfile.open(archive, "x") as tar:
        for path in sorted(root.rglob("*")):
            tar.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
    archive.chmod(0o600)


def restore_archive(root: Path, archive: Path, *, max_bytes: int = MAX_BYTES) -> None:
    if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
        raise ValueError("Restore requires an empty, real destination directory")
    with tarfile.open(archive, "r:") as tar:
        members = []
        names = set()
        total = 0
        for member in tar:
            name = PurePosixPath(member.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or not name.parts
                or name.as_posix() in names
                or not (member.isfile() or member.isdir())
                or member.size < 0
            ):
                raise ValueError("Unsafe or duplicate archive member")
            names.add(name.as_posix())
            total += member.size
            members.append(member)
            if len(members) > MAX_ENTRIES or total > max_bytes:
                raise ValueError("Archive expansion limit exceeded")
        # Stage all bytes before making restored files visible in the mount root.
        with tempfile.TemporaryDirectory(prefix=".restore-", dir=root) as staging:
            stage = Path(staging)
            for member in members:
                target = stage / member.name
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                if member.isdir():
                    target.mkdir(exist_ok=True, mode=0o700)
                else:
                    source = tar.extractfile(member)
                    if source is None:
                        raise ValueError("Unreadable archive member")
                    with source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(0o600)
            for path in stage.iterdir():
                path.rename(root / path.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("create", "restore", "snapshot"))
    args = parser.parse_args()
    root = Path(os.environ["MEDIA_ROOT"])
    if args.operation == "snapshot":
        print(json.dumps(volume_snapshot(root)))
        return
    with tempfile.TemporaryDirectory() as work:
        archive = Path(work) / "media.tar"
        if args.operation == "create":
            create_archive(root, archive)
            with archive.open("rb") as source:
                shutil.copyfileobj(source, sys.stdout.buffer)
        else:
            # Bound the input too, including tar headers/padding.
            with archive.open("xb") as output:
                copied = 0
                while chunk := sys.stdin.buffer.read(1024**2):
                    copied += len(chunk)
                    if copied > MAX_BYTES + MAX_ENTRIES * 2048:
                        raise ValueError("Archive input limit exceeded")
                    output.write(chunk)
            restore_archive(root, archive)
            print(json.dumps(volume_snapshot(root)))


if __name__ == "__main__":
    main()
