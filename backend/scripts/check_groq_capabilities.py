"""Explicit provider probes; no model fallback and no credential/body output."""

import argparse
import asyncio
import base64
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from food_recommender.infrastructure.providers.groq import GroqStructuredInference


class ProbeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", case_sensitive=True, hide_input_in_errors=True
    )
    GROQ_API_KEY: SecretStr
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_VISION_MODEL: str = "qwen/qwen3.8-27b"


async def probe(settings: ProbeSettings) -> dict[str, object]:
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    image_buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(image_buffer, format="PNG")
    image = (
        "data:image/png;base64," + base64.b64encode(image_buffer.getvalue()).decode()
    )
    outcomes = []
    async with httpx.AsyncClient(follow_redirects=False) as client:
        for capability, model, media in (
            ("text_structured", settings.GROQ_MODEL, None),
            ("vision_structured", settings.GROQ_VISION_MODEL, image),
        ):
            provider = GroqStructuredInference(client, settings.GROQ_API_KEY, model)
            try:
                content = await provider.generate(
                    [
                        {
                            "role": "user",
                            "content": 'Return {"ok":true} if you can process this request.',
                        }
                    ],
                    schema,
                    image=media,
                )
                passed = json.loads(content) == {"ok": True}
            except Exception:
                passed = False
            outcomes.append(
                {
                    "capability": capability,
                    "model": model,
                    "passed": passed,
                    "usage": provider.usage,
                }
            )
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "enabled_explicitly": True,
        "outcomes": outcomes,
        "passed": all(item["passed"] for item in outcomes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.enable_live:
        parser.error("Live calls require --enable-live")
    try:
        report = asyncio.run(probe(ProbeSettings(_env_file=args.env_file)))
    except Exception:
        print("Capability probe failed; configuration diagnostics redacted")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "outcomes": [
                    {"capability": item["capability"], "passed": item["passed"]}
                    for item in report["outcomes"]
                ],
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
