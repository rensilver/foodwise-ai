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
    "openai",
    "langchain_openai",
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
    "openai", "sqlalchemy", "psycopg", "fastmcp",
    "torch", "transformers", "sentence_transformers",
):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules), prefix
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


def test_api_handlers_depend_on_use_cases_and_never_concrete_io():
    forbidden = SDK_ROOTS - {"fastapi", "starlette"}
    violations = []
    for path in sorted((ROOT / "api").rglob("*.py")):
        if path.name == "main.py":
            continue  # The process entrypoint owns construction and lifecycle.
        for dependency in imports(path):
            parts = dependency.split(".")
            if parts[0] in forbidden or (
                parts[0] == "food_recommender"
                and len(parts) > 1
                and parts[1]
                in {"infrastructure", "composition", "agents", "mcp", "cli"}
            ):
                violations.append(f"{path.relative_to(ROOT)} -> {dependency}")
    assert not violations, "\n".join(violations)


def test_http_routers_import_shared_schemas_without_router_reexports():
    violations = []
    for path in (ROOT / "api/routers").glob("*.py"):
        for dependency in imports(path):
            if dependency.startswith("food_recommender.api.routers."):
                violations.append(f"{path.relative_to(ROOT)} -> {dependency}")
    assert not violations, "\n".join(violations)


def test_transaction_contract_import_does_not_load_use_cases():
    """Adapters can depend on repository contracts without loading services."""
    script = """
import sys
import food_recommender.application.unit_of_work

allowed = {
    "food_recommender.application.unit_of_work",
    "food_recommender.application.errors",
}
for name, module in tuple(sys.modules.items()):
    if not name.startswith("food_recommender.application."):
        continue
    if hasattr(module, "__path__"):
        continue
    assert name in allowed or name.endswith((".ports", ".cleanup_ports")), name
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("reverse", [False, True])
def test_application_modules_import_without_cycles_or_concrete_io(reverse: bool):
    """Fresh imports catch accidental cycles hidden by test collection order."""
    script = f"""
import importlib
import pkgutil
import sys
import food_recommender.application as application

names = sorted(
    (item.name for item in pkgutil.walk_packages(
        application.__path__, application.__name__ + "."
    )),
    reverse={reverse!r},
)
for name in names:
    importlib.import_module(name)
for prefix in (
    "food_recommender.infrastructure", "food_recommender.composition",
    "food_recommender.api", "food_recommender.mcp", "food_recommender.agents",
    "sqlalchemy", "psycopg", "httpx", "langgraph", "torch", "transformers",
):
    assert not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules), prefix
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr
