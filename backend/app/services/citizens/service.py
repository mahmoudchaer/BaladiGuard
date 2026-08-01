"""Citizen account persistence and profile service (issue #169)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.config import Settings, get_settings
from app.core.citizen_auth import (
    CITIZEN_SESSION_TTL_SECONDS,
    hash_citizen_token,
    issue_citizen_session,
)
from app.core.staff_auth import DEFAULT_SECRET_KEY
from app.database.citizen_store import (
    CitizenNotFoundError,
    CitizenPhoneMismatchError,
    PhoneClaimConflictError,
)
from app.schemas.citizen import (
    CitizenProfileResponse,
    CitizenProfileUpdateRequest,
    NotificationPreferences,
    StoredCitizenUser,
)
from app.schemas.citizen_session import StoredCitizenOtpChallenge
from app.utils.phone import PhoneNormalizationError, normalize_phone

logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 5 * 60
OTP_MAX_ATTEMPTS = 5
CHANGE_PHONE_PURPOSE = "CHANGE_PHONE"


class CitizenStorePort(Protocol):
    def create(self, user: StoredCitizenUser) -> StoredCitizenUser: ...

    def get(self, user_id: str) -> StoredCitizenUser | None: ...

    def get_by_phone(self, canonical_phone: str) -> StoredCitizenUser | None: ...

    def update(self, user: StoredCitizenUser) -> StoredCitizenUser: ...

    def change_phone(
        self,
        *,
        user_id: str,
        old_phone: str,
        new_phone: str,
        phone_verified_at: str,
        updated_at: str,
    ) -> StoredCitizenUser: ...


class CitizenSessionStorePort(Protocol):
    def create(self, session: Any) -> Any: ...

    def get(self, session_id: str) -> Any: ...

    def revoke_all_for_user(
        self,
        user_id: str,
        *,
        revoked_at: str,
        reason: str,
    ) -> int: ...


class CitizenOtpStorePort(Protocol):
    def create(self, challenge: StoredCitizenOtpChallenge) -> StoredCitizenOtpChallenge: ...

    def get(self, challenge_id: str) -> StoredCitizenOtpChallenge | None: ...

    def save(self, challenge: StoredCitizenOtpChallenge) -> StoredCitizenOtpChallenge: ...


class CitizenServiceError(Exception):
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


def _hash_otp_code(code: str, *, settings: Settings) -> str:
    return hmac.new(
        _secret_key(settings).encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _valid_full_name(full_name: str | None) -> bool:
    if full_name is None:
        return False
    trimmed = full_name.strip()
    return 1 <= len(trimmed) <= 120


def is_contribution_ready(user: StoredCitizenUser) -> bool:
    return bool(user.active and user.phone_verified_at and _valid_full_name(user.full_name))


def to_profile_response(user: StoredCitizenUser) -> CitizenProfileResponse:
    return CitizenProfileResponse(
        userId=user.user_id,
        phone=user.phone,
        phoneVerifiedAt=user.phone_verified_at,
        fullName=user.full_name,
        email=user.email,
        notificationPreferences=user.notification_preferences,
        publicNameVisible=user.public_name_visible,
        active=user.active,
        contributionReady=is_contribution_ready(user),
        createdAt=user.created_at,
        updatedAt=user.updated_at,
    )


class CitizenService:
    def __init__(
        self,
        *,
        store: CitizenStorePort | None = None,
        session_store: CitizenSessionStorePort | None = None,
        otp_store: CitizenOtpStorePort | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._store = store
        self._session_store = session_store
        self._otp_store = otp_store
        self._settings = settings

    def _resolved_store(self) -> CitizenStorePort:
        if self._store is not None:
            return self._store
        from app.database.store_factory import get_citizen_store

        return get_citizen_store()

    def _resolved_sessions(self) -> CitizenSessionStorePort:
        if self._session_store is not None:
            return self._session_store
        from app.database.store_factory import get_citizen_session_store

        return get_citizen_session_store()

    def _resolved_otp(self) -> CitizenOtpStorePort:
        if self._otp_store is not None:
            return self._otp_store
        from app.database.store_factory import get_citizen_otp_store

        return get_citizen_otp_store()

    def _settings_or_default(self) -> Settings:
        return self._settings or get_settings()

    def create_citizen(
        self,
        *,
        phone: str,
        region: str | None = None,
        full_name: str | None = None,
        email: str | None = None,
        now: datetime | None = None,
    ) -> StoredCitizenUser:
        try:
            canonical = normalize_phone(phone, region)
        except PhoneNormalizationError as exc:
            raise CitizenServiceError("VALIDATION_ERROR", str(exc)) from exc

        if full_name is not None and not _valid_full_name(full_name):
            raise CitizenServiceError(
                "VALIDATION_ERROR",
                "fullName must be 1–120 characters after trimming.",
            )

        moment = now or _utcnow()
        stamped = _iso(moment)
        user = StoredCitizenUser(
            userId=f"usr_{secrets.token_hex(12)}",
            phone=canonical,
            phoneVerifiedAt=stamped,
            fullName=full_name.strip() if full_name else None,
            email=email,
            notificationPreferences=NotificationPreferences(),
            publicNameVisible=False,
            active=True,
            createdAt=stamped,
            updatedAt=stamped,
        )
        try:
            return self._resolved_store().create(user)
        except PhoneClaimConflictError as exc:
            raise CitizenServiceError(
                "PHONE_UNAVAILABLE",
                "Unable to create citizen account for this phone number.",
                status_code=409,
            ) from exc

    def get_by_id(self, user_id: str) -> StoredCitizenUser | None:
        return self._resolved_store().get(user_id)

    def get_by_phone(self, phone: str, region: str | None = None) -> StoredCitizenUser | None:
        try:
            canonical = normalize_phone(phone, region)
        except PhoneNormalizationError as exc:
            raise CitizenServiceError("VALIDATION_ERROR", str(exc)) from exc
        return self._resolved_store().get_by_phone(canonical)

    def issue_session(self, user_id: str, *, now: datetime | None = None) -> str:
        token, _session = issue_citizen_session(
            user_id,
            session_store=self._resolved_sessions(),  # type: ignore[arg-type]
            settings=self._settings_or_default(),
            now=now,
        )
        return token

    def create_change_phone_challenge(
        self,
        *,
        user_id: str,
        phone: str,
        region: str | None = None,
        now: datetime | None = None,
        code: str | None = None,
    ) -> tuple[str, str]:
        """Create a purpose-bound CHANGE_PHONE challenge.

        Returns ``(challenge_id, code)``. The plaintext code is never persisted and
        must not be logged. Public OTP request/verify HTTP routes belong to #170;
        this method is the persistence foundation used by profile phone changes.
        """
        user = self._resolved_store().get(user_id)
        if user is None or not user.active:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)

        try:
            canonical = normalize_phone(phone, region)
        except PhoneNormalizationError as exc:
            raise CitizenServiceError("VALIDATION_ERROR", str(exc)) from exc

        if canonical == user.phone:
            raise CitizenServiceError(
                "VALIDATION_ERROR",
                "New phone must differ from the current phone.",
            )

        moment = now or _utcnow()
        expires = moment + timedelta(seconds=OTP_TTL_SECONDS)
        otp_code = code or f"{secrets.randbelow(1_000_000):06d}"
        challenge = StoredCitizenOtpChallenge(
            challengeId=f"chl_{secrets.token_hex(12)}",
            codeHash=_hash_otp_code(otp_code, settings=self._settings_or_default()),
            phone=canonical,
            purpose=CHANGE_PHONE_PURPOSE,
            userId=user_id,
            createdAt=_iso(moment),
            expiresAt=_iso(expires),
            ttl=int(expires.timestamp()),
        )
        self._resolved_otp().create(challenge)
        return challenge.challenge_id, otp_code

    def get_profile(self, user_id: str) -> CitizenProfileResponse:
        user = self._resolved_store().get(user_id)
        if user is None:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)
        return to_profile_response(user)

    def update_profile(
        self,
        user_id: str,
        payload: CitizenProfileUpdateRequest,
        *,
        now: datetime | None = None,
    ) -> CitizenProfileResponse:
        store = self._resolved_store()
        user = store.get(user_id)
        if user is None:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)

        moment = now or _utcnow()
        stamped = _iso(moment)
        fields_set = payload.model_fields_set

        if "phone" in fields_set and payload.phone is not None:
            return self._change_phone(
                user=user,
                phone=payload.phone,
                region=payload.region,
                challenge_id=payload.phone_change_challenge_id or "",
                code=payload.phone_change_code or "",
                profile_payload=payload,
                now=moment,
            )

        updates: dict[str, Any] = {"updated_at": stamped}

        if "full_name" in fields_set:
            updates["full_name"] = payload.full_name

        if "email" in fields_set:
            updates["email"] = payload.email

        if "public_name_visible" in fields_set and payload.public_name_visible is not None:
            updates["public_name_visible"] = payload.public_name_visible

        if (
            "notification_preferences" in fields_set
            and payload.notification_preferences is not None
        ):
            prefs = user.notification_preferences.model_copy(deep=True)
            pref_update = payload.notification_preferences
            if (
                "ticket_updates" in pref_update.model_fields_set
                and pref_update.ticket_updates is not None
            ):
                prefs.ticket_updates = pref_update.ticket_updates
            if (
                "announcements" in pref_update.model_fields_set
                and pref_update.announcements is not None
            ):
                prefs.announcements = pref_update.announcements
            updates["notification_preferences"] = prefs

        updated = user.model_copy(update=updates)
        self._validate_notification_email_rules(updated)

        try:
            stored = store.update(updated)
        except CitizenNotFoundError as exc:
            raise CitizenServiceError(
                "UNAUTHORIZED", "Citizen authentication required.", 401
            ) from exc
        except CitizenPhoneMismatchError as exc:
            raise CitizenServiceError(
                "CONFLICT",
                "Unable to update profile.",
                status_code=409,
            ) from exc

        return to_profile_response(stored)

    def _change_phone(
        self,
        *,
        user: StoredCitizenUser,
        phone: str,
        region: str | None,
        challenge_id: str,
        code: str,
        profile_payload: CitizenProfileUpdateRequest,
        now: datetime,
    ) -> CitizenProfileResponse:
        try:
            canonical = normalize_phone(phone, region)
        except PhoneNormalizationError as exc:
            raise CitizenServiceError("VALIDATION_ERROR", str(exc)) from exc

        self._consume_change_phone_challenge(
            user_id=user.user_id,
            phone=canonical,
            challenge_id=challenge_id,
            code=code,
            now=now,
        )

        stamped = _iso(now)
        try:
            updated = self._resolved_store().change_phone(
                user_id=user.user_id,
                old_phone=user.phone,
                new_phone=canonical,
                phone_verified_at=stamped,
                updated_at=stamped,
            )
        except PhoneClaimConflictError as exc:
            raise CitizenServiceError(
                "PHONE_UNAVAILABLE",
                "Unable to update phone number.",
                status_code=409,
            ) from exc
        except (CitizenNotFoundError, CitizenPhoneMismatchError) as exc:
            raise CitizenServiceError(
                "CONFLICT",
                "Unable to update phone number.",
                status_code=409,
            ) from exc

        # Phone change revokes all sessions for the account (including current).
        self._resolved_sessions().revoke_all_for_user(
            user.user_id,
            revoked_at=stamped,
            reason="phone_change",
        )
        logger.info(
            "Citizen phone claim transferred user_id=%s",
            user.user_id,
        )

        # Apply any remaining profile fields after the phone transfer.
        remaining_fields = profile_payload.model_fields_set - {
            "phone",
            "region",
            "phone_change_challenge_id",
            "phone_change_code",
        }
        if remaining_fields:
            follow_up = CitizenProfileUpdateRequest.model_validate(
                {
                    key: getattr(profile_payload, key)
                    for key in remaining_fields
                    if key
                    in {
                        "full_name",
                        "email",
                        "notification_preferences",
                        "public_name_visible",
                    }
                }
            )
            return self.update_profile(user.user_id, follow_up, now=now)

        return to_profile_response(updated)

    def _consume_change_phone_challenge(
        self,
        *,
        user_id: str,
        phone: str,
        challenge_id: str,
        code: str,
        now: datetime,
    ) -> None:
        otp_store = self._resolved_otp()
        challenge = otp_store.get(challenge_id)
        if challenge is None:
            raise CitizenServiceError(
                "OTP_EXPIRED", "The verification challenge is no longer valid."
            )

        if (
            challenge.purpose != CHANGE_PHONE_PURPOSE
            or challenge.user_id != user_id
            or challenge.phone != phone
            or challenge.consumed_at is not None
            or challenge.superseded_at is not None
        ):
            raise CitizenServiceError(
                "OTP_EXPIRED", "The verification challenge is no longer valid."
            )

        try:
            expires_at = datetime.fromisoformat(challenge.expires_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CitizenServiceError(
                "OTP_EXPIRED", "The verification challenge is no longer valid."
            ) from exc

        if now >= expires_at:
            raise CitizenServiceError(
                "OTP_EXPIRED", "The verification challenge is no longer valid."
            )

        if challenge.attempt_count >= OTP_MAX_ATTEMPTS:
            raise CitizenServiceError(
                "RATE_LIMITED",
                "Too many verification attempts. Request a new code.",
                status_code=429,
            )

        expected = challenge.code_hash
        actual = _hash_otp_code(code.strip(), settings=self._settings_or_default())
        if not hmac.compare_digest(expected, actual):
            updated = challenge.model_copy(update={"attempt_count": challenge.attempt_count + 1})
            otp_store.save(updated)
            if updated.attempt_count >= OTP_MAX_ATTEMPTS:
                raise CitizenServiceError(
                    "RATE_LIMITED",
                    "Too many verification attempts. Request a new code.",
                    status_code=429,
                )
            raise CitizenServiceError("INVALID_OTP", "The verification code is incorrect.")

        consumed = challenge.model_copy(
            update={
                "consumed_at": _iso(now),
                "attempt_count": challenge.attempt_count + 1,
            }
        )
        otp_store.save(consumed)

    @staticmethod
    def _validate_notification_email_rules(user: StoredCitizenUser) -> None:
        ticket_updates = user.notification_preferences.ticket_updates
        if ticket_updates in {"EMAIL", "BOTH"} and user.email is None:
            raise CitizenServiceError(
                "VALIDATION_ERROR",
                "notificationPreferences.ticketUpdates EMAIL/BOTH requires a non-null email.",
            )


# Default singleton uses factory-resolved stores so memory/Dynamo stay equivalent.
citizen_service = CitizenService()

# Re-export helpers useful for tests without pulling OTP plaintext into API responses.
__all__ = [
    "CITIZEN_SESSION_TTL_SECONDS",
    "CitizenService",
    "CitizenServiceError",
    "citizen_service",
    "hash_citizen_token",
    "is_contribution_ready",
    "to_profile_response",
]
