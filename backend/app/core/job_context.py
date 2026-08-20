"""Job-scoped context so worker logs/metrics share a durable correlation id."""

from __future__ import annotations

from contextvars import ContextVar, Token

_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)


def set_job_id(job_id: str | None) -> Token[str | None]:
    return _job_id.set(job_id)


def reset_job_id(token: Token[str | None]) -> None:
    _job_id.reset(token)


def get_job_id() -> str | None:
    return _job_id.get()
