from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, ImageStat, UnidentifiedImageError

from app.config import Settings, get_settings
from app.services.content_safety.policy import AuthenticityResult

logger = logging.getLogger(__name__)

_WATERMARK_MODELS = (
    "amazon.titan-image-generator-v1",
    "amazon.nova-canvas-v1:0",
)


class AuthenticityDetector(Protocol):
    def inspect(self, image_bytes: bytes) -> AuthenticityResult: ...


class CompositeAuthenticityDetector:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        watermark_client: Any | None = None,
        learned_detector: AuthenticityDetector | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._watermark_client = watermark_client
        self._learned = learned_detector

    def inspect(self, image_bytes: bytes) -> AuthenticityResult:
        signals: list[str] = []
        score: float | None = None
        model: str | None = None
        version: str | None = None
        unavailable = False

        signals.extend(_file_clue_signals(image_bytes))
        watermark = self._detect_watermark(image_bytes)
        if watermark == "unavailable":
            unavailable = True
            signals.append("AUTH_UNAVAILABLE")
        elif watermark:
            signals.append("AUTH_AWS_WATERMARK")
        else:
            signals.append("AUTH_AWS_WATERMARK_ABSENT")

        learned = self._learned
        if learned is None:
            learned = OnnxAuthenticityDetector(self._settings)
            self._learned = learned
        try:
            learned_result = learned.inspect(image_bytes)
        except Exception:
            unavailable = True
            signals.append("AUTH_UNAVAILABLE")
            learned_result = AuthenticityResult(unavailable=True, signals=("AUTH_UNAVAILABLE",))
        if learned_result.unavailable:
            unavailable = True
        if learned_result.score is not None:
            score = learned_result.score
        if learned_result.model:
            model = learned_result.model
        if learned_result.model_version:
            version = learned_result.model_version
        signals.extend(learned_result.signals)

        unique = tuple(dict.fromkeys(signals))
        return AuthenticityResult(
            score=score,
            model=model,
            model_version=version,
            signals=unique,
            unavailable=unavailable,
        )

    def _detect_watermark(self, image_bytes: bytes) -> bool | str:
        client = self._watermark_client
        if client is None:
            try:
                import boto3

                client = boto3.client("bedrock-runtime", region_name=self._settings.aws_region)
            except Exception:
                return "unavailable"
        detect = getattr(client, "detect_generated_content", None)
        if not callable(detect):
            return "unavailable"
        generated = False
        saw_success = False
        for model_id in _WATERMARK_MODELS:
            try:
                response = detect(
                    foundationModelId=model_id,
                    content={"imageContent": {"bytes": image_bytes}},
                )
            except (BotoCoreError, ClientError, TypeError, AttributeError):
                continue
            saw_success = True
            result = str(response.get("detectionResult") or "").upper()
            confidence = str(response.get("confidenceLevel") or "").upper()
            if result == "GENERATED" and confidence in {"HIGH", "MEDIUM", ""}:
                generated = True
        if not saw_success:
            return "unavailable"
        return generated


class OnnxAuthenticityDetector:
    """Community Forensics DeepfakeDet ViT. Missing weights => unavailable, never reject."""

    def __init__(self, settings: Settings | None = None, *, session=None) -> None:
        self._settings = settings or get_settings()
        self._session = session
        configured = self._settings.authenticity_detection_model or ""
        self._model_path = Path(configured) if configured else Path()
        if self._session is None and self._model_path.is_file():
            try:
                self._session = self._load_session(self._model_path)
                logger.info("Loaded authenticity ONNX model path=%s", self._model_path)
            except Exception:
                logger.warning(
                    "Authenticity ONNX model failed to load path=%s",
                    self._model_path,
                    exc_info=True,
                )
                self._session = None

    def inspect(self, image_bytes: bytes) -> AuthenticityResult:
        if self._session is None:
            return AuthenticityResult(unavailable=True, signals=("AUTH_UNAVAILABLE",))
        try:
            tensor = _preprocess(image_bytes)
            input_name = self._session.get_inputs()[0].name
            outputs = self._session.run(None, {input_name: tensor})
            score = _fake_score(outputs[0])
        except Exception:
            logger.warning("Authenticity ONNX inference failed", exc_info=True)
            return AuthenticityResult(unavailable=True, signals=("AUTH_UNAVAILABLE",))
        signal = (
            "AUTH_ONNX_HIGH"
            if score >= self._settings.content_safety_authenticity_review_score
            else "AUTH_ONNX_LOW"
        )
        version = self._model_path.name or "community-forensics-deepfakedet-vit.onnx"
        return AuthenticityResult(
            score=score,
            model="community-forensics-deepfakedet-vit",
            model_version=version,
            signals=(signal,),
        )

    def _load_session(self, path: Path):
        import onnxruntime as ort

        return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def _file_clue_signals(image_bytes: bytes) -> list[str]:
    signals: list[str] = []
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            exif = image.getexif()
            software = str(exif.get(305) or "").lower()
            has_exif = bool(exif) and any(exif.values())
            if has_exif:
                signals.append("AUTH_EXIF_PRESENT")
            else:
                signals.append("AUTH_EXIF_MISSING")
            if "screenshot" in software or "snipping" in software:
                signals.append("AUTH_SCREENSHOT")
            gray = image.convert("L").resize((64, 64))
            variance = float(ImageStat.Stat(gray).var[0])
            if variance < 12:
                signals.append("AUTH_LOW_INFORMATION")
            elif _mostly_blank(gray):
                signals.append("AUTH_LOW_INFORMATION")
    except (UnidentifiedImageError, OSError, ValueError):
        signals.append("AUTH_UNAVAILABLE")
    return signals


def _mostly_blank(gray: Image.Image) -> bool:
    extrema = gray.getextrema()
    return extrema is not None and extrema[1] - extrema[0] < 8


def _preprocess(image_bytes: bytes):
    import numpy as np

    with Image.open(BytesIO(image_bytes)) as image:
        rgb = image.convert("RGB").resize((384, 384), Image.Resampling.BILINEAR)
        array = np.asarray(rgb).astype("float32") / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype="float32")
    std = np.array([0.229, 0.224, 0.225], dtype="float32")
    array = (array - mean) / std
    return array.transpose(2, 0, 1)[None, ...]


def _fake_score(output) -> float:
    import numpy as np

    values = np.asarray(output, dtype="float64").reshape(-1)
    if values.size == 1:
        score = float(values[0])
        if 0 <= score <= 1:
            return score
        return 1.0 / (1.0 + float(np.exp(-score)))
    # Two-class logits: index 1 is the synthetic/fake class when present.
    if values.size >= 2:
        logits = values[:2]
        shifted = logits - logits.max()
        probs = np.exp(shifted)
        probs = probs / probs.sum()
        return float(probs[1])
    return 0.0
