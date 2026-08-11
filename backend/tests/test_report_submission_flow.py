from app.database.memory import ticket_store
from app.schemas.stored_ticket import PENDING_CLASSIFICATION
from app.services.complaints.ticket_service import ticket_service
from app.services.uploads.photo_upload_service import photo_upload_service
from tests.conftest import contribution_ready_auth_headers
from tests.test_upload_report_photo import FakeS3Client, image_bytes, set_aws_env

TICKET_PAYLOAD = {
    "description": "Large pothole reported near the university gate causing traffic disruption.",
    "languageHint": "auto",
    "location": {
        "latitude": 33.896112,
        "longitude": 35.478419,
        "addressText": "Near AUB Main Gate, Hamra, Beirut",
        "source": "PLACEHOLDER",
    },
    "clientMetadata": {
        "platform": "ios",
        "appVersion": "0.1.0",
    },
}


def test_upload_then_submit_report_flow(client, monkeypatch):
    fake_s3_client = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake_s3_client)

    upload_response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("pothole.jpg", image_bytes("JPEG"), "image/jpeg")},
        headers={
            "X-Client-Version": "mobile-0.1.0",
            **contribution_ready_auth_headers(),
        },
    )

    assert upload_response.status_code == 200
    image_object_key = upload_response.json()["imageObjectKey"]
    assert image_object_key.startswith("reports/photos/")
    assert image_object_key.endswith(".jpg")

    submit_response = client.post(
        "/v1/tickets",
        json={**TICKET_PAYLOAD, "imageObjectKey": image_object_key},
        headers={
            "Content-Type": "application/json",
            "X-Client-Version": "mobile-0.1.0",
            **contribution_ready_auth_headers(),
        },
    )

    assert submit_response.status_code == 201
    body = submit_response.json()
    assert body["ticketId"].startswith("tkt_")
    assert body["ticketNumber"].startswith("BG-")
    assert body["status"] == "SUBMITTED"

    stored = ticket_store.get(body["ticketId"])
    assert stored is not None
    assert stored.image_object_key == image_object_key
    assert stored.status == "SUBMITTED"
    assert stored.category == PENDING_CLASSIFICATION

    assert fake_s3_client.put_object_calls
    assert fake_s3_client.put_object_calls[0]["Key"] == image_object_key
    assert fake_s3_client.tags[image_object_key]["upload-state"] == "linked"


def test_submit_rejects_ticket_when_upload_key_is_missing(client):
    response = client.post(
        "/v1/tickets",
        json={**TICKET_PAYLOAD, "imageObjectKey": "   "},
        headers={
            "X-Client-Version": "mobile-0.1.0",
            **contribution_ready_auth_headers(),
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_failure_prevents_ticket_creation(client, monkeypatch):
    set_aws_env(monkeypatch)
    monkeypatch.setattr(
        photo_upload_service,
        "_s3_client",
        FakeS3Client(should_fail=True),
    )

    upload_response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("pothole.jpg", image_bytes("JPEG"), "image/jpeg")},
        headers=contribution_ready_auth_headers(),
    )

    assert upload_response.status_code == 502
    assert upload_response.json()["error"]["code"] == "S3_UPLOAD_FAILED"


def test_photo_cannot_be_claimed_by_another_citizen(client, monkeypatch):
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    owner_headers = contribution_ready_auth_headers(phone="+96170111001")
    other_headers = contribution_ready_auth_headers(phone="+96170111002")
    uploaded = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("photo.png", image_bytes(), "image/png")},
        headers=owner_headers,
    )
    key = uploaded.json()["imageObjectKey"]

    response = client.post(
        "/v1/tickets",
        json={**TICKET_PAYLOAD, "imageObjectKey": key},
        headers=other_headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PHOTO_NOT_OWNED"
    assert ticket_store.list() == []


def test_photo_can_only_be_attached_once(client, monkeypatch):
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    headers = contribution_ready_auth_headers(phone="+96170111003")
    uploaded = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("photo.png", image_bytes(), "image/png")},
        headers=headers,
    )
    key = uploaded.json()["imageObjectKey"]
    first = client.post(
        "/v1/tickets",
        json={**TICKET_PAYLOAD, "imageObjectKey": key},
        headers=headers,
    )
    second = client.post(
        "/v1/tickets",
        json={**TICKET_PAYLOAD, "imageObjectKey": key},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "PHOTO_ALREADY_USED"


def test_ticket_save_failure_releases_photo_for_safe_retry(client, monkeypatch):
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)
    headers = contribution_ready_auth_headers(phone="+96170111004")
    uploaded = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("photo.png", image_bytes(), "image/png")},
        headers=headers,
    )
    key = uploaded.json()["imageObjectKey"]
    real_save = ticket_service._store.save

    def fail_save(*_: object, **__: object) -> None:
        raise RuntimeError("ticket storage unavailable")

    monkeypatch.setattr(ticket_service._store, "save", fail_save)
    failed = client.post(
        "/v1/tickets",
        json={**TICKET_PAYLOAD, "imageObjectKey": key},
        headers=headers,
    )

    assert failed.status_code == 500
    assert fake.tags[key]["upload-state"] == "orphan"
    assert "ticket-scope" not in fake.tags[key]
    assert ticket_store.list() == []

    monkeypatch.setattr(ticket_service._store, "save", real_save)
    retried = client.post(
        "/v1/tickets",
        json={**TICKET_PAYLOAD, "imageObjectKey": key},
        headers=headers,
    )
    assert retried.status_code == 201
    assert fake.tags[key]["upload-state"] == "linked"
