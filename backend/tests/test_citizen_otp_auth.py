"""Citizen phone OTP login, logout, and session API tests (issue #170)."""

from __future__ import annotations

import concurrent.futures
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.citizen_auth import CITIZEN_SESSION_TTL_SECONDS, issue_citizen_session
from app.core.rate_limit import get_rate_limiter
from app.database.memory_citizen_otp import citizen_otp_store
from app.database.memory_citizen_session import citizen_session_store
from app.services.citizens.service import (
    GENERIC_OTP_MESSAGE,
    OTP_MAX_ATTEMPTS,
    CitizenServiceError,
    citizen_service,
)
from app.services.staff.bootstrap import ensure_demo_staff_accounts
from tests.conftest import issue_test_staff_token


def _request_otp(
    client: TestClient,
    *,
    phone: str = "+96170123456",
    region: str | None = None,
    purpose: str = "LOGIN_OR_SIGNUP",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    body: dict = {"phone": phone, "purpose": purpose}
    if region is not None:
        body["region"] = region
    response = client.post("/v1/citizen/auth/otp/request", json=body, headers=headers or {})
    return response.status_code, response.json()


def _verify_otp(
    client: TestClient,
    *,
    challenge_id: str,
    code: str,
    full_name: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    body: dict = {"challengeId": challenge_id, "code": code}
    if full_name is not None:
        body["fullName"] = full_name
    response = client.post("/v1/citizen/auth/otp/verify", json=body, headers=headers or {})
    return response.status_code, response.json()


def test_otp_request_returns_generic_202_without_code(anonymous_client: TestClient) -> None:
    status, body = _request_otp(anonymous_client, phone="70 123 456", region="LB")
    assert status == 202, body
    assert body["challengeId"].startswith("chl_")
    assert body["expiresIn"] == 300
    assert body["message"] == GENERIC_OTP_MESSAGE
    assert "code" not in body
    assert citizen_service.peek_dev_otp_code(body["challengeId"]) is not None


def test_otp_request_does_not_reveal_account_existence(anonymous_client: TestClient) -> None:
    citizen_service.create_citizen(phone="+96170111111", full_name="Existing")
    existing_status, existing_body = _request_otp(anonymous_client, phone="+96170111111")
    missing_status, missing_body = _request_otp(anonymous_client, phone="+96170999999")
    assert existing_status == missing_status == 202
    assert existing_body["message"] == missing_body["message"] == GENERIC_OTP_MESSAGE


def test_otp_verify_creates_new_citizen_and_session(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client, phone="+96170123456")
    assert status == 202
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None

    status, body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
        full_name="Ada Citizen",
    )
    assert status == 200, body
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] == CITIZEN_SESSION_TTL_SECONDS
    assert body["accessToken"].startswith("csess_")
    assert body["phone"] == "+96170123456"
    assert body["fullName"] == "Ada Citizen"
    assert body["contributionReady"] is True
    assert body["publicNameVisible"] is False
    assert "password" not in body
    assert "codeHash" not in body

    me = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {body['accessToken']}"},
    )
    assert me.status_code == 200
    assert me.json()["userId"] == body["userId"]


def test_otp_verify_logs_into_existing_account(anonymous_client: TestClient) -> None:
    created = citizen_service.create_citizen(phone="+96170123456", full_name="Ada")
    status, request_body = _request_otp(anonymous_client, phone="+96170123456")
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None

    status, body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
    )
    assert status == 200, body
    assert body["userId"] == created.user_id
    assert body["fullName"] == "Ada"


def test_otp_verify_allows_incomplete_profile(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client, phone="+96170123456")
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
    )
    assert status == 200, body
    assert body["fullName"] is None
    assert body["contributionReady"] is False


def test_otp_verify_inactive_account_returns_403_without_session(
    anonymous_client: TestClient,
) -> None:
    user = citizen_service.create_citizen(phone="+96170123456", full_name="Ada")
    inactivated = user.model_copy(update={"active": False})
    from app.database.memory_citizen import citizen_store

    citizen_store.update(inactivated)

    status, request_body = _request_otp(anonymous_client, phone="+96170123456")
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
    )
    assert status == 403
    assert body["error"]["code"] == "ACCOUNT_INACTIVE"


def test_incorrect_otp_returns_invalid_otp(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client)
    assert status == 202
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code="000000",
    )
    assert status == 400
    assert body["error"]["code"] == "INVALID_OTP"


