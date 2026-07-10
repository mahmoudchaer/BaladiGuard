from pydantic import BaseModel, Field

from app.schemas.ticket_status import TicketStatus


class StoredStatusHistory(BaseModel):
    history_id: str = Field(alias="historyId")
    ticket_id: str = Field(alias="ticketId")
    previous_status: TicketStatus | None = Field(default=None, alias="previousStatus")
    new_status: TicketStatus = Field(alias="newStatus")
    updated_by: str | None = Field(default=None, alias="updatedBy")
    note: str | None = None
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
