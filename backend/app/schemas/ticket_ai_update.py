from pydantic import BaseModel, Field, field_validator

from app.schemas.ai_processing import AiProcessingStatus
from app.schemas.stored_ticket import ReportPriority
from app.services.ai.categories import concrete_category_ids
from app.services.routing import department_ids


class SaveTicketAiOutputRequest(BaseModel):
    """AI processing result to persist on a ticket without touching the original report."""

    cleaned_description: str | None = Field(
        default=None, alias="cleanedDescription", max_length=4000
    )
    ai_suggested_category: str | None = Field(
        default=None, alias="aiSuggestedCategory", max_length=80
    )
    ai_category_explanation: str | None = Field(
        default=None, alias="aiCategoryExplanation", max_length=2000
    )
    ai_confidence: float | None = Field(default=None, alias="aiConfidence", ge=0, le=1)
    ai_model_version: str | None = Field(default=None, alias="aiModelVersion", max_length=80)
    urgency_score: int | None = Field(default=None, alias="urgencyScore", ge=0, le=100)
    urgency_reason: str | None = Field(default=None, alias="urgencyReason", max_length=500)
    priority: ReportPriority | None = None
    ai_processing_status: AiProcessingStatus = Field(alias="aiProcessingStatus")

    model_config = {"populate_by_name": True}


class ReviewTicketCategoryRequest(BaseModel):
    """Staff-approved category that must not overwrite the original AI suggestion."""

    final_category: str = Field(alias="finalCategory", min_length=1)
    category_reviewed_by: str | None = Field(
        default=None,
        alias="categoryReviewedBy",
        min_length=1,
        max_length=120,
    )

    model_config = {"populate_by_name": True}

    @field_validator("final_category")
    @classmethod
    def validate_final_category(cls, value: str) -> str:
        if value not in concrete_category_ids():
            supported = ", ".join(sorted(concrete_category_ids()))
            raise ValueError(f"Category must be one of: {supported}.")
        return value


class AssignTicketDepartmentRequest(BaseModel):
    """Staff department assignment that preserves the automatic suggestion separately."""

    department_id: str = Field(alias="departmentId", min_length=1)
    updated_by: str | None = Field(
        default=None,
        alias="updatedBy",
        min_length=1,
        max_length=120,
    )

    model_config = {"populate_by_name": True}

    @field_validator("department_id")
    @classmethod
    def validate_department_id(cls, value: str) -> str:
        allowed = department_ids()
        if value not in allowed:
            supported = ", ".join(sorted(allowed))
            raise ValueError(f"Department must be one of: {supported}.")
        return value
