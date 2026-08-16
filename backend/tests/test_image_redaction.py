from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import Settings
from app.database.memory import InMemoryTicketStore
from app.database.memory_redaction_job import InMemoryRedactionJobStore
from app.database.serialization import item_to_ticket
from app.schemas.stored_ticket import StoredTicket
from app.services.redaction.detector import (
    AwsRekognitionDetector,
    BoundingBox,
    Detection,
    DetectionProviderError,
)
from app.services.redaction.processor import ImageRedactionProcessor, InvalidSourceImageError
from app.services.redaction.queue import ImageRedactionQueue
from app.services.uploads.photo_upload_service import PhotoUploadService


class FakeDetector:
    name = "fake-detector"
    version = "test-v1"

    def __init__(self, detections=(), error: Exception | None = None):
        self.detections = list(detections)
        self.error = error
        self.calls = 0

    def detect(self, image_bytes: bytes):
        self.calls += 1
        assert image_bytes.startswith(b"\xff\xd8")
        if self.error:
            raise self.error
        return self.detections


class FakeBody:
    def __init__(self, value: bytes):
        self.value = value

    def read(self):
        return self.value


class FakeS3:
    def __init__(self, source: bytes, ticket_id: str):
        self.source = source
        self.ticket_id = ticket_id
        self.put_calls: list[dict] = []
        self.bound = True

    def get_object_tagging(self, **_):
        scope = PhotoUploadService.ticket_scope(self.ticket_id if self.bound else "other")
        return {
            "TagSet": [
                {"Key": "upload-state", "Value": "linked"},
                {"Key": "ticket-scope", "Value": scope},
            ]
        }

    def get_object(self, **_):
        return {"Body": FakeBody(self.source)}

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)


def _settings() -> Settings:
    settings = Settings()
    settings.app_env = "test"
    settings.aws_s3_bucket = "private-test-bucket"
    settings.image_redaction_auto_confidence = 90
    settings.image_redaction_review_confidence = 60
    settings.image_redaction_box_padding = 0.08
    settings.image_redaction_blur_radius = 18
    settings.image_redaction_job_max_attempts = 2
    settings.image_redaction_job_timeout_seconds = 30
    settings.image_redaction_job_backoff_base_seconds = 1
    settings.image_redaction_job_backoff_max_seconds = 2
    return settings


def _jpeg(*, oriented: bool = False) -> bytes:
    image = Image.new("RGB", (120, 80), "white")
    for x in range(20, 60):
        for y in range(15, 45):
            image.putpixel((x, y), (x * 3 % 255, y * 5 % 255, 100))
    output = BytesIO()
    if oriented:
        exif = Image.Exif()
        exif[274] = 6
        image.save(output, "JPEG", exif=exif)
    else:
        image.save(output, "JPEG")
    return output.getvalue()


def _processor(ticket_id: str, detector: FakeDetector, *, oriented: bool = False):
    s3 = FakeS3(_jpeg(oriented=oriented), ticket_id)
    return ImageRedactionProcessor(detector, _settings(), s3_client=s3), s3


def test_faces_plates_multiple_and_rotated_are_blurred_and_metadata_removed():
    ticket_id = "tkt_privacy"
    detector = FakeDetector(
        [
            Detection("face", 99, BoundingBox(0.1, 0.1, 0.2, 0.25)),
            Detection("face", 96, BoundingBox(0.5, 0.2, 0.15, 0.2)),
            Detection("plate", 97, BoundingBox(0.25, 0.6, 0.3, 0.15)),
        ]
    )
    processor, s3 = _processor(ticket_id, detector, oriented=True)
    result = processor.process(
        ticket_id=ticket_id, source_key="reports/photos/v2/owner/photo.jpg", generation=1
    )
    assert result.status == "completed"
    assert (result.face_count, result.plate_count) == (2, 1)
    put = s3.put_calls[0]
    assert put["ServerSideEncryption"] == "AES256"
    assert put["Key"].startswith(
        f"reports/redacted/v1/{PhotoUploadService.ticket_scope(ticket_id)}/g1/"
    )
    with Image.open(BytesIO(put["Body"])) as derivative:
        assert derivative.getexif() == {}
        assert derivative.size == (80, 120)


