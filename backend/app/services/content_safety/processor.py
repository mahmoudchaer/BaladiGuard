from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.services.content_safety.authenticity import (
    AuthenticityDetector,
    CompositeAuthenticityDetector,
)
from app.services.content_safety.image_moderator import RekognitionImageModerator
from app.services.content_safety.policy import (
    AuthenticityResult,
    ImageSafetyResult,
    SafetyDecision,
    TextSafetyResult,
    combine_safety_signals,
)
from app.services.content_safety.text_moderator import (
    BedrockTextModerator,
    TextModerationProviderError,
)
from app.services.content_safety.text_rules import evaluate_text_rules
from app.services.redaction.detector import DetectionProviderError
from app.services.uploads.photo_upload_service import PhotoUploadService


class ContentSafetyStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContentSafetyProcessingResult:
    decision: SafetyDecision


class ContentSafetyProcessor:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        s3_client=None,
        text_moderator: BedrockTextModerator | None = None,
        image_moderator: RekognitionImageModerator | None = None,
        authenticity_detector: AuthenticityDetector | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.s3 = s3_client or boto3.client("s3", region_name=self.settings.aws_region)
        self.text_moderator = text_moderator or BedrockTextModerator(
            model_id=self.settings.content_safety_text_model_id
        )
        self.image_moderator = image_moderator or RekognitionImageModerator(self.settings)
        self.authenticity = authenticity_detector or CompositeAuthenticityDetector(self.settings)

    def process(
        self, *, ticket_id: str, source_key: str, description: str | None
    ) -> SafetyDecision:
        image_bytes = self._load_image(ticket_id, source_key) if source_key else None
        text = self._moderate_text(description)
        image = self._moderate_image(image_bytes)
        authenticity = self._inspect_authenticity(image_bytes)
        return combine_safety_signals(
            text=text,
            image=image,
            authenticity=authenticity,
            fail_closed=self.settings.content_safety_fail_closed,
            authenticity_review_score=self.settings.content_safety_authenticity_review_score,
        )

    def _moderate_text(self, description: str | None) -> TextSafetyResult:
        deterministic = evaluate_text_rules(description)
        if deterministic is not None and deterministic.reason_code != "TEXT_PROMPT_INJECTION":
            return deterministic
        try:
            result = self.text_moderator.moderate(
                " ".join((description or "").split()) or "(empty)"
            )
        except TextModerationProviderError:
            if deterministic is not None:
                return deterministic
            return TextSafetyResult(
                reason_code="TEXT_PROVIDER_UNAVAILABLE",
                severity="medium",
                provider_unavailable=True,
            )
        if deterministic is not None and result.severity in {"none", "low"}:
            return deterministic
        return result

    def _moderate_image(self, image_bytes: bytes | None) -> ImageSafetyResult:
        if image_bytes is None:
            return ImageSafetyResult(reason_code="IMAGE_UNAVAILABLE", severity="none")
        try:
            return self.image_moderator.moderate(image_bytes)
        except DetectionProviderError:
            return ImageSafetyResult(
                reason_code="IMAGE_PROVIDER_UNAVAILABLE",
                severity="medium",
                provider_unavailable=True,
            )

    def _inspect_authenticity(self, image_bytes: bytes | None) -> AuthenticityResult:
        if image_bytes is None:
            return AuthenticityResult(unavailable=True, signals=("AUTH_UNAVAILABLE",))
        return self.authenticity.inspect(image_bytes)

    def _load_image(self, ticket_id: str, source_key: str) -> bytes | None:
        if not source_key or source_key == "unavailable":
            return None
        bucket = self.settings.aws_s3_bucket
        if not bucket:
            if self.settings.content_safety_fail_closed:
                raise ContentSafetyStorageError("STORAGE_NOT_CONFIGURED")
            return None
        self._verify_ticket_binding(bucket, source_key, ticket_id)
        try:
            return self.s3.get_object(Bucket=bucket, Key=source_key)["Body"].read()
        except (BotoCoreError, ClientError, KeyError, AttributeError) as exc:
            raise ContentSafetyStorageError("ORIGINAL_READ_FAILED") from exc

    def _verify_ticket_binding(self, bucket: str, source_key: str, ticket_id: str) -> None:
        try:
            tags = {
                item["Key"]: item["Value"]
                for item in self.s3.get_object_tagging(Bucket=bucket, Key=source_key).get(
                    "TagSet", []
                )
            }
        except (BotoCoreError, ClientError, KeyError, TypeError) as exc:
            raise ContentSafetyStorageError("ORIGINAL_TAGS_UNAVAILABLE") from exc
        expected = PhotoUploadService.ticket_scope(ticket_id)
        if tags.get("upload-state") != "linked" or tags.get("ticket-scope") != expected:
            raise ContentSafetyStorageError("ORIGINAL_NOT_BOUND")
