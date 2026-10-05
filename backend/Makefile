.PHONY: lint format format-check typecheck test test-integration provision-test-models check

lint:
	uv run --locked ruff check src tests scripts migrations

format:
	uv run --locked ruff format src tests scripts migrations

format-check:
	uv run --locked ruff format --check src tests scripts migrations

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

check: lint format-check typecheck api-schema-check test

# Explicit pretrained retrieval operations; no models or provider keys at startup.
.PHONY: provision-minilm index-text evaluate-text
provision-minilm:
	@test -n "$$MINILM_ROOT" || (echo "Set MINILM_ROOT to ignored pretrained model storage"; exit 2)
	uv run --locked python scripts/provision_minilm.py "$$MINILM_ROOT"

index-text:
	@test -n "$$DATABASE_URL" -a -n "$$MINILM_ROOT" || (echo "Set DATABASE_URL and MINILM_ROOT"; exit 2)
	uv run --locked python -m food_recommender.cli.text --model-root "$$MINILM_ROOT" index

evaluate-text:
	@test -n "$$DATABASE_URL" -a -n "$$MINILM_ROOT" || (echo "Set DATABASE_URL and MINILM_ROOT"; exit 2)
	uv run --locked python scripts/evaluate_text_retrieval.py --model-root "$$MINILM_ROOT" --queries ../evaluation/phase4/text_queries.json --output ../evaluation/phase4/baseline_report.json

.PHONY: provision-clip index-images
provision-clip:
	@test -n "$$CLIP_ROOT" || (echo "Set CLIP_ROOT to ignored pretrained model storage"; exit 2)
	uv run --locked python scripts/provision_clip.py "$$CLIP_ROOT"

index-images:
	@test -n "$$DATABASE_URL" -a -n "$$CLIP_ROOT" -a -n "$$MEDIA_ROOT" || (echo "Set DATABASE_URL, CLIP_ROOT and MEDIA_ROOT"; exit 2)
	uv run --locked python -m food_recommender.cli.image --clip-root "$$CLIP_ROOT" index

.PHONY: evaluate-multimodal
evaluate-multimodal:
	@test -n "$$DATABASE_URL" -a -n "$$MINILM_ROOT" -a -n "$$CLIP_ROOT" -a -n "$$MEDIA_ROOT" || (echo "Set DATABASE_URL, MINILM_ROOT, CLIP_ROOT and MEDIA_ROOT"; exit 2)
	uv run --locked python scripts/evaluate_multimodal_retrieval.py --minilm-root "$$MINILM_ROOT" --clip-root "$$CLIP_ROOT" --queries ../evaluation/phase5/queries.json --output ../evaluation/phase5/comparison_report.json


.PHONY: verify-mcp-catalog smoke-food-trends
verify-mcp-catalog:
	@test -n "$$DATABASE_URL" -a -n "$$MINILM_ROOT" -a -n "$$CLIP_ROOT" -a -n "$$MEDIA_ROOT" || (echo "Set DATABASE_URL, MINILM_ROOT, CLIP_ROOT and MEDIA_ROOT"; exit 2)
	uv run --locked python scripts/verify_mcp_catalog.py --output ../evaluation/phase6/catalog_protocol_report.json

# Deliberate opt-in; this target can use up to two paid Tavily requests.
smoke-food-trends:
	@test "$$ENABLE_LIVE_TAVILY" = "1" || (echo "Set ENABLE_LIVE_TAVILY=1 to authorize the live smoke"; exit 2)
	uv run --locked python scripts/smoke_food_trends.py --enable-live --env-file ../.env --output ../evaluation/phase6/live_smoke_report.json

.PHONY: check-openai-capabilities smoke-agent-graph
# Explicit opt-in only; ordinary checks and readiness never call paid providers.
check-openai-capabilities:
	@test "$$ENABLE_LIVE_OPENAI" = "1" || (echo "Set ENABLE_LIVE_OPENAI=1 to authorize capability probes"; exit 2)
	uv run --locked python scripts/check_openai_capabilities.py --enable-live --env-file ../.env --output ../evaluation/openai-migration/capabilities.json

# An optional second environment file supplies explicit local database/model paths.
smoke-agent-graph:
	@test "$$ENABLE_LIVE_GRAPH" = "1" || (echo "Set ENABLE_LIVE_GRAPH=1 to authorize the paid full graph smoke and catalog transfer"; exit 2)
	uv run --locked python scripts/smoke_agent_graph.py --enable-live --env-file ../.env $(if $(GRAPH_SERVICE_ENV_FILE),--env-file "$(GRAPH_SERVICE_ENV_FILE)",) --output ../evaluation/openai-migration/live_graph_report.json

.PHONY: api-schema api-schema-check
api-schema:
	uv run --locked python scripts/export_openapi.py

api-schema-check:
	uv run --locked python scripts/export_openapi.py --check

.PHONY: evaluate-acceptance
evaluate-acceptance:
	uv run --locked python scripts/evaluate_phase10_acceptance.py

.PHONY: evaluate-phase10-retrieval
evaluate-phase10-retrieval:
	@test -n "$$DATABASE_URL" -a -n "$$MINILM_ROOT" -a -n "$$CLIP_ROOT" -a -n "$$MEDIA_ROOT" || (echo "Set DATABASE_URL, MINILM_ROOT, CLIP_ROOT and MEDIA_ROOT"; exit 2)
	uv run --locked python scripts/evaluate_multimodal_retrieval.py --minilm-root "$$MINILM_ROOT" --clip-root "$$CLIP_ROOT" --queries ../evaluation/phase10/retrieval_queries.json --output ../evaluation/phase10/retrieval_report.json
	uv run --locked python scripts/compare_phase10_retrieval.py

.PHONY: test-phase10
test-phase10:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin tests/contract/test_phase10_labels.py tests/unit/test_phase10_*.py

.PHONY: measure-phase10
measure-phase10:
	OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 uv run --locked python scripts/measure_phase10_performance.py

.PHONY: audit-langfuse-cloud
# Synthetic metadata export only; no paid inference and no normal conversation export.
audit-langfuse-cloud:
	@test "$$ENABLE_LANGFUSE_CLOUD" = "1" || (echo "Set ENABLE_LANGFUSE_CLOUD=1 for synthetic Cloud export"; exit 2)
	uv run --locked python -m scripts.audit_langfuse_cloud --enable-cloud

.PHONY: measure-telemetry export-phase10-scores purge-synthetic-traces
measure-telemetry:
	uv run --locked python -m scripts.measure_telemetry_overhead

export-phase10-scores:
	uv run --locked python -m scripts.export_phase10_scores

purge-synthetic-traces:
	@test "$$ENABLE_LANGFUSE_CLOUD" = "1" || (echo "Set ENABLE_LANGFUSE_CLOUD=1 for targeted synthetic deletion"; exit 2)
	uv run --locked python -m scripts.purge_langfuse_traces --enable-cloud