def test_expired_otp_returns_otp_expired(anonymous_client: TestClient) -> None:
    past = datetime.now(UTC) - timedelta(minutes=10)
    challenge_id, _expires, code = citizen_service.request_otp(
        phone="+96170123456",
        now=past,
    )
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=challenge_id,
        code=code,
    )
    assert status == 400
    assert body["error"]["code"] == "OTP_EXPIRED"


def test_resend_supersedes_prior_challenge(anonymous_client: TestClient) -> None:
    first_status, first = _request_otp(anonymous_client, phone="+96170123456")
    second_status, second = _request_otp(anonymous_client, phone="+96170123456")
    assert first_status == second_status == 202
    assert first["challengeId"] != second["challengeId"]

    first_code = citizen_service.peek_dev_otp_code(first["challengeId"])
    assert first_code is not None
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=first["challengeId"],
        code=first_code,
    )
    assert status == 400
    assert body["error"]["code"] == "OTP_EXPIRED"

    second_code = citizen_service.peek_dev_otp_code(second["challengeId"])
    assert second_code is not None
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=second["challengeId"],
        code=second_code,
        full_name="Ada",
    )
    assert status == 200, body


def test_replayed_otp_fails(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client)
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None
    status, _body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
        full_name="Ada",
    )
    assert status == 200
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
    )
    assert status == 400
    assert body["error"]["code"] == "OTP_EXPIRED"


def test_attempt_limit_returns_rate_limited(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client)
    challenge_id = request_body["challengeId"]
    for _ in range(OTP_MAX_ATTEMPTS):
        status, body = _verify_otp(
            anonymous_client,
            challenge_id=challenge_id,
            code="000000",
        )
        assert status in {400, 429}
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=challenge_id,
        code="000000",
    )
    assert status == 429
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_concurrent_verify_has_single_winner(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client, phone="+96170888888")
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None

    def attempt(_: int) -> str | None:
        verify_status, body = _verify_otp(
            anonymous_client,
            challenge_id=request_body["challengeId"],
            code=code,
            full_name="Racer",
        )
        if verify_status == 200:
            return body["userId"]
        assert body["error"]["code"] in {"OTP_EXPIRED", "INVALID_OTP", "PHONE_UNAVAILABLE"}
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))

    winners = [user_id for user_id in results if user_id is not None]
    assert len(winners) == 1


def test_concurrent_login_verify_issues_single_session(anonymous_client: TestClient) -> None:
    """Existing-account login must not mint multiple sessions from one OTP."""
    created = citizen_service.create_citizen(phone="+96170999999", full_name="Existing")
    status, request_body = _request_otp(anonymous_client, phone="+96170999999")
    challenge_id = request_body["challengeId"]
    code = citizen_service.peek_dev_otp_code(challenge_id)
    assert code is not None

    def attempt(_: int) -> str | None:
        verify_status, body = _verify_otp(
            anonymous_client,
            challenge_id=challenge_id,
            code=code,
        )
        if verify_status == 200:
            assert body["userId"] == created.user_id
            return body["accessToken"]
        assert body["error"]["code"] in {"OTP_EXPIRED", "INVALID_OTP"}
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    tokens = [token for token in results if token is not None]
    assert len(tokens) == 1

    stored = citizen_otp_store.get(challenge_id)
    assert stored is not None
    assert stored.consumed_at is not None


def test_logout_revokes_presented_session_only(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client)
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None
    status, first = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
        full_name="Ada",
    )
    assert status == 200
    second_token = citizen_service.issue_session(first["userId"])

    logout = anonymous_client.post(
        "/v1/citizen/auth/logout",
        headers={"Authorization": f"Bearer {first['accessToken']}"},
    )
    assert logout.status_code == 204

    revoked = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {first['accessToken']}"},
    )
    assert revoked.status_code == 401
    assert revoked.headers.get("www-authenticate", "").lower().startswith("bearer")

    still_valid = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert still_valid.status_code == 200


def test_logout_replay_returns_401(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client)
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None
    status, body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
        full_name="Ada",
    )
    headers = {"Authorization": f"Bearer {body['accessToken']}"}
    assert anonymous_client.post("/v1/citizen/auth/logout", headers=headers).status_code == 204
    replay = anonymous_client.post("/v1/citizen/auth/logout", headers=headers)
    assert replay.status_code == 401


