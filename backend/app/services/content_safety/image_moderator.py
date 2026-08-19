from __future__ import annotations

from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.services.content_safety.policy import ImageSafetyResult
from app.services.redaction.detector import DetectionProviderError

SEXUAL_LABELS = frozenset(
    {
        "explicit nudity",
        "explicit",
        "nudity",
        "sexual activity",
        "sexually suggestive",
        "non-explicit nudity",
        "graphic female nudity",
        "graphic male nudity",
        "sexual situations",
        "illustrated nudity or sexual activity",
        "adult",
    }
)
HATE_LABELS = frozenset(
    {
        "hate symbols",
        "nazi party",
        "white supremacy",
        "extremist",
        "hate",
    }
)
VIOLENCE_LABELS = frozenset(
    {
        "graphic violence or gore",
        "violence",
        "visually disturbing",
        "emaciated bodies",
        "corpses",
        "hanging",
        "explosions and blasts",
        "physical violence",
        "blood and gore",
    }
)
DRUG_LABELS = frozenset(
    {
        "drugs",
        "drug products",
        "pills",
        "drug use",
        "drug paraphernalia",
    }
)
WEAPON_LABELS = frozenset(
    {
        "weapons",
        "firearms",
        "knives",
    }
)


class RekognitionImageModerator:
    def __init__(self, settings: Settings | None = None, *, client=None) -> None:
        self._settings = settings or get_settings()
        self._client = client

    def moderate(self, image_bytes: bytes) -> ImageSafetyResult:
        client = self._client
        if client is None:
            import boto3

            client = boto3.client("rekognition", region_name=self._settings.aws_region)
        try:
            response = client.detect_moderation_labels(
                Image={"Bytes": image_bytes},
                MinConfidence=self._settings.content_safety_image_review_confidence,
            )
        except (BotoCoreError, ClientError) as exc:
            raise DetectionProviderError("IMAGE_PROVIDER_UNAVAILABLE") from exc

        labels = response.get("ModerationLabels") or []
        mapped: list[tuple[str, float, str]] = []
        for item in labels:
            try:
                name = str(item.get("Name") or "").strip()
                parent = str(item.get("ParentName") or "").strip()
                confidence = float(item.get("Confidence") or 0)
            except (TypeError, ValueError) as exc:
                raise DetectionProviderError("MALFORMED_MODERATION_OUTPUT") from exc
            if not name or not 0 <= confidence <= 100:
                continue
            reason = _reason_for_label(name, parent)
            if reason:
                mapped.append((reason, confidence, _bounded_label(name)))

        if not mapped:
            return ImageSafetyResult(reason_code="IMAGE_CLEAN", confidence=0.0, severity="none")

        mapped.sort(key=lambda row: row[1], reverse=True)
        reason, confidence, _ = mapped[0]
        bounded_labels = tuple(dict.fromkeys(label for _, __, label in mapped))
        reject_at = self._settings.content_safety_image_reject_confidence
        review_at = self._settings.content_safety_image_review_confidence
        if confidence >= reject_at:
            severity = "high"
        elif confidence >= review_at:
            severity = "medium"
        else:
            severity = "low"
        return ImageSafetyResult(
            reason_code=reason,
            labels=bounded_labels[:12],
            confidence=confidence,
            severity=severity,
        )


def _reason_for_label(name: str, parent: str) -> str | None:
    haystack = f"{name} {parent}".lower()
    if any(label in haystack for label in SEXUAL_LABELS):
        return "IMAGE_SEXUAL"
    if any(label in haystack for label in HATE_LABELS):
        return "IMAGE_HATE"
    if any(label in haystack for label in VIOLENCE_LABELS):
        return "IMAGE_VIOLENCE_GRAPHIC"
    if any(label in haystack for label in DRUG_LABELS):
        return "IMAGE_DRUGS"
    if any(label in haystack for label in WEAPON_LABELS):
        return "IMAGE_WEAPONS"
    return "IMAGE_OTHER_UNSAFE"


def _bounded_label(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in name.strip())
    return cleaned.lower()[:40] or "other"
