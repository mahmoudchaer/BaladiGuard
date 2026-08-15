import os

import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

# Import app.config early, then force deterministic test settings for the suite.
import app.config  # noqa: F401
from app.config import Settings, get_settings

os.environ["DATABASE_BACKEND"] = "memory"
os.environ["APP_ENV"] = "test"
# Avoid background readiness publisher threads across the suite; dedicated tests
# exercise the publisher explicitly.
os.environ["READINESS_PROBE_PUBLISHER"] = "false"
# Tests must use the curated local place index even when the shared team .env
# configures a live Amazon Location index.
os.environ["LOCATION_PLACE_INDEX_NAME"] = ""
# Deterministic staff credentials for issue #72 authorization tests.
os.environ["SECRET_KEY"] = "test-secret-key-for-ci"
os.environ["STAFF_USERNAME"] = "staff"
os.environ["STAFF_PASSWORD"] = "staff-demo-password"
os.environ["DEMO_STAFF_PASSWORD"] = "staff-demo-password"
os.environ["SEED_DEMO_STAFF"] = "true"
os.environ["STAFF_TOKEN_TTL_SECONDS"] = "43200"
# Keep staff login usable across suite helpers; production defaults stay stricter.
os.environ["RATE_LIMIT_STAFF_LOGIN_LIMIT"] = "1000"
os.environ["RATE_LIMIT_STAFF_LOGIN_WINDOW_SECONDS"] = "60"
get_settings.cache_clear()

from app.core.rate_limit import clear_rate_limiter_cache, public_ticket_rate_limiter  # noqa: E402
from app.database.memory import ticket_store  # noqa: E402
from app.database.memory_account_audit import account_audit_store  # noqa: E402
from app.database.memory_ai_job import ai_job_store  # noqa: E402
from app.database.memory_audit_history import audit_history_store  # noqa: E402
from app.database.memory_citizen import citizen_store  # noqa: E402
from app.database.memory_citizen_otp import citizen_otp_store  # noqa: E402
from app.database.memory_citizen_session import citizen_session_store  # noqa: E402
from app.database.memory_duplicate_group import duplicate_group_store  # noqa: E402
from app.database.memory_notification_delivery import notification_delivery_store  # noqa: E402
from app.database.memory_photo_claim import photo_claim_store  # noqa: E402
from app.database.memory_resolution_review import resolution_review_store  # noqa: E402
from app.database.memory_staff import staff_store  # noqa: E402
from app.database.memory_staff_comments import staff_comment_store  # noqa: E402
from app.database.memory_staff_password_reset import staff_password_reset_store  # noqa: E402
from app.database.memory_status_history import status_history_store  # noqa: E402
from app.database.memory_work_order import work_order_store  # noqa: E402
from app.database.memory_work_order_evidence import work_order_evidence_store  # noqa: E402
from app.database.memory_workforce import workforce_store  # noqa: E402
from app.database.migrations import create_tables  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.citizen import CitizenProfileUpdateRequest, StoredCitizenUser  # noqa: E402
from app.schemas.classification import ClassificationInputs, ClassificationResult  # noqa: E402
from app.schemas.cleaning import CleaningResult  # noqa: E402
from app.services.citizens.service import citizen_service  # noqa: E402
from app.services.complaints.ticket_service import ticket_service  # noqa: E402
from app.services.staff.bootstrap import ensure_demo_staff_accounts  # noqa: E402
from app.services.staff.password_reset import staff_password_reset_service  # noqa: E402

DEFAULT_CITIZEN_PHONE = "+96170123456"
DEFAULT_CITIZEN_FULL_NAME = "Citizen Name"
DEFAULT_CITIZEN_EMAIL = "citizen@example.com"


