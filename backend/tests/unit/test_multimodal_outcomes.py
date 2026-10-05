import asyncio

import pytest
from test_text_fusion import hit

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.recommendations.contracts import multimodal_adapter
from food_recommender.retrieval.fusion import fuse
from food_recommender.retrieval.models import TextPlan
from food_recommender.retrieval.multimodal import MultimodalRetrieval
from food_recommender.retrieval.outcomes import TextRetrievalOutcome


class Text:
    def __init__(self, candidates=()):
        self.candidates = candidates

    async def run(self, plan):
        return TextRetrievalOutcome(
            "success" if self.candidates else "no_results",
            self.candidates,
            "model",
            "revision",
            0,
        )


class Images:
    def __init__(self, failure=None):
        self.failure = failure

    async def text(self, plan):
        if self.failure:
            raise self.failure
        return ()

    async def image(self, plan, media_id, session_id):
        return await self.text(plan)


@pytest.mark.asyncio
async def test_missing_dependency_does_not_hide_as_empty_and_success_reports_degradation():
    plan = TextPlan("pizza")
    assert (
        await MultimodalRetrieval(Text(), Images()).run(plan)
    ).status == "no_results"
    assert (
        await MultimodalRetrieval(None, None).run(plan)
    ).status == "dependency_error"
    assert (
        await MultimodalRetrieval(Text(), None).run(plan)
    ).status == "dependency_error"
    candidates = fuse((hit("a", "a"),), (), 20)
    result = await MultimodalRetrieval(Text(candidates), None).run(plan)
    assert (
        result.status == "success"
        and "Image dependency unavailable" in result.limitations
    )
    assert result.categories[0].fusion.text_weight == 1
    assert (
        multimodal_adapter.validate_json(multimodal_adapter.dump_json(result)) == result
    )


@pytest.mark.asyncio
async def test_unauthorized_image_and_invalid_encoding_abort_without_text_fallback():
    from uuid import uuid4

    candidates = fuse((hit("a", "a"),), (), 20)
    for error in [ApplicationError(ErrorCode.NOT_FOUND), ValueError("invalid")]:
        result = await MultimodalRetrieval(Text(candidates), Images(error)).run(
            TextPlan("pizza"), media_id="unknown", session_id=uuid4()
        )
        assert result.status == "invalid_request" and result.candidates == ()
    result = await MultimodalRetrieval(Text(candidates), None).run(
        TextPlan("pizza"), media_id="unknown", session_id=uuid4()
    )
    assert result.status == "dependency_error" and result.candidates == ()


@pytest.mark.asyncio
async def test_deadline_and_cancellation_propagation():
    class Slow(Images):
        async def text(self, plan):
            await asyncio.sleep(1)

    assert (
        await MultimodalRetrieval(Text(), Slow()).run(TextPlan("pizza"), timeout=0.01)
    ).status == "dependency_error"
    task = asyncio.create_task(
        MultimodalRetrieval(Text(), Slow()).run(TextPlan("pizza"))
    )
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
