from datetime import UTC, datetime

from app.database.memory import ticket_store
from app.services.complaints.sla import derive_ticket_sla
from tests.test_read_tickets import create_ticket


def _ticket(client, *, priority="high", status="SUBMITTED", created_at=None):
    created = create_ticket(client, "SLA coverage ticket")
    ticket = ticket_store.patch_fields(
        created["ticketId"],
        {
            "priority": priority,
            "status": status,
        },
    )
    assert ticket is not None
    return ticket.model_copy(
        update={"created_at": created_at or "2026-01-01T00:00:00Z", "priority": priority}
    )


def test_sla_boundary_and_terminal_states(client):
    ticket = _ticket(client)
    assert derive_ticket_sla(ticket, now=datetime(2026, 1, 2, tzinfo=UTC)).state == "due_soon"
    assert (
        derive_ticket_sla(ticket, now=datetime(2026, 1, 2, 0, 0, 1, tzinfo=UTC)).state == "overdue"
    )
    assert derive_ticket_sla(_ticket(client, status="RESOLVED")).state == "completed"


def test_sla_is_timezone_safe_and_unavailable_for_legacy_data(client):
    ticket = _ticket(client, created_at="2026-01-01T02:00:00+02:00")
    assert derive_ticket_sla(ticket, now=datetime(2026, 1, 2, tzinfo=UTC)).state == "due_soon"
    legacy = _ticket(client, created_at="not-a-timestamp")
    assert derive_ticket_sla(legacy).state == "unavailable"
    no_priority = _ticket(client, priority=None)
    assert derive_ticket_sla(no_priority).state == "unavailable"
