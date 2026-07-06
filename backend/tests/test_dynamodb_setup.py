import os
from datetime import UTC, datetime

import pytest
from moto import mock_aws

from app.config import Settings, get_settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.dynamodb_tables import build_table_name
from app.database.migrations import create_tables
from app.schemas.stored_ticket import PENDING_CLASSIFICATION, StoredTicket
from app.schemas.ticket import ReportContact, ReportLocation


@pytest.fixture
def dynamodb_settings() -> Settings:
    original_backend = os.environ.get("DATABASE_BACKEND")
    original_region = os.environ.get("AWS_REGION")
    original_endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL")
    original_seed = os.environ.get("SEED_SAMPLE_TICKETS")

    with mock_aws():
        os.environ["DATABASE_BACKEND"] = "dynamodb"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["SEED_SAMPLE_TICKETS"] = "false"
        os.environ.pop("DYNAMODB_ENDPOINT_URL", None)
        get_settings.cache_clear()

        settings = Settings()
        create_tables(settings.dynamodb_table_prefix, settings)

        yield settings

    if original_backend is None:
        os.environ.pop("DATABASE_BACKEND", None)
    else:
        os.environ["DATABASE_BACKEND"] = original_backend

    if original_region is None:
        os.environ.pop("AWS_REGION", None)
    else:
        os.environ["AWS_REGION"] = original_region

    if original_endpoint is None:
        os.environ.pop("DYNAMODB_ENDPOINT_URL", None)
    else:
        os.environ["DYNAMODB_ENDPOINT_URL"] = original_endpoint

    if original_seed is None:
        os.environ.pop("SEED_SAMPLE_TICKETS", None)
    else:
        os.environ["SEED_SAMPLE_TICKETS"] = original_seed

    get_settings.cache_clear()


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
