"""In-memory contribution ledger and ranking projection (issue #323)."""

from __future__ import annotations

from threading import Lock

from app.schemas.stored_rewards import StoredRewardEvent, StoredRewardProjection


class InMemoryRewardsLedgerStore:
    def __init__(self) -> None:
        self._by_key: dict[str, StoredRewardEvent] = {}
        self._by_citizen: dict[str, list[str]] = {}
        self._by_ticket: dict[str, list[str]] = {}
        self._lock = Lock()

    def get_by_event_key(self, event_key: str) -> StoredRewardEvent | None:
        with self._lock:
            event = self._by_key.get(event_key)
            return event.model_copy(deep=True) if event else None

    def put_if_absent(self, event: StoredRewardEvent) -> StoredRewardEvent:
        with self._lock:
            existing = self._by_key.get(event.event_key)
            if existing is not None:
                return existing.model_copy(deep=True)
            stored = event.model_copy(deep=True)
            self._by_key[stored.event_key] = stored
            self._by_citizen.setdefault(stored.citizen_user_id, []).append(stored.event_key)
            if stored.ticket_id:
                self._by_ticket.setdefault(stored.ticket_id, []).append(stored.event_key)
            return stored.model_copy(deep=True)

    def list_by_citizen(self, citizen_user_id: str) -> list[StoredRewardEvent]:
        with self._lock:
            keys = list(self._by_citizen.get(citizen_user_id, []))
            items = [self._by_key[key].model_copy(deep=True) for key in keys if key in self._by_key]
        items.sort(key=lambda item: (item.created_at, item.event_id))
        return items

    def list_by_ticket(self, ticket_id: str) -> list[StoredRewardEvent]:
        with self._lock:
            keys = list(self._by_ticket.get(ticket_id, []))
            items = [self._by_key[key].model_copy(deep=True) for key in keys if key in self._by_key]
        items.sort(key=lambda item: (item.created_at, item.event_id))
        return items

    def clear(self) -> None:
        with self._lock:
            self._by_key.clear()
            self._by_citizen.clear()
            self._by_ticket.clear()


class InMemoryRewardsProjectionStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredRewardProjection] = {}
        self._lock = Lock()

    def get(self, citizen_user_id: str) -> StoredRewardProjection | None:
        with self._lock:
            item = self._items.get(citizen_user_id)
            return item.model_copy(deep=True) if item else None

    def save(self, projection: StoredRewardProjection) -> None:
        with self._lock:
            self._items[projection.citizen_user_id] = projection.model_copy(deep=True)

    def list_ranked(
        self, *, public_only: bool, period: str, period_key: str
    ) -> list[StoredRewardProjection]:
        with self._lock:
            items = [item.model_copy(deep=True) for item in self._items.values()]
        ranked: list[StoredRewardProjection] = []
        for item in items:
            if item.withdrawn:
                continue
            points = (
                item.confirmed_points_monthly
                if period == "monthly" and item.monthly_period_key == period_key
                else item.confirmed_points_all_time
            )
            if period == "monthly" and item.monthly_period_key != period_key:
                points = 0
            if points <= 0:
                continue
            if public_only and not item.public_eligible:
                continue
            ranked.append(item)
        if period == "monthly":
            ranked.sort(
                key=lambda item: (
                    -item.confirmed_points_monthly,
                    item.first_award_at or "9999",
                    item.citizen_user_id,
                )
            )
        else:
            ranked.sort(
                key=lambda item: (
                    -item.confirmed_points_all_time,
                    item.first_award_at or "9999",
                    item.citizen_user_id,
                )
            )
        return ranked

    def list_all(self) -> list[StoredRewardProjection]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._items.values()]

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


rewards_ledger_store = InMemoryRewardsLedgerStore()
rewards_projection_store = InMemoryRewardsProjectionStore()
