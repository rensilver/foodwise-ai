"""Private deletion rejects traversal and does not follow a symlinked root."""

from pathlib import Path

import pytest

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.infrastructure.media.files import LocalMediaFiles


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key", ["../private.png", "/tmp/private.png", "sub/file.png", "..", "x\x00.png"]
)
async def test_deletion_rejects_caller_paths(tmp_path, key):
    with pytest.raises(ApplicationError) as failure:
        await LocalMediaFiles(tmp_path).delete(key)
    assert failure.value.code == ErrorCode.INVALID_REQUEST


@pytest.mark.asyncio
async def test_root_symlink_does_not_remove_target(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    file = actual / "keep.png"
    file.write_bytes(b"keep")
    root = tmp_path / "link"
    root.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ApplicationError) as failure:
        await LocalMediaFiles(root).delete("keep.png")
    assert failure.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert file.read_bytes() == b"keep"


@pytest.mark.asyncio
async def test_missing_file_is_safe_to_retry(tmp_path):
    await LocalMediaFiles(tmp_path).delete("missing.png")


@pytest.mark.parametrize("path", [Path("relative"), Path("/"), Path("/tmp/../etc")])
def test_media_root_requires_mount_scope(path):
    with pytest.raises(ValueError):
        LocalMediaFiles(path)
