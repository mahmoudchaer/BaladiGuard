"""Amazon Bedrock client for multimodal complaint classification."""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

import app.config  # noqa: F401 - ensure .env is loaded for standalone scripts

DEFAULT_BEDROCK_MODEL_ID = "amazon.nova-lite-v1:0"
SUPPORTED_IMAGE_FORMATS = frozenset({"jpeg", "png", "gif", "webp"})


class BedrockClassificationError(RuntimeError):
    """Raised when Bedrock cannot produce a usable classification payload."""


class BedrockClassificationClient:
    def __init__(
        self,
        *,
        model_id: str | None = None,
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model_id = (
            model_id or os.environ.get("BEDROCK_MODEL_ID", "").strip() or DEFAULT_BEDROCK_MODEL_ID
        )
        self.region_name = (
            region_name or os.environ.get("AWS_REGION", "us-east-1").strip() or "us-east-1"
        )
        self._client = client

    def _get_client(self):
        if self._client is None:
            kwargs: dict[str, Any] = {"region_name": self.region_name}
            access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
            secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
            if access_key and secret_key:
                kwargs["aws_access_key_id"] = access_key
                kwargs["aws_secret_access_key"] = secret_key
            self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def classify(
        self,
        *,
        system_prompt: str,
        user_text: str,
        image_bytes: bytes | None = None,
        image_format: str | None = None,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"text": user_text}]
        if image_bytes is not None:
            fmt = (image_format or "png").lower()
            if fmt == "jpg":
                fmt = "jpeg"
            if fmt not in SUPPORTED_IMAGE_FORMATS:
                raise BedrockClassificationError(f"Unsupported image format: {fmt}")
            content.append(
                {
                    "image": {
                        "format": fmt,
                        "source": {"bytes": image_bytes},
                    }
                }
            )

        try:
            response = self._get_client().converse(
                modelId=self.model_id,
                system=[{"text": system_prompt}],
                messages=[{"role": "user", "content": content}],
                inferenceConfig={
                    "maxTokens": 400,
                    "temperature": 0,
                },
                toolConfig={
                    "tools": [
                        {
                            "toolSpec": {
                                "name": "submit_classification",
                                "description": (
                                    "Submit the chosen municipal complaint category "
                                    "and a short explanation."
                                ),
                                "inputSchema": {
                                    "json": {
                                        "type": "object",
                                        "properties": {
                                            "category": {
                                                "type": "string",
                                                "description": (
                                                    "One allowed category key from the "
                                                    "system prompt allowlist."
                                                ),
                                            },
                                            "explanation": {
                                                "type": "string",
                                                "description": (
                                                    "Short explanation of why this "
                                                    "category was chosen."
                                                ),
                                            },
                                        },
                                        "required": ["category", "explanation"],
                                    }
                                },
                            }
                        }
                    ],
                    "toolChoice": {"tool": {"name": "submit_classification"}},
                },
            )
        except (BotoCoreError, ClientError) as exc:
            raise BedrockClassificationError("Bedrock classification request failed.") from exc

        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: dict[str, Any]) -> dict[str, Any]:
        message = response.get("output", {}).get("message", {})
        content_blocks = message.get("content") or []

        for block in content_blocks:
            tool_use = block.get("toolUse")
            if not tool_use:
                continue
            payload = tool_use.get("input")
            if isinstance(payload, dict):
                return payload
            if isinstance(payload, str):
                try:
                    parsed = json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise BedrockClassificationError(
                        "Bedrock tool payload was not valid JSON."
                    ) from exc
                if isinstance(parsed, dict):
                    return parsed

        # Fallback: some models may return plain JSON text instead of tool use.
        for block in content_blocks:
            text = block.get("text")
            if not text:
                continue
            parsed = BedrockClassificationClient._extract_json_object(text)
            if parsed is not None:
                return parsed

        raise BedrockClassificationError("Bedrock response did not include classification JSON.")

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        stripped = text.strip()
        try:
            parsed = json.loads(stripped)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None


bedrock_classification_client = BedrockClassificationClient()
