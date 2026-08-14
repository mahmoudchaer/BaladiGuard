from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image

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
    name = "aws-rekognition+open-image-models"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client=None,
        plate_detector=None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client or boto3.client("rekognition", region_name=self._settings.aws_region)
        self._plate_detector = plate_detector
        model_name = Path(self._settings.plate_detection_model).name
        self.version = f"detect-faces+open-image-models-0.6.0+{model_name}"

    def detect(self, image_bytes: bytes) -> list[Detection]:
        try:
            faces = self._client.detect_faces(
                Image={"Bytes": image_bytes}, Attributes=["DEFAULT"]
            ).get("FaceDetails", [])
        except (BotoCoreError, ClientError) as exc:
            raise DetectionProviderError("DETECTION_PROVIDER_UNAVAILABLE") from exc

        try:
            detections = [
                Detection("face", float(item["Confidence"]), _box(item["BoundingBox"]))
                for item in faces
            ]
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            raise DetectionProviderError("MALFORMED_DETECTION_OUTPUT") from exc
        detections.extend(self._detect_plates(image_bytes))
        return detections

    def _detect_plates(self, image_bytes: bytes) -> list[Detection]:
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                rgb = image.convert("RGB")
                width, height = rgb.size
                # OpenCV-based detectors expect BGR channel order.
                import numpy as np

                frame = np.asarray(rgb)[:, :, ::-1].copy()
            if self._plate_detector is None:
                self._plate_detector = self._build_plate_detector()
            detector = self._plate_detector
            results = detector.predict(frame)

            detections: list[Detection] = []
            for item in results:
                box = item.bounding_box
                confidence = float(item.confidence)
                x1, y1, x2, y2 = map(float, (box.x1, box.y1, box.x2, box.y2))
                if (
                    width <= 0
                    or height <= 0
                    or not all(math.isfinite(value) for value in (confidence, x1, y1, x2, y2))
                    or not 0 <= confidence <= 1
                    or x2 <= x1
                    or y2 <= y1
                ):
                    raise DetectionProviderError("MALFORMED_DETECTION_OUTPUT")
                detections.append(
                    Detection(
                        "plate",
                        confidence * 100,
                        BoundingBox(
                            left=x1 / width,
                            top=y1 / height,
                            width=(x2 - x1) / width,
                            height=(y2 - y1) / height,
                        ),
                    )
                )
        except (DetectionConfigurationError, DetectionProviderError):
            raise
        except Exception as exc:
            raise DetectionProviderError("PLATE_DETECTOR_UNAVAILABLE") from exc
        return detections

    def _build_plate_detector(self):
        try:
            from open_image_models import create_detector
        except ImportError as exc:
            raise DetectionConfigurationError("PLATE_DETECTOR_NOT_INSTALLED") from exc

        model = self._settings.plate_detection_model
        if model.lower().endswith(".onnx"):
            return create_detector(
                model,
                backend="yolo_v9",
                class_labels=("License Plate",),
                conf_thresh=0.01,
                providers=["CPUExecutionProvider"],
            )
        return create_detector(
            model,
            conf_thresh=0.01,
            providers=["CPUExecutionProvider"],
        )


def _box(value: dict) -> BoundingBox:
    return BoundingBox(
        left=float(value.get("Left", 0)),
        top=float(value.get("Top", 0)),
        width=float(value.get("Width", 0)),
        height=float(value.get("Height", 0)),
    )
