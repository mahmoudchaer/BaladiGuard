import secrets
from datetime import UTC, datetime
from uuid import uuid4

TRACKING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_TICKET_PREFIX = "BG"


def generate_ticket_id() -> str:
    return f"tkt_{uuid4().hex}"


def generate_tracking_code(length: int = 6) -> str:
    return "".join(secrets.choice(TRACKING_CODE_ALPHABET) for _ in range(length))


def generate_ticket_number(sequence: int, prefix: str = DEFAULT_TICKET_PREFIX) -> str:
    year = datetime.now(UTC).year
    return f"{prefix}-{year}-{sequence:04d}"
