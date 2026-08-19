"""WhatsApp conversation + inbound dedup store protocols (issue #296)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.whatsapp_conversation import WhatsAppConversation


class ConversationVersionConflict(RuntimeError):
    """Conditional write failed because another webhook advanced the conversation."""


class WhatsAppConversationStore(Protocol):
    def get(self, conversation_key: str) -> WhatsAppConversation | None: ...

    def put_new(self, conversation: WhatsAppConversation) -> WhatsAppConversation: ...

    def conditional_update(
        self,
        conversation: WhatsAppConversation,
        *,
        expected_version: int,
    ) -> WhatsAppConversation: ...

    def clear(self) -> None: ...


class WhatsAppDedupStore(Protocol):
    def try_record(self, *, message_id: str, ttl_seconds: int) -> bool:
        """Return True if this message_id is newly recorded; False if duplicate."""

    def clear(self) -> None: ...
