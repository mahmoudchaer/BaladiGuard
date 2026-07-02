from app.models.ticket import TicketRecord


class InMemoryTicketStore:
    def __init__(self) -> None:
        self._tickets: dict[str, TicketRecord] = {}
        self._ticket_numbers: set[str] = set()
        self._tracking_codes: set[str] = set()
        self._sequence = 0

    def next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def save(self, ticket: TicketRecord) -> TicketRecord:
        if ticket.ticket_id in self._tickets:
            raise ValueError("Ticket ID already exists.")
        if ticket.ticket_number in self._ticket_numbers:
            raise ValueError("Ticket number already exists.")
        if ticket.tracking_code in self._tracking_codes:
            raise ValueError("Tracking code already exists.")

        self._tickets[ticket.ticket_id] = ticket
        self._ticket_numbers.add(ticket.ticket_number)
        self._tracking_codes.add(ticket.tracking_code)
        return ticket

    def get(self, ticket_id: str) -> TicketRecord | None:
        return self._tickets.get(ticket_id)

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
