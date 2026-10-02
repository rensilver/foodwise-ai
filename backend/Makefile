.PHONY: lint format format-check typecheck test test-integration provision-test-models check

lint:
	uv run --locked ruff check src tests scripts

format:
	uv run --locked ruff format src tests scripts

format-check:
	uv run --locked ruff format --check src tests scripts

typecheck:
	uv run --locked mypy

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin

test-integration:
	@test -n "$$TEST_DATABASE_URL" || (echo "Set TEST_DATABASE_URL to the disposable test database"; exit 2)
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin tests/integration

provision-test-models:
	@test -n "$$TEST_MODEL_ROOT" || (echo "Set TEST_MODEL_ROOT to an ignored model-fixture directory"; exit 2)
	uv run --locked python scripts/provision_test_models.py "$$TEST_MODEL_ROOT"

check: lint format-check typecheck test