def test_expired_session_returns_401(anonymous_client: TestClient) -> None:
    user = citizen_service.create_citizen(phone="+96170123456", full_name="Ada")
    past = datetime.now(UTC) - timedelta(days=31)
    token, session = issue_citizen_session(
        user.user_id,
        session_epoch=user.session_epoch,
        session_store=citizen_session_store,
        now=past,
    )
    # Force expired timestamps even if issue helper clamps.
    citizen_session_store.create(
        session.model_copy(
            update={
                "created_at": past.isoformat().replace("+00:00", "Z"),
                "expires_at": (past + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
            }
        )
    )
    response = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


def test_staff_token_cannot_authenticate_citizen_routes(anonymous_client: TestClient) -> None:
    ensure_demo_staff_accounts()
    staff_token = issue_test_staff_token(anonymous_client)
    headers = {"Authorization": f"Bearer {staff_token}"}

    me = anonymous_client.get("/v1/citizen/me", headers=headers)
    assert me.status_code == 401

    change_request = anonymous_client.post(
        "/v1/citizen/auth/otp/request",
        json={"phone": "+96170123456", "purpose": "CHANGE_PHONE"},
        headers=headers,
    )
    assert change_request.status_code == 401

    logout = anonymous_client.post("/v1/citizen/auth/logout", headers=headers)
    assert logout.status_code == 401


def test_guest_change_phone_request_returns_401(anonymous_client: TestClient) -> None:
    status, body = _request_otp(
        anonymous_client,
        phone="+96171999999",
        purpose="CHANGE_PHONE",
    )
    assert status == 401
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_change_phone_via_otp_verify(anonymous_client: TestClient) -> None:
    user = citizen_service.create_citizen(phone="+96170123456", full_name="Ada")
    old_token = citizen_service.issue_session(user.user_id)
    status, request_body = _request_otp(
        anonymous_client,
        phone="+96171999999",
        purpose="CHANGE_PHONE",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert status == 202, request_body
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None

    status, body = _verify_otp(
        anonymous_client,
        challenge_id=request_body["challengeId"],
        code=code,
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert status == 200, body
    assert body["phone"] == "+96171999999"

    stale = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert stale.status_code == 401
    fresh = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {body['accessToken']}"},
    )
    assert fresh.status_code == 200
    assert fresh.json()["phone"] == "+96171999999"


def test_malformed_phone_returns_validation_error(anonymous_client: TestClient) -> None:
    status, body = _request_otp(anonymous_client, phone="not-a-phone")
    assert status == 400
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_otp_request_rate_limit(anonymous_client: TestClient) -> None:
    get_rate_limiter().reset()
    # Default policy is 5 / 300s; force a tiny limit via repeated calls after reset
    # against the shared limiter by exhausting the configured test-friendly path.
    # Use many requests until 429; suite default may be high, so temporarily lower.
    from app.config import get_settings
    from app.core.rate_limit import build_rate_limit_policies

    settings = get_settings()
    policy = build_rate_limit_policies(settings)["citizen-otp-request"]
    # Exhaust by calling enforce path through the API until denied or safety cap.
    saw_429 = False
    for _ in range(policy.limit + 3):
        status, body = _request_otp(anonymous_client, phone="+96170123456")
        if status == 429:
            saw_429 = True
            assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            break
        assert status == 202
    assert saw_429


def test_request_otp_service_rejects_wrong_purpose_auth() -> None:
    try:
        citizen_service.request_otp(
            phone="+96170123456",
            purpose="CHANGE_PHONE",
            authenticated_user_id=None,
        )
        raise AssertionError("expected unauthorized")
    except CitizenServiceError as exc:
        assert exc.code == "UNAUTHORIZED"
        assert exc.status_code == 401


def test_otp_challenge_stores_hash_only(anonymous_client: TestClient) -> None:
    status, request_body = _request_otp(anonymous_client)
    assert status == 202
    stored = citizen_otp_store.get(request_body["challengeId"])
    assert stored is not None
    code = citizen_service.peek_dev_otp_code(request_body["challengeId"])
    assert code is not None
    assert code not in stored.model_dump_json()
    assert stored.code_hash
    assert len(stored.code_hash) == 64


def test_otp_request_invalidates_challenge_when_delivery_raises(
    anonymous_client: TestClient, monkeypatch
) -> None:
    def _boom(**_kwargs):
        raise RuntimeError("sns unavailable")

    monkeypatch.setattr(
        "app.api.citizen.deliver_citizen_otp",
        _boom,
    )

    status, body = _request_otp(anonymous_client, phone="+96170123456")
    assert status == 500

    # Challenge must not remain live after a failed delivery.
    live = [
        challenge
        for challenge in citizen_otp_store._challenges.values()  # noqa: SLF001
        if challenge.phone == "+96170123456"
        and challenge.consumed_at is None
        and challenge.superseded_at is None
    ]
    assert live == []
    assert "challengeId" not in body or body.get("challengeId") is None
