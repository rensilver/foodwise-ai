from unittest.mock import AsyncMock

import pytest

from food_recommender.application.catalog.lookups import LookupService, RestaurantMatch


@pytest.mark.asyncio
async def test_lookup_distinguishes_ambiguity_and_no_match():
    store = AsyncMock()
    store.restaurants.return_value = (
        RestaurantMatch(id="1", name="Cafe", source_id="catalog"),
        RestaurantMatch(id="2", name="Cafe", source_id="catalog"),
    )
    service = LookupService(store)
    assert (await service.restaurant("Cafe")).status == "ambiguous"
    store.restaurants.return_value = ()
    assert (await service.restaurant("missing")).status == "no_match"
    store.reviews.return_value = ()
    assert (await service.review("1", "synthetic")).status == "no_match"
    store.restaurants.return_value = (
        RestaurantMatch(id="1", name="Cafe", source_id="catalog"),
    )
    assert (await service.restaurant("Cafe")).status == "matched"


@pytest.mark.asyncio
async def test_vibe_passes_literal_query_and_bounded_limit():
    store = AsyncMock()
    store.vibes.return_value = ()
    assert (await LookupService(store).vibe("quiet", 4)).status == "no_match"
    store.vibes.assert_awaited_once_with("quiet", 4)
    with pytest.raises(ValueError):
        await LookupService(store).vibe("quiet", 21)
