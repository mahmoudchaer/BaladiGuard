from pydantic import BaseModel, Field

from app.schemas.ai_processing import AiProcessingStatus


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

    final_category: str = Field(alias="finalCategory")
    category_reviewed_by: str = Field(alias="categoryReviewedBy", min_length=1, max_length=120)

    model_config = {"populate_by_name": True}
