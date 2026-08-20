from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.content_safety import (
    ContentSafetyProvenance,
    ContentSafetySeverity,
    ContentSafetyStatus,
)
from app.schemas.stored_ticket import StoredTicket

CONTENT_SAFETY_HISTORY_CAP = 20
TERMINAL_TEXT_REJECT = frozenset(
    {
        "TEXT_GARBAGE",
        "TEXT_SPAM_LINKS",
        "TEXT_REPETITION",
        "TEXT_TOO_SHORT",
    }
)
HIGH_REJECT_IMAGE = frozenset({"IMAGE_SEXUAL", "IMAGE_HATE"})
GRAPHIC_IMAGE = frozenset({"IMAGE_VIOLENCE_GRAPHIC"})
AUTH_RISK_SIGNALS = frozenset({"AUTH_AWS_WATERMARK", "AUTH_ONNX_HIGH"})


@dataclass(frozen=True)
class TextSafetyResult:
    reason_code: str
    civic_emergency: bool = False
    confidence: float = 1.0
    severity: ContentSafetySeverity = "none"
    model: str | None = None
    provider_unavailable: bool = False


@dataclass(frozen=True)
class ImageSafetyResult:
    reason_code: str
    labels: tuple[str, ...] = ()
    confidence: float = 0.0
    severity: ContentSafetySeverity = "none"
    provider_unavailable: bool = False


@dataclass(frozen=True)
class AuthenticityResult:
    score: float | None = None
    model: str | None = None
    model_version: str | None = None
    signals: tuple[str, ...] = ()
    unavailable: bool = False


@dataclass(frozen=True)
class SafetyDecision:
    status: ContentSafetyStatus
    reason_code: str
    severity: ContentSafetySeverity
    text: TextSafetyResult
    image: ImageSafetyResult
    authenticity: AuthenticityResult
    image_labels: tuple[str, ...] = field(default_factory=tuple)


def content_safety_allows_public_ticket(ticket: StoredTicket) -> bool:
    """Public list/detail/publish require passed screening, or an unenrolled ticket."""
    if not ticket.content_safety_enrolled:
        return True
    return ticket.content_safety_status == "passed"


def content_safety_allows_public_image(ticket: StoredTicket) -> bool:
    """Legacy unenrolled tickets keep historical redaction auto-publish."""
    return content_safety_allows_public_ticket(ticket)


def public_photo_key_if_eligible(ticket: StoredTicket) -> str | None:
    if not content_safety_allows_public_image(ticket):
        return None
    key = (ticket.public_image_object_key or "").strip()
    if key:
        return key
    if ticket.image_redaction_status == "completed":
        candidate = (ticket.image_redaction_candidate_object_key or "").strip()
        return candidate or None
    return None


def should_promote_public_image(ticket: StoredTicket, status: ContentSafetyStatus) -> bool:
    return (
        status == "passed"
        and ticket.image_redaction_status == "completed"
        and bool(ticket.image_redaction_candidate_object_key)
    )


def should_clear_public_image(status: ContentSafetyStatus) -> bool:
    return status in {"review_required", "private_only", "rejected", "failed", "pending"}


def public_unpublish_fields(ticket: StoredTicket) -> dict[str, Any]:
    """Drop a live public projection when screening is no longer passed.

    DRAFT stays DRAFT. PUBLISHED becomes UNPUBLISHED so the Dynamo public GSI
    hash moves off the published partition.
    """
    fields: dict[str, Any] = {}
    if ticket.public_status == "PUBLISHED":
        fields["public_status"] = "UNPUBLISHED"
    if ticket.public_image_object_key:
        fields["public_image_object_key"] = None
    return fields


def snapshot_content_safety(
    ticket: StoredTicket, *, status: ContentSafetyStatus | None = None
) -> dict[str, Any]:
    record_status = status or ticket.content_safety_status
    return ContentSafetyProvenance(
        generation=ticket.content_safety_generation,
        status=record_status,
        outcomeStatus=ticket.content_safety_status,
        reasonCode=ticket.content_safety_reason_code,
        severity=ticket.content_safety_severity,
        textModel=ticket.content_safety_text_model,
        imageLabels=list(ticket.content_safety_image_labels),
        authenticityScore=ticket.authenticity_score,
        authenticityModel=ticket.authenticity_model,
        authenticityModelVersion=ticket.authenticity_model_version,
        authenticitySignals=list(ticket.authenticity_signals),
        completedAt=ticket.content_safety_completed_at,
        staffNote=ticket.content_safety_staff_note,
    ).model_dump(by_alias=True)


def _history_entries(ticket: StoredTicket) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in ticket.content_safety_history:
        if hasattr(item, "model_dump"):
            entries.append(item.model_dump(by_alias=True))
        else:
            entries.append(dict(item))
    return entries


def append_content_safety_history(
    ticket: StoredTicket, *, status: ContentSafetyStatus | None = None
) -> list[dict[str, Any]]:
    history = _history_entries(ticket)
    generation = ticket.content_safety_generation
    if any(int(entry.get("generation") or 0) == generation for entry in history):
        return history[-CONTENT_SAFETY_HISTORY_CAP:]
    history.append(snapshot_content_safety(ticket, status=status))
    return history[-CONTENT_SAFETY_HISTORY_CAP:]


def superseded_content_safety_history(ticket: StoredTicket) -> list[dict[str, Any]]:
    """Keep the prior generation when reprocessing; write superseded provenance."""
    history = _history_entries(ticket)
    generation = ticket.content_safety_generation
    found = False
    for entry in history:
        if int(entry.get("generation") or 0) == generation:
            entry["status"] = "superseded"
            entry.setdefault("outcomeStatus", ticket.content_safety_status)
            found = True
    if not found:
        history.append(snapshot_content_safety(ticket, status="superseded"))
    return history[-CONTENT_SAFETY_HISTORY_CAP:]


