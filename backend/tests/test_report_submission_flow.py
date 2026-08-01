from app.database.memory import ticket_store
from app.schemas.stored_ticket import PENDING_CLASSIFICATION
from app.services.uploads.photo_upload_service import photo_upload_service
from tests.test_upload_report_photo import FakeS3Client, set_aws_env
from tests.conftest import contribution_ready_auth_headers

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
        files={"file": ("pothole.jpg", b"image-bytes", "image/jpeg")},
        headers={"X-Client-Version": "mobile-0.1.0"},
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
        files={"file": ("pothole.jpg", b"image-bytes", "image/jpeg")},
    )

    assert upload_response.status_code == 502
    assert upload_response.json()["error"]["code"] == "S3_UPLOAD_FAILED"
