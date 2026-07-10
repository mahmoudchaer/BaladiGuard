from app.config import Settings, get_settings
from app.database.memory import ticket_store
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


def get_ticket_store() -> TicketStore:
    return build_ticket_store(get_settings())


def get_status_history_store() -> StatusHistoryStore:
    return build_status_history_store(get_settings())
