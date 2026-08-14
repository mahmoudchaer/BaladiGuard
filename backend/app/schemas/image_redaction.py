from typing import Literal

from pydantic import BaseModel, Field

ImageRedactionStatus = Literal[
    "pending",
    "processing",
    "completed",
    "failed",
    "review_required",
    "private_only",
]

MAX_MANUAL_REDACTION_REGIONS = 12


class RedactionProvenance(BaseModel):
    generation: int = Field(ge=1)
    status: ImageRedactionStatus
    source_fingerprint: str = Field(alias="sourceFingerprint")
    derivative_object_key: str | None = Field(default=None, alias="derivativeObjectKey")
    detector: str
    detector_version: str = Field(alias="detectorVersion")
    face_count: int = Field(default=0, alias="faceCount", ge=0)
    plate_count: int = Field(default=0, alias="plateCount", ge=0)
    minimum_confidence: float | None = Field(default=None, alias="minimumConfidence")
    completed_at: str = Field(alias="completedAt")
    reason_code: str | None = Field(default=None, alias="reasonCode")

    model_config = {"populate_by_name": True}


class TicketImageRedaction(BaseModel):
    status: ImageRedactionStatus
    generation: int = Field(ge=1)
    detector: str | None = None
    detector_version: str | None = Field(default=None, alias="detectorVersion")
    face_count: int = Field(default=0, alias="faceCount", ge=0)
    plate_count: int = Field(default=0, alias="plateCount", ge=0)
    completed_at: str | None = Field(default=None, alias="completedAt")
    reason_code: str | None = Field(default=None, alias="reasonCode")

    model_config = {"populate_by_name": True}


class ReprocessImageResponse(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    status: Literal["pending"] = "pending"
    generation: int = Field(ge=1)

    model_config = {"populate_by_name": True}


class StoredRedactionRegion(BaseModel):
    kind: Literal["face", "plate", "manual"]
    left: float
    top: float
    width: float
    height: float
    confidence: float | None = None

    model_config = {"populate_by_name": True}


class ManualRedactionRegion(BaseModel):
    left: float
    top: float
    width: float
    height: float


class ImageRedactionDecisionRequest(BaseModel):
    expected_generation: int = Field(alias="expectedGeneration", ge=1)
    expected_candidate_revision: int = Field(alias="expectedCandidateRevision", ge=0)
    regions: list[ManualRedactionRegion] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class ImageRedactionReviewResponse(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    generation: int
    candidate_revision: int = Field(alias="candidateRevision", ge=0)
    status: ImageRedactionStatus
    original_image_url: str | None = Field(default=None, alias="originalImageUrl")
    candidate_image_url: str | None = Field(default=None, alias="candidateImageUrl")
    public_image_ready: bool = Field(alias="publicImageReady")
    detector: str | None = None
    detector_version: str | None = Field(default=None, alias="detectorVersion")
    face_count: int = Field(default=0, alias="faceCount", ge=0)
    plate_count: int = Field(default=0, alias="plateCount", ge=0)
    completed_at: str | None = Field(default=None, alias="completedAt")
    reason_code: str | None = Field(default=None, alias="reasonCode")
    regions: list[StoredRedactionRegion] = Field(default_factory=list)
    can_approve: bool = Field(alias="canApprove")
    can_reject: bool = Field(alias="canReject")
    can_reprocess: bool = Field(alias="canReprocess")
    can_add_manual_regions: bool = Field(alias="canAddManualRegions")

    model_config = {"populate_by_name": True}
