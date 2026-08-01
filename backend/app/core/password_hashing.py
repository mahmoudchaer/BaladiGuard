"""Password hashing helpers for staff accounts (issue #175).

Uses PBKDF2-HMAC-SHA256 with a per-password salt. Hashes are never logged or
returned from APIs.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_SCHEME = "pbkdf2_sha256"
_DEFAULT_ITERATIONS = 260_000


def hash_password(password: str, *, iterations: int = _DEFAULT_ITERATIONS) -> str:
    if not password:
        raise ValueError("Password is required.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"{_SCHEME}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_raw, salt, expected_hex = encoded.split("$", 3)
        if scheme != _SCHEME:
            return False
        iterations = int(iterations_raw)
        if iterations < 1:
            return False
    except (ValueError, AttributeError):
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return hmac.compare_digest(digest.hex(), expected_hex)
