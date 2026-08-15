"""DynamoDB work-order uniqueness and conditional transitions (issue #247)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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


def test_dynamo_create_race_keeps_one_active_work_order(dynamodb_settings: Settings) -> None:
    tickets = DynamoTicketStore(dynamodb_settings)
    store = DynamoWorkOrderStore(dynamodb_settings)
    ticket = _ticket()
    tickets.save(ticket)
    first = _work_order(ticket.ticket_id)
    second = _work_order(ticket.ticket_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        winners = list(pool.map(store.create_active, [first, second]))

    ids = {item.work_order_id for item in winners}
    assert len(ids) == 1
    active = store.find_active_for_ticket(ticket.ticket_id)
    assert active is not None
    assert active.work_order_id in {first.work_order_id, second.work_order_id}
    assert {item.work_order_id for item in store.list_by_ticket_id(ticket.ticket_id)} == {
        active.work_order_id
    }
    refreshed = tickets.get(ticket.ticket_id)
    assert refreshed is not None
    assert refreshed.active_work_order_id == active.work_order_id


def test_dynamo_conflicting_terminal_transitions_keep_one_winner(
    dynamodb_settings: Settings,
) -> None:
    tickets = DynamoTicketStore(dynamodb_settings)
    store = DynamoWorkOrderStore(dynamodb_settings)
    ticket = _ticket("tkt_wo_terminal")
    tickets.save(ticket)
    created = store.create_active(_work_order(ticket.ticket_id, state="IN_PROGRESS"))
    started_at = created.updated_at

    complete = created.model_copy(
        update={
            "state": "COMPLETED",
            "completed_at": _now(),
            "completed_by": "staff_admin_001",
            "updated_at": _now(),
            "updated_by": "staff_admin_001",
        }
    )
    cancel = created.model_copy(
        update={
            "state": "CANCELLED",
            "cancelled_at": _now(),
            "cancelled_by": "staff_admin_001",
            "cancel_reason_code": "NO_LONGER_NEEDED",
            "updated_at": _now(),
            "updated_by": "staff_admin_001",
        }
    )

    def _complete() -> StoredWorkOrder | None:
        return store.save_if_state(
            complete,
            expected_state="IN_PROGRESS",
            expected_updated_at=started_at,
            clear_active=True,
        )

    def _cancel() -> StoredWorkOrder | None:
        return store.save_if_state(
            cancel,
            expected_state="IN_PROGRESS",
            expected_updated_at=started_at,
            clear_active=True,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda fn: fn(), [_complete, _cancel]))

    winners = [item for item in results if item is not None]
    assert len(winners) == 1
    loaded = store.get(created.work_order_id)
    assert loaded is not None
    assert loaded.state in {"COMPLETED", "CANCELLED"}
    assert store.find_active_for_ticket(ticket.ticket_id) is None
    refreshed = tickets.get(ticket.ticket_id)
    assert refreshed is not None
    assert refreshed.active_work_order_id is None
    stale = store.save_if_state(
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
    assert stale is None
