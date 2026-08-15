"""DynamoDB work-order uniqueness and conditional transitions (issue #247)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.dynamo_work_order_store import DynamoWorkOrderStore
from app.schemas.stored_ticket import StoredTicket
from app.schemas.work_order import StoredWorkOrder
from app.services.work_orders.service import generate_work_order_id

BEIRUT = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ROAD = "d1111111-1111-1111-1111-111111111111"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _ticket(ticket_id: str = "tkt_wo_dynamo") -> StoredTicket:
    stamped = _now()
    return StoredTicket(
        ticketId=ticket_id,
        ticketNumber="BG-2026-9247",
        trackingCode="WO247A",
        description="Pothole near the university gate.",
        contact={"phone": "+96170123456"},
        location={
            "latitude": 33.89,
            "longitude": 35.50,
            "addressText": "Hamra, Beirut",
            "source": "GPS",
        },
        imageObjectKey="reports/photos/v2/owner/pothole.jpg",
        status="UNDER_REVIEW",
        municipalityId=BEIRUT,
        departmentId=ROAD,
        createdAt=stamped,
        updatedAt=stamped,
    )


def _work_order(
    ticket_id: str, *, state: str = "QUEUED", stamped: str | None = None
) -> StoredWorkOrder:
    created = stamped or _now()
    return StoredWorkOrder(
        workOrderId=generate_work_order_id(),
        ticketId=ticket_id,
        municipalityId=BEIRUT,
        departmentId=ROAD,
        state=state,
        summary="Inspect and fill the pothole.",
        createdAt=created,
        createdBy="staff_admin_001",
        updatedAt=created,
        updatedBy="staff_admin_001",
    )


def test_dynamo_second_create_returns_the_existing_active_work_order(
    dynamodb_settings: Settings,
) -> None:
    tickets = DynamoTicketStore(dynamodb_settings)
    store = DynamoWorkOrderStore(dynamodb_settings)
    ticket = _ticket()
    tickets.save(ticket)
    first = _work_order(ticket.ticket_id)
    second = _work_order(ticket.ticket_id)

    created = store.create_active(first)
    replayed = store.create_active(second)

    assert created.work_order_id == first.work_order_id
    assert replayed.work_order_id == first.work_order_id
    active = store.find_active_for_ticket(ticket.ticket_id)
    assert active is not None
    assert active.work_order_id == first.work_order_id
    assert {item.work_order_id for item in store.list_by_ticket_id(ticket.ticket_id)} == {
        first.work_order_id
    }
    refreshed = tickets.get(ticket.ticket_id)
    assert refreshed is not None
    assert refreshed.active_work_order_id == first.work_order_id


def test_dynamo_stale_terminal_transition_cannot_overwrite_winner(
    dynamodb_settings: Settings,
) -> None:
    tickets = DynamoTicketStore(dynamodb_settings)
    store = DynamoWorkOrderStore(dynamodb_settings)
    ticket = _ticket("tkt_wo_terminal")
    tickets.save(ticket)
    created = store.create_active(_work_order(ticket.ticket_id, state="IN_PROGRESS"))
    started_at = created.updated_at

    completed = store.save_if_state(
        created.model_copy(
            update={
                "state": "COMPLETED",
                "completed_at": _now(),
                "completed_by": "staff_admin_001",
                "updated_at": _now(),
                "updated_by": "staff_admin_001",
            }
        ),
        expected_state="IN_PROGRESS",
        expected_updated_at=started_at,
        clear_active=True,
    )
    assert completed is not None
    loaded = store.get(created.work_order_id)
    assert loaded is not None
    assert loaded.state == "COMPLETED"
    assert store.find_active_for_ticket(ticket.ticket_id) is None
    refreshed = tickets.get(ticket.ticket_id)
    assert refreshed is not None
    assert refreshed.active_work_order_id is None

    cancelled = store.save_if_state(
        created.model_copy(
            update={
                "state": "CANCELLED",
                "cancelled_at": _now(),
                "cancelled_by": "staff_admin_001",
                "cancel_reason_code": "NO_LONGER_NEEDED",
                "updated_at": _now(),
                "updated_by": "staff_admin_001",
            }
        ),
        expected_state="IN_PROGRESS",
        expected_updated_at=started_at,
        clear_active=True,
    )
    assert cancelled is None
    still_complete = store.get(created.work_order_id)
    assert still_complete is not None
    assert still_complete.state == "COMPLETED"

    stale_assign = store.save_if_state(
        created.model_copy(
            update={
                "state": "ASSIGNED",
                "updated_at": _now(),
                "updated_by": "staff_admin_001",
            }
        ),
        expected_state="IN_PROGRESS",
        expected_updated_at=started_at,
    )
    assert stale_assign is None
