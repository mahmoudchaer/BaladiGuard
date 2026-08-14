"""Staff review and correction of redacted image candidates (issue #255)."""

from __future__ import annotations

from app.schemas.image_redaction import MAX_MANUAL_REDACTION_REGIONS, ManualRedactionRegion
from app.services.redaction.detector import BoundingBox, Detection
from app.services.redaction.processor import _valid_detection


class ImageRedactionReviewError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ImageRedactionReviewConflictError(ImageRedactionReviewError):
    def __init__(self) -> None:
        super().__init__(
            "REDACTION_REVIEW_CONFLICT",
            "A newer redaction decision already exists for this generation.",
        )


def detections_from_stored(regions: list) -> list[Detection]:
    detections: list[Detection] = []
    for region in regions:
        kind = getattr(region, "kind", None) or region.get("kind")
        left = getattr(region, "left", None) if not isinstance(region, dict) else region.get("left")
        top = getattr(region, "top", None) if not isinstance(region, dict) else region.get("top")
        width = (
            getattr(region, "width", None) if not isinstance(region, dict) else region.get("width")
        )
        height = (
            getattr(region, "height", None)
            if not isinstance(region, dict)
            else region.get("height")
        )
        confidence = (
            getattr(region, "confidence", None)
            if not isinstance(region, dict)
            else region.get("confidence")
        )
        detections.append(
            Detection(
                str(kind or "manual"),
                float(confidence if confidence is not None else 100),
                BoundingBox(float(left), float(top), float(width), float(height)),
            )
        )
    return detections


def parse_manual_regions(regions: list[ManualRedactionRegion]) -> list[Detection]:
    if not regions:
        raise ImageRedactionReviewError(
            "VALIDATION_ERROR",
            "At least one manual blur region is required.",
        )
    if len(regions) > MAX_MANUAL_REDACTION_REGIONS:
        raise ImageRedactionReviewError(
            "VALIDATION_ERROR",
            f"At most {MAX_MANUAL_REDACTION_REGIONS} manual blur regions are allowed.",
        )
    detections: list[Detection] = []
    for region in regions:
        detection = Detection(
            "manual",
            100,
            BoundingBox(region.left, region.top, region.width, region.height),
        )
        if not _valid_detection(detection):
            raise ImageRedactionReviewError(
                "VALIDATION_ERROR",
                "Manual blur regions must lie within the image (normalized 0–1 boxes).",
            )
        detections.append(detection)
    return detections
