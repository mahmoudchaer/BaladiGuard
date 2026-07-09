from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.ticket import ReportContact, ReportLocation
from app.schemas.ticket_status import TicketStatus

ReportPriority = Literal["low", "medium", "high"]

PENDING_CLASSIFICATION = "PENDING_CLASSIFICATION"


class StoredTicket(BaseModel):
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str = Field(alias="ticketNumber")
    tracking_code: str = Field(alias="trackingCode")
    description: str
    contact: ReportContact
    location: ReportLocation
    image_object_key: str = Field(alias="imageObjectKey")
    status: TicketStatus
    category: str = PENDING_CLASSIFICATION
    priority: ReportPriority | None = None
    created_by: str | None = Field(default=None, alias="createdBy")
    municipality_id: str | None = Field(default=None, alias="municipalityId")
    department_id: str | None = Field(default=None, alias="departmentId")
    duplicate_group_id: str | None = Field(default=None, alias="duplicateGroupId")
    created_at: str = Field(alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    updated_by: str | None = Field(default=None, alias="updatedBy")

    model_config = {"populate_by_name": True}
