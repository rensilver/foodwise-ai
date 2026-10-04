import io
import zipfile

import httpx
import pytest
from PIL import Image

from food_recommender.infrastructure.media.downloads import CourseDownloader
from food_recommender.ingestion.adapters import SourceError
from food_recommender.ingestion.images import prepare_image, recipe_archive


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


@pytest.mark.parametrize(
    "kind",
    [
        "empty_file",
        "empty_zip",
        "directory_only",
        "corrupt",
        "duplicate_identity",
        "symlink",
        "expansion",
        "crc",
    ],
)
def test_archive_failure_matrix(tmp_path, kind):
    path = tmp_path / "recipes.zip"
    if kind == "empty_file":
        path.write_bytes(b"")
    elif kind == "corrupt":
        path.write_bytes(b"PK corrupt")
    else:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as handle:
            if kind == "directory_only":
                handle.writestr("synthetic_recipe_images/", b"")
            elif kind == "duplicate_identity":
                handle.writestr("recipe1.png", png())
                handle.writestr("synthetic_recipe_images/recipe1.png", png())
            elif kind == "symlink":
                info = zipfile.ZipInfo("recipe1.png")
                info.create_system = 3
                info.external_attr = 0o120777 << 16
                handle.writestr(info, png())
            elif kind == "expansion":
                handle.writestr(
                    "recipe1.png", b"x" * 1000000, compress_type=zipfile.ZIP_DEFLATED
                )
            elif kind == "crc":
                handle.writestr("recipe1.png", png())
        if kind == "crc":
            content = bytearray(path.read_bytes())
            content[30 + len("recipe1.png") + 12] ^= 1
            path.write_bytes(content)
    with pytest.raises(SourceError):
        recipe_archive(path, {"1"}, tmp_path / "media")
    assert not (tmp_path / "media").exists()


def test_missing_and_duplicate_media_are_reported_without_placeholder(tmp_path):
    path = tmp_path / "recipes.zip"
    archive(path, ["synthetic_recipe_images/recipe2.png"])
    report = recipe_archive(path, {"1", "2"}, tmp_path / "media")
    assert report.missing == ("1",) and set(report.images) == {"2"}
    first = report.images["2"]
    repeated = recipe_archive(path, {"1", "2"}, tmp_path / "media")
    assert repeated.images["2"] == first
    assert len(list((tmp_path / "media").iterdir())) == 1


def test_storage_symlink_and_decode_limits(tmp_path, monkeypatch):
    import food_recommender.ingestion.images as module

    real = tmp_path / "real"
    real.mkdir()
    root = tmp_path / "link"
    root.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        prepare_image(png(), root)
    assert list(real.iterdir()) == []
    monkeypatch.setattr(module, "MAX_PIXELS", 1)
    with pytest.raises(SourceError):
        prepare_image(png(), real)
    monkeypatch.setattr(module, "MAX_BYTES", 1)
    with pytest.raises(SourceError):
        prepare_image(png(), real)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        "oversized_header",
        "oversized_body",
        "timeout",
        "redirect_loop",
        "empty",
        "mixed_dns",
    ],
)
async def test_bounded_download_failures(kind, monkeypatch):
    import food_recommender.infrastructure.media.downloads as module

    monkeypatch.setattr(module, "MAX_BYTES", 100)
    calls = []

    def respond(request):
        calls.append(request)
        if kind == "oversized_header":
            return httpx.Response(200, headers={"Content-Length": "101"}, content=b"x")
        if kind == "oversized_body":
            return httpx.Response(200, content=b"x" * 101)
        if kind == "timeout":
            raise httpx.ReadTimeout("synthetic")
        if kind == "redirect_loop":
            return httpx.Response(302, headers={"Location": "/again"})
        return httpx.Response(200, content=b"")

    async def resolve(host):
        return ["8.8.8.8", "127.0.0.1"] if kind == "mixed_dns" else ["8.8.8.8"]

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SourceError):
            await CourseDownloader(client, resolve=resolve).download(
                "https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/a.png"
            )
    assert len(calls) <= 4
    if kind == "mixed_dns":
        assert calls == []
