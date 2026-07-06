from app.schemas.stored_ticket import StoredTicket


class InMemoryTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, StoredTicket] = {}
        self._ticket_numbers: set[str] = set()
        self._tracking_codes: set[str] = set()
        self._sequence = 0

    def next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def save(self, ticket: StoredTicket) -> None:
        self._tickets[ticket.ticket_id] = ticket
        self._ticket_numbers.add(ticket.ticket_number)
        self._tracking_codes.add(ticket.tracking_code)

    def get(self, ticket_id: str) -> StoredTicket | None:
        return self._tickets.get(ticket_id)

    def list(self) -> list[StoredTicket]:
        return list(self._tickets.values())

    def has_ticket_id(self, ticket_id: str) -> bool:
        return ticket_id in self._tickets

    def has_ticket_number(self, ticket_number: str) -> bool:
        return ticket_number in self._ticket_numbers

    def has_tracking_code(self, tracking_code: str) -> bool:
        return tracking_code in self._tracking_codes

    def clear(self) -> None:
        self._tickets.clear()
        self._ticket_numbers.clear()
        self._tracking_codes.clear()
        self._sequence = 0


ticket_store = InMemoryTicketStore()