def combine_safety_signals(
    *,
    text: TextSafetyResult,
    image: ImageSafetyResult,
    authenticity: AuthenticityResult,
    fail_closed: bool,
    authenticity_review_score: float,
) -> SafetyDecision:
    image_labels = tuple(label for label in image.labels if label)[:12]
    provider_down = text.provider_unavailable or image.provider_unavailable

    if text.reason_code in TERMINAL_TEXT_REJECT:
        return _decision(
            "rejected",
            text.reason_code,
            _higher_severity(text.severity, "medium"),
            text,
            image,
            authenticity,
            image_labels,
        )

    if image.reason_code in HIGH_REJECT_IMAGE and image.confidence >= 80:
        return _decision(
            "rejected",
            image.reason_code,
            "high",
            text,
            image,
            authenticity,
            image_labels,
        )

    if image.reason_code == "IMAGE_NUDITY_SUGGESTIVE":
        return _decision(
            "review_required",
            image.reason_code,
            _higher_severity(image.severity, "medium"),
            text,
            image,
            authenticity,
            image_labels,
        )

    if image.reason_code in GRAPHIC_IMAGE:
        # Graphic civic evidence stays available to staff and never becomes public.
        return _decision(
            "private_only",
            image.reason_code,
            _higher_severity(image.severity, "high"),
            text,
            image,
            authenticity,
            image_labels,
        )

    if text.reason_code in {
        "TEXT_UNSAFE",
        "TEXT_SCAM",
        "TEXT_HARASSMENT",
        "TEXT_HATE",
        "TEXT_SEXUAL",
    }:
        if text.civic_emergency:
            return _decision(
                "review_required",
                text.reason_code,
                _higher_severity(text.severity, "medium"),
                text,
                image,
                authenticity,
                image_labels,
            )
        if text.confidence >= 0.8:
            return _decision(
                "rejected",
                text.reason_code,
                _higher_severity(text.severity, "high"),
                text,
                image,
                authenticity,
                image_labels,
            )
        return _decision(
            "review_required",
            text.reason_code,
            _higher_severity(text.severity, "medium"),
            text,
            image,
            authenticity,
            image_labels,
        )

    if image.reason_code in {"IMAGE_DRUGS", "IMAGE_WEAPONS", "IMAGE_OTHER_UNSAFE"}:
        if image.confidence >= 80 and not text.civic_emergency:
            return _decision(
                "rejected",
                image.reason_code,
                "high",
                text,
                image,
                authenticity,
                image_labels,
            )
        return _decision(
            "review_required",
            image.reason_code,
            _higher_severity(image.severity, "medium"),
            text,
            image,
            authenticity,
            image_labels,
        )

    if provider_down:
        if fail_closed:
            return _decision(
                "review_required",
                "SAFETY_PROVIDER_UNAVAILABLE",
                "medium",
                text,
                image,
                authenticity,
                image_labels,
            )
        return _decision(
            "passed",
            text.reason_code if text.reason_code != "TEXT_PROVIDER_UNAVAILABLE" else "TEXT_CLEAN",
            "none",
            text,
            image,
            authenticity,
            image_labels,
        )

    if text.severity == "medium" or image.severity == "medium":
        return _decision(
            "review_required",
            text.reason_code if text.severity == "medium" else image.reason_code,
            "medium",
            text,
            image,
            authenticity,
            image_labels,
        )

    auth_high = _authenticity_high(authenticity, authenticity_review_score)
    other_risk = (
        text.severity in {"low", "medium"}
        or image.severity in {"low", "medium"}
        or "AUTH_SCREENSHOT" in authenticity.signals
        or "AUTH_LOW_INFORMATION" in authenticity.signals
    )
    if auth_high and other_risk:
        return _decision(
            "review_required",
            next(
                (code for code in authenticity.signals if code in AUTH_RISK_SIGNALS),
                "AUTH_ONNX_HIGH",
            ),
            "medium",
            text,
            image,
            authenticity,
            image_labels,
        )

    reason = "TEXT_CIVIC_EMERGENCY" if text.civic_emergency else "TEXT_CLEAN"
    if image.reason_code not in {"IMAGE_CLEAN", "IMAGE_UNAVAILABLE", "IMAGE_PROVIDER_UNAVAILABLE"}:
        reason = image.reason_code
    return _decision(
        "passed",
        reason,
        "none",
        text,
        image,
        authenticity,
        image_labels,
    )


def _authenticity_high(result: AuthenticityResult, threshold: float) -> bool:
    if any(signal in AUTH_RISK_SIGNALS for signal in result.signals):
        return True
    if result.score is None:
        return False
    return result.score >= threshold


def _higher_severity(
    left: ContentSafetySeverity, right: ContentSafetySeverity
) -> ContentSafetySeverity:
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    return left if order[left] >= order[right] else right


def _decision(
    status: ContentSafetyStatus,
    reason_code: str,
    severity: ContentSafetySeverity,
    text: TextSafetyResult,
    image: ImageSafetyResult,
    authenticity: AuthenticityResult,
    image_labels: tuple[str, ...],
) -> SafetyDecision:
    return SafetyDecision(
        status=status,
        reason_code=reason_code,
        severity=severity,
        text=text,
        image=image,
        authenticity=authenticity,
        image_labels=image_labels,
    )
