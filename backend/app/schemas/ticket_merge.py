"""Request body for staff duplicate merge (issue #27)."""

from pydantic import BaseModel, Field, field_validator


class MergeDuplicateTicketsRequest(BaseModel):
    canonical_ticket_id: str = Field(alias="canonicalTicketId", min_length=1, max_length=80)
    duplicate_ticket_ids: list[str] = Field(alias="duplicateTicketIds", min_length=1, max_length=20)
    merged_by: str | None = Field(default=None, alias="mergedBy", max_length=120)

    model_config = {"populate_by_name": True}

    @field_validator("duplicate_ticket_ids")
    @classmethod
    def validate_duplicate_ticket_ids(cls, value: list[str]) -> list[str]:
        cleaned = [ticket_id.strip() for ticket_id in value if ticket_id and ticket_id.strip()]
        if not cleaned:
            raise ValueError("Provide at least one duplicate ticket ID.")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Duplicate ticket IDs must be unique.")
        if any(len(ticket_id) > 80 for ticket_id in cleaned):
            raise ValueError("Each duplicate ticket ID must be at most 80 characters.")
        return cleaned
