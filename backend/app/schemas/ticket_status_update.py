from pydantic import BaseModel, Field

from app.schemas.ticket_status import TicketStatus


class UpdateTicketStatusRequest(BaseModel):
    status: TicketStatus
    updated_by: str | None = Field(default=None, alias="updatedBy", max_length=120)
    note: str | None = Field(default=None, max_length=500)

    model_config = {"populate_by_name": True}
