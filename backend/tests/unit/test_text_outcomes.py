import asyncio

import pytest

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.retrieval.models import TextPlan
from food_recommender.retrieval.service import TextRetrieval


class Encoder:
    model_id = "fixture"
    revision = "r1"
    max_tokens = 254

    def encode(self, texts):
        return ((1.0,) + (0.0,) * 383,)


class Search:
    def __init__(self, error=None):
        self.error = error

    async def search(self, *args, **kwargs):
        if self.error:
            raise self.error
        return ()


@pytest.mark.asyncio
async def test_no_results_dependency_error_and_cancellation_are_distinct():
    empty = await TextRetrieval(Search(), Encoder()).run(TextPlan("pizza"))
    assert (
        empty.status == "no_results"
        and empty.candidates == ()
        and empty.error_code is None
    )
    failed = await TextRetrieval(
        Search(ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)), Encoder()
    ).run(TextPlan("pizza"))
    assert (
        failed.status == "dependency_error"
        and failed.error_code == ErrorCode.DEPENDENCY_UNAVAILABLE
    )
    assert "password" not in str(failed)
    with pytest.raises(asyncio.CancelledError):
        await TextRetrieval(Search(asyncio.CancelledError()), Encoder()).run(
            TextPlan("pizza")
        )


@pytest.mark.asyncio
async def test_timeout_returns_typed_failure():
    class Slow(Search):
        async def search(self, *args, **kwargs):
            await asyncio.sleep(1)
            return ()

    result = await TextRetrieval(Slow(), Encoder()).run(TextPlan("pizza"), timeout=0.01)
    assert result.status == "dependency_error"
