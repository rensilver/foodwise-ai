.PHONY: lint format format-check typecheck test check

lint:
	uv run --locked ruff check src tests

format:
	uv run --locked ruff format src tests

format-check:
	uv run --locked ruff format --check src tests

typecheck:
	uv run --locked mypy

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin

check: lint format-check typecheck test
