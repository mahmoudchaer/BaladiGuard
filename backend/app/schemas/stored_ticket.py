from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ai_processing import AiProcessingStatus
from app.schemas.image_redaction import (
    ImageRedactionStatus,
    RedactionProvenance,
    StoredRedactionRegion,
)
from app.schemas.ticket import ReportContact, ReportLocation
from app.schemas.ticket_status import TicketStatus

ReportPriority = Literal["low", "medium", "high", "critical"]
PublicTicketStatus = Literal["DRAFT", "PUBLISHED", "UNPUBLISHED"]

PENDING_CLASSIFICATION = "PENDING_CLASSIFICATION"


class StoredTicket(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str = Field(alias="ticketNumber")
    tracking_code: str = Field(alias="trackingCode")
    description: str
    original_description: str | None = Field(default=None, alias="originalDescription")
    cleaned_description: str | None = Field(default=None, alias="cleanedDescription")
    contact: ReportContact
    location: ReportLocation
    image_object_key: str = Field(alias="imageObjectKey")
    # Stable citizen owner; null/absent for legacy unowned tickets. Never OTP/session data.
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    status: TicketStatus
    category: str = PENDING_CLASSIFICATION
    ai_suggested_category: str | None = Field(default=None, alias="aiSuggestedCategory")
    ai_category_explanation: str | None = Field(default=None, alias="aiCategoryExplanation")
    ai_confidence: float | None = Field(default=None, alias="aiConfidence")
    final_category: str | None = Field(default=None, alias="finalCategory")
    category_reviewed_by: str | None = Field(default=None, alias="categoryReviewedBy")
    category_reviewed_at: str | None = Field(default=None, alias="categoryReviewedAt")
    public_status: PublicTicketStatus = Field(default="DRAFT", alias="publicStatus")
    public_description: str | None = Field(default=None, alias="publicDescription")
    public_location_label: str | None = Field(default=None, alias="publicLocationLabel")
    public_published_at: str | None = Field(default=None, alias="publicPublishedAt")
    # Optional staff-approved public photo key. Unapproved uploads stay private.
    public_image_object_key: str | None = Field(default=None, alias="publicImageObjectKey")
    image_redaction_status: ImageRedactionStatus = Field(
        default="pending", alias="imageRedactionStatus"
    )
    image_redaction_generation: int = Field(default=1, alias="imageRedactionGeneration", ge=1)
    image_redaction_claim_token: str | None = Field(default=None, alias="imageRedactionClaimToken")
    image_redaction_detector: str | None = Field(default=None, alias="imageRedactionDetector")
    image_redaction_detector_version: str | None = Field(
        default=None, alias="imageRedactionDetectorVersion"
    )
    image_redaction_face_count: int = Field(default=0, alias="imageRedactionFaceCount", ge=0)
    image_redaction_plate_count: int = Field(default=0, alias="imageRedactionPlateCount", ge=0)
    image_redaction_completed_at: str | None = Field(
        default=None, alias="imageRedactionCompletedAt"
    )
    image_redaction_reason_code: str | None = Field(default=None, alias="imageRedactionReasonCode")
    image_redaction_history: list[RedactionProvenance] = Field(
        default_factory=list, alias="imageRedactionHistory"
    )
    image_redaction_candidate_object_key: str | None = Field(
        default=None, alias="imageRedactionCandidateObjectKey"
    )
    image_redaction_candidate_revision: int = Field(
        default=0, alias="imageRedactionCandidateRevision", ge=0
    )
    image_redaction_regions: list[StoredRedactionRegion] = Field(
        default_factory=list, alias="imageRedactionRegions"
    )

    ai_processing_status: AiProcessingStatus = Field(
        default="pending",
        alias="aiProcessingStatus",
    )
    ai_processing_claim_token: str | None = Field(default=None, alias="aiProcessingClaimToken")
    ai_model_version: str | None = Field(default=None, alias="aiModelVersion")
    priority: ReportPriority | None = None
    urgency_score: int | None = Field(default=None, alias="urgencyScore", ge=0, le=100)
    urgency_reason: str | None = Field(default=None, alias="urgencyReason")
    created_by: str | None = Field(default=None, alias="createdBy")
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    department_id: str | None = Field(default=None, alias="departmentId")
    suggested_department_id: str | None = Field(default=None, alias="suggestedDepartmentId")
    assigned_worker_id: str | None = Field(default=None, alias="assignedWorkerId")
    assigned_team_id: str | None = Field(default=None, alias="assignedTeamId")
    active_work_order_id: str | None = Field(default=None, alias="activeWorkOrderId")
    resolution_reason_code: str | None = Field(default=None, alias="resolutionReasonCode")
    resolution_note: str | None = Field(default=None, alias="resolutionNote")
    resolved_at: str | None = Field(default=None, alias="resolvedAt")
    resolved_by: str | None = Field(default=None, alias="resolvedBy")
    closure_reason_code: str | None = Field(default=None, alias="closureReasonCode")
    closure_note: str | None = Field(default=None, alias="closureNote")
    closed_at: str | None = Field(default=None, alias="closedAt")
    closed_by: str | None = Field(default=None, alias="closedBy")
    resolution_feedback_status: str | None = Field(default=None, alias="resolutionFeedbackStatus")
    resolution_feedback_note: str | None = Field(default=None, alias="resolutionFeedbackNote")
    resolution_feedback_submitted_at: str | None = Field(
        default=None, alias="resolutionFeedbackSubmittedAt"
    )
    resolution_feedback_review_status: str | None = Field(
        default=None, alias="resolutionFeedbackReviewStatus"
    )
    resolution_feedback_reviewed_at: str | None = Field(
        default=None, alias="resolutionFeedbackReviewedAt"
    )
    resolution_feedback_reviewed_by: str | None = Field(
        default=None, alias="resolutionFeedbackReviewedBy"
    )
    resolution_feedback_review_action: str | None = Field(
        default=None, alias="resolutionFeedbackReviewAction"
    )
    duplicate_group_id: str | None = Field(default=None, alias="duplicateGroupId")
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    updated_by: str | None = Field(default=None, alias="updatedBy")

    model_config = {"populate_by_name": True}
