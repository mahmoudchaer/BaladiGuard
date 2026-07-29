import secrets
from datetime import UTC, datetime
from uuid import uuid4

TRACKING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TRACKING_CODE_LENGTH = 6
DEFAULT_TICKET_PREFIX = "BG"


def generate_ticket_id() -> str:
    return f"tkt_{uuid4().hex}"


def generate_status_history_id() -> str:
    return f"hist_{uuid4().hex}"


def generate_duplicate_group_id() -> str:
    return f"dup_{uuid4().hex}"


def generate_tracking_code(length: int = TRACKING_CODE_LENGTH) -> str:
    return "".join(secrets.choice(TRACKING_CODE_ALPHABET) for _ in range(length))


def normalize_tracking_code(tracking_code: str) -> str:
    return tracking_code.strip().upper()


def is_valid_tracking_code(tracking_code: str) -> bool:
    """True when the code matches the citizen-facing tracking-code format."""
    normalized = normalize_tracking_code(tracking_code)
    if len(normalized) != TRACKING_CODE_LENGTH:
        return False
    return all(character in TRACKING_CODE_ALPHABET for character in normalized)


def generate_ticket_number(sequence: int, prefix: str = DEFAULT_TICKET_PREFIX) -> str:
    year = datetime.now(UTC).year
    return f"{prefix}-{year}-{sequence:04d}"
