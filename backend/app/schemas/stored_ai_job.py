from typing import Literal

from pydantic import BaseModel, Field

AiJobStatus = Literal["queued", "running", "succeeded", "dead_lettered"]


class StoredAiJob(BaseModel):
    job_id: str = Field(alias="jobId")
    ticket_id: str = Field(alias="ticketId")
    status: AiJobStatus
    attempts: int = 0
    available_at: int = Field(alias="availableAt")
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")
    claim_token: str | None = Field(default=None, alias="claimToken")
    claim_expires_at: int | None = Field(default=None, alias="claimExpiresAt")
    last_error: str | None = Field(default=None, alias="lastError")

    model_config = {"populate_by_name": True}
