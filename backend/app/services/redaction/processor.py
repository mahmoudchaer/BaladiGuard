from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlencode
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

from app.config import Settings, get_settings
from app.services.redaction.detector import (
    Detection,
    DetectionConfigurationError,
    DetectionProviderError,
    RedactionDetector,
)
from app.services.uploads.photo_upload_service import PhotoUploadService


class RedactionStorageError(RuntimeError):
    pass


class InvalidSourceImageError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    derivative_key: str | None
    source_fingerprint: str
    detector: str
    detector_version: str
    face_count: int
    plate_count: int
    minimum_confidence: float | None
    reason_code: str | None = None


class ImageRedactionProcessor:
    def __init__(
        self,
        detector: RedactionDetector,
        settings: Settings | None = None,
        *,
        s3_client=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.detector = detector
        self.s3 = s3_client or boto3.client("s3", region_name=self.settings.aws_region)

    def process(self, *, ticket_id: str, source_key: str, generation: int) -> ProcessingResult:
        bucket = self.settings.aws_s3_bucket
        if not bucket:
            raise RedactionStorageError("STORAGE_NOT_CONFIGURED")
        self._verify_ticket_binding(bucket, source_key, ticket_id)
        try:
            source = self.s3.get_object(Bucket=bucket, Key=source_key)["Body"].read()
        except (BotoCoreError, ClientError, KeyError, AttributeError) as exc:
            raise RedactionStorageError("ORIGINAL_READ_FAILED") from exc

        fingerprint = hashlib.sha256(source).hexdigest()
        image, detector_bytes = _normalize(source)
        try:
            detections = self.detector.detect(detector_bytes)
        except DetectionConfigurationError as exc:
            return self._private_result(fingerprint, str(exc))
        except DetectionProviderError:
            raise

        valid = [d for d in detections if _valid_detection(d)]
        minimum = min((d.confidence for d in valid), default=None)
        low_confidence = any(
            d.confidence < self.settings.image_redaction_auto_confidence for d in valid
        )
        blurred = _blur(
            image,
            valid,
            padding=self.settings.image_redaction_box_padding,
            radius=self.settings.image_redaction_blur_radius,
        )
        body = _metadata_free_jpeg(blurred)
        derivative_key = (
            f"reports/redacted/v1/{PhotoUploadService.ticket_scope(ticket_id)}/"
            f"g{generation}/{uuid4().hex}.jpg"
        )
        try:
            self.s3.put_object(
                Bucket=bucket,
                Key=derivative_key,
                Body=body,
                ContentType="image/jpeg",
                ServerSideEncryption="AES256",
                CacheControl="private, max-age=300",
                Tagging=urlencode(
                    {
                        "asset-class": "redacted-derivative",
                        "ticket-scope": PhotoUploadService.ticket_scope(ticket_id),
                        "generation": str(generation),
                        "approval-state": "review-required" if low_confidence else "approved",
                    }
                ),
                Metadata={"metadata-stripped": "true", "source-sha256": fingerprint},
            )
        except (BotoCoreError, ClientError) as exc:
            raise RedactionStorageError("DERIVATIVE_WRITE_FAILED") from exc

        return ProcessingResult(
            status="review_required" if low_confidence else "completed",
            derivative_key=derivative_key,
            source_fingerprint=fingerprint,
            detector=self.detector.name,
            detector_version=self.detector.version,
            face_count=sum(d.kind == "face" for d in valid),
            plate_count=sum(d.kind == "plate" for d in valid),
            minimum_confidence=minimum,
            reason_code="LOW_CONFIDENCE" if low_confidence else None,
        )

    def _verify_ticket_binding(self, bucket: str, source_key: str, ticket_id: str) -> None:
        if not source_key.startswith("reports/photos/v2/"):
            # Legacy fixtures remain processable in local tests, but production accepts v2 only.
            if self.settings.app_env in {"production", "staging"}:
                raise InvalidSourceImageError("INVALID_ORIGINAL_KEY")
            return
        try:
            tags = self.s3.get_object_tagging(Bucket=bucket, Key=source_key).get("TagSet", [])
        except (BotoCoreError, ClientError) as exc:
            raise RedactionStorageError("ORIGINAL_TAG_READ_FAILED") from exc
        tag_map = {item.get("Key"): item.get("Value") for item in tags}
        if tag_map.get("upload-state") != "linked" or tag_map.get(
            "ticket-scope"
        ) != PhotoUploadService.ticket_scope(ticket_id):
            raise InvalidSourceImageError("ORIGINAL_NOT_TICKET_BOUND")

    def _private_result(self, fingerprint: str, reason: str) -> ProcessingResult:
        return ProcessingResult(
            status="review_required",
            derivative_key=None,
            source_fingerprint=fingerprint,
            detector=self.detector.name,
            detector_version=self.detector.version,
            face_count=0,
            plate_count=0,
            minimum_confidence=None,
            reason_code=reason,
        )


def _normalize(contents: bytes) -> tuple[Image.Image, bytes]:
    try:
        with Image.open(BytesIO(contents)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.load()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidSourceImageError("INVALID_ORIGINAL_IMAGE") from exc
    output = BytesIO()
    image.save(output, format="JPEG", quality=90, optimize=True)
    return image, output.getvalue()


def _valid_detection(detection: Detection) -> bool:
    box = detection.box
    return (
        detection.kind in {"face", "plate"}
        and detection.confidence >= 0
        and box.width > 0
        and box.height > 0
        and box.left < 1
        and box.top < 1
        and box.left + box.width > 0
        and box.top + box.height > 0
    )


def _blur(image: Image.Image, detections: list[Detection], *, padding: float, radius: float):
    result = image.copy()
    width, height = result.size
    for detection in detections:
        box = detection.box
        pad_x = box.width * padding
        pad_y = box.height * padding
        left = max(0, int((box.left - pad_x) * width))
        top = max(0, int((box.top - pad_y) * height))
        right = min(width, int((box.left + box.width + pad_x) * width + 0.999))
        bottom = min(height, int((box.top + box.height + pad_y) * height + 0.999))
        if right <= left or bottom <= top:
            continue
        region = result.crop((left, top, right, bottom))
        effective_radius = max(radius, min(region.size) / 5)
        result.paste(region.filter(ImageFilter.GaussianBlur(effective_radius)), (left, top))
    return result


def _metadata_free_jpeg(image: Image.Image) -> bytes:
    output = BytesIO()
    image.convert("RGB").save(output, format="JPEG", quality=85, optimize=True)
    return output.getvalue()
