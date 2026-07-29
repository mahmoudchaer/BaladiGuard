import os

import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

# Importing app.config loads .env with override=True, so force memory afterward.
import app.config  # noqa: F401
from app.config import Settings, get_settings

os.environ["DATABASE_BACKEND"] = "memory"
os.environ["APP_ENV"] = "test"
# Tests must use the curated local place index even when the shared team .env
# configures a live Amazon Location index.
os.environ["LOCATION_PLACE_INDEX_NAME"] = ""
# Deterministic staff credentials for issue #72 authorization tests.
os.environ["SECRET_KEY"] = "test-secret-key-for-ci"
os.environ["STAFF_USERNAME"] = "staff"
os.environ["STAFF_PASSWORD"] = "staff-demo-password"
os.environ["STAFF_TOKEN_TTL_SECONDS"] = "43200"
get_settings.cache_clear()

from app.database.memory import ticket_store  # noqa: E402
from app.database.memory_duplicate_group import duplicate_group_store  # noqa: E402
from app.database.memory_status_history import status_history_store  # noqa: E402
from app.database.migrations import create_tables  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.classification import ClassificationInputs, ClassificationResult  # noqa: E402
from app.schemas.cleaning import CleaningResult  # noqa: E402
from app.services.complaints.ticket_service import ticket_service  # noqa: E402


def issue_test_staff_token(client: TestClient) -> str:
    response = client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "staff-demo-password"},
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


def authenticated_test_client() -> TestClient:
    """Build a staff-authenticated TestClient for tests that construct one manually."""
    client = TestClient(app)
    token = issue_test_staff_token(client)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture(autouse=True)
def reset_ticket_store() -> None:
    ticket_store.clear()
    status_history_store.clear()
    duplicate_group_store.clear()
    from app.services.notifications import reset_delivery_ledger

    reset_delivery_ledger()


@pytest.fixture(autouse=True)
def deterministic_submission_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    def classify(description: str, **_: object) -> ClassificationResult:
        return ClassificationResult(
            category="road_damage",
            explanation="The report describes damage to a public road.",
            usedInputs=ClassificationInputs(description=bool(description), image=False),
        )

    def clean(description: str, **_: object) -> CleaningResult:
        return CleaningResult(
            cleanedDescription=description,
            usedFallback=False,
        )

    monkeypatch.setattr(ticket_service, "_classifier", classify)
    monkeypatch.setattr(ticket_service, "_description_cleaner", clean)


@pytest.fixture
def anonymous_client() -> TestClient:
    """Unauthenticated client for public routes and 401 authorization tests."""
    return TestClient(app)


@pytest.fixture
def client(anonymous_client: TestClient) -> TestClient:
    """Default client is staff-authenticated so existing ticket tests keep working."""
    token = issue_test_staff_token(anonymous_client)
    anonymous_client.headers.update({"Authorization": f"Bearer {token}"})
    return anonymous_client


@pytest.fixture
def staff_auth_headers(anonymous_client: TestClient) -> dict[str, str]:
    token = issue_test_staff_token(anonymous_client)
    return {"Authorization": f"Bearer {token}"}


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
