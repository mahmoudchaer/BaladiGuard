from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.config import Settings
from app.database.memory import InMemoryTicketStore
from app.database.memory_redaction_job import InMemoryRedactionJobStore
from app.schemas.stored_ticket import StoredTicket
from app.services.redaction.detector import (
    AwsRekognitionDetector,
    BoundingBox,
    Detection,
    DetectionConfigurationError,
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

    def detect_custom_labels(self, **kwargs):
        assert kwargs["MinConfidence"] == 0
        return {
            "CustomLabels": [
                {
                    "Name": "License_Plate",
                    "Confidence": 88,
                    "Geometry": {
                        "BoundingBox": {
                            "Left": 0.5,
                            "Top": 0.6,
                            "Width": 0.2,
                            "Height": 0.1,
                        }
                    },
                },
                {
                    "Name": "Car",
                    "Confidence": 99,
                    "Geometry": {"BoundingBox": {"Left": 0, "Top": 0, "Width": 1, "Height": 1}},
                },
            ]
        }


def test_aws_adapter_combines_faces_and_only_plate_custom_labels():
    settings = _settings()
    settings.rekognition_plate_model_arn = "arn:aws:rekognition:us-east-1:123:model/test"
    detections = AwsRekognitionDetector(settings, client=FakeRekognition()).detect(b"image")
    assert [item.kind for item in detections] == ["face", "plate"]
    assert [item.confidence for item in detections] == [98, 88]


def test_aws_adapter_fails_closed_without_plate_model():
    settings = _settings()
    settings.rekognition_plate_model_arn = None
    detector = AwsRekognitionDetector(settings, client=FakeRekognition())
    with pytest.raises(DetectionConfigurationError, match="PLATE_MODEL_NOT_CONFIGURED"):
        detector.detect(b"image")


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
