"""Ticket submission idempotency ledger (issue #258).

Clients send ``Idempotency-Key`` (or body ``clientSubmissionId``) so retries after
upload-only success or flaky networks do not create duplicate tickets.
Keys are scoped to the authenticated citizen: ``{ownerUserId}:{clientKey}``.

Durability model:
- ``claimed`` — exclusive in-progress attempt (with ``claimedAt``)
- ``pendingTicketId`` written as soon as the ticket is about to be / was
  persisted so a crash after ``save`` can recover without a second ticket
- ``completed`` — full ``SubmitTicketResponse`` for safe replay
- Stale in-progress claims without a durable ticket id are reclaimed after
  ``CLAIM_STALE_SECONDS`` so permanent ``SUBMISSION_IN_PROGRESS`` is avoided
- DynamoDB TTL attribute ``ttl`` purges completed claims after
  ``CLAIM_RETENTION_SECONDS`` (and abandoned claims after a short window)
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Protocol

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.schemas.ticket import SubmitTicketResponse

# UUID / ULID-like keys from clients; keep conservative to avoid huge storage abuse.
# WhatsApp keys look like ``wa:{phone-id}:{sender}:{hex}``; HTTP keys stay UUID-like.
_CLIENT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")

# Unfinished claims without a ticket id may be reclaimed after this window.
CLAIM_STALE_SECONDS = 120
# Completed replay rows retained long enough for offline client retries.
CLAIM_RETENTION_SECONDS = 14 * 24 * 60 * 60  # 14 days
# Claimed-only rows (no ticket yet) expire via Dynamo TTL shortly after stale window.
CLAIMED_ROW_TTL_SECONDS = CLAIM_STALE_SECONDS * 4  # 8 minutes


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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _epoch_seconds() -> int:
    return int(time.time())


def _parse_iso_epoch(raw: str | None) -> float | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _is_claim_stale(claimed_at: str | None, *, now: float | None = None) -> bool:
    claimed_epoch = _parse_iso_epoch(claimed_at)
    if claimed_epoch is None:
        return True
    clock = now if now is not None else time.time()
    return (clock - claimed_epoch) >= CLAIM_STALE_SECONDS


def _response_from_payload(payload: Any) -> SubmitTicketResponse | None:
    if not payload:
        return None
    try:
        if isinstance(payload, str):
            data: Any = json.loads(payload)
        else:
            data = payload
        return SubmitTicketResponse.model_validate(data)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


class TicketSubmissionIdempotencyStore(Protocol):
    def get_completed(self, composite_key: str) -> SubmitTicketResponse | None:
        """Return a completed response for a prior successful claim, if any."""

    def try_begin(self, composite_key: str) -> bool:
        """Claim ``composite_key`` for a new attempt.

        Returns True when this caller owns the attempt; False when another
        attempt already claimed (fresh) or completed it. Stale unfinished
        claims without a durable ticket id are reclaimed.
        """

    def bind_ticket(
        self,
        composite_key: str,
        *,
        ticket_id: str,
        provisional_response: SubmitTicketResponse | None = None,
    ) -> None:
        """Record ticket identity on the claim before/at durable ticket save."""

    def get_pending_ticket_id(self, composite_key: str) -> str | None:
        """Return bound ticket id for an unfinished claim, if any."""

    def complete(self, composite_key: str, response: SubmitTicketResponse) -> None:
        """Persist the successful response for replay (idempotent overwrite)."""

    def try_recover(self, composite_key: str) -> SubmitTicketResponse | None:
        """If a claim already has a completed/provisional response, return it."""

    def release(self, composite_key: str) -> None:
        """Release an unfinished claim that has no durable ticket identity."""

    def force_release(self, composite_key: str) -> None:
        """Drop a non-completed claim (e.g. bind happened but ticket save failed)."""


class InMemoryTicketSubmissionIdempotencyStore:
    def __init__(self) -> None:
        self._lock = Lock()
        # In-flight: {"status": "claimed", claimedAt, pendingTicketId?, response?}
        # Completed: {"status": "completed", response: SubmitTicketResponse, ...}
        self._entries: dict[str, dict[str, Any]] = {}

    def get_completed(self, composite_key: str) -> SubmitTicketResponse | None:
        with self._lock:
            entry = self._entries.get(composite_key)
            if not entry or entry.get("status") != "completed":
                return None
            response = entry.get("response")
            return response if isinstance(response, SubmitTicketResponse) else None

    def try_begin(self, composite_key: str) -> bool:
        with self._lock:
            entry = self._entries.get(composite_key)
            if entry is None:
                self._entries[composite_key] = {
                    "status": "claimed",
                    "claimedAt": _now_iso(),
                }
                return True
            if entry.get("status") == "completed":
                return False
            if entry.get("pendingTicketId") or entry.get("response"):
                return False
            if not _is_claim_stale(entry.get("claimedAt")):
                return False
            # Reclaim stale in-flight claim with no durable ticket.
            self._entries[composite_key] = {
                "status": "claimed",
                "claimedAt": _now_iso(),
            }
            return True

    def bind_ticket(
        self,
        composite_key: str,
        *,
        ticket_id: str,
        provisional_response: SubmitTicketResponse | None = None,
    ) -> None:
        with self._lock:
            entry = self._entries.get(composite_key)
            if entry is None:
                entry = {"status": "claimed", "claimedAt": _now_iso()}
                self._entries[composite_key] = entry
            if entry.get("status") == "completed":
                return
            entry["status"] = "claimed"
            entry["pendingTicketId"] = ticket_id.strip()
            if provisional_response is not None:
                entry["response"] = provisional_response

    def get_pending_ticket_id(self, composite_key: str) -> str | None:
        with self._lock:
            entry = self._entries.get(composite_key)
            if not entry or entry.get("status") == "completed":
                return None
            pending = entry.get("pendingTicketId")
            return pending if isinstance(pending, str) and pending.strip() else None

    def complete(self, composite_key: str, response: SubmitTicketResponse) -> None:
        with self._lock:
            self._entries[composite_key] = {
                "status": "completed",
                "completedAt": _now_iso(),
                "pendingTicketId": response.ticket_id,
                "response": response,
            }

    def try_recover(self, composite_key: str) -> SubmitTicketResponse | None:
        with self._lock:
            entry = self._entries.get(composite_key)
            if not entry:
                return None
            if entry.get("status") == "completed":
                response = entry.get("response")
                return response if isinstance(response, SubmitTicketResponse) else None
            response = entry.get("response")
            if isinstance(response, SubmitTicketResponse):
                entry["status"] = "completed"
                entry["completedAt"] = _now_iso()
                return response
            return None

    def release(self, composite_key: str) -> None:
        with self._lock:
            entry = self._entries.get(composite_key)
            if not entry:
                return
            if entry.get("status") == "completed":
                return
            if entry.get("pendingTicketId") or entry.get("response"):
                # Ticket already durable; never drop the claim.
                return
            self._entries.pop(composite_key, None)

    def force_release(self, composite_key: str) -> None:
        with self._lock:
            entry = self._entries.get(composite_key)
            if not entry:
                return
            if entry.get("status") == "completed":
                return
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
        item = self._get_item(composite_key)
        if not item or item.get("status") != "completed":
            return None
        return _response_from_payload(item.get("responseJson"))

    def try_begin(self, composite_key: str) -> bool:
        now = _now_iso()
        ttl = _epoch_seconds() + CLAIMED_ROW_TTL_SECONDS
        try:
            self._table.put_item(
                Item={
                    "idempotencyKey": composite_key,
                    "status": "claimed",
                    "claimedAt": now,
                    "ttl": ttl,
                },
                ConditionExpression="attribute_not_exists(idempotencyKey)",
            )
            return True
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

        item = self._get_item(composite_key)
        if not item:
            # Race: disappeared between put and get — retry once as new claim.
            try:
                self._table.put_item(
                    Item={
                        "idempotencyKey": composite_key,
                        "status": "claimed",
                        "claimedAt": now,
                        "ttl": ttl,
                    },
                    ConditionExpression="attribute_not_exists(idempotencyKey)",
                )
                return True
            except ClientError as retry_error:
                if (
                    retry_error.response.get("Error", {}).get("Code")
                    == "ConditionalCheckFailedException"
                ):
                    return False
                raise

        if item.get("status") == "completed":
            return False
        if item.get("pendingTicketId") or item.get("responseJson"):
            return False
        if not _is_claim_stale(item.get("claimedAt")):
            return False

        # Reclaim only stale claims with no ticket identity.
        try:
            self._table.put_item(
                Item={
                    "idempotencyKey": composite_key,
                    "status": "claimed",
                    "claimedAt": now,
                    "ttl": ttl,
                },
                ConditionExpression=(
                    "attribute_exists(idempotencyKey) AND #s = :claimed "
                    "AND attribute_not_exists(pendingTicketId) "
                    "AND attribute_not_exists(responseJson)"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":claimed": "claimed"},
            )
            return True
        except ClientError as reclaim_error:
            if (
                reclaim_error.response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException"
            ):
                return False
            raise

    def bind_ticket(
        self,
        composite_key: str,
        *,
        ticket_id: str,
        provisional_response: SubmitTicketResponse | None = None,
    ) -> None:
        now = _now_iso()
        ttl = _epoch_seconds() + CLAIM_RETENTION_SECONDS
        item: dict[str, Any] = {
            "idempotencyKey": composite_key,
            "status": "claimed",
            "claimedAt": now,
            "pendingTicketId": ticket_id.strip(),
            "ttl": ttl,
        }
        if provisional_response is not None:
            body = provisional_response.model_dump(by_alias=True, mode="json")
            item["responseJson"] = json.dumps(body)
        # Unconditional overwrite of claim fields is safe once this worker owns
        # the claim; completed rows are upgraded only via complete().
        existing = self._get_item(composite_key)
        if existing and existing.get("status") == "completed":
            return
        if existing and existing.get("claimedAt"):
            item["claimedAt"] = existing["claimedAt"]
        self._table.put_item(Item=item)

    def get_pending_ticket_id(self, composite_key: str) -> str | None:
        item = self._get_item(composite_key)
        if not item or item.get("status") == "completed":
            return None
        pending = item.get("pendingTicketId")
        return pending.strip() if isinstance(pending, str) and pending.strip() else None

    def complete(self, composite_key: str, response: SubmitTicketResponse) -> None:
        now = _now_iso()
        body = response.model_dump(by_alias=True, mode="json")
        self._table.put_item(
            Item={
                "idempotencyKey": composite_key,
                "status": "completed",
                "completedAt": now,
                "pendingTicketId": response.ticket_id,
                "responseJson": json.dumps(body),
                "ttl": _epoch_seconds() + CLAIM_RETENTION_SECONDS,
            }
        )

    def try_recover(self, composite_key: str) -> SubmitTicketResponse | None:
        item = self._get_item(composite_key)
        if not item:
            return None
        if item.get("status") == "completed":
            return _response_from_payload(item.get("responseJson"))
        response = _response_from_payload(item.get("responseJson"))
        if response is not None:
            self.complete(composite_key, response)
            return response
        return None

    def release(self, composite_key: str) -> None:
        item = self._get_item(composite_key)
        if not item:
            return
        if item.get("status") == "completed":
            return
        if item.get("pendingTicketId") or item.get("responseJson"):
            return
        try:
            self._table.delete_item(
                Key={"idempotencyKey": composite_key},
                ConditionExpression=(
                    "attribute_exists(idempotencyKey) AND #s = :claimed "
                    "AND attribute_not_exists(pendingTicketId)"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":claimed": "claimed"},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return
            raise

    def force_release(self, composite_key: str) -> None:
        item = self._get_item(composite_key)
        if not item:
            return
        if item.get("status") == "completed":
            return
        try:
            self._table.delete_item(
                Key={"idempotencyKey": composite_key},
                ConditionExpression="attribute_exists(idempotencyKey) AND #s <> :completed",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":completed": "completed"},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return
            raise

    def _get_item(self, composite_key: str) -> dict[str, Any] | None:
        result = self._table.get_item(Key={"idempotencyKey": composite_key})
        item = result.get("Item")
        return item if isinstance(item, dict) else None


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
