import json

import pytest

from food_recommender.ingestion.adapters import adapt_recipe
from food_recommender.ingestion.models import SeedItem
from food_recommender.ingestion.runner import ImportRunner


class Store:
    def __init__(self, fail_at=None):
        self.saved = {}
        self.fail_at = fail_at
        self.calls = 0

    async def upsert(self, item):
        self.calls += 1
        if self.calls == self.fail_at:
            raise RuntimeError("interruption")
        key = item.category, item.data.id
        status = "unchanged" if self.saved.get(key) == item.fingerprint else "imported"
        self.saved[key] = item.fingerprint
        return status


def items():
    return [
        SeedItem(adapt_recipe({"id": n, "name": "Soup"}, "recipes").data)
        for n in (1, 2)
    ]


@pytest.mark.asyncio
async def test_repeated_runs_use_content_hashes_and_durable_reports(tmp_path):
    store = Store()
    runner = ImportRunner(store, tmp_path / "manifest.json")
    first = await runner.run(items())
    second = await runner.run(items())
    assert first["totals"]["imported"] == 2
    assert second["totals"]["unchanged"] == 2
    assert json.loads((tmp_path / "manifest.json").read_text()) == second


@pytest.mark.asyncio
async def test_interruption_reports_pending_and_resumes_committed_items(tmp_path):
    store = Store(fail_at=2)
    runner = ImportRunner(store, tmp_path / "manifest.json")
    with pytest.raises(RuntimeError):
        await runner.run(items())
    report = json.loads((tmp_path / "manifest.json").read_text())
    assert report["status"] == "interrupted"
    assert report["totals"]["imported"] == 1 and report["totals"]["pending"] == 1
    store.fail_at = None
    resumed = await runner.run(items())
    assert resumed["totals"]["imported"] == 1 and resumed["totals"]["unchanged"] == 1
