"""In-memory WhatsApp conversation + inbound dedup stores (tests/local)."""

from __future__ import annotations

import time
from threading import Lock

from app.database.whatsapp_store import ConversationVersionConflict
from app.schemas.whatsapp_conversation import WhatsAppConversation


class InMemoryWhatsAppConversationStore:
    def __init__(self) -> None:
        self._rows: dict[str, WhatsAppConversation] = {}
        self._lock = Lock()

    def get(self, conversation_key: str) -> WhatsAppConversation | None:
        with self._lock:
            row = self._rows.get(conversation_key)
            return row.model_copy(deep=True) if row is not None else None

    def put_new(self, conversation: WhatsAppConversation) -> WhatsAppConversation:
        with self._lock:
            if conversation.conversation_key in self._rows:
                raise ConversationVersionConflict("Conversation already exists.")
            stored = conversation.model_copy(deep=True)
            self._rows[conversation.conversation_key] = stored
            return stored.model_copy(deep=True)

    def conditional_update(
        self,
        conversation: WhatsAppConversation,
        *,
        expected_version: int,
    ) -> WhatsAppConversation:
        with self._lock:
            current = self._rows.get(conversation.conversation_key)
            if current is None or current.version != expected_version:
                raise ConversationVersionConflict("Conversation version mismatch.")
            stored = conversation.model_copy(deep=True)
            stored.version = expected_version + 1
            self._rows[conversation.conversation_key] = stored
            return stored.model_copy(deep=True)

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()


class InMemoryWhatsAppDedupStore:
    def __init__(self) -> None:
        self._seen: dict[str, float] = {}
        self._lock = Lock()

    def try_record(self, *, message_id: str, ttl_seconds: int) -> bool:
        now = time.time()
        with self._lock:
            expires = self._seen.get(message_id)
            if expires is not None and expires > now:
                return False
            self._seen[message_id] = now + max(ttl_seconds, 1)
            # Opportunistic cleanup
            stale = [key for key, exp in self._seen.items() if exp <= now]
            for key in stale[:100]:
                self._seen.pop(key, None)
            return True

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()


whatsapp_conversation_store = InMemoryWhatsAppConversationStore()
whatsapp_dedup_store = InMemoryWhatsAppDedupStore()
