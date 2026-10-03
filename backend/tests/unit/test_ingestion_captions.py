import io

import pytest
from PIL import Image

from food_recommender.ingestion.adapters import SourceError
from food_recommender.ingestion.captions import CaptionService, supplied_captions


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_supplied_caption_provenance_and_missing_caption_gaps():
    captions, gaps = supplied_captions(
        {"image_captions": ["A bowl"]}, ["url1", "url2"], source="reviews", record_id=9
    )
    assert captions[0].attribution == "imported"
    assert captions[0].generator is None
    assert captions[0].text == "A bowl"
    assert gaps == ("url2",)
    assert supplied_captions({}, ["url"], source="reviews", record_id=9) == (
        (),
        ("url",),
    )
    with pytest.raises(SourceError):
        supplied_captions(
            {"image_captions": ["x", "y"]}, ["url"], source="reviews", record_id=9
        )


@pytest.mark.asyncio
async def test_vision_is_separate_cached_and_preserves_imported(tmp_path):
    class Vision:
        model = "vision-model"
        calls = 0

        async def generate(self, messages, schema, *, image=None):
            self.calls += 1
            assert image.startswith("data:image/png;base64,")
            assert "allergen" in messages[0]["content"]
            return '{"text":"A bowl of food"}'

    vision = Vision()
    service = CaptionService(vision, tmp_path)
    supplied, _ = supplied_captions(
        {"image_description": "Imported bowl"},
        ["recipe1.png"],
        source="recipes",
        record_id=1,
    )
    assert (
        await service.caption(png(), "image/png", supplied=supplied[0])
    ).text == "Imported bowl"
    assert vision.calls == 0
    first = await service.caption(png(), "image/png")
    second = await service.caption(png(), "image/png")
    assert first == second and vision.calls == 1
    assert first.attribution == "generated" and first.generator == "vision-model"
    assert first.input_hash is not None


@pytest.mark.asyncio
async def test_bad_image_never_reaches_provider(tmp_path):
    class Vision:
        model = "vision"

        async def generate(self, *args, **kwargs):
            pytest.fail("Bad image reached inference")

    with pytest.raises(SourceError):
        await CaptionService(Vision(), tmp_path).caption(b"bad", "image/png")
