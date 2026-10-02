"""Offline configuration contracts; all credentials here are synthetic."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from food_recommender.infrastructure.config import (
    ConfigurationError,
    Settings,
    load_settings,
)


def encoded_hash(*, memory: int = 65536, iterations: int = 3) -> str:
    """PHC-shaped test data, never a usable administrator credential."""
    salt = base64.b64encode(b"synthetic-salt!!x").decode().rstrip("=")
    digest = base64.b64encode(bytes(range(32))).decode().rstrip("=")
    return f"$argon2id$v=19$m={memory},t={iterations},p=1${salt}${digest}"


def environment() -> dict[str, str]:
    return {
        "GROQ_API_KEY": "synthetic-groq-credential",
        "DATABASE_URL": "postgresql://demo:synthetic-db-password@db:5432/foodwise",
        "MCP_SERVER_URL": "http://mcp:8001/mcp",
        "MEDIA_ROOT": "/tmp/foodwise-config-test-media",
        "ADMIN_PASSWORD_HASH": encoded_hash(),
    }


class SettingsTests(unittest.TestCase):
    def test_environment_defaults_and_typed_values(self) -> None:
        with patch.dict(os.environ, environment(), clear=True):
            settings = load_settings()
        self.assertEqual(settings.groq_model, "qwen/qwen3.8-27b")
        self.assertEqual(settings.groq_vision_model, "qwen/qwen3.8-27b")
        self.assertEqual(
            settings.groq_api_key.get_secret_value(), environment()["GROQ_API_KEY"]
        )
        self.assertTrue(
            settings.database_url.get_secret_value().startswith("postgresql+psycopg://")
        )
        self.assertEqual(str(settings.mcp_server_url), "http://mcp:8001/mcp")
        self.assertEqual(settings.media_root, Path(environment()["MEDIA_ROOT"]))
        self.assertIsNone(settings.tavily_api_key)

    def test_provider_overrides_are_independent(self) -> None:
        values = environment() | {
            "GROQ_MODEL": "configured/text-model",
            "GROQ_VISION_MODEL": "configured/vision-model",
            "TAVILY_API_KEY": "synthetic-tavily-credential",
        }
        with patch.dict(os.environ, values, clear=True):
            settings = load_settings()
        self.assertEqual(settings.groq_model, values["GROQ_MODEL"])
        self.assertEqual(settings.groq_vision_model, values["GROQ_VISION_MODEL"])
        self.assertEqual(
            settings.tavily_api_key.get_secret_value(), values["TAVILY_API_KEY"]
        )
        with patch.dict(
            os.environ, environment() | {"GROQ_MODEL": "custom-text"}, clear=True
        ):
            self.assertEqual(load_settings().groq_vision_model, "qwen/qwen3.8-27b")

    def test_blank_tavily_means_unavailable(self) -> None:
        for blank in ("", "   "):
            with (
                self.subTest(blank=blank),
                patch.dict(
                    os.environ, environment() | {"TAVILY_API_KEY": blank}, clear=True
                ),
            ):
                self.assertIsNone(load_settings().tavily_api_key)

    def test_required_fields_cannot_be_missing_or_empty(self) -> None:
        for field in environment():
            for value in (None, "", "  "):
                values = environment()
                if value is None:
                    values.pop(field)
                else:
                    values[field] = value
                with (
                    self.subTest(field=field, value=value),
                    patch.dict(os.environ, values, clear=True),
                ):
                    with self.assertRaises(ConfigurationError) as caught:
                        load_settings()
                    self.assertIn(field, str(caught.exception))

    def test_invalid_values_are_rejected(self) -> None:
        invalid = {
            "GROQ_API_KEY": ["contains spaces", "secret\n"],
            "TAVILY_API_KEY": ["contains spaces", "secret\n"],
            "GROQ_MODEL": ["", "  ", "model name", "model\n"],
            "GROQ_VISION_MODEL": ["", "model name"],
            "DATABASE_URL": [
                "sqlite:///database.db",
                "postgresql+asyncpg://u:p@db/name",
                "postgresql://u:p@db",
                "postgresql:///name",
                "postgresql://u:p@db:0/name",
                "postgresql://u:p@db:65536/name",
                "postgresql://u:p@db:bad/name",
                "not-a-url",
            ],
            "MCP_SERVER_URL": [
                "file:///tmp/mcp",
                "ws://mcp:8001/mcp",
                "http://",
                "http://user:password@mcp/mcp",
                "http://mcp/mcp#fragment",
                "http://mcp/mcp?token=secret",
                "http://mcp:0/mcp",
            ],
            "MEDIA_ROOT": ["relative/media", "~/media", "/", "/tmp/../etc"],
            "ADMIN_PASSWORD_HASH": [
                "plaintext-password",
                "a" * 64,
                encoded_hash(memory=1024),
                encoded_hash(iterations=1),
                encoded_hash(memory=99999999),
                encoded_hash(iterations=9999),
                encoded_hash().replace("$argon2id$", "$argon2i$"),
                encoded_hash().replace("$v=19$", "$v=16$"),
                encoded_hash().replace(",p=1$", ",p=99$"),
                encoded_hash().rsplit("$", 1)[0] + "$abc",
            ],
        }
        for field, values in invalid.items():
            for value in values:
                with (
                    self.subTest(field=field, value=value),
                    patch.dict(os.environ, environment() | {field: value}, clear=True),
                ):
                    with self.assertRaises(ConfigurationError):
                        load_settings()

    def test_secrets_are_redacted_from_representations_and_failures(self) -> None:
        values = environment() | {"TAVILY_API_KEY": "synthetic-tavily-credential"}
        with patch.dict(os.environ, values, clear=True):
            settings = load_settings()
        outputs = (
            repr(settings),
            str(settings),
            repr(settings.model_dump()),
            settings.model_dump_json(),
        )
        for output in outputs:
            for field in ("GROQ_API_KEY", "TAVILY_API_KEY", "ADMIN_PASSWORD_HASH"):
                self.assertNotIn(values[field], output)
            self.assertNotIn("synthetic-db-password", output)
        for field in values:
            with (
                self.subTest(field=field),
                patch.dict(
                    os.environ,
                    values | {field: "private-value with spaces"},
                    clear=True,
                ),
            ):
                with self.assertRaises(ConfigurationError) as caught:
                    load_settings()
                self.assertNotIn("private-value", str(caught.exception))

    def test_dotenv_is_explicit_and_environment_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "\n".join(f"{key}='{value}'" for key, value in environment().items())
                + "\nGROQ_MODEL=file-model\nUNRELATED_SETTING=ignored\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ, {"GROQ_MODEL": "environment-model"}, clear=True
            ):
                settings = load_settings(env_file=env_file)
            self.assertEqual(settings.groq_model, "environment-model")
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("os.getcwd", return_value=directory),
            ):
                with self.assertRaises(ConfigurationError):
                    load_settings()

    def test_initialization_overrides_environment(self) -> None:
        with patch.dict(os.environ, environment(), clear=True):
            settings = Settings(GROQ_MODEL="injected-model")
            self.assertEqual(settings.groq_model, "injected-model")

    def test_environment_names_are_exactly_the_documented_uppercase_aliases(
        self,
    ) -> None:
        with patch.dict(
            os.environ,
            {key.lower(): value for key, value in environment().items()},
            clear=True,
        ):
            with self.assertRaises(ConfigurationError):
                load_settings()

    def test_invalid_direct_inputs_and_errors_do_not_expose_secrets(self) -> None:
        with patch.dict(os.environ, environment(), clear=True):
            with self.assertRaises(ValidationError):
                Settings(MEDIA_ROOT="/tmp/\x00media")
            with self.assertRaises(ValidationError) as caught:
                Settings(DATABASE_URL="postgresql://u:private-db-value@db:bad/name")
        self.assertNotIn("private-db-value", str(caught.exception))

    def test_explicit_missing_dotenv_file_is_rejected(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, environment(), clear=True),
        ):
            with self.assertRaises(ConfigurationError) as caught:
                load_settings(env_file=Path(directory) / "absent.env")
        self.assertIn("ENV_FILE", str(caught.exception))

    def test_missing_configuration_has_field_specific_setup_guidance(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError) as caught:
                load_settings()
        message = str(caught.exception)
        for guidance in (
            "fresh Groq API key",
            "PostgreSQL connection URL",
            "HTTP(S) MCP endpoint",
            "absolute media directory",
            "Argon2id v19 password hash",
            ".env.example",
        ):
            self.assertIn(guidance, message)

    def test_invalid_configuration_has_safe_corrective_guidance(self) -> None:
        with patch.dict(
            os.environ, environment() | {"GROQ_MODEL": "private bad model"}, clear=True
        ):
            with self.assertRaises(ConfigurationError) as caught:
                load_settings()
        self.assertIn("model identifier", str(caught.exception))
        self.assertNotIn("private bad model", str(caught.exception))

    def test_configuration_cli_reports_only_status_and_safe_guidance(self) -> None:
        command = [sys.executable, "-m", "food_recommender.infrastructure.config"]
        for values, expected_status in ((environment(), 0), ({}, 2)):
            with self.subTest(status=expected_status):
                result = subprocess.run(
                    command, env=values, capture_output=True, text=True, timeout=10
                )
                self.assertEqual(result.returncode, expected_status, result.stderr)
                output = result.stdout + result.stderr
                for value in environment().values():
                    self.assertNotIn(value, output)
                self.assertNotIn("Traceback", output)
                if expected_status == 0:
                    self.assertIn("Configuration valid", output)
                    self.assertIn("Live trends unavailable", output)
                else:
                    self.assertIn("GROQ_API_KEY", output)
                    self.assertIn(".env.example", output)

    def test_example_requires_only_local_secrets_and_preserves_model_defaults(
        self,
    ) -> None:
        env_file = Path(__file__).resolve().parents[3] / ".env.example"
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigurationError) as caught:
                load_settings(env_file=env_file)
        message = str(caught.exception)
        for field in ("GROQ_API_KEY", "ADMIN_PASSWORD_HASH"):
            self.assertIn(field, message)
        for field in ("DATABASE_URL", "MCP_SERVER_URL", "MEDIA_ROOT"):
            self.assertNotIn(field, message)
        with patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": environment()["GROQ_API_KEY"],
                "ADMIN_PASSWORD_HASH": encoded_hash(),
            },
            clear=True,
        ):
            settings = load_settings(env_file=env_file)
        self.assertEqual(settings.groq_model, "qwen/qwen3.8-27b")
        self.assertEqual(settings.groq_vision_model, settings.groq_model)
        self.assertIsNone(settings.tavily_api_key)

    def test_loading_is_not_cached_and_settings_are_frozen(self) -> None:
        with patch.dict(os.environ, environment(), clear=True):
            first = load_settings()
            os.environ["GROQ_MODEL"] = "new-model"
            second = load_settings()
        self.assertNotEqual(first.groq_model, second.groq_model)
        with self.assertRaises(ValidationError):
            first.groq_model = "mutated"

    def test_import_and_loading_do_not_require_services_or_create_media(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import food_recommender.infrastructure.config"],
            env={},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            media_root = Path(directory) / "not-created"
            with patch.dict(
                os.environ, environment() | {"MEDIA_ROOT": str(media_root)}, clear=True
            ):
                load_settings()
            self.assertFalse(media_root.exists())


if __name__ == "__main__":
    unittest.main()
