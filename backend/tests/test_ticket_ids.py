"""Unit tests for ticket ID / tracking code generation."""

from __future__ import annotations

from datetime import UTC, datetime

from app.utils.ticket_ids import (
    DEFAULT_TICKET_PREFIX,
    TRACKING_CODE_ALPHABET,
    TRACKING_CODE_LENGTH,
    generate_audit_history_id,
    generate_status_history_id,
    generate_ticket_id,
    generate_ticket_number,
    generate_tracking_code,
    is_valid_tracking_code,
    normalize_tracking_code,
)

AMBIGUOUS_CHARS = set("IO01")


def test_generate_ticket_id_uses_tkt_prefix_and_hex() -> None:
    ticket_id = generate_ticket_id()
    assert ticket_id.startswith("tkt_"), (
        f"ticket_ids.generate_ticket_id: expected tkt_ prefix, got {ticket_id!r}"
    )
    suffix = ticket_id.removeprefix("tkt_")
    assert len(suffix) == 32, (
        f"ticket_ids.generate_ticket_id: expected 32 hex chars, got {len(suffix)}"
    )
    assert all(c in "0123456789abcdef" for c in suffix), (
        f"ticket_ids.generate_ticket_id: non-hex suffix in {ticket_id!r}"
    )


def test_generate_ticket_id_is_unique() -> None:
    ids = {generate_ticket_id() for _ in range(50)}
    assert len(ids) == 50, "ticket_ids.generate_ticket_id: expected unique ids across 50 calls"


def test_generate_status_history_id_uses_hist_prefix() -> None:
    history_id = generate_status_history_id()
    assert history_id.startswith("hist_"), (
        f"ticket_ids.generate_status_history_id: expected hist_ prefix, got {history_id!r}"
    )
    suffix = history_id.removeprefix("hist_")
    assert len(suffix) == 32, (
        f"ticket_ids.generate_status_history_id: expected 32 hex chars, got {len(suffix)}"
    )


def test_generate_audit_history_id_uses_aud_prefix() -> None:
    audit_id = generate_audit_history_id()
    assert audit_id.startswith("aud_"), (
        f"ticket_ids.generate_audit_history_id: expected aud_ prefix, got {audit_id!r}"
    )
    suffix = audit_id.removeprefix("aud_")
    assert len(suffix) == 32, (
        f"ticket_ids.generate_audit_history_id: expected 32 hex chars, got {len(suffix)}"
    )


def test_generate_tracking_code_default_length_and_alphabet() -> None:
    code = generate_tracking_code()
    assert len(code) == TRACKING_CODE_LENGTH, (
        f"ticket_ids.generate_tracking_code: expected length {TRACKING_CODE_LENGTH}, "
        f"got {len(code)} ({code!r})"
    )
    assert set(code) <= set(TRACKING_CODE_ALPHABET), (
        f"ticket_ids.generate_tracking_code: chars outside alphabet in {code!r}"
    )
    assert not (set(code) & AMBIGUOUS_CHARS), (
        f"ticket_ids.generate_tracking_code: ambiguous chars in {code!r}"
    )
    assert is_valid_tracking_code(code)


def test_normalize_and_validate_tracking_code() -> None:
    assert normalize_tracking_code(" ab12cd ") == "AB12CD"
    assert is_valid_tracking_code("ab23cd")
    assert is_valid_tracking_code("  AB23CD  ")
    assert not is_valid_tracking_code("")
    assert not is_valid_tracking_code("   ")
    assert not is_valid_tracking_code("AB12")
    assert not is_valid_tracking_code("IIIIII")
    assert not is_valid_tracking_code("AB12O1")


def test_generate_tracking_code_custom_length() -> None:
    code = generate_tracking_code(length=10)
    assert len(code) == 10, (
        f"ticket_ids.generate_tracking_code: expected length 10, got {len(code)}"
    )
    assert set(code) <= set(TRACKING_CODE_ALPHABET)


def test_generate_ticket_number_zero_pads_and_uses_utc_year() -> None:
    year = datetime.now(UTC).year
    number = generate_ticket_number(1)
    assert number == f"{DEFAULT_TICKET_PREFIX}-{year}-0001", (
        f"ticket_ids.generate_ticket_number: unexpected format {number!r}"
    )

    number_large = generate_ticket_number(42, prefix="LB")
    assert number_large == f"LB-{year}-0042", (
        f"ticket_ids.generate_ticket_number: unexpected prefixed format {number_large!r}"
    )


def test_tracking_code_alphabet_excludes_ambiguous_characters() -> None:
    assert not (set(TRACKING_CODE_ALPHABET) & AMBIGUOUS_CHARS), (
        "ticket_ids.TRACKING_CODE_ALPHABET: must exclude I, O, 0, and 1"
    )
