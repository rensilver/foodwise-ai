"""Bounded Pillow decoding shared by encoders and authorized media reads."""

import io
import warnings

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000


def decode_image(data: bytes) -> Image.Image:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Image exceeds byte limit or is empty")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if (
                    image.format not in {"JPEG", "PNG", "WEBP"}
                    or image.width * image.height > MAX_PIXELS
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError("Unsupported image format/dimensions/animation")
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                return image.convert("RGB")
    except (
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as error:
        raise ValueError("Invalid image") from error
