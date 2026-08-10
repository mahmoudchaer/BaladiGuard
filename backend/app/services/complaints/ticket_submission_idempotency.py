"""Ticket submission idempotency ledger (issue #258).

Clients send ``Idempotency-Key`` (or body ``clientSubmissionId``) so retries after
upload-only success or flaky networks do not create duplicate tickets.
Keys are scoped to the authenticated citizen: ``{ownerUserId}:{clientKey}``.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.ticket import SubmitTicketResponse

# UUID / ULID-like keys from clients; keep conservative to avoid huge storage abuse.
_CLIENT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def normalize_client_submission_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if not _CLIENT_KEY_PATTERN.match(cleaned):
        return None
    return cleaned


def composite_submission_key(*, owner_user_id: str, client_key: str) -> str:
    return f"{owner_user_id.strip()}:{client_key.strip()}"


class TicketSubmissionIdempotencyStore(Protocol):
    def get_completed(self, composite_key: str) -> SubmitTicketResponse | None:
        """Return a completed response for a prior successful claim, if any."""

    def try_begin(self, composite_key: str) -> bool:
        """Claim ``composite_key`` for a new attempt.

        Returns True when this caller owns the attempt; False when another
        attempt already claimed or completed it.
        """

    def complete(self, composite_key: str, response: SubmitTicketResponse) -> None:
        """Persist the successful response for replay."""

    def release(self, composite_key: str) -> None:
        """Release an unfinished claim after a failed create."""


class InMemoryTicketSubmissionIdempotencyStore:
    def __init__(self) -> None:
        self._lock = Lock()
        # value: None while in flight; SubmitTicketResponse when completed
        self._entries: dict[str, SubmitTicketResponse | None] = {}

    def get_completed(self, composite_key: str) -> SubmitTicketResponse | None:
        with self._lock:
            value = self._entries.get(composite_key)
            if value is None:
                return None
            return value

    def try_begin(self, composite_key: str) -> bool:
        with self._lock:
            if composite_key in self._entries:
                return False
            self._entries[composite_key] = None
            return True

    def complete(self, composite_key: str, response: SubmitTicketResponse) -> None:
        with self._lock:
            self._entries[composite_key] = response

    def release(self, composite_key: str) -> None:
        with self._lock:
            existing = self._entries.get(composite_key)
            if existing is None:
                self._entries.pop(composite_key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class DynamoTicketSubmissionIdempotencyStore:
    """DynamoDB conditional claims on ``ticket-submission-claims``."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "ticket-submission-claims"))

    def get_completed(self, composite_key: str) -> SubmitTicketResponse | None:
        result = self._table.get_item(Key={"idempotencyKey": composite_key})
        item = result.get("Item")
        if not item:
            return None
        if item.get("status") != "completed":
            return None
        payload = item.get("responseJson")
        if not payload:
            return None
        if isinstance(payload, str):
            data: Any = json.loads(payload)
        else:
            data = payload
        return SubmitTicketResponse.model_validate(data)

    def try_begin(self, composite_key: str) -> bool:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        try:
            self._table.put_item(
                Item={
                    "idempotencyKey": composite_key,
                    "status": "claimed",
                    "claimedAt": now,
                },
                ConditionExpression="attribute_not_exists(idempotencyKey)",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def complete(self, composite_key: str, response: SubmitTicketResponse) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        body = response.model_dump(by_alias=True, mode="json")
        self._table.put_item(
            Item={
                "idempotencyKey": composite_key,
                "status": "completed",
                "completedAt": now,
                "responseJson": json.dumps(body),
            }
        )

    def release(self, composite_key: str) -> None:
        result = self._table.get_item(Key={"idempotencyKey": composite_key})
        item = result.get("Item")
        if not item:
            return
        if item.get("status") == "completed":
            return
        self._table.delete_item(Key={"idempotencyKey": composite_key})


_store = InMemoryTicketSubmissionIdempotencyStore()


def get_ticket_submission_idempotency_store(
    settings: Settings | None = None,
) -> TicketSubmissionIdempotencyStore:
    resolved = settings or get_settings()
    if resolved.use_dynamodb:
        return DynamoTicketSubmissionIdempotencyStore(resolved)
    return _store


def reset_ticket_submission_idempotency_store() -> None:
    """Test helper: clear in-memory claims between cases."""
    _store.clear()
