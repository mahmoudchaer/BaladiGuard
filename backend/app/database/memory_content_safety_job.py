from threading import Lock
from uuid import uuid4

from app.schemas.stored_content_safety_job import StoredContentSafetyJob


def content_safety_job_id(ticket_id: str, generation: int) -> str:
    return f"safety:{ticket_id}:g{generation}"


class InMemoryContentSafetyJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, StoredContentSafetyJob] = {}
        self._lock = Lock()

    def enqueue(self, ticket_id: str, generation: int, now: int) -> StoredContentSafetyJob:
        job_id = content_safety_job_id(ticket_id, generation)
        with self._lock:
            existing = self._jobs.get(job_id)
            if existing:
                return existing.model_copy(deep=True)
            job = StoredContentSafetyJob(
                jobId=job_id,
                ticketId=ticket_id,
                generation=generation,
                status="queued",
                availableAt=now,
                createdAt=now,
                updatedAt=now,
            )
            self._jobs[job_id] = job
            return job.model_copy(deep=True)

    def get(self, job_id: str) -> StoredContentSafetyJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def claim_next(self, *, now: int, claim_ttl_seconds: int) -> StoredContentSafetyJob | None:
        with self._lock:
            eligible = sorted(
                (j for j in self._jobs.values() if j.status == "queued" and j.available_at <= now),
                key=lambda j: (j.available_at, j.created_at, j.job_id),
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
        return self._finish(job_id, claim_token, now, "succeeded", None)

    def retry(
        self, job_id: str, claim_token: str, *, available_at: int, now: int, reason: str
    ) -> bool:
        with self._lock:
            job = self._claimed(job_id, claim_token)
            if not job:
                return False
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": "queued",
                    "available_at": available_at,
                    "updated_at": now,
                    "claim_token": None,
                    "claim_expires_at": None,
                    "last_error_code": reason,
                }
            )
            return True

    def dead_letter(self, job_id: str, claim_token: str, *, now: int, reason: str) -> bool:
        return self._finish(job_id, claim_token, now, "dead_lettered", reason)

    def recover_stale(self, *, now: int) -> list[StoredContentSafetyJob]:
        recovered = []
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
                        "last_error_code": "CLAIM_EXPIRED",
                    }
                )
                self._jobs[job_id] = queued
                recovered.append(job.model_copy(deep=True))
        return recovered

    def list(self) -> list[StoredContentSafetyJob]:
        with self._lock:
            return [j.model_copy(deep=True) for j in self._jobs.values()]

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()

    def _claimed(self, job_id: str, token: str):
        job = self._jobs.get(job_id)
        return job if job and job.status == "running" and job.claim_token == token else None

    def _finish(self, job_id: str, token: str, now: int, status: str, reason: str | None) -> bool:
        with self._lock:
            job = self._claimed(job_id, token)
            if not job:
                return False
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": status,
                    "updated_at": now,
                    "claim_token": None,
                    "claim_expires_at": None,
                    "last_error_code": reason,
                }
            )
            return True


content_safety_job_store = InMemoryContentSafetyJobStore()
