from pydantic import BaseModel, Field


class ClassificationInputs(BaseModel):
    description: bool = False
    image: bool = False


class ClassificationResult(BaseModel):
    category: str
    explanation: str = Field(min_length=1)
    used_inputs: ClassificationInputs = Field(alias="usedInputs")
    used_fallback: bool = Field(default=False, alias="usedFallback")

    model_config = {"populate_by_name": True}