def test_neither_detection_is_safe_when_both_detectors_succeeded():
    processor, s3 = _processor("tkt_none", FakeDetector())
    result = processor.process(
        ticket_id="tkt_none", source_key="reports/photos/v2/owner/photo.jpg", generation=1
    )
    assert result.status == "completed"
    assert result.face_count == result.plate_count == 0
    assert len(s3.put_calls) == 1


def test_low_confidence_derivative_is_review_required_and_not_approved():
    detector = FakeDetector([Detection("plate", 70, BoundingBox(0.2, 0.3, 0.4, 0.2))])
    processor, s3 = _processor("tkt_low", detector)
    result = processor.process(
        ticket_id="tkt_low", source_key="reports/photos/v2/owner/photo.jpg", generation=1
    )
    assert result.status == "review_required"
    assert result.reason_code == "LOW_CONFIDENCE"
    assert "approval-state=review-required" in s3.put_calls[0]["Tagging"]


def test_manual_regions_blur_original_and_write_new_derivative():
    detector = FakeDetector([Detection("plate", 70, BoundingBox(0.2, 0.3, 0.4, 0.2))])
    processor, s3 = _processor("tkt_manual", detector)
    auto = processor.process(
        ticket_id="tkt_manual", source_key="reports/photos/v2/owner/photo.jpg", generation=1
    )
    assert auto.status == "review_required"
    result = processor.apply_manual_regions(
        ticket_id="tkt_manual",
        source_key="reports/photos/v2/owner/photo.jpg",
        generation=1,
        regions=[
            Detection("plate", 70, BoundingBox(0.2, 0.3, 0.4, 0.2)),
            Detection("manual", 100, BoundingBox(0.05, 0.05, 0.1, 0.1)),
        ],
    )
    assert result.status == "review_required"
    assert result.reason_code == "MANUAL_CORRECTION"
    assert len(s3.put_calls) == 2
    assert s3.put_calls[1]["Key"] != s3.put_calls[0]["Key"]
    assert "approval-state=review-required" in s3.put_calls[1]["Tagging"]


@pytest.mark.parametrize(
    "detection",
    [
        Detection("face", 98, BoundingBox(0.1, 0.1, 0, 0.2)),
        Detection("plate", float("nan"), BoundingBox(0.1, 0.1, 0.2, 0.2)),
        Detection("plate", 101, BoundingBox(0.1, 0.1, 0.2, 0.2)),
        Detection("plate", 98, BoundingBox(0.1, 0.1, float("inf"), 0.2)),
    ],
)
def test_any_malformed_detection_fails_closed_without_upload(detection):
    processor, s3 = _processor("tkt_malformed", FakeDetector([detection]))
    with pytest.raises(DetectionProviderError, match="MALFORMED_DETECTION_OUTPUT"):
        processor.process(
            ticket_id="tkt_malformed",
            source_key="reports/photos/v2/owner/photo.jpg",
            generation=1,
        )
    assert not s3.put_calls


def test_foreign_or_unbound_original_key_is_rejected():
    processor, s3 = _processor("tkt_bound", FakeDetector())
    s3.bound = False
    with pytest.raises(InvalidSourceImageError, match="ORIGINAL_NOT_TICKET_BOUND"):
        processor.process(
            ticket_id="tkt_bound", source_key="reports/photos/v2/owner/photo.jpg", generation=1
        )
    assert not s3.put_calls


class FakeRekognition:
    def detect_faces(self, **_):
        return {
            "FaceDetails": [
                {
                    "Confidence": 98,
                    "BoundingBox": {"Left": 0.1, "Top": 0.2, "Width": 0.3, "Height": 0.4},
                }
            ]
        }


