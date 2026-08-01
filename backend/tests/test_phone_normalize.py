import pytest

from app.utils.phone import PhoneNormalizationError, normalize_phone, phone_claim_key


def test_normalizes_e164_with_formatting() -> None:
    assert normalize_phone("+961 70 123 456") == "+96170123456"


def test_normalizes_national_with_explicit_region() -> None:
    assert normalize_phone("70 123 456", region="LB") == "+96170123456"


def test_drops_lebanese_trunk_zero() -> None:
    assert normalize_phone("03 123 456", region="LB") == "+9613123456"


def test_rejects_national_without_region() -> None:
    with pytest.raises(PhoneNormalizationError, match="explicit region"):
        normalize_phone("70 123 456")


def test_rejects_invalid_region() -> None:
    with pytest.raises(PhoneNormalizationError, match="ISO 3166-1"):
        normalize_phone("70 123 456", region="LBN")


def test_rejects_extensions() -> None:
    with pytest.raises(PhoneNormalizationError, match="extensions"):
        normalize_phone("+96170123456;ext=123")


def test_rejects_short_codes() -> None:
    with pytest.raises(PhoneNormalizationError):
        normalize_phone("911", region="US")


def test_phone_claim_key_format() -> None:
    assert phone_claim_key("+96170123456") == "PHONE#+96170123456"
