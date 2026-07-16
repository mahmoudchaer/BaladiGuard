from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ai_processing import AiProcessingStatus
from app.schemas.ticket import ReportContact, ReportLocation
from app.schemas.ticket_status import TicketStatus

ReportPriority = Literal["low", "medium", "high"]

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
    status: TicketStatus
    category: str = PENDING_CLASSIFICATION
    ai_suggested_category: str | None = Field(default=None, alias="aiSuggestedCategory")
    ai_category_explanation: str | None = Field(default=None, alias="aiCategoryExplanation")
    ai_confidence: float | None = Field(default=None, alias="aiConfidence")
    final_category: str | None = Field(default=None, alias="finalCategory")
    category_reviewed_by: str | None = Field(default=None, alias="categoryReviewedBy")
    category_reviewed_at: str | None = Field(default=None, alias="categoryReviewedAt")
    ai_processing_status: AiProcessingStatus = Field(
        default="pending",
        alias="aiProcessingStatus",
    )
    ai_model_version: str | None = Field(default=None, alias="aiModelVersion")
    priority: ReportPriority | None = None
    created_by: str | None = Field(default=None, alias="createdBy")
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    department_id: str | None = Field(default=None, alias="departmentId")
    duplicate_group_id: str | None = Field(default=None, alias="duplicateGroupId")
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    updated_by: str | None = Field(default=None, alias="updatedBy")

    model_config = {"populate_by_name": True}
