"""Log and source/build scans reveal locations, never secret match values."""

import importlib.util
import json
import logging
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from food_recommender.infrastructure.media.downloads import CourseDownloader
from food_recommender.infrastructure.observability import StructuredFormatter
from food_recommender.ingestion.adapters import SourceError

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "phase10_secret_scan", ROOT / "scripts/scan_secrets.py"
)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def test_source_and_built_javascript_scan_redacts_match_values(tmp_path):
    token = "sk-" + "A" * 32
    paths = []
    for suffix in [".py", ".tsx", ".js", ".html", ".mjs", ".yaml"]:
        path = tmp_path / ("canary" + suffix)
        path.write_text('const leaked = "' + token + '";')
        paths.append(path)
    report = scanner.scan_files(paths, tmp_path)
    assert report["files_scanned"] == 6
    assert len(report["findings"]) == 6
    assert token not in json.dumps(report)
    assert all(
        row["line"] == 1 and row["pattern"] == "OpenAI token"
        for row in report["findings"]
    )


def test_logs_omit_message_exception_and_arbitrary_sensitive_fields():
    canary = "synthetic-private-value"
    record = logging.LogRecord(
        "provider",
        logging.ERROR,
        "private.py",
        1,
        canary,
        (),
        (ValueError, ValueError(canary), None),
    )
    record.event = "request_failed"
    record.request_id = uuid4()
    record.run_id = uuid4()
    record.stage = "recommendation"
    record.duration_ms = 12
    for key in [
        "headers",
        "profile",
        "image",
        "media",
        "api_key",
        "messages",
        "tool_arguments",
        "exception",
        "session_id",
    ]:
        setattr(record, key, canary)
    payload = StructuredFormatter().format(record)
    assert canary not in payload and "private.py" not in payload
    assert json.loads(payload)["duration_ms"] == 12
    assert json.loads(payload)["event"] == "request_failed"


HOST = "cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["::1"],
        ["169.254.169.254"],
        ["10.0.0.1"],
        ["fc00::1"],
        ["fe80::1"],
        ["::ffff:127.0.0.1"],
        ["8.8.8.8", "192.168.1.1"],
    ],
)
async def test_nonpublic_or_mixed_dns_answers_never_dispatch(addresses):
    async def resolve(host):
        return addresses

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: pytest.fail("Disallowed outbound request")
        )
    ) as client:
        with pytest.raises(SourceError):
            await CourseDownloader(client, resolve=resolve).download(
                f"https://{HOST}/food.png"
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        f"http://{HOST}/food.png",
        f"https://name:password@{HOST}/food.png",
        f"https://{HOST}:444/food.png",
        f"https://{HOST}/food.png#fragment",
    ],
)
async def test_unapproved_url_forms_are_rejected_before_dns(url):
    async def resolve(host):
        pytest.fail("Disallowed DNS query")

    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceError):
            await CourseDownloader(client, resolve=resolve).download(url)


def test_scan_preserves_private_dotenv_and_checks_example_without_following_links(
    tmp_path,
):
    token = "tvly-" + "X" * 24
    private = tmp_path / ".env"
    private.write_text(token)
    example = tmp_path / ".env.example"
    example.write_text(token)
    linked = tmp_path / "linked.js"
    linked.symlink_to(private)
    report = scanner.scan_files([private, example, linked], tmp_path)
    assert report["files_scanned"] == 1
    assert report["findings"] == [
        {"file": ".env.example", "line": 1, "pattern": "Tavily token"}
    ]
    assert private.read_text() == token
    assert token not in json.dumps(report)
