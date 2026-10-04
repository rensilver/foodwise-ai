"""Keep business logic independent of concrete adapters and process wiring."""

import ast
import subprocess
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2] / "src" / "food_recommender"
CORE = {"domain", "application", "retrieval", "ingestion"}
SDK_ROOTS = {
    "sqlalchemy",
    "psycopg",
    "pgvector",
    "fastapi",
    "starlette",
    "fastmcp",
    "httpx",
    "langchain_groq",
    "langgraph",
    "tavily",
    "sentence_transformers",
    "transformers",
    "torch",
}


def imports(path: Path) -> set[str]:
    parts = path.relative_to(ROOT.parent).with_suffix("").parts
    package = ".".join(parts[:-1])
    result: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = resolve_name("." * node.level + module, package)
            result.add(module)
            result.update(f"{module}.{alias.name}" for alias in node.names)
    return result


@pytest.mark.parametrize("package", sorted(CORE))
def test_core_packages_do_not_import_adapters_or_sdks(package: str) -> None:
    violations = []
    allowed = {"domain"} if package == "domain" else CORE
    for path in sorted((ROOT / package).rglob("*.py")):
        for dependency in sorted(imports(path)):
            parts = dependency.split(".")
            if parts[0] in SDK_ROOTS or (
                parts[0] == "food_recommender"
                and len(parts) > 1
                and parts[1] not in allowed
            ):
                violations.append(f"{path.relative_to(ROOT)} -> {dependency}")
    assert not violations, "\n".join(violations)


def test_infrastructure_does_not_import_entrypoints() -> None:
    forbidden = {"api", "mcp", "cli", "transport", "composition", "agents"}
    violations = []
    for path in sorted((ROOT / "infrastructure").rglob("*.py")):
        for dependency in sorted(imports(path)):
            parts = dependency.split(".")
            if (
                parts[0] == "food_recommender"
                and len(parts) > 1
                and parts[1] in forbidden
            ) or parts[0] in {"fastapi", "starlette", "fastmcp"}:
                violations.append(f"{path.relative_to(ROOT)} -> {dependency}")
    assert not violations, "\n".join(violations)


def test_metadata_registry_is_complete_in_a_fresh_process() -> None:
    """Collection order must not hide missing mappings or adapter imports."""
    script = """
import sys
from food_recommender.infrastructure.persistence.models import Base

assert set(Base.metadata.tables) == {
    "restaurants", "recipes", "reviews", "sources", "source_records",
    "documents", "media", "text_embeddings", "image_embeddings",
    "browser_sessions", "conversations", "profiles", "demo_profiles",
    "messages", "conversation_media", "trend_cache", "trend_evidence",
    "media_cleanup_jobs", "ingestion_checkpoints", "admin_sessions",
}
for table in Base.metadata.tables.values():
    for foreign_key in table.foreign_keys:
        assert foreign_key.column.table.name in Base.metadata.tables
for prefix in (
    "food_recommender.infrastructure.persistence.repositories",
    "food_recommender.infrastructure.persistence.engine",
    "food_recommender.infrastructure.persistence.ingestion",
    "food_recommender.infrastructure.providers",
    "food_recommender.infrastructure.embeddings",
    "food_recommender.composition",
    "langgraph", "torch", "transformers", "sentence_transformers",
):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules), prefix
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_graph_dependencies_are_limited_to_core_and_workflow_sdks():
    violations = []
    for path in sorted((ROOT / "agents").rglob("*.py")):
        for dependency in imports(path):
            parts = dependency.split(".")
            if parts[0] in SDK_ROOTS - {"langgraph"} or (
                parts[0] == "food_recommender"
                and len(parts) > 1
                and parts[1] not in CORE | {"agents"}
            ):
                violations.append(f"{path.relative_to(ROOT)} -> {dependency}")
    assert not violations, "\n".join(violations)


def test_graph_import_has_no_provider_media_or_database_adapter_dependencies():
    script = """
import sys
import food_recommender.agents.graph
import food_recommender.agents.runner
for prefix in (
    "food_recommender.infrastructure", "food_recommender.mcp",
    "groq", "sqlalchemy", "psycopg", "fastmcp",
    "torch", "transformers", "sentence_transformers",
):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules), prefix
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr
