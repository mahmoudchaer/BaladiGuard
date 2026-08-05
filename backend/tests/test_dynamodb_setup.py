from datetime import UTC, datetime

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.dynamodb_tables import build_table_name
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import ReportContact, ReportLocation


def _dynamo_owned_ticket(
    *,
    ticket_id: str,
    ticket_number: str,
    tracking_code: str,
    owner_user_id: str | None,
    created_at: str,
) -> StoredTicket:
    return StoredTicket(
        ticketId=ticket_id,
        ticketNumber=ticket_number,
        trackingCode=tracking_code,
        description="Broken bench in the park.",
        contact=ReportContact(name="Test User", phone="+96170000000"),
        location=ReportLocation(
            latitude=33.89,
            longitude=35.50,
            addressText="Hamra, Beirut",
            source="MANUAL",
        ),
        imageObjectKey="reports/mock/test.jpg",
        ownerUserId=owner_user_id,
        status="SUBMITTED",
        category=PENDING_CLASSIFICATION,
        createdAt=created_at,
        updatedAt=created_at,
    )


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
    assert store.has_tracking_code("zx99yw")

    by_tracking = store.get_by_tracking_code("zx99yw")
    assert by_tracking is not None
    assert by_tracking.ticket_id == "tkt_test_001"
    assert by_tracking.tracking_code == "ZX99YW"
    assert store.get_by_tracking_code("ZZZZZZ") is None

    first_sequence = store.next_sequence()
    second_sequence = store.next_sequence()
    assert first_sequence == 1
    assert second_sequence == 2


def test_dynamo_ticket_store_updates_status(dynamodb_settings: Settings) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    ticket = StoredTicket(
        ticketId="tkt_test_status",
        ticketNumber="BG-2026-0100",
        trackingCode="AA11BB",
        description="Traffic signal is not working.",
        contact=ReportContact(name="Test User", phone="+96170000000"),
        location=ReportLocation(
            latitude=33.89,
            longitude=35.50,
            addressText="Sodeco, Beirut",
            source="MANUAL",
        ),
        imageObjectKey="reports/mock/signal.jpg",
        status="SUBMITTED",
        category=PENDING_CLASSIFICATION,
        createdAt=created_at,
        updatedAt=created_at,
    )

    store.save(ticket)
    updated = store.update_status("tkt_test_status", "IN_PROGRESS", "2026-07-09T10:30:00Z")

    assert updated is not None
    assert updated.status == "IN_PROGRESS"
    assert updated.updated_at == "2026-07-09T10:30:00Z"

    loaded = store.get("tkt_test_status")
    assert loaded is not None
    assert loaded.status == "IN_PROGRESS"
    assert loaded.updated_at == "2026-07-09T10:30:00Z"


def test_dynamo_ticket_store_update_status_returns_none_for_missing_ticket(
    dynamodb_settings: Settings,
) -> None:
    store = DynamoTicketStore(dynamodb_settings)

    updated = store.update_status("tkt_missing", "IN_PROGRESS", "2026-07-09T10:30:00Z")

    assert updated is None


def test_dynamo_ticket_store_lists_owner_history_with_stable_cursor(
    dynamodb_settings: Settings,
) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    for ticket in (
        _dynamo_owned_ticket(
            ticket_id="tkt_owner_oldest",
            ticket_number="BG-2026-0201",
            tracking_code="OLD111",
            owner_user_id="usr_owner",
            created_at="2026-08-01T09:00:00Z",
        ),
        _dynamo_owned_ticket(
            ticket_id="tkt_owner_middle",
            ticket_number="BG-2026-0202",
            tracking_code="MID222",
            owner_user_id="usr_owner",
            created_at="2026-08-02T09:00:00Z",
        ),
        _dynamo_owned_ticket(
            ticket_id="tkt_owner_newest",
            ticket_number="BG-2026-0203",
            tracking_code="NEW333",
            owner_user_id="usr_owner",
            created_at="2026-08-03T09:00:00Z",
        ),
        _dynamo_owned_ticket(
            ticket_id="tkt_other_owner",
            ticket_number="BG-2026-0204",
            tracking_code="OTH444",
            owner_user_id="usr_other",
            created_at="2026-08-04T09:00:00Z",
        ),
        _dynamo_owned_ticket(
            ticket_id="tkt_legacy",
            ticket_number="BG-2026-0205",
            tracking_code="LEG555",
            owner_user_id=None,
            created_at="2026-08-05T09:00:00Z",
        ),
    ):
        store.save(ticket)

    first = store.list_by_owner("usr_owner", limit=2)
    assert [ticket.tracking_code for ticket in first.items] == ["NEW333", "MID222"]
    assert first.next_cursor

    store.save(
        _dynamo_owned_ticket(
            ticket_id="tkt_owner_inserted_newer",
            ticket_number="BG-2026-0206",
            tracking_code="INS666",
            owner_user_id="usr_owner",
            created_at="2026-08-06T09:00:00Z",
        )
    )

    second = store.list_by_owner("usr_owner", limit=2, cursor=first.next_cursor)
    assert [ticket.tracking_code for ticket in second.items] == ["OLD111"]
    assert second.next_cursor is None


def test_dynamo_ticket_store_lists_public_reports_from_publishable_index(
    dynamodb_settings: Settings,
) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    unpublished = _dynamo_owned_ticket(
        ticket_id="tkt_public_unpublished",
        ticket_number="BG-2026-0301",
        tracking_code="PUB301",
        owner_user_id="usr_public",
        created_at="2026-08-01T09:00:00Z",
    )
    published = _dynamo_owned_ticket(
        ticket_id="tkt_public_published",
        ticket_number="BG-2026-0302",
        tracking_code="PUB302",
        owner_user_id="usr_public",
        created_at="2026-08-02T09:00:00Z",
    )
    store.save(unpublished)
    store.save(published)

    assert store.list_public(limit=10).items == []
    assert store.get_by_ticket_number("bg-2026-0302") is not None

    updated = store.patch_fields(
        published.ticket_id,
        {
            "final_category": "road_damage",
            "category": "road_damage",
            "public_status": "PUBLISHED",
            "public_description": "Approved public road hazard summary.",
            "public_location_label": "Hamra, Beirut",
            "public_published_at": "2026-08-05T12:00:00Z",
        },
    )

    assert updated is not None
    public_page = store.list_public(limit=10)
    assert [ticket.ticket_number for ticket in public_page.items] == ["BG-2026-0302"]

    store.patch_fields(published.ticket_id, {"public_status": "UNPUBLISHED"})
    assert store.list_public(limit=10).items == []


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


def test_seed_script_loads_sample_ticket_story_when_enabled(
    dynamodb_settings: Settings,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SEED_SAMPLE_TICKETS", "true")

    from app.config import Settings as RuntimeSettings
    from app.database.dynamo_duplicate_group_store import DynamoDuplicateGroupStore
    from app.database.dynamo_status_history_store import DynamoStatusHistoryStore
    from app.database.dynamo_ticket_store import DynamoTicketStore
    from app.database.dynamodb import create_dynamodb_resource
    from app.database.seeding import run_seed
    from app.utils.phone import phone_claim_key

    settings = RuntimeSettings()
    run_seed(settings)

    resource = create_dynamodb_resource(settings)
    prefix = settings.dynamodb_table_prefix
    users_table = resource.Table(build_table_name(prefix, "users"))
    claims_table = resource.Table(build_table_name(prefix, "phone-claims"))
    users = users_table.scan()["Items"]
    assert len(users) == 3
    assert users_table.get_item(Key={"userId": "usr_demo_layla"})["Item"]["publicNameVisible"]
    assert (
        claims_table.get_item(Key={"phoneKey": phone_claim_key("+96170123456")})["Item"]["userId"]
        == "usr_demo_ahmad"
    )

    ticket_store = DynamoTicketStore(settings)
    public_page = ticket_store.list_public(limit=20)
    ticket_numbers = [ticket.ticket_number for ticket in public_page.items]
    assert "BG-2026-0008" in ticket_numbers
    assert "BG-2026-0011" not in ticket_numbers

    detail = ticket_store.get_by_ticket_number("bg-2026-0008")
    assert detail is not None
    assert detail.owner_user_id == "usr_demo_layla"
    assert detail.public_location_label != detail.location.address_text

    status_history = DynamoStatusHistoryStore(settings).list_by_ticket_id(detail.ticket_id)
    assert [entry.new_status for entry in status_history] == ["SUBMITTED"]

    group = DynamoDuplicateGroupStore(settings).get("99999999-9999-9999-9999-999999999999")
    assert group is not None
    assert group.canonical_ticket_id == "tkt_55555555555555555555555555555555"
