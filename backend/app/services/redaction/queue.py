from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from app.config import get_settings
from app.core.metrics import emit_metric
from app.database.memory_redaction_job import redaction_job_id
from app.database.redaction_job_store import RedactionJobStore
from app.database.store_factory import get_redaction_job_store, get_ticket_store
from app.database.ticket_store import TicketStore
from app.schemas.image_redaction import RedactionProvenance
from app.schemas.stored_redaction_job import StoredRedactionJob
from app.services.redaction.detector import AwsRekognitionDetector, DisabledRedactionDetector
from app.services.redaction.processor import (
    ImageRedactionProcessor,
    InvalidSourceImageError,
    RedactionStorageError,
)

logger = logging.getLogger(__name__)

_MAX_UNREDACTABLE_SKIPS_PER_POLL = 250


def _ticket_can_be_redacted(ticket) -> bool:
    """Legacy tickets default to pending in the model but were never enrolled."""
    return bool(
        ticket.image_redaction_enrolled
        and ticket.image_redaction_status in {"pending", "processing"}
        and ticket.image_object_key
        and ticket.image_object_key != "unavailable"
    )


class ImageRedactionQueue:
    def __init__(self, jobs: RedactionJobStore, tickets: TicketStore, processor) -> None:
        self.jobs = jobs
        self.tickets = tickets
        self.processor = processor

    def enqueue(self, ticket_id: str, generation: int | None = None, *, now: int | None = None):
        ticket = self.tickets.get(ticket_id)
        if ticket is None:
            raise KeyError("ticket not found")
        target = generation or ticket.image_redaction_generation
        job = self.jobs.enqueue(ticket_id, target, now if now is not None else int(time.time()))
        emit_metric("ImageRedactionJobsQueued")
        return job

    def reconcile(self, *, now: int | None = None) -> int:
        timestamp = now if now is not None else int(time.time())
        created = 0
        for ticket in self.tickets.list():
            if not _ticket_can_be_redacted(ticket):
                continue
            job_id = redaction_job_id(ticket.ticket_id, ticket.image_redaction_generation)
            if self.jobs.get(job_id) is None:
                self.jobs.enqueue(ticket.ticket_id, ticket.image_redaction_generation, timestamp)
                created += 1
        return created

    def run_once(self, *, now: int | None = None) -> str:
        timestamp = now if now is not None else int(time.time())
        self.reconcile(now=timestamp)
        for recovered in self.jobs.recover_stale(now=timestamp):
            if recovered.claim_token:
                self.tickets.requeue_image_redaction(
                    recovered.ticket_id,
                    recovered.generation,
                    recovered.claim_token,
                    _iso(timestamp),
                )
        settings = get_settings()
        skipped = 0
        while skipped < _MAX_UNREDACTABLE_SKIPS_PER_POLL:
            job = self.jobs.claim_next(
                now=timestamp, claim_ttl_seconds=settings.image_redaction_job_timeout_seconds
            )
            if job is None:
                return "idle"
            outcome = self._run_claimed_job(job, timestamp=timestamp, settings=settings)
            if outcome != "skipped_unredactable":
                return outcome
            skipped += 1
        return "idle"

    def _run_claimed_job(self, job: StoredRedactionJob, *, timestamp: int, settings) -> str:
        token = job.claim_token
        assert token
        ticket = self.tickets.get(job.ticket_id)
        if ticket is None:
            transitioned = self.jobs.dead_letter(
                job.job_id, token, now=timestamp, reason="TICKET_MISSING"
            )
            return "dead_lettered" if transitioned else "claim_lost"
        if not ticket.image_redaction_enrolled or ticket.image_object_key in {"", "unavailable"}:
            logger.info(
                "Skipping unredactable redaction job job_id=%s reason=REDACTION_NOT_ENROLLED",
                job.job_id,
            )
            transitioned = self.jobs.dead_letter(
                job.job_id, token, now=timestamp, reason="REDACTION_NOT_ENROLLED"
            )
            return "skipped_unredactable" if transitioned else "claim_lost"
        if ticket.image_redaction_generation != job.generation or ticket.image_redaction_status in {
            "completed",
            "review_required",
        }:
            transitioned = self.jobs.succeed(job.job_id, token, timestamp)
            return "succeeded" if transitioned else "claim_lost"
        if ticket.image_redaction_status == "failed":
            transitioned = self.jobs.dead_letter(
                job.job_id,
                token,
                now=timestamp,
                reason=ticket.image_redaction_reason_code or "TICKET_REDACTION_FAILED",
            )
            return "dead_lettered" if transitioned else "claim_lost"
        claimed = self.tickets.claim_image_redaction(
            job.ticket_id, job.generation, token, _iso(timestamp)
        )
        if claimed is None:
            delay = settings.image_redaction_job_backoff_base_seconds
            transitioned = self.jobs.retry(
                job.job_id,
                token,
                available_at=timestamp + delay,
                now=timestamp,
                reason="TICKET_CLAIM_UNAVAILABLE",
            )
            return "retried" if transitioned else "claim_lost"
        try:
            result = self.processor.process(
                ticket_id=job.ticket_id,
                source_key=claimed.image_object_key,
                generation=job.generation,
            )
            expected_prefix = (
                f"reports/redacted/v1/{_ticket_scope(job.ticket_id)}/g{job.generation}/"
            )
            if result.status == "completed" and (
                not result.derivative_key or not result.derivative_key.startswith(expected_prefix)
            ):
                raise RuntimeError("INVALID_DERIVATIVE_KEY")
            completed_at = _iso(int(time.time()))
            provenance = RedactionProvenance(
                generation=job.generation,
                status=result.status,
                sourceFingerprint=result.source_fingerprint,
                derivativeObjectKey=result.derivative_key,
                detector=result.detector,
                detectorVersion=result.detector_version,
                faceCount=result.face_count,
                plateCount=result.plate_count,
                minimumConfidence=result.minimum_confidence,
                completedAt=completed_at,
                reasonCode=result.reason_code,
            )
            history = [*claimed.image_redaction_history, provenance][-20:]
            fields = {
                "image_redaction_status": result.status,
                "image_redaction_detector": result.detector,
                "image_redaction_detector_version": result.detector_version,
                "image_redaction_face_count": result.face_count,
                "image_redaction_plate_count": result.plate_count,
                "image_redaction_completed_at": completed_at,
                "image_redaction_reason_code": result.reason_code,
                "image_redaction_candidate_object_key": result.derivative_key,
                "image_redaction_candidate_revision": claimed.image_redaction_candidate_revision
                + 1,
                "image_redaction_regions": list(result.regions),
                "image_redaction_history": [
                    entry.model_dump(by_alias=True, mode="json") for entry in history
                ],
                "updated_at": completed_at,
            }
            # Only an automatically approved derivative becomes public. During
            # reprocessing, the previous approved derivative remains atomic/current.
            if result.status == "completed":
                fields["public_image_object_key"] = result.derivative_key
            updated = self.tickets.finalize_image_redaction(
                job.ticket_id, job.generation, token, fields
            )
            if updated is None:
                raise RuntimeError("REDACTION_CLAIM_LOST")
            if not self.jobs.succeed(job.job_id, token, int(time.time())):
                return "claim_lost"
            emit_metric("ImageRedactionJobsSucceeded", dimensions={"status": result.status})
            return "succeeded"
        except InvalidSourceImageError as exc:
            return self._terminal_failure(job, token, str(exc), now=timestamp)
        except Exception as exc:
            # Logs contain only exception type and opaque identifiers, never image data/URLs.
            code = str(exc) if isinstance(exc, RedactionStorageError) else type(exc).__name__
            logger.warning("Image redaction retry job_id=%s error_code=%s", job.job_id, code)
            return self._retry_or_fail(job, token, code, now=timestamp)

    def _retry_or_fail(self, job: StoredRedactionJob, token: str, reason: str, *, now: int) -> str:
        settings = get_settings()
        if job.attempts >= settings.image_redaction_job_max_attempts:
            return self._terminal_failure(job, token, reason, now=now)
        released = self.tickets.requeue_image_redaction(
            job.ticket_id, job.generation, token, _iso(now)
        )
        if released is None:
            return "claim_lost"
        delay = min(
            settings.image_redaction_job_backoff_max_seconds,
            settings.image_redaction_job_backoff_base_seconds * (2 ** max(0, job.attempts - 1)),
        )
        if not self.jobs.retry(
            job.job_id, token, available_at=now + delay, now=now, reason=reason[:80]
        ):
            return "claim_lost"
        emit_metric("ImageRedactionJobsRetried")
        return "retried"

    def _terminal_failure(
        self, job: StoredRedactionJob, token: str, reason: str, *, now: int
    ) -> str:
        ticket = self.tickets.get(job.ticket_id)
        history = list(ticket.image_redaction_history) if ticket else []
        if ticket:
            history.append(
                RedactionProvenance(
                    generation=job.generation,
                    status="failed",
                    sourceFingerprint="unavailable",
                    detector="redaction-worker",
                    detectorVersion="v1",
                    completedAt=_iso(now),
                    reasonCode=reason[:80],
                )
            )
        finalized = self.tickets.finalize_image_redaction(
            job.ticket_id,
            job.generation,
            token,
            {
                "image_redaction_status": "failed",
                "image_redaction_reason_code": reason[:80],
                "image_redaction_completed_at": _iso(now),
                "image_redaction_history": [
                    entry.model_dump(by_alias=True, mode="json") for entry in history[-20:]
                ],
                "updated_at": _iso(now),
            },
        )
        if finalized is None:
            return "claim_lost"
        if not self.jobs.dead_letter(job.job_id, token, now=now, reason=reason[:80]):
            return "claim_lost"
        emit_metric("ImageRedactionJobsDeadLettered")
        return "dead_lettered"

    def replay(self, job_id: str, *, now: int | None = None) -> bool:
        timestamp = now if now is not None else int(time.time())
        job = self.jobs.get(job_id)
        if job is None or job.status != "dead_lettered":
            return False
        replayed = self.jobs.replay(job_id, now=timestamp)
        if replayed is None:
            return False
        ticket = self.tickets.get(job.ticket_id)
        if ticket is None:
            emit_metric("ImageRedactionJobsQueued", dimensions={"source": "manual_replay"})
            return True
        if ticket.image_redaction_status != "completed":
            self.tickets.save(
                ticket.model_copy(
                    update={
                        "image_redaction_status": "pending",
                        "image_redaction_claim_token": None,
                        "updated_at": _iso(timestamp),
                    }
                )
            )
        emit_metric("ImageRedactionJobsQueued", dimensions={"source": "manual_replay"})
        return True


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


def _ticket_scope(ticket_id: str) -> str:
    from app.services.uploads.photo_upload_service import PhotoUploadService

    return PhotoUploadService.ticket_scope(ticket_id)


def build_image_redaction_queue() -> ImageRedactionQueue:
    settings = get_settings()
    detector = (
        AwsRekognitionDetector(settings)
        if settings.image_redaction_enabled
        and settings.image_redaction_detector == "aws_rekognition"
        else DisabledRedactionDetector()
    )
    processor = ImageRedactionProcessor(detector, settings)
    return ImageRedactionQueue(get_redaction_job_store(), get_ticket_store(), processor)


image_redaction_queue = build_image_redaction_queue()
