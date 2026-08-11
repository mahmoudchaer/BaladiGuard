from io import BytesIO
from urllib.parse import parse_qsl

from botocore.exceptions import ClientError
from PIL import Image, PngImagePlugin

from app.services.citizens.service import citizen_service
from app.services.uploads.photo_upload_service import photo_upload_service
from tests.conftest import contribution_ready_auth_headers


def set_aws_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_S3_BUCKET", "baladiguard-test")


def image_bytes(
    image_format: str = "PNG",
    *,
    size: tuple[int, int] = (32, 24),
    metadata: bool = False,
) -> bytes:
    output = BytesIO()
    image = Image.new("RGB", size, "red")
    kwargs = {}
    if image_format == "PNG" and metadata:
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("citizen-name", "private metadata")
        kwargs["pnginfo"] = pnginfo
    image.save(output, format=image_format, **kwargs)
    return output.getvalue()


class FakeS3Client:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.put_object_calls = []
        self.tags: dict[str, dict[str, str]] = {}

    def put_object(self, **kwargs):
        if self.should_fail:
            raise ClientError(
                {"Error": {"Code": "InternalError", "Message": "Upload failed"}},
                "PutObject",
            )
        self.put_object_calls.append(kwargs)
        self.tags[kwargs["Key"]] = dict(parse_qsl(kwargs["Tagging"]))

    def get_object_tagging(self, *, Bucket, Key):  # noqa: N803
        return {
            "TagSet": [
                {"Key": key, "Value": value} for key, value in self.tags.get(Key, {}).items()
            ]
        }

    def put_object_tagging(self, *, Bucket, Key, Tagging):  # noqa: N803
        self.tags[Key] = {item["Key"]: item["Value"] for item in Tagging["TagSet"]}


def _upload(client, body: bytes, filename: str, content_type: str):
    return client.post(
        "/v1/uploads/report-photo",
        files={"file": (filename, body, content_type)},
        headers=contribution_ready_auth_headers(),
    )


def test_upload_report_photo_validates_sanitizes_encrypts_and_scopes_key(client, monkeypatch):
    fake = FakeS3Client()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)

    response = _upload(client, image_bytes(metadata=True), "citizen-original.png", "image/png")

    assert response.status_code == 200
    key = response.json()["imageObjectKey"]
    assert key.startswith("reports/photos/v2/")
    assert "citizen-original" not in key
    call = fake.put_object_calls[0]
    assert call["Key"] == key
    assert call["ContentType"] == "image/png"
    assert call["ServerSideEncryption"] == "AES256"
    assert call["Metadata"] == {"sanitized": "true"}
    assert fake.tags[key]["upload-state"] == "orphan"
    with Image.open(BytesIO(call["Body"])) as sanitized:
        assert "citizen-name" not in sanitized.info


def test_upload_requires_contribution_ready_citizen(anonymous_client):
    response = anonymous_client.post(
        "/v1/uploads/report-photo",
        files={"file": ("x.png", image_bytes(), "image/png")},
    )
    assert response.status_code == 401


def test_upload_report_photo_requires_auth(client, monkeypatch):
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", FakeS3Client())

    response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("pothole.png", b"image-bytes", "image/png")},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_upload_report_photo_rejects_incomplete_profile(client, monkeypatch):
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", FakeS3Client())
    # Phone-only account: authenticated but not contribution-ready.
    user = citizen_service.create_citizen(phone="+96170999888")
    token = citizen_service.issue_session(user.user_id)

    response = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("pothole.png", b"image-bytes", "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONTRIBUTION_PROFILE_REQUIRED"


def test_upload_report_photo_rejects_missing_file(client):
    response = client.post(
        "/v1/uploads/report-photo", files={}, headers=contribution_ready_auth_headers()
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_FILE"


def test_upload_rejects_mime_or_extension_spoofing(client, monkeypatch):
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", FakeS3Client())
    response = _upload(client, image_bytes("PNG"), "fake.jpg", "image/jpeg")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IMAGE_TYPE_MISMATCH"


def test_upload_rejects_invalid_signature(client, monkeypatch):
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", FakeS3Client())
    response = _upload(client, b"not-an-image", "fake.jpg", "image/jpeg")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_IMAGE_CONTENT"


def test_upload_rejects_unsupported_content_type(client):
    response = _upload(client, b"text", "notes.txt", "text/plain")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"


def test_upload_rejects_large_encoded_file(client):
    response = _upload(client, b"x" * (5 * 1024 * 1024 + 1), "large.jpg", "image/jpeg")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_rejects_oversized_decoded_dimensions(client, monkeypatch):
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", FakeS3Client())
    monkeypatch.setattr("app.services.uploads.photo_upload_service.MAX_IMAGE_PIXELS", 10)
    response = _upload(client, image_bytes(size=(4, 4)), "large.png", "image/png")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IMAGE_DIMENSIONS_TOO_LARGE"


def test_upload_handles_s3_failure_without_leaking_details(client, monkeypatch):
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", FakeS3Client(should_fail=True))
    response = _upload(client, image_bytes("WEBP"), "pothole.webp", "image/webp")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "S3_UPLOAD_FAILED"
    assert "InternalError" not in response.text
