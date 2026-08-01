"""Canonical E.164 phone normalization (issue #193 / #169).

All account creation, OTP, login, lookup, phone update, ticket linking, and
future WhatsApp reconciliation must use this single algorithm. The server never
guesses a region from locale, IP, or deployment.
"""

from __future__ import annotations

import re

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

# E.164: '+' plus 8–15 digits (country code + national significant number).
_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


class PhoneNormalizationError(ValueError):
    """Raised when a phone cannot be normalized to a valid E.164 value."""


def normalize_phone(phone: str, region: str | None = None) -> str:
    """Return the canonical E.164 form for ``phone``.

    Accepts an E.164 number (region optional) or a national number with an
    explicit ISO 3166-1 alpha-2 ``region``. Formatting characters are handled
    only by the parser. Extensions, short codes, and numbers that are not both
    possible and valid are rejected.
    """
    if phone is None or not str(phone).strip():
        raise PhoneNormalizationError("Phone number is required.")

    raw = str(phone).strip()
    region_code: str | None
    if region is None or not str(region).strip():
        region_code = None
    else:
        region_code = str(region).strip().upper()
        if len(region_code) != 2 or not region_code.isalpha():
            raise PhoneNormalizationError("Region must be an ISO 3166-1 alpha-2 code.")

    if not raw.startswith("+") and region_code is None:
        raise PhoneNormalizationError("National-format phone numbers require an explicit region.")

    try:
        parsed = phonenumbers.parse(raw, region_code)
    except NumberParseException as exc:
        raise PhoneNormalizationError("Phone number could not be parsed.") from exc

    if parsed.extension:
        raise PhoneNormalizationError("Phone number extensions are not supported.")

    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        raise PhoneNormalizationError("Phone number is not a valid number.")

    canonical = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    if not _E164_PATTERN.fullmatch(canonical):
        raise PhoneNormalizationError("Phone number is not a valid E.164 value.")
    return canonical


def phone_claim_key(canonical_phone: str) -> str:
    """Return the phone-claims partition key for a canonical E.164 phone."""
    if not _E164_PATTERN.fullmatch(canonical_phone):
        raise PhoneNormalizationError("Phone claim key requires a canonical E.164 phone.")
    return f"PHONE#{canonical_phone}"
