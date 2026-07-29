from app.config import Settings, get_settings
from app.database.audit_history_store import AuditHistoryStore
from app.database.duplicate_group_store import DuplicateGroupStore
from app.database.memory import ticket_store
from app.database.memory_audit_history import audit_history_store
from app.database.memory_duplicate_group import duplicate_group_store
from app.database.memory_status_history import status_history_store
from app.database.status_history_store import StatusHistoryStore
from app.database.ticket_store import TicketStore


def build_ticket_store(settings: Settings | None = None) -> TicketStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_ticket_store import DynamoTicketStore

        return DynamoTicketStore(settings)
    return ticket_store


def build_status_history_store(settings: Settings | None = None) -> StatusHistoryStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_status_history_store import DynamoStatusHistoryStore

        return DynamoStatusHistoryStore(settings)
    return status_history_store


def build_audit_history_store(settings: Settings | None = None) -> AuditHistoryStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_audit_history_store import DynamoAuditHistoryStore

        return DynamoAuditHistoryStore(settings)
    return audit_history_store


def build_duplicate_group_store(settings: Settings | None = None) -> DuplicateGroupStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_duplicate_group_store import DynamoDuplicateGroupStore

        return DynamoDuplicateGroupStore(settings)
    return duplicate_group_store


def get_ticket_store() -> TicketStore:
    return build_ticket_store(get_settings())


def get_status_history_store() -> StatusHistoryStore:
    return build_status_history_store(get_settings())


def get_audit_history_store() -> AuditHistoryStore:
    return build_audit_history_store(get_settings())


def get_duplicate_group_store() -> DuplicateGroupStore:
    return build_duplicate_group_store(get_settings())
