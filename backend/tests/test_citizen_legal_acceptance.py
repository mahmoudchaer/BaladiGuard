"""Citizen legal acceptance on OTP, profile, and anonymization (issue #321)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.database.memory_citizen import citizen_store
from app.database.memory_privacy_request import privacy_request_audit_store
from app.schemas.citizen import LegalAcceptance
from app.services.citizens.service import citizen_service, legal_acceptance_required
from app.services.legal.documents import CURRENT_LEGAL_VERSION


def _request_and_code(client: TestClient, phone: str = "+96170123456") -> tuple[str, str]:
    requested = client.post(
        "/v1/citizen/auth/otp/request",
        json={"phone": phone, "purpose": "LOGIN_OR_SIGNUP"},
    )
    assert requested.status_code == 202, requested.text
    challenge_id = requested.json()["challengeId"]
    code = citizen_service.peek_dev_otp_code(challenge_id)
    assert code is not None
    return challenge_id, code


def test_otp_verify_requires_legal_acceptance(anonymous_client: TestClient) -> None:
    challenge_id, code = _request_and_code(anonymous_client)
    missing = anonymous_client.post(
        "/v1/citizen/auth/otp/verify",
        json={"challengeId": challenge_id, "code": code},
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "LEGAL_ACCEPTANCE_REQUIRED"

    challenge_id, code = _request_and_code(anonymous_client, phone="+96170123457")
    rejected = anonymous_client.post(
        "/v1/citizen/auth/otp/verify",
        json={"challengeId": challenge_id, "code": code, "acceptLegal": False},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "LEGAL_ACCEPTANCE_REQUIRED"


def test_otp_verify_persists_legal_acceptance(anonymous_client: TestClient) -> None:
    challenge_id, code = _request_and_code(anonymous_client)
    verified = anonymous_client.post(
        "/v1/citizen/auth/otp/verify",
        json={
            "challengeId": challenge_id,
            "code": code,
            "acceptLegal": True,
            "legalLocale": "ar",
            "fullName": "Ada Citizen",
        },
    )
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["legalAcceptanceRequired"] is False
    acceptance = body["legalAcceptance"]
    assert acceptance["termsVersion"] == CURRENT_LEGAL_VERSION
    assert acceptance["privacyVersion"] == CURRENT_LEGAL_VERSION
    assert acceptance["acceptableUseVersion"] == CURRENT_LEGAL_VERSION
    assert acceptance["locale"] == "ar"
    assert acceptance["source"] == "otp_verify"

    me = anonymous_client.get(
        "/v1/citizen/me",
        headers={"Authorization": f"Bearer {body['accessToken']}"},
    )
    assert me.status_code == 200
    assert me.json()["legalAcceptanceRequired"] is False
    assert me.json()["legalAcceptance"]["termsVersion"] == CURRENT_LEGAL_VERSION


def test_profile_flags_version_mismatch_and_reaccept(anonymous_client: TestClient) -> None:
    user = citizen_service.create_citizen(phone="+96170111111", full_name="Legacy")
    token = citizen_service.issue_session(user.user_id)
    headers = {"Authorization": f"Bearer {token}"}

    me = anonymous_client.get("/v1/citizen/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["legalAcceptance"] is None
    assert me.json()["legalAcceptanceRequired"] is True

    stale = user.model_copy(
        update={
            "legal_acceptance": LegalAcceptance(
                termsVersion="2020-01-01",
                privacyVersion="2020-01-01",
                acceptableUseVersion="2020-01-01",
                acceptedAt="2020-01-01T00:00:00Z",
                source="otp_verify",
            )
        }
    )
    citizen_store.update(stale)
    assert legal_acceptance_required(citizen_store.get(user.user_id)) is True

    me_stale = anonymous_client.get("/v1/citizen/me", headers=headers)
    assert me_stale.json()["legalAcceptanceRequired"] is True

    accepted = anonymous_client.post(
        "/v1/citizen/me/legal-acceptance",
        headers=headers,
        json={"acceptLegal": True, "locale": "fr"},
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["legalAcceptanceRequired"] is False
    assert body["legalAcceptance"]["source"] == "reacceptance"
    assert body["legalAcceptance"]["locale"] == "fr"
    assert body["legalAcceptance"]["termsVersion"] == CURRENT_LEGAL_VERSION


def test_anonymize_clears_legal_acceptance_and_logs_privacy_request(
    anonymous_client: TestClient,
) -> None:
    challenge_id, code = _request_and_code(anonymous_client, phone="+96170999991")
    verified = anonymous_client.post(
        "/v1/citizen/auth/otp/verify",
        json={"challengeId": challenge_id, "code": code, "acceptLegal": True},
    )
    assert verified.status_code == 200, verified.text
    token = verified.json()["accessToken"]
    user_id = verified.json()["userId"]
    headers = {"Authorization": f"Bearer {token}"}

    export = anonymous_client.get("/v1/citizen/me/export", headers=headers)
    assert export.status_code == 200
    recent = privacy_request_audit_store.list_recent()
    assert any(item.action == "citizen_export" for item in recent)

    deleted = anonymous_client.post("/v1/citizen/me/delete", headers=headers)
    assert deleted.status_code == 200
    stored = citizen_store.get(user_id)
    assert stored is not None
    assert stored.legal_acceptance is None
    recent = privacy_request_audit_store.list_recent()
    assert any(item.action == "citizen_delete" for item in recent)
