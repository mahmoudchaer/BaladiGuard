"""Staff password-reset API tests (issue #178)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.database.memory_staff_password_reset import staff_password_reset_store
from app.services.staff.password_reset import (
    GENERIC_RESET_MESSAGE,
    RESET_MAX_ATTEMPTS,
    staff_password_reset_service,
)


def _latest_code(username: str = "staff") -> str:
    challenge = staff_password_reset_store.get_latest_for_username(username)
    assert challenge is not None
    code = staff_password_reset_service.peek_dev_reset_code(challenge.challenge_id)
    assert code is not None
    return code


def test_reset_request_is_account_neutral(anonymous_client: TestClient) -> None:
    known = anonymous_client.post(
        "/v1/staff/password-reset/request",
        json={"username": "staff"},
    )
    unknown = anonymous_client.post(
        "/v1/staff/password-reset/request",
        json={"username": "does-not-exist"},
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"] == GENERIC_RESET_MESSAGE
    assert "challengeId" not in known.json() or known.json().get("challengeId") is None
    assert "code" not in known.json()
    assert "code" not in unknown.json()


def test_valid_reset_then_login_with_new_password(anonymous_client: TestClient) -> None:
    request = anonymous_client.post(
        "/v1/staff/password-reset/request",
        json={"username": "staff"},
    )
    assert request.status_code == 200
    code = _latest_code("staff")

    confirm = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "staff",
            "code": code,
            "newPassword": "new-staff-password-123",
        },
    )
    assert confirm.status_code == 200, confirm.text

    old_login = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "staff-demo-password"},
    )
    assert old_login.status_code == 401

    new_login = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "new-staff-password-123"},
    )
    assert new_login.status_code == 200, new_login.text
    assert new_login.json()["username"] == "staff"


def test_expired_reset_code_rejected(anonymous_client: TestClient) -> None:
    past = datetime.now(UTC) - timedelta(minutes=20)
    staff_password_reset_service.request_reset("staff", now=past)
    code = _latest_code("staff")
    confirm = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "staff",
            "code": code,
            "newPassword": "another-password-123",
        },
    )
    assert confirm.status_code == 400
    assert confirm.json()["error"]["code"] == "RESET_EXPIRED"


def test_reuse_of_consumed_code_rejected(anonymous_client: TestClient) -> None:
    anonymous_client.post("/v1/staff/password-reset/request", json={"username": "staff"})
    code = _latest_code("staff")
    first = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "staff",
            "code": code,
            "newPassword": "first-password-12345",
        },
    )
    assert first.status_code == 200
    second = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "staff",
            "code": code,
            "newPassword": "second-password-12345",
        },
    )
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "RESET_INVALID"


def test_unknown_account_confirm_is_safe(anonymous_client: TestClient) -> None:
    confirm = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "missing-user",
            "code": "123456",
            "newPassword": "whatever-password",
        },
    )
    assert confirm.status_code == 400
    assert confirm.json()["error"]["code"] == "RESET_INVALID"


def test_incorrect_code_then_attempt_limit(anonymous_client: TestClient) -> None:
    anonymous_client.post("/v1/staff/password-reset/request", json={"username": "staff"})
    for _ in range(RESET_MAX_ATTEMPTS):
        response = anonymous_client.post(
            "/v1/staff/password-reset/confirm",
            json={
                "username": "staff",
                "code": "000000",
                "newPassword": "whatever-password",
            },
        )
        assert response.status_code in {400, 429}
    limited = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "staff",
            "code": "000000",
            "newPassword": "whatever-password",
        },
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_dev_adapter_exposes_code_only_locally() -> None:
    _message, challenge_id = staff_password_reset_service.request_reset("admin")
    assert challenge_id is not None
    code = staff_password_reset_service.peek_dev_reset_code(challenge_id)
    assert code is not None
    assert len(code) == 6
    stored = staff_password_reset_store.get(challenge_id)
    assert stored is not None
    assert code not in stored.model_dump_json()


def test_resend_supersedes_prior_open_challenge(anonymous_client: TestClient) -> None:
    first = staff_password_reset_service.request_reset("staff")
    first_id = first[1]
    assert first_id is not None
    first_code = staff_password_reset_service.peek_dev_reset_code(first_id)
    assert first_code is not None

    second = staff_password_reset_service.request_reset("staff")
    second_id = second[1]
    assert second_id is not None
    assert second_id != first_id
    second_code = _latest_code("staff")

    stale = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "staff",
            "code": first_code,
            "newPassword": "should-not-apply-123",
        },
    )
    assert stale.status_code == 400
    assert stale.json()["error"]["code"] == "RESET_INVALID"

    ok = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "staff",
            "code": second_code,
            "newPassword": "supersede-password-123",
        },
    )
    assert ok.status_code == 200


def test_concurrent_confirm_applies_password_once(anonymous_client: TestClient) -> None:
    import concurrent.futures

    anonymous_client.post("/v1/staff/password-reset/request", json={"username": "staff"})
    code = _latest_code("staff")

    def attempt(index: int) -> int:
        response = anonymous_client.post(
            "/v1/staff/password-reset/confirm",
            json={
                "username": "staff",
                "code": code,
                "newPassword": f"race-password-{index:02d}-xx",
            },
        )
        return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(attempt, range(8)))

    assert statuses.count(200) == 1
    assert all(status in {200, 400} for status in statuses)

    winners = [
        anonymous_client.post(
            "/v1/staff/login",
            json={"username": "staff", "password": f"race-password-{index:02d}-xx"},
        ).status_code
        for index in range(8)
    ]
    assert winners.count(200) == 1


def test_reset_revokes_existing_staff_sessions(anonymous_client: TestClient) -> None:
    login = anonymous_client.post(
        "/v1/staff/login",
        json={"username": "staff", "password": "staff-demo-password"},
    )
    assert login.status_code == 200
    token = login.json()["accessToken"]

    anonymous_client.post("/v1/staff/password-reset/request", json={"username": "staff"})
    code = _latest_code("staff")
    confirm = anonymous_client.post(
        "/v1/staff/password-reset/confirm",
        json={
            "username": "staff",
            "code": code,
            "newPassword": "rotated-password-999",
        },
    )
    assert confirm.status_code == 200

    stale = anonymous_client.get(
        "/v1/tickets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert stale.status_code == 401

# CI re-trigger marker for atomic consume follow-up.

