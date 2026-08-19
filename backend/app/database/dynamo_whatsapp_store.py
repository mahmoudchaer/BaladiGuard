"""DynamoDB WhatsApp conversation + inbound message dedup stores (issue #296)."""

from __future__ import annotations

import time
from typing import Any

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.whatsapp_store import ConversationVersionConflict
from app.schemas.whatsapp_conversation import WhatsAppConversation


class DynamoWhatsAppConversationStore:
    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        resource = create_dynamodb_resource(cfg)
        prefix = cfg.dynamodb_table_prefix
        self._table = resource.Table(build_table_name(prefix, "whatsapp-conversations"))

    def get(self, conversation_key: str) -> WhatsAppConversation | None:
        response = self._table.get_item(Key={"conversationKey": conversation_key})
        item = response.get("Item")
        if not item:
            return None
        return WhatsAppConversation.model_validate(item)

    def put_new(self, conversation: WhatsAppConversation) -> WhatsAppConversation:
        item = conversation.model_dump(by_alias=True, exclude_none=True)
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(conversationKey)",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise ConversationVersionConflict("Conversation already exists.") from exc
            raise
        return conversation

    def conditional_update(
        self,
        conversation: WhatsAppConversation,
        *,
        expected_version: int,
    ) -> WhatsAppConversation:
        updated = conversation.model_copy(deep=True)
        updated.version = expected_version + 1
        item = updated.model_dump(by_alias=True, exclude_none=True)
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_exists(conversationKey) AND version = :v",
                ExpressionAttributeValues={":v": expected_version},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise ConversationVersionConflict("Conversation version mismatch.") from exc
            raise
        return updated


class DynamoWhatsAppDedupStore:
    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        resource = create_dynamodb_resource(cfg)
        prefix = cfg.dynamodb_table_prefix
        self._table = resource.Table(build_table_name(prefix, "whatsapp-inbound-dedup"))

    def try_record(self, *, message_id: str, ttl_seconds: int) -> bool:
        expires = int(time.time()) + max(ttl_seconds, 1)
        item: dict[str, Any] = {
            "messageId": message_id,
            "ttl": expires,
            "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(messageId)",
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise
