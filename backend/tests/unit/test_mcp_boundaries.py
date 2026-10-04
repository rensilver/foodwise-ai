"""Capabilities remain bounded without client roots or sampling callbacks."""

import ast
from pathlib import Path

import pytest

from food_recommender.application.errors import ApplicationError
from food_recommender.infrastructure.media.files import LocalMediaFiles


def test_mcp_has_no_inference_sampling_shell_or_mutation_imports():
    root = Path(__file__).parents[2] / "src" / "food_recommender" / "mcp"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any(
            "openai" in name or "langchain" in name or name in {"subprocess", "os"}
            for name in imports
        )
        calls = {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }
        assert "create_message" not in calls and "sampling" not in calls


@pytest.mark.asyncio
async def test_filesystem_boundary_rejects_paths_and_symlinks_without_roots(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("private content")
    (media / "image.png").symlink_to(outside)
    files = LocalMediaFiles(media)
    for key in ("../private.txt", str(outside), "image.png"):
        with pytest.raises(ApplicationError):
            await files.read(key)
    linked_root = tmp_path / "link"
    linked_root.symlink_to(media, target_is_directory=True)
    with pytest.raises(ApplicationError):
        await LocalMediaFiles(linked_root).read("image.png")
