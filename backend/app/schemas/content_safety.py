from typing import Literal

from pydantic import BaseModel, Field

ContentSafetyStatus = Literal[
    "pending",
    "processing",
    "passed",
    "review_required",
    "private_only",
    "rejected",
    "failed",
    "superseded",
]

ContentSafetySeverity = Literal["none", "low", "medium", "high"]

ContentSafetyDecision = Literal["approve", "reject", "private_only"]

# Bounded codes persisted on the ticket. Never store provider essays or image bytes.
TEXT_REASON_CODES = frozenset(
    {
        "TEXT_CLEAN",
        "TEXT_TOO_SHORT",
        "TEXT_GARBAGE",
        "TEXT_SPAM_LINKS",
        "TEXT_REPETITION",
        "TEXT_UNSAFE",
        "TEXT_SCAM",
        "TEXT_HARASSMENT",
        "TEXT_HATE",
        "TEXT_SEXUAL",
        "TEXT_CIVIC_EMERGENCY",
        "TEXT_PROMPT_INJECTION",
        "TEXT_PROVIDER_UNAVAILABLE",
    }
)

IMAGE_REASON_CODES = frozenset(
    {
        "IMAGE_CLEAN",
        "IMAGE_SEXUAL",
        "IMAGE_HATE",
        "IMAGE_VIOLENCE_GRAPHIC",
        "IMAGE_DRUGS",
        "IMAGE_WEAPONS",
        "IMAGE_OTHER_UNSAFE",
        "IMAGE_PROVIDER_UNAVAILABLE",
        "IMAGE_UNAVAILABLE",
    }
)

AUTHENTICITY_SIGNAL_CODES = frozenset(
    {
        "AUTH_EXIF_PRESENT",
        "AUTH_EXIF_MISSING",
        "AUTH_SCREENSHOT",
        "AUTH_LOW_INFORMATION",
        "AUTH_AWS_WATERMARK",
        "AUTH_AWS_WATERMARK_ABSENT",
        "AUTH_ONNX_HIGH",
        "AUTH_ONNX_LOW",
        "AUTH_UNAVAILABLE",
    }
)

COMBINED_REASON_CODES = (
    TEXT_REASON_CODES
    | IMAGE_REASON_CODES
    | AUTHENTICITY_SIGNAL_CODES
    | {
        "STAFF_APPROVED",
        "STAFF_REJECTED",
        "STAFF_PRIVATE_ONLY",
        "SAFETY_PROVIDER_UNAVAILABLE",
        "SAFETY_DISABLED",
        "SAFETY_FAILED",
    }
)


class TicketContentSafety(BaseModel):
    status: ContentSafetyStatus
    generation: int = Field(ge=1)
    reason_code: str | None = Field(default=None, alias="reasonCode")
    severity: ContentSafetySeverity | None = None
    text_model: str | None = Field(default=None, alias="textModel")
    image_labels: list[str] = Field(default_factory=list, alias="imageLabels")
    authenticity_score: float | None = Field(default=None, alias="authenticityScore")
    authenticity_model: str | None = Field(default=None, alias="authenticityModel")
    authenticity_model_version: str | None = Field(default=None, alias="authenticityModelVersion")
    authenticity_signals: list[str] = Field(default_factory=list, alias="authenticitySignals")
    completed_at: str | None = Field(default=None, alias="completedAt")

    model_config = {"populate_by_name": True}


class ContentSafetyDecisionRequest(BaseModel):
    expected_generation: int = Field(alias="expectedGeneration", ge=1)
    reason_code: str | None = Field(default=None, alias="reasonCode", max_length=64)
    note: str | None = Field(default=None, max_length=500)

    model_config = {"populate_by_name": True}


class ReprocessContentSafetyResponse(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    status: Literal["pending"] = "pending"
    generation: int = Field(ge=1)

    model_config = {"populate_by_name": True}


class ContentSafetyReviewResponse(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    generation: int = Field(ge=1)
    status: ContentSafetyStatus
    reason_code: str | None = Field(default=None, alias="reasonCode")
    severity: ContentSafetySeverity | None = None
    text_model: str | None = Field(default=None, alias="textModel")
    image_labels: list[str] = Field(default_factory=list, alias="imageLabels")
    authenticity_score: float | None = Field(default=None, alias="authenticityScore")
    authenticity_model: str | None = Field(default=None, alias="authenticityModel")
    authenticity_model_version: str | None = Field(default=None, alias="authenticityModelVersion")
    authenticity_signals: list[str] = Field(default_factory=list, alias="authenticitySignals")
    completed_at: str | None = Field(default=None, alias="completedAt")
    original_image_url: str | None = Field(default=None, alias="originalImageUrl")
    public_image_ready: bool = Field(alias="publicImageReady")
    can_approve: bool = Field(alias="canApprove")
    can_reject: bool = Field(alias="canReject")
    can_mark_private: bool = Field(alias="canMarkPrivate")
    can_reprocess: bool = Field(alias="canReprocess")

    model_config = {"populate_by_name": True}
