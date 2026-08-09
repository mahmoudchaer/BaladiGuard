from threading import Lock
from uuid import uuid4

from app.schemas.stored_ai_job import StoredAiJob


def ai_job_id(ticket_id: str) -> str:
    return f"ai:{ticket_id}"


class InMemoryAiJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, StoredAiJob] = {}
        self._lock = Lock()

    def enqueue(self, ticket_id: str, now: int) -> StoredAiJob:
        job_id = ai_job_id(ticket_id)
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing is not None:
                return existing.model_copy(deep=True)
            job = StoredAiJob(
                jobId=job_id,
                ticketId=ticket_id,
                status="queued",
                availableAt=now,
                createdAt=now,
                updatedAt=now,
            )
            self._jobs[job_id] = job
            return job.model_copy(deep=True)

    def get(self, job_id: str) -> StoredAiJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def claim_next(self, *, now: int, claim_ttl_seconds: int) -> StoredAiJob | None:
        with self._lock:
            eligible = sorted(
                (
                    job
                    for job in self._jobs.values()
                    if job.status == "queued" and job.available_at <= now
                ),
                key=lambda job: (job.available_at, job.created_at, job.job_id),
            )
            if not eligible:
                return None
            job = eligible[0]
            claimed = job.model_copy(
                update={
                    "status": "running",
                    "attempts": job.attempts + 1,
                    "claim_token": uuid4().hex,
                    "claim_expires_at": now + claim_ttl_seconds,
                    "updated_at": now,
                }
            )
            self._jobs[job.job_id] = claimed
            return claimed.model_copy(deep=True)

    def succeed(self, job_id: str, claim_token: str, now: int) -> bool:
        return self._finish(job_id, claim_token, now=now, status="succeeded", reason=None)

    def retry(
        self,
        job_id: str,
        claim_token: str,
        *,
        available_at: int,
        now: int,
        reason: str,
    ) -> bool:
        with self._lock:
            job = self._claimed(job_id, claim_token)
            if job is None:
                return False
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": "queued",
                    "available_at": available_at,
                    "updated_at": now,
                    "claim_token": None,
                    "claim_expires_at": None,
                    "last_error": reason,
                }
            )
            return True

    def dead_letter(self, job_id: str, claim_token: str, *, now: int, reason: str) -> bool:
        return self._finish(job_id, claim_token, now=now, status="dead_lettered", reason=reason)

    def recover_stale(self, *, now: int) -> list[StoredAiJob]:
        recovered: list[StoredAiJob] = []
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                if (
                    job.status != "running"
                    or job.claim_expires_at is None
                    or job.claim_expires_at > now
                ):
                    continue
                queued = job.model_copy(
                    update={
                        "status": "queued",
                        "available_at": now,
                        "updated_at": now,
                        "claim_token": None,
                        "claim_expires_at": None,
                        "last_error": "Worker claim expired before completion.",
                    }
                )
                self._jobs[job_id] = queued
                recovered.append(queued.model_copy(deep=True))
        return recovered

    def replay(self, job_id: str, *, now: int) -> StoredAiJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != "dead_lettered":
                return None
            replayed = job.model_copy(
                update={
                    "status": "queued",
                    "attempts": 0,
                    "available_at": now,
                    "updated_at": now,
                    "claim_token": None,
                    "claim_expires_at": None,
                    "last_error": None,
                }
            )
            self._jobs[job_id] = replayed
            return replayed.model_copy(deep=True)

    def list(self) -> list[StoredAiJob]:
        with self._lock:
            return [job.model_copy(deep=True) for job in self._jobs.values()]

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()

    def _claimed(self, job_id: str, claim_token: str) -> StoredAiJob | None:
        job = self._jobs.get(job_id)
        if job is None or job.status != "running" or job.claim_token != claim_token:
            return None
        return job

    def _finish(
        self,
        job_id: str,
        claim_token: str,
        *,
        now: int,
        status: str,
        reason: str | None,
    ) -> bool:
        with self._lock:
            job = self._claimed(job_id, claim_token)
            if job is None:
                return False
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": status,
                    "updated_at": now,
                    "claim_token": None,
                    "claim_expires_at": None,
                    "last_error": reason,
                }
            )
            return True


ai_job_store = InMemoryAiJobStore()
