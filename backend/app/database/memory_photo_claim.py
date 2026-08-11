from threading import Lock


class InMemoryPhotoClaimStore:
    def __init__(self) -> None:
        self._claims: dict[str, tuple[str, str]] = {}
        self._lock = Lock()

    def claim(self, object_key: str, *, owner_scope: str, ticket_id: str) -> bool:
        with self._lock:
            if object_key in self._claims:
                return False
            self._claims[object_key] = (owner_scope, ticket_id)
            return True

    def release(self, object_key: str, *, ticket_id: str) -> bool:
        with self._lock:
            claim = self._claims.get(object_key)
            if claim is None or claim[1] != ticket_id:
                return False
            del self._claims[object_key]
            return True

    def clear(self) -> None:
        with self._lock:
            self._claims.clear()


photo_claim_store = InMemoryPhotoClaimStore()
