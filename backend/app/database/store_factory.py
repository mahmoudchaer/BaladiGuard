from app.config import Settings, get_settings
from app.database.memory import ticket_store
from app.database.ticket_store import TicketStore


def build_ticket_store(settings: Settings | None = None) -> TicketStore:
    settings = settings or get_settings()
    if settings.use_dynamodb:
        from app.database.dynamo_ticket_store import DynamoTicketStore

        return DynamoTicketStore(settings)
    return ticket_store


def get_ticket_store() -> TicketStore:
    return build_ticket_store(get_settings())
