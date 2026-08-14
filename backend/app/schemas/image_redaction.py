from typing import Literal

from pydantic import BaseModel, Field

ImageRedactionStatus = Literal[
    "pending",
    "processing",
    "completed",
    "failed",
    "review_required",
]


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
