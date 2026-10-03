import hashlib

import pytest

from food_recommender.ingestion.adapters import SourceError
from food_recommender.ingestion.reconciliation import reconcile, stable_addition_id


def row(n, text, item_id=None):
    return {
        "paragraph": n,
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "itemId": item_id,
    }


def test_all_paragraphs_accounted_and_addition_ids_stable():
    paragraphs = ["Existing", "New"]
    result = reconcile(paragraphs, [row(1, "Existing", 5), row(2, "New")], {"5"})
    assert result[0].entity_id == "5"
    assert result[1].status == "unresolved"
    accepted = {result[1].content_hash: {"name": "New restaurant"}}
    result = reconcile(
        paragraphs, [row(1, "Existing", 5), row(2, "New")], {"5"}, accepted
    )
    assert result[1].entity_id == stable_addition_id(result[1].content_hash)
    assert result[1].status == "accepted_addition"
    assert result[1].text == "New"


@pytest.mark.parametrize(
    "rows",
    [
        [row(1, "wrong", 5)],
        [row(1, "Existing", 6)],
        [row(1, "Existing", 5), row(2, "New", 5)],
        [],
    ],
)
def test_stale_or_incomplete_mappings_fail(rows):
    with pytest.raises(SourceError):
        reconcile(["Existing", "New"], rows, {"5"})


def test_unknown_acceptance_hash_rejected():
    with pytest.raises(SourceError):
        reconcile(["New"], [row(1, "New")], set(), {"f" * 64: {"name": "Other"}})
