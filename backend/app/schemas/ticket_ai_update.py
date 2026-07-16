from pydantic import BaseModel, Field, field_validator

from app.schemas.ai_processing import AiProcessingStatus
from app.services.ai.categories import concrete_category_ids


class SaveTicketAiOutputRequest(BaseModel):
    """AI processing result to persist on a ticket without touching the original report."""

    cleaned_description: str | None = Field(default=None, alias="cleanedDescription")
    ai_suggested_category: str | None = Field(default=None, alias="aiSuggestedCategory")
    ai_category_explanation: str | None = Field(default=None, alias="aiCategoryExplanation")
    ai_confidence: float | None = Field(default=None, alias="aiConfidence", ge=0, le=1)
    ai_model_version: str | None = Field(default=None, alias="aiModelVersion")
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
