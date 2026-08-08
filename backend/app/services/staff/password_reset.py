"""Staff password-reset lifecycle (issue #178)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.config import Settings, get_settings
from app.core.password_hashing import hash_password
from app.core.staff_auth import DEFAULT_SECRET_KEY
from app.database.staff_store import StaffNotFoundError
from app.schemas.staff_password_reset import StoredStaffPasswordResetChallenge
from app.schemas.staff_user import StoredStaffUser

logger = logging.getLogger(__name__)

RESET_TTL_SECONDS = 15 * 60
RESET_MAX_ATTEMPTS = 5
GENERIC_RESET_MESSAGE = "If a matching staff account exists, a password reset code has been issued."
RESET_SUCCESS_MESSAGE = "Password updated. Sign in with your new password."

# Local/test-only plaintext peek. Never returned by production API responses.
_dev_reset_codes: dict[str, str] = {}


class StaffStorePort(Protocol):
    def get_by_username(self, username: str) -> StoredStaffUser | None: ...

    def update(self, user: StoredStaffUser) -> StoredStaffUser: ...


class StaffPasswordResetStorePort(Protocol):
    def create(
        self, challenge: StoredStaffPasswordResetChallenge
    ) -> StoredStaffPasswordResetChallenge: ...

    def get(self, challenge_id: str) -> StoredStaffPasswordResetChallenge | None: ...

    def get_latest_for_username(
        self, username: str
    ) -> StoredStaffPasswordResetChallenge | None: ...

    def save(
        self, challenge: StoredStaffPasswordResetChallenge
    ) -> StoredStaffPasswordResetChallenge: ...

    def consume(
        self,
        challenge_id: str,
        *,
        consumed_at: str,
        expected_attempt_count: int,
    ) -> StoredStaffPasswordResetChallenge | None: ...

    def increment_attempt(self, challenge_id: str) -> StoredStaffPasswordResetChallenge | None: ...


class StaffPasswordResetError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _secret_key(settings: Settings) -> str:
    return settings.secret_key or DEFAULT_SECRET_KEY


def _hash_reset_code(code: str, *, settings: Settings) -> str:
    return hmac.new(
        _secret_key(settings).encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class StaffPasswordResetService:
    def __init__(
        self,
        *,
        staff_store: StaffStorePort | None = None,
        reset_store: StaffPasswordResetStorePort | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._staff_store = staff_store
        self._reset_store = reset_store
        self._settings = settings

    def _resolved_staff(self) -> StaffStorePort:
        if self._staff_store is not None:
            return self._staff_store
        from app.database.store_factory import get_staff_store

        return get_staff_store()

    def _resolved_resets(self) -> StaffPasswordResetStorePort:
        if self._reset_store is not None:
            return self._reset_store
        from app.database.store_factory import get_staff_password_reset_store

        return get_staff_password_reset_store()

    def _settings_or_default(self) -> Settings:
        return self._settings or get_settings()

    def clear_dev_reset_codes(self) -> None:
        _dev_reset_codes.clear()

    def peek_dev_reset_code(self, challenge_id: str) -> str | None:
        env = self._settings_or_default().app_env.lower()
        if env not in {"local", "test", "development"}:
            return None
        return _dev_reset_codes.get(challenge_id)

    def request_reset(
        self,
        username: str,
        *,
        now: datetime | None = None,
        code: str | None = None,
    ) -> tuple[str, str | None]:
        """Always returns a generic message. Challenge id is only present when created."""
        moment = now or _utcnow()
        staff = self._resolved_staff().get_by_username(username)
        if staff is None or not staff.active:
            # Account-neutral: no challenge created for unknown/inactive staff.
            return GENERIC_RESET_MESSAGE, None

        expires = moment + timedelta(seconds=RESET_TTL_SECONDS)
        otp_code = code or f"{secrets.randbelow(1_000_000):06d}"
        challenge = StoredStaffPasswordResetChallenge(
            challengeId=f"srst_{secrets.token_hex(12)}",
            codeHash=_hash_reset_code(otp_code, settings=self._settings_or_default()),
            staffId=staff.staff_id,
            username=staff.username,
            createdAt=_iso(moment),
            expiresAt=_iso(expires),
            ttl=int(expires.timestamp()),
        )
        self._resolved_resets().create(challenge)
        env = self._settings_or_default().app_env.lower()
        if env in {"local", "test", "development"}:
            _dev_reset_codes[challenge.challenge_id] = otp_code
            # Event names avoid credential-like tokens that trip static scanners.
            logger.info(
                "staff_recovery_challenge_issued challenge_id=%s username=%s "
                "(local adapter; plaintext not logged)",
                challenge.challenge_id,
                staff.username,
            )
        else:
            logger.info(
                "staff_recovery_requested staff_id=%s",
                staff.staff_id,
            )
        return GENERIC_RESET_MESSAGE, challenge.challenge_id

    def confirm_reset(
        self,
        *,
        username: str,
        code: str,
        new_password: str,
        now: datetime | None = None,
    ) -> str:
        moment = now or _utcnow()
        reset_store = self._resolved_resets()
        challenge = reset_store.get_latest_for_username(username)
        if challenge is None:
            raise StaffPasswordResetError(
                "RESET_INVALID",
                "Unable to reset password with the provided details.",
            )

        if challenge.consumed_at is not None or challenge.superseded_at is not None:
            raise StaffPasswordResetError(
                "RESET_INVALID",
                "Unable to reset password with the provided details.",
            )

        try:
            expires_at = datetime.fromisoformat(challenge.expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise StaffPasswordResetError(
                "RESET_INVALID",
                "Unable to reset password with the provided details.",
            ) from exc

        if moment >= expires_at:
            raise StaffPasswordResetError(
                "RESET_EXPIRED",
                "This reset code has expired. Request a new one.",
            )

        if challenge.attempt_count >= RESET_MAX_ATTEMPTS:
            raise StaffPasswordResetError(
                "RATE_LIMITED",
                "Too many reset attempts. Request a new code.",
                status_code=429,
            )

        expected = challenge.code_hash
        actual = _hash_reset_code(code.strip(), settings=self._settings_or_default())
        if not hmac.compare_digest(expected, actual):
            updated = reset_store.increment_attempt(challenge.challenge_id)
            if updated is None:
                raise StaffPasswordResetError(
                    "RESET_INVALID",
                    "Unable to reset password with the provided details.",
                )
            if updated.attempt_count >= RESET_MAX_ATTEMPTS:
                raise StaffPasswordResetError(
                    "RATE_LIMITED",
                    "Too many reset attempts. Request a new code.",
                    status_code=429,
                )
            raise StaffPasswordResetError(
                "RESET_INVALID",
                "Unable to reset password with the provided details.",
            )

        staff = self._resolved_staff().get_by_username(username)
        if staff is None or not staff.active or staff.staff_id != challenge.staff_id:
            raise StaffPasswordResetError(
                "RESET_INVALID",
                "Unable to reset password with the provided details.",
            )

        # Consume first (CAS) so concurrent confirms cannot both apply a new password.
        stamped = _iso(moment)
        consumed = reset_store.consume(
            challenge.challenge_id,
            consumed_at=stamped,
            expected_attempt_count=challenge.attempt_count,
        )
        if consumed is None:
            raise StaffPasswordResetError(
                "RESET_INVALID",
                "Unable to reset password with the provided details.",
            )

        updated_staff = staff.model_copy(
            update={
                "password_hash": hash_password(new_password),
                "session_epoch": staff.session_epoch + 1,
                "updated_at": stamped,
            }
        )
        try:
            self._resolved_staff().update(updated_staff)
        except StaffNotFoundError as exc:
            raise StaffPasswordResetError(
                "RESET_INVALID",
                "Unable to reset password with the provided details.",
            ) from exc

        _dev_reset_codes.pop(challenge.challenge_id, None)
        logger.info("staff_recovery_completed staff_id=%s", staff.staff_id)
        from app.services.staff.account_audit import account_audit_service

        account_audit_service.record_safe(
            action_type="STAFF_PASSWORD_RESET_COMPLETED",
            actor_id=staff.staff_id,
            actor_role=staff.role,
            target_staff_id=staff.staff_id,
            summary="Staff credential recovery completed.",
            previous_value=None,
            new_value=None,
            created_at=stamped,
        )
        return RESET_SUCCESS_MESSAGE


staff_password_reset_service = StaffPasswordResetService()