class FakePlateDetector:
    def predict(self, frame):
        assert frame.shape == (80, 120, 3)
        return [
            SimpleNamespace(
                confidence=0.88,
                bounding_box=SimpleNamespace(x1=60, y1=48, x2=84, y2=56),
            )
        ]


def test_aws_adapter_combines_faces_and_pretrained_plate_detector():
    settings = _settings()
    detections = AwsRekognitionDetector(
        settings,
        client=FakeRekognition(),
        plate_detector=FakePlateDetector(),
    ).detect(_jpeg())
    assert [item.kind for item in detections] == ["face", "plate"]
    assert [item.confidence for item in detections] == [98, 88]
    assert detections[1].box == BoundingBox(left=0.5, top=0.6, width=0.2, height=0.1)


def test_aws_adapter_fails_closed_when_plate_detector_is_unavailable():
    settings = _settings()
    detector = AwsRekognitionDetector(
        settings,
        client=FakeRekognition(),
        plate_detector=SimpleNamespace(predict=lambda _: (_ for _ in ()).throw(RuntimeError())),
    )
    with pytest.raises(DetectionProviderError, match="PLATE_DETECTOR_UNAVAILABLE"):
        detector.detect(_jpeg())


def test_aws_adapter_fails_closed_for_malformed_plate_detector_output():
    settings = _settings()
    detector = AwsRekognitionDetector(
        settings,
        client=FakeRekognition(),
        plate_detector=SimpleNamespace(predict=lambda _: [SimpleNamespace()]),
    )
    with pytest.raises(DetectionProviderError, match="PLATE_DETECTOR_UNAVAILABLE"):
        detector.detect(_jpeg())


def test_pipeline_fails_closed_for_malformed_rekognition_box():
    rekognition = SimpleNamespace(
        detect_faces=lambda **_: {
            "FaceDetails": [
                {
                    "Confidence": 98,
                    "BoundingBox": {"Left": 0.1, "Top": 0.2, "Width": 0, "Height": 0.4},
                }
            ]
        }
    )
    detector = AwsRekognitionDetector(
        _settings(),
        client=rekognition,
        plate_detector=SimpleNamespace(predict=lambda _: []),
    )
    processor, s3 = _processor("tkt_bad_face", detector)
    with pytest.raises(DetectionProviderError, match="MALFORMED_DETECTION_OUTPUT"):
        processor.process(
            ticket_id="tkt_bad_face",
            source_key="reports/photos/v2/owner/photo.jpg",
            generation=1,
        )
    assert not s3.put_calls


@pytest.mark.parametrize(
    ("confidence", "x2"),
    [(float("nan"), 84), (1.1, 84), (0.88, float("inf")), (0.88, 60)],
)
def test_aws_adapter_fails_closed_for_invalid_plate_values(confidence, x2):
    plate_detector = SimpleNamespace(
        predict=lambda _: [
            SimpleNamespace(
                confidence=confidence,
                bounding_box=SimpleNamespace(x1=60, y1=48, x2=x2, y2=56),
            )
        ]
    )
    detector = AwsRekognitionDetector(
        _settings(), client=FakeRekognition(), plate_detector=plate_detector
    )
    with pytest.raises(DetectionProviderError, match="MALFORMED_DETECTION_OUTPUT"):
        detector.detect(_jpeg())


