from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from app.config import get_settings
from app.core.metrics import emit_metric
from app.database.content_safety_job_store import ContentSafetyJobStore
from app.database.memory_content_safety_job import content_safety_job_id
from app.database.store_factory import get_content_safety_job_store, get_ticket_store
from app.database.ticket_store import TicketStore
from app.schemas.stored_content_safety_job import StoredContentSafetyJob
from app.services.content_safety.authenticity import CompositeAuthenticityDetector
from app.services.content_safety.image_moderator import RekognitionImageModerator
from app.services.content_safety.policy import (
    SafetyDecision,
    append_content_safety_history,
    public_unpublish_fields,
    should_clear_public_image,
    should_promote_public_image,
)
from app.services.content_safety.processor import (
    ContentSafetyProcessor,
    ContentSafetyStorageError,
)
from app.services.content_safety.text_moderator import BedrockTextModerator
from app.services.redaction.detector import DetectionProviderError

logger = logging.getLogger(__name__)

_MAX_UNPROCESSABLE_SKIPS_PER_POLL = 250


def _ticket_can_be_screened(ticket) -> bool:
    return bool(
        ticket.content_safety_enrolled and ticket.content_safety_status in {"pending", "processing"}
    )


class ContentSafetyQueue:
    def __init__(self, jobs: ContentSafetyJobStore, tickets: TicketStore, processor) -> None:
        self.jobs = jobs
        self.tickets = tickets
        self.processor = processor

    def enqueue(self, ticket_id: str, generation: int | None = None, *, now: int | None = None):
        ticket = self.tickets.get(ticket_id)
        if ticket is None:
            raise KeyError("ticket not found")
        if not ticket.content_safety_enrolled:
            return None
        target = generation or ticket.content_safety_generation
        job = self.jobs.enqueue(ticket_id, target, now if now is not None else int(time.time()))
        emit_metric("ContentSafetyJobsQueued")
        return job

    def reconcile(self, *, now: int | None = None) -> int:
        timestamp = now if now is not None else int(time.time())
        created = 0
        for ticket in self.tickets.list():
            if not _ticket_can_be_screened(ticket):
                continue
            job_id = content_safety_job_id(ticket.ticket_id, ticket.content_safety_generation)
            if self.jobs.get(job_id) is None:
                self.jobs.enqueue(ticket.ticket_id, ticket.content_safety_generation, timestamp)
                created += 1
        return created

    def run_once(self, *, now: int | None = None) -> str:
        timestamp = now if now is not None else int(time.time())
        self.reconcile(now=timestamp)
        for recovered in self.jobs.recover_stale(now=timestamp):
            if recovered.claim_token:
                self.tickets.requeue_content_safety(
                    recovered.ticket_id,
                    recovered.generation,
                    recovered.claim_token,
                    _iso(timestamp),
                )
        settings = get_settings()
        skipped = 0
        while skipped < _MAX_UNPROCESSABLE_SKIPS_PER_POLL:
            job = self.jobs.claim_next(
                now=timestamp, claim_ttl_seconds=settings.content_safety_job_timeout_seconds
            )
            if job is None:
                return "idle"
            outcome = self._run_claimed_job(job, timestamp=timestamp, settings=settings)
            if outcome != "skipped_unenrolled":
                return outcome
            skipped += 1
        return "idle"

    def _run_claimed_job(self, job: StoredContentSafetyJob, *, timestamp: int, settings) -> str:
        token = job.claim_token
        assert token
        ticket = self.tickets.get(job.ticket_id)
        if ticket is None:
            transitioned = self.jobs.dead_letter(
                job.job_id, token, now=timestamp, reason="TICKET_MISSING"
            )
            return "dead_lettered" if transitioned else "claim_lost"
        if not ticket.content_safety_enrolled:
            transitioned = self.jobs.dead_letter(
                job.job_id, token, now=timestamp, reason="SAFETY_NOT_ENROLLED"
            )
            return "skipped_unenrolled" if transitioned else "claim_lost"
        if ticket.content_safety_generation != job.generation or ticket.content_safety_status in {
            "passed",
            "review_required",
            "private_only",
            "rejected",
            "superseded",
        }:
            transitioned = self.jobs.succeed(job.job_id, token, timestamp)
            return "succeeded" if transitioned else "claim_lost"
        if ticket.content_safety_status == "failed":
            transitioned = self.jobs.dead_letter(
                job.job_id,
                token,
                now=timestamp,
                reason=ticket.content_safety_reason_code or "TICKET_SAFETY_FAILED",
            )
            return "dead_lettered" if transitioned else "claim_lost"
        claimed = self.tickets.claim_content_safety(
            job.ticket_id, job.generation, token, _iso(timestamp)
        )
        if claimed is None:
            delay = settings.content_safety_job_backoff_base_seconds
            transitioned = self.jobs.retry(
                job.job_id,
                token,
                available_at=timestamp + delay,
                now=timestamp,
                reason="TICKET_CLAIM_UNAVAILABLE",
            )
            return "retried" if transitioned else "claim_lost"
        try:
            started_at = time.perf_counter()
            decision = self.processor.process(
                ticket_id=job.ticket_id,
                source_key=claimed.image_object_key,
                description=claimed.description,
            )
            fields = _fields_for_decision(claimed, decision, completed_at=_iso(int(time.time())))
            updated = self.tickets.finalize_content_safety(
                job.ticket_id, job.generation, token, fields
            )
            if updated is None:
                raise RuntimeError("SAFETY_CLAIM_LOST")
            from app.services.rewards.observe import observe_ticket_rewards

            observe_ticket_rewards(updated)
            if not self.jobs.succeed(job.job_id, token, int(time.time())):
                return "claim_lost"
            emit_metric("ContentSafetyJobsSucceeded", dimensions={"status": decision.status})
            emit_metric(
                "ContentSafetyJobLatencyMs",
                value=round((time.perf_counter() - started_at) * 1000.0, 2),
                unit="Milliseconds",
                dimensions={"status": decision.status},
            )
            if decision.text.model:
                emit_metric(
                    "ContentSafetyModelVersion",
                    dimensions={"model": decision.text.model[:64]},
                )
            return "succeeded"
        except DetectionProviderError as exc:
            return self._retry_or_fail(
                job, token, str(exc)[:80] or "PROVIDER_UNAVAILABLE", now=timestamp
            )
        except ContentSafetyStorageError as exc:
            return self._retry_or_fail(job, token, str(exc)[:80], now=timestamp)
        except Exception as exc:
            code = type(exc).__name__
            logger.warning("Content safety retry job_id=%s error_code=%s", job.job_id, code)
            return self._retry_or_fail(job, token, code, now=timestamp)

    def _retry_or_fail(
        self, job: StoredContentSafetyJob, token: str, reason: str, *, now: int
    ) -> str:
        settings = get_settings()
        if job.attempts >= settings.content_safety_job_max_attempts:
            return self._terminal_failure(job, token, reason, now=now)
        released = self.tickets.requeue_content_safety(
            job.ticket_id, job.generation, token, _iso(now)
        )
        if released is None:
            return "claim_lost"
        delay = min(
            settings.content_safety_job_backoff_max_seconds,
            settings.content_safety_job_backoff_base_seconds * (2 ** max(0, job.attempts - 1)),
        )
        if not self.jobs.retry(
            job.job_id, token, available_at=now + delay, now=now, reason=reason[:80]
        ):
            return "claim_lost"
        emit_metric("ContentSafetyJobsRetried")
        return "retried"

    def _terminal_failure(
        self, job: StoredContentSafetyJob, token: str, reason: str, *, now: int
    ) -> str:
        fail_closed = get_settings().content_safety_fail_closed
        status = "review_required" if fail_closed else "failed"
        ticket = self.tickets.get(job.ticket_id)
        fields = {
            "content_safety_status": status,
            "content_safety_reason_code": reason[:80] or "SAFETY_FAILED",
            "content_safety_severity": "medium",
            "content_safety_completed_at": _iso(now),
            "updated_at": _iso(now),
        }
        if ticket is not None:
            snapshot = ticket.model_copy(update=fields)
            fields["content_safety_history"] = append_content_safety_history(
                snapshot, status=status
            )
            fields.update(public_unpublish_fields(ticket))
        elif should_clear_public_image(status):
            fields["public_image_object_key"] = None
        finalized = self.tickets.finalize_content_safety(
            job.ticket_id, job.generation, token, fields
        )
        if finalized is None:
            return "claim_lost"
        from app.services.rewards.observe import observe_ticket_rewards

        observe_ticket_rewards(finalized)
        if not self.jobs.dead_letter(job.job_id, token, now=now, reason=reason[:80]):
            return "claim_lost"
        emit_metric("ContentSafetyJobsDeadLettered")
        return "dead_lettered"


