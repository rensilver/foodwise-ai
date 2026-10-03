import io

import pytest
from PIL import Image

from food_recommender.infrastructure.clip_encoder import MAX_BYTES, decode_image


@pytest.mark.parametrize("format", ["JPEG", "PNG", "WEBP"])
def test_query_images_are_decoded_as_rgb(format):
    buffer = io.BytesIO()
    Image.new("RGB", (24, 24), "red").save(buffer, format=format)
    image = decode_image(buffer.getvalue())
    assert image.mode == "RGB" and image.size == (24, 24)
    image.close()


@pytest.mark.parametrize(
    "data", [b"", b"not an image", b'<svg onload="alert(1)"/>', b"x" * (MAX_BYTES + 1)]
)
def test_malformed_empty_unsupported_and_oversized_uploads_rejected(data):
    with pytest.raises(ValueError):
        decode_image(data)


def test_pixel_limit_animation_and_truncated_images_rejected():
    buffer = io.BytesIO()
    Image.new("RGB", (5000, 4001)).save(buffer, format="PNG")
    with pytest.raises(ValueError):
        decode_image(buffer.getvalue())
    buffer = io.BytesIO()
    frames = [Image.new("RGB", (24, 24), color) for color in ("red", "blue")]
    frames[0].save(buffer, format="PNG", save_all=True, append_images=frames[1:])
    with pytest.raises(ValueError):
        decode_image(buffer.getvalue())
    with pytest.raises(ValueError):
        decode_image(buffer.getvalue()[:80])
