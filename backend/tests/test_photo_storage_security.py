from app.config import get_settings
from app.services.complaints import ticket_read_mapper


class FakePresignClient:
    def __init__(self) -> None:
        self.calls = []

    def generate_presigned_url(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        return "https://signed.example/photo?expires=120"


def test_image_access_uses_short_lived_controlled_url(monkeypatch):
    fake = FakePresignClient()
    monkeypatch.setenv("AWS_S3_BUCKET", "private-reports")
    monkeypatch.setenv("S3_PRESIGNED_URL_TTL_SECONDS", "120")
    get_settings.cache_clear()
    monkeypatch.setattr(ticket_read_mapper, "get_s3_client", lambda: fake)

    url = ticket_read_mapper.build_image_url("reports/photos/v2/scope/photo.jpg")

    assert url == "https://signed.example/photo?expires=120"
    operation, kwargs = fake.calls[0]
    assert operation == "get_object"
    assert kwargs["ExpiresIn"] == 120
    assert kwargs["Params"]["ResponseContentDisposition"] == "inline"
    get_settings.cache_clear()
