from botocore.exceptions import ClientError

from app.services.uploads.photo_upload_service import photo_upload_service


def set_aws_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_S3_BUCKET", "baladiguard-test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")


class FakeS3Client:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.put_object_calls = []

    def put_object(self, **kwargs):
        if self.should_fail:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "Upload failed"}},
                "PutObject",
            )
        self.put_object_calls.append(kwargs)


def test_upload_report_photo_success(client, monkeypatch):
    fake_s3_client = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake_s3_client)

    response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("pothole.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imageObjectKey"].startswith("reports/photos/")
    assert body["imageObjectKey"].endswith(".png")

    assert fake_s3_client.put_object_calls
    call = fake_s3_client.put_object_calls[0]
    assert call["Bucket"] == "baladiguard-test"
    assert call["Key"] == body["imageObjectKey"]
    assert call["Body"] == b"image-bytes"
    assert call["ContentType"] == "image/png"


def test_upload_report_photo_rejects_missing_file(client):
    response = client.post("/v1/uploads/report-photo", files={})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_FILE"


def test_upload_report_photo_rejects_invalid_file_type(client):
    response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("notes.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_upload_report_photo_rejects_invalid_content_type(client):
    response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("fake.jpg", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_upload_report_photo_rejects_large_file(client):
    response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("large.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_report_photo_handles_s3_upload_failure(client, monkeypatch):
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", FakeS3Client(should_fail=True))

    response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("pothole.webp", b"image-bytes", "image/webp")},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "S3_UPLOAD_FAILED"
