import io
import zipfile

import httpx
import pytest
from PIL import Image

from food_recommender.ingestion.adapters import SourceError
from food_recommender.ingestion.images import (
    CourseDownloader,
    prepare_image,
    recipe_archive,
)


def png():
    stream = io.BytesIO()
    Image.new("RGB", (4, 3)).save(stream, format="PNG")
    return stream.getvalue()


def archive(path, names):
    with zipfile.ZipFile(path, "w") as handle:
        for name in names:
            handle.writestr(name, png())


def test_id_associations_generated_names_and_missing_extra(tmp_path):
    path = tmp_path / "recipes.zip"
    archive(path, ["recipe10.png", "recipe2.png", "recipe99.png"])
    report = recipe_archive(path, {"2", "10", "3"}, tmp_path / "media")
    assert set(report.images) == {"2", "10"}
    assert report.missing == ("3",) and report.extra == ("99",)
    for image in report.images.values():
        assert image.storage_key != "recipe2.png"
        assert (tmp_path / "media" / image.storage_key).is_file()
        assert (image.width, image.height) == (4, 3)


@pytest.mark.parametrize(
    "name",
    [
        "../recipe1.png",
        "/recipe1.png",
        "folder/recipe1.png",
        "recipe01.png",
        "other.png",
        "recipe1\\.png",
    ],
)
def test_unsafe_archive_rejected_before_writes(tmp_path, name):
    path = tmp_path / "recipes.zip"
    archive(path, ["recipe1.png", name])
    with pytest.raises(SourceError):
        recipe_archive(path, {"1"}, tmp_path / "media")
    assert not (tmp_path / "media").exists()


def test_decode_limits_and_metadata(tmp_path):
    with pytest.raises(SourceError):
        prepare_image(b"not image", tmp_path)
    image = prepare_image(png(), tmp_path)
    assert image.mime_type == "image/png"
    with Image.open(tmp_path / image.storage_key) as decoded:
        assert decoded.info == {}


@pytest.mark.asyncio
async def test_download_redirects_revalidate_and_pin_public_address():
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://127.0.0.1/secret"})

    async def resolve(host):
        return ["8.8.8.8"]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond), follow_redirects=True
    ) as client:
        downloader = CourseDownloader(client, resolve=resolve)
        with pytest.raises(SourceError):
            await downloader.download(
                "https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/image.png"
            )
    assert len(seen) == 1
    assert seen[0].url.host == "8.8.8.8"
    assert (
        seen[0].headers["host"]
        == "cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud"
    )


@pytest.mark.asyncio
async def test_private_resolution_and_unapproved_hosts_blocked():
    async def resolve(host):
        return ["10.0.0.1"]

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: pytest.fail("Network request"))
    ) as client:
        downloader = CourseDownloader(client, resolve=resolve)
        for url in [
            "http://example.org/x",
            "https://evil.example/x",
            "https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/x",
        ]:
            with pytest.raises(SourceError):
                await downloader.download(url)
