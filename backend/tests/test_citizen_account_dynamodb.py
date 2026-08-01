"""DynamoDB-backed citizen account store tests (issue #169)."""

from __future__ import annotations

import concurrent.futures

from app.config import Settings
from app.database.dynamo_citizen_otp import DynamoCitizenOtpStore
from app.database.dynamo_citizen_session import DynamoCitizenSessionStore
from app.database.dynamo_citizen_store import DynamoCitizenStore
from app.database.dynamodb_tables import TABLE_DEFINITIONS, build_table_name
from app.services.citizens.service import CitizenService, CitizenServiceError


def _service(settings: Settings) -> CitizenService:
    return CitizenService(
        store=DynamoCitizenStore(settings),
        session_store=DynamoCitizenSessionStore(settings),
        otp_store=DynamoCitizenOtpStore(settings),
        settings=settings,
    )


def test_users_table_has_no_email_index(dynamodb_settings: Settings) -> None:
    users_def = next(item for item in TABLE_DEFINITIONS if item["suffix"] == "users")
    index_names = {index["IndexName"] for index in users_def["global_secondary_indexes"]}
    assert "phone-index" in index_names
    assert "email-index" not in index_names

    suffixes = {item["suffix"] for item in TABLE_DEFINITIONS}
    assert {"phone-claims", "citizen-otp-challenges", "citizen-sessions"}.issubset(suffixes)

    from app.database.dynamodb import create_dynamodb_client

    client = create_dynamodb_client(dynamodb_settings)
    description = client.describe_table(
        TableName=build_table_name(dynamodb_settings.dynamodb_table_prefix, "users")
    )["Table"]
    gsis = {index["IndexName"] for index in description.get("GlobalSecondaryIndexes", [])}
    assert "email-index" not in gsis
    assert "phone-index" in gsis


def test_dynamo_create_lookup_and_duplicate_phone(dynamodb_settings: Settings) -> None:
    service = _service(dynamodb_settings)
    created = service.create_citizen(phone="+961 70 123 456", full_name="Ada")
    found = service.get_by_phone("70123456", region="LB")
    assert found is not None
    assert found.user_id == created.user_id

    try:
        service.create_citizen(phone="+96170123456", full_name="Other")
        raise AssertionError("expected conflict")
    except CitizenServiceError as exc:
        assert exc.code == "PHONE_UNAVAILABLE"


def test_dynamo_concurrent_phone_claims(dynamodb_settings: Settings) -> None:
    service = _service(dynamodb_settings)

    def attempt(index: int) -> str | None:
        try:
            return service.create_citizen(
                phone="+96170888888",
                full_name=f"Dyn {index}",
            ).user_id
        except CitizenServiceError:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        winners = [user_id for user_id in pool.map(attempt, range(6)) if user_id]
    assert len(winners) == 1


def test_dynamo_partial_update_and_phone_change(dynamodb_settings: Settings) -> None:
    from app.schemas.citizen import CitizenProfileUpdateRequest

    service = _service(dynamodb_settings)
    user = service.create_citizen(phone="+96170123456", full_name="Ada")
    updated = service.update_profile(
        user.user_id,
        CitizenProfileUpdateRequest.model_validate(
            {
                "email": "ada@example.com",
                "notificationPreferences": {"ticketUpdates": "EMAIL"},
            }
        ),
    )
    assert updated.email == "ada@example.com"
    assert updated.notification_preferences.ticket_updates == "EMAIL"

    challenge_id, code = service.create_change_phone_challenge(
        user_id=user.user_id,
        phone="+96171999999",
    )
    token = service.issue_session(user.user_id)
    changed = service.update_profile(
        user.user_id,
        CitizenProfileUpdateRequest.model_validate(
            {
                "phone": "+96171999999",
                "phoneChangeChallengeId": challenge_id,
                "phoneChangeCode": code,
            }
        ),
    )
    assert changed.phone == "+96171999999"
    assert service.get_by_phone("+96170123456") is None
    assert service.get_by_phone("+96171999999") is not None

    from app.core.citizen_auth import CitizenAuthError, verify_citizen_access_token

    try:
        verify_citizen_access_token(
            token, session_store=DynamoCitizenSessionStore(dynamodb_settings)
        )
        raise AssertionError("expected revoked session")
    except CitizenAuthError:
        pass
