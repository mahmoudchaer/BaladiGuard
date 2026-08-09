import logging
import time
from dataclasses import dataclass

from app.config import get_settings
from app.core.metrics import emit_metric
from app.database.ai_job_store import AiJobStore
from app.database.store_factory import get_ai_job_store, get_ticket_store
from app.database.ticket_store import TicketStore
from app.schemas.stored_ai_job import StoredAiJob
from app.services.complaints.ticket_service import TicketService, ticket_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerResult:
    outcome: str
    job_id: str | None = None


class AiJobQueue:
    def __init__(
        self,
        job_store: AiJobStore,
        ticket_store: TicketStore,
        processor: TicketService,
    ) -> None:
        self._jobs = job_store
        self._tickets = ticket_store
        self._processor = processor

    def enqueue(self, ticket_id: str, *, now: int | None = None) -> StoredAiJob:
        job = self._jobs.enqueue(ticket_id, now if now is not None else int(time.time()))
        emit_metric("AiJobsQueued")
        self.emit_queue_metrics()
        return job

    def reconcile(self, *, now: int | None = None) -> int:
        """Ensure every accepted non-terminal ticket has a durable job record."""
        timestamp = now if now is not None else int(time.time())
        created = 0
        for ticket in self._tickets.list():
            if ticket.ai_processing_status not in {"pending", "processing"}:
                continue
            job_id = f"ai:{ticket.ticket_id}"
            if self._jobs.get(job_id) is None:
                self._jobs.enqueue(ticket.ticket_id, timestamp)
                created += 1
        if created:
            emit_metric("AiJobsQueued", value=float(created), dimensions={"source": "reconcile"})
        return created

    def recover_stale(self, *, now: int | None = None) -> int:
        timestamp = now if now is not None else int(time.time())
        recovered = self._jobs.recover_stale(now=timestamp)
        updated_at = _iso(timestamp)
        for job in recovered:
            self._tickets.requeue_ai_processing(job.ticket_id, updated_at)
            emit_metric("AiJobsRetried", dimensions={"reason": "stale_claim"})
        return len(recovered)

    def run_once(self, *, now: int | None = None) -> WorkerResult:
        timestamp = now if now is not None else int(time.time())
        # Pending tickets are the transactional outbox. Reconcile on every poll
        # so a queue write that failed after ticket persistence is recovered
        # without an API/client retry or a worker restart.
        self.reconcile(now=timestamp)
        self.recover_stale(now=timestamp)
        settings = get_settings()
        job = self._jobs.claim_next(
            now=timestamp,
            claim_ttl_seconds=settings.ai_job_timeout_seconds,
        )
        if job is None:
            self.emit_queue_metrics(now=timestamp)
            return WorkerResult("idle")
        emit_metric("AiJobsRunning")
        token = job.claim_token
        assert token is not None

        ticket = self._tickets.get(job.ticket_id)
        if ticket is None:
            self._jobs.dead_letter(
                job.job_id,
                token,
                now=timestamp,
                reason="Ticket no longer exists.",
            )
            emit_metric("AiJobsDeadLettered", dimensions={"reason": "missing_ticket"})
            return WorkerResult("dead_lettered", job.job_id)
        if ticket.ai_processing_status == "completed":
            self._jobs.succeed(job.job_id, token, timestamp)
            emit_metric("AiJobsSucceeded", dimensions={"outcome": "duplicate_delivery"})
            return WorkerResult("succeeded", job.job_id)

        try:
            processed = self._processor.process_ticket_ai(job.ticket_id, claim_token=token)
            latest = self._tickets.get(job.ticket_id)
            if processed and latest and latest.ai_processing_status == "completed":
                self._jobs.succeed(job.job_id, token, int(time.time()))
                emit_metric("AiJobsSucceeded")
                return WorkerResult("succeeded", job.job_id)
            reason = "AI providers returned no usable output."
        except Exception as exc:  # worker boundary must keep polling
            reason = f"Transient processing error: {type(exc).__name__}."
            logger.warning("AI job failed job_id=%s error=%s", job.job_id, type(exc).__name__)

        finished_at = int(time.time())
        if job.attempts >= settings.ai_job_max_attempts:
            self._jobs.dead_letter(
                job.job_id,
                token,
                now=finished_at,
                reason=reason,
            )
            emit_metric("AiJobsDeadLettered", dimensions={"reason": "attempts_exhausted"})
            return WorkerResult("dead_lettered", job.job_id)

        reset = self._tickets.requeue_ai_processing(job.ticket_id, _iso(finished_at))
        if reset is None:
            latest = self._tickets.get(job.ticket_id)
            if latest and latest.ai_processing_status == "completed":
                self._jobs.succeed(job.job_id, token, finished_at)
                emit_metric("AiJobsSucceeded", dimensions={"outcome": "concurrent_completion"})
                return WorkerResult("succeeded", job.job_id)
        delay = min(
            settings.ai_job_backoff_max_seconds,
            settings.ai_job_backoff_base_seconds * (2 ** max(0, job.attempts - 1)),
        )
        self._jobs.retry(
            job.job_id,
            token,
            available_at=finished_at + delay,
            now=finished_at,
            reason=reason,
        )
        emit_metric("AiJobsRetried")
        return WorkerResult("retried", job.job_id)

    def replay(self, job_id: str, *, now: int | None = None) -> bool:
        timestamp = now if now is not None else int(time.time())
        job = self._jobs.get(job_id)
        if job is None or job.status != "dead_lettered":
            return False
        replayed = self._jobs.replay(job_id, now=timestamp)
        if replayed is None:
            return False
        reset = self._tickets.requeue_ai_processing(job.ticket_id, _iso(timestamp))
        if reset is None:
            latest = self._tickets.get(job.ticket_id)
            return bool(latest and latest.ai_processing_status == "completed")
        emit_metric("AiJobsQueued", dimensions={"source": "manual_replay"})
        return True

    def emit_queue_metrics(self, *, now: int | None = None) -> None:
        timestamp = now if now is not None else int(time.time())
        jobs = self._jobs.list()
        for status in ("queued", "running", "succeeded", "dead_lettered"):
            emit_metric(
                "AiJobQueueDepth",
                value=float(sum(job.status == status for job in jobs)),
                unit="Count",
                dimensions={"status": status},
            )
        active = [job for job in jobs if job.status in {"queued", "running"}]
        oldest_age = max((timestamp - job.created_at for job in active), default=0)
        emit_metric("AiJobOldestAgeSeconds", value=float(max(0, oldest_age)), unit="Seconds")


def _iso(timestamp: int) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


ai_job_queue = AiJobQueue(get_ai_job_store(), get_ticket_store(), ticket_service)
