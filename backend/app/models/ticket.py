from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.schemas.ticket import ReportContact, ReportLocation, TicketStatus


@dataclass
class TicketRecord:
    ticket_id: str
    ticket_number: str
    tracking_code: str
    status: TicketStatus
    description: str
    language_hint: str
    contact: ReportContact
    location: ReportLocation
    image_object_key: str
    platform: str
    app_version: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
