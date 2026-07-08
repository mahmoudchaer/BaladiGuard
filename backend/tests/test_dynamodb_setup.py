from datetime import UTC, datetime

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import ReportContact, ReportLocation


def test_dynamo_ticket_store_save_get_and_sequence(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    ticket = StoredTicket(
        ticketId="tkt_test_001",
        ticketNumber="BG-2026-0099",
        trackingCode="ZX99YW",
        description="Broken bench in the park.",
        contact=ReportContact(name="Test User", phone="+96170000000"),
        location=ReportLocation(
            latitude=33.89,
            longitude=35.50,
            addressText="Hamra, Beirut",
            source="MANUAL",
        ),
        imageObjectKey="reports/mock/test.jpg",
        status="SUBMITTED",
        category=PENDING_CLASSIFICATION,
        createdAt=created_at,
        updatedAt=created_at,
    )

    store.save(ticket)
    loaded = store.get("tkt_test_001")

    assert loaded is not None
    assert loaded.ticket_number == "BG-2026-0099"
    assert loaded.location.address_text == "Hamra, Beirut"
    assert store.has_ticket_number("BG-2026-0099")
    assert store.has_tracking_code("ZX99YW")

    first_sequence = store.next_sequence()
    second_sequence = store.next_sequence()
    assert first_sequence == 1
    assert second_sequence == 2


def test_seed_script_loads_reference_data(dynamodb_settings: Settings) -> None:
    from app.database.seeding import run_seed

    run_seed(dynamodb_settings)

    from app.database.dynamodb import create_dynamodb_resource

    resource = create_dynamodb_resource(dynamodb_settings)
    prefix = dynamodb_settings.dynamodb_table_prefix

    municipalities = resource.Table(build_table_name(prefix, "municipalities")).scan()["Items"]
    departments = resource.Table(build_table_name(prefix, "departments")).scan()["Items"]
    categories = resource.Table(build_table_name(prefix, "categories")).scan()["Items"]

    assert len(municipalities) == 1
    assert len(departments) == 8
    assert len(categories) == 10