def _fields_for_decision(ticket, decision: SafetyDecision, *, completed_at: str) -> dict:
    fields = {
        "content_safety_status": decision.status,
        "content_safety_reason_code": decision.reason_code,
        "content_safety_severity": decision.severity,
        "content_safety_text_model": decision.text.model,
        "content_safety_image_labels": list(decision.image_labels),
        "authenticity_score": decision.authenticity.score,
        "authenticity_model": decision.authenticity.model,
        "authenticity_model_version": decision.authenticity.model_version,
        "authenticity_signals": list(decision.authenticity.signals),
        "content_safety_completed_at": completed_at,
        "updated_at": completed_at,
    }
    if should_promote_public_image(ticket, decision.status):
        fields["public_image_object_key"] = ticket.image_redaction_candidate_object_key
    elif should_clear_public_image(decision.status):
        fields["public_image_object_key"] = None
    if decision.status != "passed":
        fields.update(public_unpublish_fields(ticket))
    snapshot = ticket.model_copy(update=fields)
    fields["content_safety_history"] = append_content_safety_history(
        snapshot, status=decision.status
    )
    return fields


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


def build_content_safety_queue() -> ContentSafetyQueue:
    settings = get_settings()
    processor = ContentSafetyProcessor(
        settings,
        text_moderator=BedrockTextModerator(model_id=settings.content_safety_text_model_id),
        image_moderator=RekognitionImageModerator(settings),
        authenticity_detector=CompositeAuthenticityDetector(settings),
    )
    return ContentSafetyQueue(get_content_safety_job_store(), get_ticket_store(), processor)


content_safety_queue = build_content_safety_queue()