class ResultProcessor:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = 0

    def process(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise DetectionProviderError("DETECTION_PROVIDER_UNAVAILABLE")
        from app.services.redaction.processor import ProcessingResult

        scope = PhotoUploadService.ticket_scope(kwargs["ticket_id"])
        generation = kwargs["generation"]
        return ProcessingResult(
            "completed",
            f"reports/redacted/v1/{scope}/g{generation}/ok.jpg",
            "abc",
            "fake",
            "v1",
            1,
            1,
            99,
        )


class LeaseExpiryProcessor:
    def __init__(self, jobs, tickets):
        self.jobs = jobs
        self.tickets = tickets
        self.replacement_token = None

    def process(self, **kwargs):
        expired = self.jobs.recover_stale(now=41)
        assert len(expired) == 1 and expired[0].claim_token
        assert self.tickets.requeue_image_redaction(
            kwargs["ticket_id"], kwargs["generation"], expired[0].claim_token, _iso(41)
        )
        replacement = self.jobs.claim_next(now=41, claim_ttl_seconds=30)
        assert replacement is not None and replacement.claim_token
        assert self.tickets.claim_image_redaction(
            kwargs["ticket_id"], kwargs["generation"], replacement.claim_token, _iso(41)
        )
        self.replacement_token = replacement.claim_token
        raise DetectionProviderError("DETECTION_PROVIDER_UNAVAILABLE")


def _iso(timestamp: int) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


def _ticket(ticket_id="tkt_queue") -> StoredTicket:
    return StoredTicket(
        ticketId=ticket_id,
        ticketNumber="BG-2026-0001",
        trackingCode="ABC234",
        description="test",
        contact={"phone": "+96170123456"},
        location={"latitude": 0, "longitude": 0, "addressText": "Test street", "source": "GPS"},
        imageObjectKey="reports/photos/v2/o/a.jpg",
        status="SUBMITTED",
        createdAt="2026-08-13T00:00:00Z",
    )


def test_queue_is_idempotent_and_atomically_approves_derivative(monkeypatch):
    monkeypatch.setattr("app.services.redaction.queue.get_settings", _settings)
    tickets = InMemoryTicketStore()
    tickets.save(_ticket())
    jobs = InMemoryRedactionJobStore()
    processor = ResultProcessor()
    queue = ImageRedactionQueue(jobs, tickets, processor)
    assert queue.enqueue("tkt_queue", now=10).job_id == queue.enqueue("tkt_queue", now=11).job_id
    assert queue.run_once(now=10) == "succeeded"
    assert queue.run_once(now=10) == "idle"
    stored = tickets.get("tkt_queue")
    assert stored.image_redaction_status == "completed"
    assert stored.public_image_object_key.endswith("ok.jpg")
    assert len(stored.image_redaction_history) == 1
    assert processor.calls == 1


def test_provider_failure_retries_then_fails_closed(monkeypatch):
    monkeypatch.setattr("app.services.redaction.queue.get_settings", _settings)
    tickets = InMemoryTicketStore()
    tickets.save(_ticket("tkt_failure"))
    jobs = InMemoryRedactionJobStore()
    queue = ImageRedactionQueue(jobs, tickets, ResultProcessor(fail=True))
    queue.enqueue("tkt_failure", now=10)
    assert queue.run_once(now=10) == "retried"
    assert tickets.get("tkt_failure").public_image_object_key is None
    assert queue.run_once(now=11) == "dead_lettered"
    stored = tickets.get("tkt_failure")
    assert stored.image_redaction_status == "failed"
    assert stored.public_image_object_key is None


def test_expired_worker_cannot_clear_replacement_ticket_claim(monkeypatch):
    monkeypatch.setattr("app.services.redaction.queue.get_settings", _settings)
    tickets = InMemoryTicketStore()
    tickets.save(_ticket("tkt_lease_race"))
    jobs = InMemoryRedactionJobStore()
    processor = LeaseExpiryProcessor(jobs, tickets)
    queue = ImageRedactionQueue(jobs, tickets, processor)
    queue.enqueue("tkt_lease_race", now=10)

    assert queue.run_once(now=10) == "claim_lost"

    ticket = tickets.get("tkt_lease_race")
    job = jobs.get("redaction:tkt_lease_race:g1")
    assert ticket is not None and ticket.image_redaction_status == "processing"
    assert ticket.image_redaction_claim_token == processor.replacement_token
    assert job is not None and job.status == "running"
    assert job.claim_token == processor.replacement_token


def test_reprocessing_preserves_old_approval_until_new_generation_completes(monkeypatch):
    monkeypatch.setattr("app.services.redaction.queue.get_settings", _settings)
    tickets = InMemoryTicketStore()
    ticket = _ticket("tkt_reprocess").model_copy(
        update={
            "image_redaction_status": "completed",
            "public_image_object_key": "reports/redacted/v1/scope/g1/old.jpg",
        }
    )
    tickets.save(ticket)
    tickets.patch_fields(
        "tkt_reprocess", {"image_redaction_generation": 2, "image_redaction_status": "pending"}
    )
    assert tickets.get("tkt_reprocess").public_image_object_key.endswith("old.jpg")
    queue = ImageRedactionQueue(InMemoryRedactionJobStore(), tickets, ResultProcessor())
    queue.enqueue("tkt_reprocess", 2, now=10)
    assert queue.run_once(now=10) == "succeeded"
    assert tickets.get("tkt_reprocess").image_redaction_generation == 2


def test_worker_skips_unenrolled_tickets_and_processes_oldest_redactable(monkeypatch):
    monkeypatch.setattr("app.services.redaction.queue.get_settings", _settings)
    tickets = InMemoryTicketStore()
    jobs = InMemoryRedactionJobStore()
    processor = ResultProcessor()
    tickets.save(
        _ticket("tkt_legacy_old").model_copy(update={"image_redaction_enrolled": False})
    )
    tickets.save(_ticket("tkt_ready_new"))
    queue = ImageRedactionQueue(jobs, tickets, processor)
    jobs.enqueue("tkt_legacy_old", 1, 10)
    jobs.enqueue("tkt_ready_new", 1, 20)

    assert queue.run_once(now=30) == "succeeded"
    assert jobs.get("redaction:tkt_legacy_old:g1").status == "dead_lettered"
    assert jobs.get("redaction:tkt_legacy_old:g1").last_error_code == "REDACTION_NOT_ENROLLED"
    assert jobs.get("redaction:tkt_ready_new:g1").status == "succeeded"
    assert tickets.get("tkt_legacy_old").image_redaction_status == "pending"
    assert tickets.get("tkt_ready_new").image_redaction_status == "completed"
    assert processor.calls == 1


def test_reconcile_does_not_enqueue_unenrolled_tickets(monkeypatch):
    monkeypatch.setattr("app.services.redaction.queue.get_settings", _settings)
    tickets = InMemoryTicketStore()
    jobs = InMemoryRedactionJobStore()
    tickets.save(
        _ticket("tkt_legacy_reconcile").model_copy(update={"image_redaction_enrolled": False})
    )
    tickets.save(_ticket("tkt_enrolled_reconcile"))
    queue = ImageRedactionQueue(jobs, tickets, ResultProcessor())

    assert queue.reconcile(now=10) == 1
    assert jobs.get("redaction:tkt_legacy_reconcile:g1") is None
    assert jobs.get("redaction:tkt_enrolled_reconcile:g1") is not None


def _legacy_dynamo_item() -> dict:
    return {
        "ticketId": "tkt_legacy_row",
        "ticketNumber": "BG-2026-0002",
        "trackingCode": "LEGACY1",
        "description": "Old report without redaction fields.",
        "contact": {"phone": "+96170123456"},
        "location": {
            "latitude": 33.89,
            "longitude": 35.50,
            "addressText": "Hamra, Beirut",
            "source": "GPS",
        },
        "imageObjectKey": "reports/temp/old/photo.jpg",
        "status": "SUBMITTED",
        "createdAt": "2026-01-01T00:00:00Z",
    }


def test_item_to_ticket_marks_legacy_rows_unenrolled():
    ticket = item_to_ticket(_legacy_dynamo_item())
    assert ticket.image_redaction_enrolled is False
    assert ticket.image_redaction_status == "pending"


def test_item_to_ticket_marks_persisted_redaction_status_enrolled():
    ticket = item_to_ticket({**_legacy_dynamo_item(), "imageRedactionStatus": "pending"})
    assert ticket.image_redaction_enrolled is True
