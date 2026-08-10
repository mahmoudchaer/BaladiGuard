from datetime import UTC, datetime

from app.database.memory import ticket_store
from app.services.complaints.sla import derive_ticket_sla
from app.services.complaints.ticket_list_filters import parse_ticket_list_filters
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


def test_sla_policy_levels_and_exact_due_soon_boundary(client):
    for priority in ("low", "medium", "high", "critical"):
        ticket = _ticket(client, priority=priority)
        result = derive_ticket_sla(ticket, now=datetime(2026, 1, 1, 3, tzinfo=UTC))
        assert result.policy_key == priority
        assert result.state in {"on_track", "due_soon", "overdue"}
    # High acknowledgement is 24h; its final 20% begins exactly 4h48m before due.
    high = _ticket(client, priority="high")
    assert derive_ticket_sla(high, now=datetime(2026, 1, 1, 19, 12, tzinfo=UTC)).state == "due_soon"


def test_sla_filter_validation():
    filters, errors = parse_ticket_list_filters(sla_state="overdue")
    assert errors == []
    assert filters is not None and filters.sla_state == "overdue"
    filters, errors = parse_ticket_list_filters(sla_state="late")
    assert filters is None
    assert {error.field for error in errors} == {"slaState"}
