from typing import Literal

from pydantic import BaseModel, Field

RedactionJobStatus = Literal["queued", "running", "succeeded", "dead_lettered"]


class StoredRedactionJob(BaseModel):
    job_id: str = Field(alias="jobId")
    ticket_id: str = Field(alias="ticketId")
    generation: int = Field(ge=1)
    status: RedactionJobStatus
    attempts: int = 0
    available_at: int = Field(alias="availableAt")
    created_at: int = Field(alias="createdAt")
    updated_at: int = Field(alias="updatedAt")
    claim_token: str | None = Field(default=None, alias="claimToken")
    claim_expires_at: int | None = Field(default=None, alias="claimExpiresAt")
    last_error_code: str | None = Field(default=None, alias="lastErrorCode")

    model_config = {"populate_by_name": True}
