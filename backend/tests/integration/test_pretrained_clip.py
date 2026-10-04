import io
import os
from pathlib import Path

import pytest
from PIL import Image

from food_recommender.infrastructure.embeddings.clip import CLIPEncoder
from food_recommender.retrieval.embedding_contracts import validate_clip


@pytest.fixture(scope="module")
def clip():
    root = os.environ.get("TEST_CLIP_ROOT")
    if not root:
        pytest.skip("Set TEST_CLIP_ROOT to separately provisioned pretrained CLIP")
    return CLIPEncoder(Path(root))


def test_real_clip_text_and_image_queries_share_revision_and_normalization(clip):
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(buffer, format="PNG")
    image = clip.encode_images((buffer.getvalue(),))[0]
    text = clip.encode_texts(("a red square",))[0]
    for vector in (image, text):
        validate_clip(vector, clip.model_id, clip.revision)
    assert clip.model.device.type == "cpu"
    assert clip.encode_images((buffer.getvalue(),))[0] == image
    with pytest.raises(ValueError, match="token"):
        clip.encode_texts(("tomato " * 150,))
    with pytest.raises(ValueError):
        clip.encode_images((b"broken",))