def issue_test_staff_token(
    client: TestClient,
    *,
    username: str = "admin",
    password: str = "staff-demo-password",
) -> str:
    response = client.post(
        "/v1/staff/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]


def ensure_contribution_ready_citizen(
    *,
    phone: str = DEFAULT_CITIZEN_PHONE,
    full_name: str = DEFAULT_CITIZEN_FULL_NAME,
    email: str | None = DEFAULT_CITIZEN_EMAIL,
    ticket_updates: str = "SMS",
) -> tuple[StoredCitizenUser, str]:
    """Get-or-create a contribution-ready citizen and return ``(user, bearer_token)``."""
    user = citizen_service.get_by_phone(phone)
    if user is None:
        user = citizen_service.create_citizen(phone=phone, full_name=full_name, email=email)
    updates: dict[str, object] = {}
    if user.full_name != full_name:
        updates["fullName"] = full_name
    if email is not None and user.email != email:
        updates["email"] = email
    if user.notification_preferences.ticket_updates != ticket_updates:
        updates["notificationPreferences"] = {"ticketUpdates": ticket_updates}
    if updates:
        profile = citizen_service.update_profile(
            user.user_id,
            CitizenProfileUpdateRequest.model_validate(updates),
        )
        refreshed = citizen_service.get_by_phone(phone)
        assert refreshed is not None
        user = refreshed
        assert profile.contribution_ready is True
    token = citizen_service.issue_session(user.user_id)
    return user, token


def contribution_ready_auth_headers(
    *,
    phone: str = DEFAULT_CITIZEN_PHONE,
    full_name: str = DEFAULT_CITIZEN_FULL_NAME,
    email: str | None = DEFAULT_CITIZEN_EMAIL,
    ticket_updates: str = "SMS",
) -> dict[str, str]:
    _user, token = ensure_contribution_ready_citizen(
        phone=phone,
        full_name=full_name,
        email=email,
        ticket_updates=ticket_updates,
    )
    return {"Authorization": f"Bearer {token}"}


def authenticated_test_client() -> TestClient:
    """Build a staff-authenticated TestClient for tests that construct one manually."""
    client = TestClient(app)
    token = issue_test_staff_token(client)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture(autouse=True)
def force_mock_notification_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep HTTP workflow tests on the mock adapter even if local `.env` sets real SES/SNS."""
    monkeypatch.setenv("NOTIFICATION_ADAPTER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_ticket_store() -> None:
    ticket_store.clear()
    status_history_store.clear()
    audit_history_store.clear()
    staff_comment_store.clear()
    account_audit_store.clear()
    ai_job_store.clear()
    duplicate_group_store.clear()
    notification_delivery_store.clear()
    photo_claim_store.clear()
    citizen_store.clear()
    citizen_session_store.clear()
    citizen_otp_store.clear()
    staff_store.clear()
    staff_password_reset_store.clear()
    workforce_store.clear()
    work_order_store.clear()
    work_order_evidence_store.clear()
    resolution_review_store.clear()
    staff_password_reset_service.clear_dev_reset_codes()
    from app.services.citizens.service import citizen_service

    citizen_service.clear_dev_otp_codes()
    ensure_demo_staff_accounts()
    clear_rate_limiter_cache()
    public_ticket_rate_limiter.reset()
    from app.services.notifications import reset_delivery_ledger

    reset_delivery_ledger()
    from app.services.complaints.ticket_submission_idempotency import (
        reset_ticket_submission_idempotency_store,
    )

    reset_ticket_submission_idempotency_store()


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
def contribution_ready_citizen() -> tuple[StoredCitizenUser, str]:
    return ensure_contribution_ready_citizen()


@pytest.fixture
def contribution_ready_citizen_headers(
    contribution_ready_citizen: tuple[StoredCitizenUser, str],
) -> dict[str, str]:
    _user, token = contribution_ready_citizen
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(anonymous_client: TestClient) -> TestClient:
    """Default client is staff-authenticated so existing ticket tests keep working."""
    token = issue_test_staff_token(anonymous_client)
    anonymous_client.headers.update({"Authorization": f"Bearer {token}"})
    return anonymous_client


@pytest.fixture
def staff_auth_headers(anonymous_client: TestClient) -> dict[str, str]:
    token = issue_test_staff_token(anonymous_client, username="staff")
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
        clear_rate_limiter_cache()

        settings = Settings()
        create_tables(settings.dynamodb_table_prefix, settings)
        # Staff login now uses persisted accounts (#175); seed demos into moto.
        ensure_demo_staff_accounts(settings=settings)

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
    clear_rate_limiter_cache()
