from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from app.config import get_settings
from app.database.dynamo_photo_claim_store import DynamoPhotoClaimStore
from app.services.complaints import ticket_read_mapper
from app.services.uploads.photo_upload_service import InvalidUploadError, photo_upload_service
from tests.test_upload_report_photo import FakeS3Client, set_aws_env


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


def test_concurrent_photo_claim_allows_exactly_one_ticket(monkeypatch):
    owner_user_id = "usr_concurrent_photo_owner"
    owner_scope = photo_upload_service.owner_scope(owner_user_id)
    object_key = f"reports/photos/v2/{owner_scope}/photo.png"
    barrier = Barrier(2)

    class ConcurrentReadS3(FakeS3Client):
        def __init__(self) -> None:
            super().__init__()
            self.tags[object_key] = {
                "upload-state": "orphan",
                "owner-scope": owner_scope,
            }
            self._reads = 0
            self._read_lock = Lock()

        def get_object_tagging(self, *, Bucket, Key):  # noqa: N803
            snapshot = super().get_object_tagging(Bucket=Bucket, Key=Key)
            with self._read_lock:
                self._reads += 1
                should_wait = self._reads <= 2
            if should_wait:
                barrier.wait(timeout=5)
            return snapshot

    fake = ConcurrentReadS3()
    set_aws_env(monkeypatch)
    monkeypatch.setattr(photo_upload_service, "_s3_client", fake)

    def attempt(ticket_id: str) -> bool:
        try:
            return photo_upload_service.claim_for_ticket(
                object_key,
                owner_user_id=owner_user_id,
                ticket_id=ticket_id,
            )
        except InvalidUploadError as exc:
            assert exc.code == "PHOTO_ALREADY_USED"
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ("tkt_concurrent_1", "tkt_concurrent_2")))

    assert sorted(results) == [False, True]


def test_dynamo_photo_claim_condition_allows_one_concurrent_winner(dynamodb_settings):
    store = DynamoPhotoClaimStore(dynamodb_settings)

    def attempt(ticket_id: str) -> bool:
        return store.claim(
            "reports/photos/v2/owner/photo.png",
            owner_scope="owner",
            ticket_id=ticket_id,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ("tkt_dynamo_1", "tkt_dynamo_2")))

    assert sorted(results) == [False, True]
