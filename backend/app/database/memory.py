class InMemoryTicketStore:
    def __init__(self) -> None:
        self._ticket_ids: set[str] = set()
        self._ticket_numbers: set[str] = set()
        self._tracking_codes: set[str] = set()
        self._sequence = 0

    def next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def save(self, ticket_id: str, ticket_number: str, tracking_code: str) -> None:
        self._ticket_ids.add(ticket_id)
        self._ticket_numbers.add(ticket_number)
        self._tracking_codes.add(tracking_code)

    def has_ticket_id(self, ticket_id: str) -> bool:
        return ticket_id in self._ticket_ids

    def has_ticket_number(self, ticket_number: str) -> bool:
        return ticket_number in self._ticket_numbers

    def has_tracking_code(self, tracking_code: str) -> bool:
        return tracking_code in self._tracking_codes

    def clear(self) -> None:
        self._ticket_ids.clear()
        self._ticket_numbers.clear()
        self._tracking_codes.clear()
        self._sequence = 0


ticket_store = InMemoryTicketStore()
