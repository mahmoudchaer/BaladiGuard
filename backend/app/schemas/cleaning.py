from pydantic import BaseModel, Field

# Documented upper bound for cleaned municipal descriptions (issue #18).
MAX_CLEANED_DESCRIPTION_LENGTH = 500


class CleaningResult(BaseModel):
    """Structured output from the standalone description-cleaning service."""

    cleaned_description: str | None = Field(default=None, alias="cleanedDescription")
    used_fallback: bool = Field(default=False, alias="usedFallback")
    message: str | None = None

    model_config = {"populate_by_name": True}
