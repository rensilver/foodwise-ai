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

from food_recommender.infrastructure.providers.openai import OpenAIStructuredInference


class ProbeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", case_sensitive=True, hide_input_in_errors=True
    )
    OPENAI_API_KEY: SecretStr
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_VISION_MODEL: str = "gpt-4o-mini"


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
            ("text_structured", settings.OPENAI_MODEL, None),
            ("vision_structured", settings.OPENAI_VISION_MODEL, image),
        ):
            provider = OpenAIStructuredInference(client, settings.OPENAI_API_KEY, model)
            try:
                expected = {"ok": True} if media is None else {"color": "red"}
                selected_schema = (
                    schema
                    if media is None
                    else {
                        "type": "object",
                        "properties": {
                            "color": {
                                "type": "string",
                                "enum": ["red", "green", "blue", "unknown"],
                            }
                        },
                        "required": ["color"],
                        "additionalProperties": False,
                    }
                )
                prompt = (
                    'Return {"ok":true} if you can process this request.'
                    if media is None
                    else "Identify the dominant color of the supplied image. Choose red, green, blue or unknown; return only the color field in JSON."
                )
                content = await provider.generate(
                    [
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    selected_schema,
                    image=media,
                )
                passed = json.loads(content) == expected
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
