from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings


@dataclass(frozen=True)
class BoundingBox:
    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True)
class Detection:
    kind: str
    confidence: float
    box: BoundingBox


class DetectionProviderError(RuntimeError):
    """Transient provider failure; safe message/code only."""


class DetectionConfigurationError(RuntimeError):
    """Provider is not ready; image must remain private."""


class RedactionDetector(Protocol):
    name: str
    version: str

    def detect(self, image_bytes: bytes) -> list[Detection]: ...


class DisabledRedactionDetector:
    name = "disabled"
    version = "v1"

    def detect(self, image_bytes: bytes) -> list[Detection]:
        del image_bytes
        raise DetectionConfigurationError("IMAGE_REDACTION_DISABLED")


class AwsRekognitionDetector:
    name = "aws-rekognition"
    version = "detect-faces+custom-labels-v1"

    def __init__(self, settings: Settings | None = None, *, client=None) -> None:
        self._settings = settings or get_settings()
        self._client = client or boto3.client("rekognition", region_name=self._settings.aws_region)

    def detect(self, image_bytes: bytes) -> list[Detection]:
        model_arn = self._settings.rekognition_plate_model_arn
        if not model_arn:
            raise DetectionConfigurationError("PLATE_MODEL_NOT_CONFIGURED")
        try:
            faces = self._client.detect_faces(
                Image={"Bytes": image_bytes}, Attributes=["DEFAULT"]
            ).get("FaceDetails", [])
            labels = self._client.detect_custom_labels(
                Image={"Bytes": image_bytes},
                ProjectVersionArn=model_arn,
                # Ask for every plate-label candidate so confidence policy is
                # applied locally and low-confidence results cannot look like "none".
                MinConfidence=0,
            ).get("CustomLabels", [])
        except (BotoCoreError, ClientError) as exc:
            raise DetectionProviderError("DETECTION_PROVIDER_UNAVAILABLE") from exc

        detections = [
            Detection("face", float(item.get("Confidence", 0)), _box(item.get("BoundingBox")))
            for item in faces
            if item.get("BoundingBox")
        ]
        for item in labels:
            geometry = item.get("Geometry") or {}
            box = geometry.get("BoundingBox")
            if box and _is_plate_label(str(item.get("Name", ""))):
                detections.append(Detection("plate", float(item.get("Confidence", 0)), _box(box)))
        return detections


def _box(value: dict) -> BoundingBox:
    return BoundingBox(
        left=float(value.get("Left", 0)),
        top=float(value.get("Top", 0)),
        width=float(value.get("Width", 0)),
        height=float(value.get("Height", 0)),
    )


def _is_plate_label(name: str) -> bool:
    normalized = name.strip().lower().replace("_", " ").replace("-", " ")
    return normalized in {"license plate", "licence plate", "number plate", "vehicle plate"}
