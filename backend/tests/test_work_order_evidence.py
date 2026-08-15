"""Maintenance completion evidence (issue #248)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.database.memory import ticket_store
from app.database.memory_audit_history import audit_history_store
from app.services.ai_job_queue import ai_job_queue
from app.services.uploads.photo_upload_service import photo_upload_service
from tests.conftest import contribution_ready_auth_headers, issue_test_staff_token
from tests.test_submit_ticket import VALID_PAYLOAD
from tests.test_upload_report_photo import FakeS3Client, image_bytes, set_aws_env
from tests.test_workforce import BEIRUT, OTHER_MUNICIPALITY, ROAD


def _admin(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='admin')}"}


def _staff(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username='staff')}"}


def _create_accepted_ticket(client: TestClient) -> dict:
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_auth_headers(),
    )
    assert response.status_code == 201, response.text
    assert ai_job_queue.run_once().outcome == "succeeded"
    created = response.json()
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={"municipality_id": BEIRUT, "department_id": ROAD, "status": "UNDER_REVIEW"}
        )
    )
    return created


def _create_work_order(client: TestClient, ticket_id: str) -> dict:
    response = client.post(f"/v1/tickets/{ticket_id}/work-orders", json={}, headers=_admin(client))
    assert response.status_code == 201, response.text
    return response.json()


def _start(client: TestClient, work_order_id: str) -> None:
    worker = client.post(
        "/v1/workforce/workers",
        json={"municipalityId": BEIRUT, "displayName": "Crew", "departmentIds": [ROAD]},
        headers=_admin(client),
    ).json()
    assigned = client.post(
        f"/v1/work-orders/{work_order_id}/assign",
        json={"workerId": worker["workerId"]},
        headers=_admin(client),
    )
    assert assigned.status_code == 200, assigned.text
    started = client.post(f"/v1/work-orders/{work_order_id}/start", headers=_admin(client))
    assert started.status_code == 200, started.text


def _upload(
    client: TestClient,
    work_order_id: str,
    *,
    kind: str,
    headers: dict[str, str] | None = None,
    filename: str = "after.png",
    body: bytes | None = None,
    content_type: str = "image/png",
):
    return client.post(
        f"/v1/work-orders/{work_order_id}/evidence",
        params={"kind": kind},
        files={"file": (filename, body if body is not None else image_bytes(), content_type)},
        headers=_admin(client) if headers is None else headers,
    )


def test_create_associates_original_report_photo(client: TestClient) -> None:
    created = _create_accepted_ticket(client)
    work_order = _create_work_order(client, created["ticketId"])
    kinds = [item["kind"] for item in work_order["evidence"]]
    assert "ORIGINAL_REPORT" in kinds
    original = next(item for item in work_order["evidence"] if item["kind"] == "ORIGINAL_REPORT")
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert original["objectKey"] == stored.image_object_key
    assert original["source"] == "TICKET_ORIGINAL"
    assert original["ticketId"] == created["ticketId"]
    assert original["workOrderId"] == work_order["workOrderId"]


def test_staff_can_upload_before_and_after_images(client: TestClient, monkeypatch) -> None:
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    created = _create_accepted_ticket(client)
    work_order = _create_work_order(client, created["ticketId"])

    before = _upload(client, work_order["workOrderId"], kind="BEFORE", filename="before.png")
    after = _upload(client, work_order["workOrderId"], kind="AFTER", filename="after.png")
    assert before.status_code == 200, before.text
    assert after.status_code == 200, after.text
    assert before.json()["kind"] == "BEFORE"
    assert after.json()["kind"] == "AFTER"
    assert before.json()["objectKey"].startswith("work-orders/evidence/v1/")
    assert work_order["workOrderId"] in after.json()["objectKey"]
    assert fake.put_object_calls
    assert fake.put_object_calls[0]["ServerSideEncryption"] == "AES256"

    listed = client.get(
        f"/v1/work-orders/{work_order['workOrderId']}", headers=_admin(client)
    ).json()
    kinds = {item["kind"] for item in listed["evidence"]}
    assert kinds == {"ORIGINAL_REPORT", "BEFORE", "AFTER"}
    assert listed["afterImageCount"] == 1


def test_evidence_upload_requires_staff_and_scope(client: TestClient, monkeypatch) -> None:
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    created = _create_accepted_ticket(client)
    work_order = _create_work_order(client, created["ticketId"])

    guest = TestClient(app)
    anonymous = _upload(guest, work_order["workOrderId"], kind="AFTER", headers={})
    assert anonymous.status_code == 401

    citizen = _upload(
        guest,
        work_order["workOrderId"],
        kind="AFTER",
        headers=contribution_ready_auth_headers(),
    )
    assert citizen.status_code == 401

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.save(stored.model_copy(update={"municipality_id": OTHER_MUNICIPALITY}))
    other_staff = _upload(client, work_order["workOrderId"], kind="AFTER", headers=_staff(client))
    assert other_staff.status_code == 404


def test_rejects_invalid_kind_and_oversized_or_mismatched_files(
    client: TestClient, monkeypatch
) -> None:
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    created = _create_accepted_ticket(client)
    work_order = _create_work_order(client, created["ticketId"])

    invalid_kind = _upload(client, work_order["workOrderId"], kind="ORIGINAL_REPORT")
    assert invalid_kind.status_code == 400
    assert invalid_kind.json()["error"]["code"] == "INVALID_EVIDENCE_KIND"

    mismatch = _upload(
        client,
        work_order["workOrderId"],
        kind="AFTER",
        filename="after.jpg",
        content_type="image/jpeg",
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] == "IMAGE_TYPE_MISMATCH"

    too_large = _upload(
        client,
        work_order["workOrderId"],
        kind="AFTER",
        body=b"x" * (5 * 1024 * 1024 + 10),
        filename="after.png",
    )
    assert too_large.status_code == 400
    assert too_large.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_failed_upload_does_not_attach_or_allow_completion(
    client: TestClient, monkeypatch
) -> None:
    fake = FakeS3Client(should_fail=True)
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    created = _create_accepted_ticket(client)
    work_order = _create_work_order(client, created["ticketId"])
    _start(client, work_order["workOrderId"])

    failed = _upload(client, work_order["workOrderId"], kind="AFTER")
    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "S3_UPLOAD_FAILED"

    listed = client.get(
        f"/v1/work-orders/{work_order['workOrderId']}", headers=_admin(client)
    ).json()
    assert listed["afterImageCount"] == 0
    assert all(item["kind"] != "AFTER" for item in listed["evidence"])

    complete = client.post(
        f"/v1/work-orders/{work_order['workOrderId']}/complete",
        json={},
        headers=_admin(client),
    )
    assert complete.status_code == 400
    assert complete.json()["error"]["code"] == "COMPLETION_EVIDENCE_REQUIRED"


def test_completion_requires_after_image_and_is_retryable(
    client: TestClient, monkeypatch
) -> None:
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    created = _create_accepted_ticket(client)
    work_order = _create_work_order(client, created["ticketId"])
    _start(client, work_order["workOrderId"])

    before_only = _upload(client, work_order["workOrderId"], kind="BEFORE")
    assert before_only.status_code == 200
    blocked = client.post(
        f"/v1/work-orders/{work_order['workOrderId']}/complete",
        json={},
        headers=_admin(client),
    )
    assert blocked.status_code == 400

    first = _upload(client, work_order["workOrderId"], kind="AFTER")
    retry = _upload(client, work_order["workOrderId"], kind="AFTER")
    assert first.status_code == 200
    assert retry.status_code == 200
    assert first.json()["evidenceId"] != retry.json()["evidenceId"]

    completed = client.post(
        f"/v1/work-orders/{work_order['workOrderId']}/complete",
        json={},
        headers=_admin(client),
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["state"] == "COMPLETED"
    assert client.get(f"/v1/tickets/{created['ticketId']}").json()["status"] == "IN_PROGRESS"

    late_upload = _upload(client, work_order["workOrderId"], kind="AFTER")
    assert late_upload.status_code == 400
    assert late_upload.json()["error"]["code"] == "WORK_ORDER_NOT_ACTIVE"


def test_evidence_audit_omits_urls_and_keys(client: TestClient, monkeypatch) -> None:
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    created = _create_accepted_ticket(client)
    work_order = _create_work_order(client, created["ticketId"])
    uploaded = _upload(client, work_order["workOrderId"], kind="AFTER")
    assert uploaded.status_code == 200
    object_key = uploaded.json()["objectKey"]

    entries = [
        entry
        for entry in audit_history_store.list_by_ticket_id(created["ticketId"])
        if entry.action_type == "WORK_ORDER_EVIDENCE_ADD"
    ]
    assert entries
    serialized = str(entries[0].model_dump())
    assert object_key not in serialized
    assert "http" not in serialized
    assert entries[0].new_value == "AFTER"

    tracking = client.get(f"/v1/tickets/track/{created['trackingCode']}")
    assert tracking.status_code == 200
    assert "objectKey" not in tracking.text
    assert "afterImage" not in tracking.text.lower()
    assert "evidence" not in tracking.text.lower()
