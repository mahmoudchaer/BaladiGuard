from datetime import UTC, datetime

from app.config import Settings
from app.database.dynamo_redaction_job_store import DynamoRedactionJobStore
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.schemas.stored_ticket import StoredTicket
from app.services.redaction.detector import DetectionProviderError
from app.services.redaction.queue import ImageRedactionQueue


def _ticket() -> StoredTicket:
    stamped = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return StoredTicket(
        ticketId="tkt_redaction_dynamo",
        ticketNumber="BG-2026-9001",
        trackingCode="ABC234",
        description="Vehicle blocks the sidewalk.",
        contact={"phone": "+96170123456"},
        location={
            "latitude": 33.89,
            "longitude": 35.50,
            "addressText": "Hamra, Beirut",
            "source": "GPS",
        },
        imageObjectKey="reports/photos/v2/owner/photo.jpg",
        status="SUBMITTED",
        createdAt=stamped,
        updatedAt=stamped,
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
            kwargs["ticket_id"],
            kwargs["generation"],
            expired[0].claim_token,
            "1970-01-01T00:00:41Z",
        )
        replacement = self.jobs.claim_next(now=41, claim_ttl_seconds=30)
        assert replacement is not None and replacement.claim_token
        assert self.tickets.claim_image_redaction(
            kwargs["ticket_id"],
            kwargs["generation"],
            replacement.claim_token,
            "1970-01-01T00:00:41Z",
        )
        self.replacement_token = replacement.claim_token
        raise DetectionProviderError("DETECTION_PROVIDER_UNAVAILABLE")


def test_dynamo_job_enqueue_claim_retry_and_success_are_idempotent(
    dynamodb_settings: Settings,
) -> None:
    store = DynamoRedactionJobStore(dynamodb_settings)
    first = store.enqueue("tkt_redaction_dynamo", 1, 10)
    duplicate = store.enqueue("tkt_redaction_dynamo", 1, 20)
    assert duplicate.job_id == first.job_id
    assert len(store.list()) == 1

    claimed = store.claim_next(now=10, claim_ttl_seconds=30)
    assert claimed is not None and claimed.claim_token
    assert store.retry(
        claimed.job_id,
        claimed.claim_token,
        available_at=12,
        now=11,
        reason="PROVIDER_UNAVAILABLE",
    )
    reclaimed = store.claim_next(now=12, claim_ttl_seconds=30)
    assert reclaimed is not None and reclaimed.attempts == 2 and reclaimed.claim_token
    assert store.succeed(reclaimed.job_id, reclaimed.claim_token, 13)
    assert store.get(first.job_id).status == "succeeded"


def test_dynamo_ticket_redaction_claim_finalization_and_generation_are_conditional(
    dynamodb_settings: Settings,
) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    store.save(_ticket())
    assert store.claim_image_redaction(
        "tkt_redaction_dynamo", 1, "token-one", "2026-08-13T00:00:01Z"
    )
    assert (
        store.claim_image_redaction("tkt_redaction_dynamo", 1, "token-two", "2026-08-13T00:00:02Z")
        is None
    )
    assert (
        store.finalize_image_redaction(
            "tkt_redaction_dynamo",
            1,
            "wrong-token",
            {"image_redaction_status": "completed"},
        )
        is None
    )
    finalized = store.finalize_image_redaction(
        "tkt_redaction_dynamo",
        1,
        "token-one",
        {
            "image_redaction_status": "completed",
            "public_image_object_key": "reports/redacted/v1/scope/g1/approved.jpg",
        },
    )
    assert finalized is not None and finalized.image_redaction_status == "completed"

    second = store.start_image_reprocessing("tkt_redaction_dynamo", "2026-08-13T00:00:03Z")
    third = store.start_image_reprocessing("tkt_redaction_dynamo", "2026-08-13T00:00:04Z")
    assert second is not None and second.image_redaction_generation == 2
    assert third is not None and third.image_redaction_generation == 3
    assert third.public_image_object_key == "reports/redacted/v1/scope/g1/approved.jpg"


def test_dynamo_expired_worker_cannot_clear_replacement_ticket_claim(
    dynamodb_settings: Settings, monkeypatch
) -> None:
    dynamodb_settings.image_redaction_job_timeout_seconds = 30
    dynamodb_settings.image_redaction_job_max_attempts = 2
    dynamodb_settings.image_redaction_job_backoff_base_seconds = 1
    dynamodb_settings.image_redaction_job_backoff_max_seconds = 2
    monkeypatch.setattr("app.services.redaction.queue.get_settings", lambda: dynamodb_settings)
    tickets = DynamoTicketStore(dynamodb_settings)
    tickets.save(_ticket())
    jobs = DynamoRedactionJobStore(dynamodb_settings)
    processor = LeaseExpiryProcessor(jobs, tickets)
    queue = ImageRedactionQueue(jobs, tickets, processor)
    queue.enqueue("tkt_redaction_dynamo", now=10)

    assert queue.run_once(now=10) == "claim_lost"

    ticket = tickets.get("tkt_redaction_dynamo")
    job = jobs.get("redaction:tkt_redaction_dynamo:g1")
    assert ticket is not None and ticket.image_redaction_status == "processing"
    assert ticket.image_redaction_claim_token == processor.replacement_token
    assert job is not None and job.status == "running"
    assert job.claim_token == processor.replacement_token
