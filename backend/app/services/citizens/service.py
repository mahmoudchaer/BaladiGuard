"""Citizen account persistence, profile, and OTP session service (issues #169 / #170)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

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
from app.database.ticket_store import TicketHistoryPage
from app.schemas.citizen import (
    CitizenDataExportResponse,
    CitizenDeleteResponse,
    CitizenExportTicketSummary,
    CitizenProfileResponse,
    CitizenProfileUpdateRequest,
    CitizenPushDevice,
    CitizenPushDeviceRequest,
    CitizenTicketHistoryItem,
    CitizenTicketHistoryResponse,
    LegalAcceptance,
    LegalAcceptanceRequest,
    LegalAcceptanceSource,
    NotificationPreferences,
    StoredCitizenUser,
)
from app.schemas.citizen_auth import CitizenOtpVerifyResponse
from app.schemas.citizen_session import OtpPurpose, StoredCitizenOtpChallenge
from app.schemas.ticket import PreferredChannel, ReportContact
from app.services.legal.documents import CURRENT_LEGAL_VERSION, normalize_lang
from app.utils.phone import PhoneNormalizationError, normalize_phone

logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 5 * 60
OTP_MAX_ATTEMPTS = 5
LOGIN_OR_SIGNUP_PURPOSE: OtpPurpose = "LOGIN_OR_SIGNUP"
CHANGE_PHONE_PURPOSE: OtpPurpose = "CHANGE_PHONE"
GENERIC_OTP_MESSAGE = "If the request is valid, a verification code has been sent."
ANONYMIZED_PHONE_PREFIX = "ANON:"
CITIZEN_TICKET_HISTORY_DEFAULT_LIMIT = 20
CITIZEN_TICKET_HISTORY_MAX_LIMIT = 50

# Local/test-only plaintext OTP peek. Never returned by HTTP responses.
_dev_otp_codes: dict[str, str] = {}


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
        updated_user: StoredCitizenUser,
    ) -> StoredCitizenUser: ...

    def anonymize(
        self,
        *,
        user_id: str,
        current_phone: str,
        anonymized_user: StoredCitizenUser,
    ) -> StoredCitizenUser: ...


class TicketStorePort(Protocol):
    def list(self) -> list[Any]: ...

    def list_by_owner(
        self,
        owner_user_id: str,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> TicketHistoryPage: ...


class CitizenSessionStorePort(Protocol):
    def create(self, session: Any) -> Any: ...

    def get(self, session_id: str) -> Any: ...

    def revoke(
        self,
        session_id: str,
        *,
        revoked_at: str,
        reason: str,
    ) -> Any: ...

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

    def consume(
        self,
        challenge_id: str,
        *,
        consumed_at: str,
    ) -> StoredCitizenOtpChallenge | None: ...

    def increment_attempt(self, challenge_id: str) -> StoredCitizenOtpChallenge | None: ...


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
    """Verified-phone sessions may contribute; full name is optional (#270)."""
    return bool(user.active and user.phone_verified_at)


def legal_acceptance_required(user: StoredCitizenUser) -> bool:
    """True when acceptance is missing or does not match the current package."""
    acceptance = user.legal_acceptance
    if acceptance is None:
        return True
    version = CURRENT_LEGAL_VERSION
    return (
        acceptance.terms_version != version
        or acceptance.privacy_version != version
        or acceptance.acceptable_use_version != version
    )


def build_legal_acceptance(
    *,
    accepted_at: str,
    locale: str | None = None,
    source: LegalAcceptanceSource = "otp_verify",
) -> LegalAcceptance:
    version = CURRENT_LEGAL_VERSION
    return LegalAcceptance(
        termsVersion=version,
        privacyVersion=version,
        acceptableUseVersion=version,
        acceptedAt=accepted_at,
        locale=normalize_lang(locale) if locale else None,
        source=source,
    )


def anonymized_phone_for(user_id: str) -> str:
    return f"{ANONYMIZED_PHONE_PREFIX}{user_id}"


def is_anonymized_citizen(user: StoredCitizenUser) -> bool:
    return (not user.active) and user.phone.startswith(ANONYMIZED_PHONE_PREFIX)


def preferred_channel_from_ticket_updates(
    ticket_updates: str,
) -> PreferredChannel | None:
    """Map profile ``ticketUpdates`` preference to the singular ticket snapshot channel."""
    if ticket_updates == "SMS":
        return "SMS"
    if ticket_updates == "EMAIL":
        return "EMAIL"
    if ticket_updates == "BOTH":
        return "SMS"
    return None


def snapshot_contact_for_ticket(user: StoredCitizenUser) -> ReportContact:
    """Immutable submission-time contact snapshot from the authenticated profile (#173)."""
    return ReportContact(
        name=user.full_name.strip() if user.full_name else None,
        phone=user.phone,
        email=user.email,
        preferredChannel=preferred_channel_from_ticket_updates(
            user.notification_preferences.ticket_updates
        ),
    )


def to_profile_response(user: StoredCitizenUser) -> CitizenProfileResponse:
    preferences = user.notification_preferences
    if preferences.preference_version == 1:
        preferences = preferences.model_copy(
            update={
                "email_enabled": preferences.ticket_updates in {"EMAIL", "BOTH"},
                "whatsapp_enabled": preferences.ticket_updates in {"SMS", "BOTH"},
            }
        )
    return CitizenProfileResponse(
        userId=user.user_id,
        phone=user.phone,
        phoneVerifiedAt=user.phone_verified_at,
        fullName=user.full_name,
        email=user.email,
        notificationPreferences=preferences,
        pushAvailable=any(device.active for device in user.push_devices),
        publicNameVisible=user.public_name_visible,
        leaderboardOptIn=user.leaderboard_opt_in,
        active=user.active,
        contributionReady=is_contribution_ready(user),
        legalAcceptance=user.legal_acceptance,
        legalAcceptanceRequired=legal_acceptance_required(user),
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
        ticket_store: TicketStorePort | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._store = store
        self._session_store = session_store
        self._otp_store = otp_store
        self._ticket_store = ticket_store
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

    def _resolved_tickets(self) -> TicketStorePort:
        if self._ticket_store is not None:
            return self._ticket_store
        from app.database.store_factory import get_ticket_store

        return get_ticket_store()

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
            leaderboardOptIn=False,
            active=True,
            createdAt=stamped,
            updatedAt=stamped,
        )
        try:
            created = self._resolved_store().create(user)
        except PhoneClaimConflictError as exc:
            raise CitizenServiceError(
                "PHONE_UNAVAILABLE",
                "Unable to create citizen account for this phone number.",
                status_code=409,
            ) from exc
        from app.core.metrics import emit_metric

        emit_metric("CitizensRegistered")
        return created

    def get_by_id(self, user_id: str) -> StoredCitizenUser | None:
        return self._resolved_store().get(user_id)

    def get_by_phone(self, phone: str, region: str | None = None) -> StoredCitizenUser | None:
        try:
            canonical = normalize_phone(phone, region)
        except PhoneNormalizationError as exc:
            raise CitizenServiceError("VALIDATION_ERROR", str(exc)) from exc
        return self._resolved_store().get_by_phone(canonical)

    def issue_session(self, user_id: str, *, now: datetime | None = None) -> str:
        user = self._resolved_store().get(user_id)
        if user is None or not user.active:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)
        token, _session = issue_citizen_session(
            user_id,
            session_epoch=user.session_epoch,
            session_store=self._resolved_sessions(),  # type: ignore[arg-type]
            settings=self._settings_or_default(),
            now=now,
        )
        return token

    def peek_dev_otp_code(self, challenge_id: str) -> str | None:
        """Return plaintext OTP only in local/test/development environments."""
        env = self._settings_or_default().app_env.lower()
        if env not in {"local", "test", "development"}:
            return None
        return _dev_otp_codes.get(challenge_id)

    def clear_dev_otp_codes(self) -> None:
        _dev_otp_codes.clear()

    def invalidate_otp_challenge(self, challenge_id: str) -> None:
        """Mark a live challenge superseded (e.g. after delivery failure)."""
        store = self._resolved_otp()
        challenge = store.get(challenge_id.strip())
        if challenge is None or challenge.consumed_at or challenge.superseded_at:
            return
        store.save(challenge.model_copy(update={"superseded_at": _iso(_utcnow())}))
        _dev_otp_codes.pop(challenge_id, None)

    def request_otp(
        self,
        *,
        phone: str,
        region: str | None = None,
        purpose: OtpPurpose = LOGIN_OR_SIGNUP_PURPOSE,
        authenticated_user_id: str | None = None,
        now: datetime | None = None,
        code: str | None = None,
        verification_provider: Literal["local", "twilio"] = "local",
    ) -> tuple[str, int, str | None]:
        """Create a purpose-bound OTP challenge.

        Returns ``(challenge_id, expires_in_seconds, plaintext_code)``. The plaintext
        code must never be included in HTTP responses. It exists only for local
        hash-verified providers; Twilio Verify challenges return no local code.
        """
        if purpose == CHANGE_PHONE_PURPOSE:
            if not authenticated_user_id:
                raise CitizenServiceError(
                    "UNAUTHORIZED",
                    "Citizen authentication required.",
                    status_code=401,
                )
            challenge_id, otp_code = self.create_change_phone_challenge(
                user_id=authenticated_user_id,
                phone=phone,
                region=region,
                now=now,
                code=code,
                verification_provider=verification_provider,
            )
            return challenge_id, OTP_TTL_SECONDS, otp_code

        if purpose != LOGIN_OR_SIGNUP_PURPOSE:
            raise CitizenServiceError("VALIDATION_ERROR", "Unsupported OTP purpose.")

        try:
            canonical = normalize_phone(phone, region)
        except PhoneNormalizationError as exc:
            raise CitizenServiceError("VALIDATION_ERROR", str(exc)) from exc

        moment = now or _utcnow()
        expires = moment + timedelta(seconds=OTP_TTL_SECONDS)
        otp_code = (
            code or f"{secrets.randbelow(1_000_000):06d}"
            if verification_provider == "local"
            else None
        )
        challenge = StoredCitizenOtpChallenge(
            challengeId=f"chl_{secrets.token_hex(12)}",
            codeHash=(
                _hash_otp_code(otp_code, settings=self._settings_or_default())
                if otp_code is not None
                else None
            ),
            verificationProvider=verification_provider,
            phone=canonical,
            purpose=LOGIN_OR_SIGNUP_PURPOSE,
            userId=None,
            createdAt=_iso(moment),
            expiresAt=_iso(expires),
            ttl=int(expires.timestamp()),
        )
        self._resolved_otp().create(challenge)
        if otp_code is not None:
            self._remember_dev_otp(challenge.challenge_id, otp_code)
        # Never log the plaintext code. Phone is account-sensitive; keep logs generic.
        logger.info("Citizen OTP challenge created purpose=%s", purpose)
        return challenge.challenge_id, OTP_TTL_SECONDS, otp_code

    def create_change_phone_challenge(
        self,
        *,
        user_id: str,
        phone: str,
        region: str | None = None,
        now: datetime | None = None,
        code: str | None = None,
        verification_provider: Literal["local", "twilio"] = "local",
    ) -> tuple[str, str | None]:
        """Create a purpose-bound CHANGE_PHONE challenge.

        Returns ``(challenge_id, code)``. The plaintext code is never persisted and
        must not be logged.
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
        otp_code = (
            code or f"{secrets.randbelow(1_000_000):06d}"
            if verification_provider == "local"
            else None
        )
        challenge = StoredCitizenOtpChallenge(
            challengeId=f"chl_{secrets.token_hex(12)}",
            codeHash=(
                _hash_otp_code(otp_code, settings=self._settings_or_default())
                if otp_code is not None
                else None
            ),
            verificationProvider=verification_provider,
            phone=canonical,
            purpose=CHANGE_PHONE_PURPOSE,
            userId=user_id,
            createdAt=_iso(moment),
            expiresAt=_iso(expires),
            ttl=int(expires.timestamp()),
        )
        self._resolved_otp().create(challenge)
        if otp_code is not None:
            self._remember_dev_otp(challenge.challenge_id, otp_code)
        return challenge.challenge_id, otp_code

    def verify_otp(
        self,
        *,
        challenge_id: str,
        code: str,
        full_name: str | None = None,
        accept_legal: bool | None = None,
        legal_locale: str | None = None,
        authenticated_user_id: str | None = None,
        now: datetime | None = None,
    ) -> CitizenOtpVerifyResponse:
        """Atomically consume a challenge and establish an authenticated citizen session."""
        moment = now or _utcnow()
        challenge = self._resolved_otp().get(challenge_id.strip())
        if challenge is None:
            raise CitizenServiceError(
                "OTP_EXPIRED", "The verification challenge is no longer valid."
            )

        if challenge.purpose == LOGIN_OR_SIGNUP_PURPOSE:
            if accept_legal is not True:
                raise CitizenServiceError(
                    "LEGAL_ACCEPTANCE_REQUIRED",
                    "You must accept the current Terms, Privacy Policy, and "
                    "Acceptable Use Policy to continue.",
                )
            self._consume_otp_challenge(
                challenge=challenge,
                expected_purpose=LOGIN_OR_SIGNUP_PURPOSE,
                expected_user_id=None,
                expected_phone=challenge.phone,
                code=code,
                now=moment,
            )
            return self._complete_login_or_signup(
                phone=challenge.phone,
                full_name=full_name,
                legal_locale=legal_locale,
                now=moment,
            )

        if challenge.purpose == CHANGE_PHONE_PURPOSE:
            if not authenticated_user_id:
                raise CitizenServiceError(
                    "UNAUTHORIZED",
                    "Citizen authentication required.",
                    status_code=401,
                )
            if challenge.user_id != authenticated_user_id:
                raise CitizenServiceError(
                    "OTP_EXPIRED", "The verification challenge is no longer valid."
                )
            return self._complete_change_phone_verify(
                user_id=authenticated_user_id,
                phone=challenge.phone,
                challenge_id=challenge.challenge_id,
                code=code,
                now=moment,
            )

        raise CitizenServiceError("VALIDATION_ERROR", "Unsupported OTP purpose.")

    def logout_session(self, session_id: str, *, now: datetime | None = None) -> None:
        moment = now or _utcnow()
        revoked = self._resolved_sessions().revoke(
            session_id,
            revoked_at=_iso(moment),
            reason="logout",
        )
        if revoked is None:
            raise CitizenServiceError(
                "UNAUTHORIZED",
                "Citizen authentication required.",
                status_code=401,
            )

    def _remember_dev_otp(self, challenge_id: str, code: str) -> None:
        env = self._settings_or_default().app_env.lower()
        if env in {"local", "test", "development"}:
            _dev_otp_codes[challenge_id] = code

    def _complete_login_or_signup(
        self,
        *,
        phone: str,
        full_name: str | None,
        legal_locale: str | None,
        now: datetime,
    ) -> CitizenOtpVerifyResponse:
        store = self._resolved_store()
        user = store.get_by_phone(phone)
        if user is None:
            try:
                user = self.create_citizen(phone=phone, full_name=full_name, now=now)
            except CitizenServiceError as exc:
                if exc.code != "PHONE_UNAVAILABLE":
                    raise
                # Concurrent create: the winner already owns the phone.
                user = store.get_by_phone(phone)
                if user is None:
                    raise

        if not user.active:
            raise CitizenServiceError(
                "ACCOUNT_INACTIVE",
                "This account is inactive.",
                status_code=403,
            )

        stamped = _iso(now)
        updates: dict[str, Any] = {
            "legal_acceptance": build_legal_acceptance(
                accepted_at=stamped,
                locale=legal_locale,
                source="otp_verify",
            ),
            "updated_at": stamped,
        }
        # First-time name may be supplied on verify; ignore if the account already has one.
        if full_name and not _valid_full_name(user.full_name):
            updates["full_name"] = full_name.strip()

        updated = user.model_copy(update=updates)
        try:
            user = store.update(updated)
        except CitizenNotFoundError as exc:
            raise CitizenServiceError(
                "UNAUTHORIZED", "Citizen authentication required.", 401
            ) from exc

        token = self.issue_session(user.user_id, now=now)
        profile = to_profile_response(user)
        return CitizenOtpVerifyResponse.from_session(
            access_token=token,
            expires_in=CITIZEN_SESSION_TTL_SECONDS,
            profile=profile,
        )

    def _complete_change_phone_verify(
        self,
        *,
        user_id: str,
        phone: str,
        challenge_id: str,
        code: str,
        now: datetime,
    ) -> CitizenOtpVerifyResponse:
        store = self._resolved_store()
        user = store.get(user_id)
        if user is None or not user.active:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)

        stamped = _iso(now)
        projected = user.model_copy(
            update={
                "phone": phone,
                "phone_verified_at": stamped,
                "updated_at": stamped,
                "session_epoch": user.session_epoch + 1,
            }
        )
        prior_challenge = self._consume_change_phone_challenge(
            user_id=user_id,
            phone=phone,
            challenge_id=challenge_id,
            code=code,
            now=now,
        )
        try:
            updated = store.change_phone(
                user_id=user_id,
                old_phone=user.phone,
                updated_user=projected,
            )
        except PhoneClaimConflictError as exc:
            self._restore_change_phone_challenge(prior_challenge)
            raise CitizenServiceError(
                "PHONE_UNAVAILABLE",
                "Unable to update phone number.",
                status_code=409,
            ) from exc
        except (CitizenNotFoundError, CitizenPhoneMismatchError) as exc:
            self._restore_change_phone_challenge(prior_challenge)
            raise CitizenServiceError(
                "CONFLICT",
                "Unable to update phone number.",
                status_code=409,
            ) from exc

        self._resolved_sessions().revoke_all_for_user(
            user_id,
            revoked_at=stamped,
            reason="phone_change",
        )
        token = self.issue_session(updated.user_id, now=now)
        return CitizenOtpVerifyResponse.from_session(
            access_token=token,
            expires_in=CITIZEN_SESSION_TTL_SECONDS,
            profile=to_profile_response(updated),
        )

    def _consume_otp_challenge(
        self,
        *,
        challenge: StoredCitizenOtpChallenge,
        expected_purpose: OtpPurpose,
        expected_user_id: str | None,
        expected_phone: str,
        code: str,
        now: datetime,
    ) -> StoredCitizenOtpChallenge:
        """Consume a challenge; returns the pre-consume snapshot."""
        otp_store = self._resolved_otp()
        if (
            challenge.purpose != expected_purpose
            or challenge.user_id != expected_user_id
            or challenge.phone != expected_phone
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
                "RATE_LIMIT_EXCEEDED",
                "Too many verification attempts. Request a new code.",
                status_code=429,
            )

        if challenge.verification_provider == "twilio":
            from app.services.citizens.otp_delivery import (
                OtpVerificationError,
                check_twilio_verify,
            )

            try:
                approved = check_twilio_verify(
                    canonical_phone=challenge.phone,
                    code=code,
                    settings=self._settings_or_default(),
                )
            except OtpVerificationError as exc:
                if exc.category == "twilio_rate_limited":
                    raise CitizenServiceError(
                        "RATE_LIMIT_EXCEEDED",
                        "Too many verification attempts. Request a new code.",
                        status_code=429,
                    ) from exc
                raise CitizenServiceError(
                    "OTP_VERIFICATION_UNAVAILABLE",
                    "Could not verify the code. Try again in a moment.",
                    status_code=503,
                ) from exc
            if approved:
                return self._consume_approved_challenge(challenge, now=now)
        else:
            expected = challenge.code_hash
            actual = _hash_otp_code(code.strip(), settings=self._settings_or_default())
            if expected is not None and hmac.compare_digest(expected, actual):
                return self._consume_approved_challenge(challenge, now=now)

        # A rejected Verify check is equivalent to a local HMAC mismatch: apply
        # BaladiGuard's own limit before returning an account-neutral error.
        updated = otp_store.increment_attempt(challenge.challenge_id)
        if updated is None:
            raise CitizenServiceError(
                "OTP_EXPIRED", "The verification challenge is no longer valid."
            )
        if updated.attempt_count >= OTP_MAX_ATTEMPTS:
            raise CitizenServiceError(
                "RATE_LIMIT_EXCEEDED",
                "Too many verification attempts. Request a new code.",
                status_code=429,
            )
        raise CitizenServiceError("INVALID_OTP", "The verification code is incorrect.")

    def _consume_approved_challenge(
        self, challenge: StoredCitizenOtpChallenge, *, now: datetime
    ) -> StoredCitizenOtpChallenge:
        """Compare-and-set consume after local or Twilio verification approval."""
        otp_store = self._resolved_otp()
        consumed = otp_store.consume(
            challenge.challenge_id,
            consumed_at=_iso(now),
        )
        if consumed is None:
            raise CitizenServiceError(
                "OTP_EXPIRED", "The verification challenge is no longer valid."
            )
        _dev_otp_codes.pop(challenge.challenge_id, None)
        return challenge

    def get_profile(self, user_id: str) -> CitizenProfileResponse:
        user = self._resolved_store().get(user_id)
        if user is None:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)
        return to_profile_response(user)

    def register_push_device(
        self, user_id: str, payload: CitizenPushDeviceRequest, *, now: datetime | None = None
    ) -> CitizenProfileResponse:
        """Upsert one app-scoped device without disturbing a citizen's other devices."""
        store = self._resolved_store()
        user = store.get(user_id)
        if user is None or not user.active:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)
        stamped = _iso(now or datetime.now(UTC))
        device = CitizenPushDevice(**payload.model_dump(by_alias=True), lastSeenAt=stamped)
        devices = [item for item in user.push_devices if item.device_id != device.device_id]
        devices.append(device)
        stored = store.update(
            user.model_copy(update={"push_devices": devices, "updated_at": stamped})
        )
        return to_profile_response(stored)

    def unregister_push_device(
        self, user_id: str, device_id: str, *, now: datetime | None = None
    ) -> CitizenProfileResponse:
        store = self._resolved_store()
        user = store.get(user_id)
        if user is None or not user.active:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)
        stamped = _iso(now or datetime.now(UTC))
        devices = [item for item in user.push_devices if item.device_id != device_id]
        stored = store.update(
            user.model_copy(update={"push_devices": devices, "updated_at": stamped})
        )
        return to_profile_response(stored)

    def record_legal_acceptance(
        self,
        user_id: str,
        payload: LegalAcceptanceRequest,
        *,
        now: datetime | None = None,
    ) -> CitizenProfileResponse:
        """Record or renew acceptance of the current legal package (#321)."""
        if payload.accept_legal is not True:
            raise CitizenServiceError(
                "LEGAL_ACCEPTANCE_REQUIRED",
                "You must accept the current Terms, Privacy Policy, and "
                "Acceptable Use Policy to continue.",
            )
        store = self._resolved_store()
        user = store.get(user_id)
        if user is None or not user.active or is_anonymized_citizen(user):
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)

        moment = now or _utcnow()
        stamped = _iso(moment)
        source: LegalAcceptanceSource = (
            "reacceptance" if user.legal_acceptance is not None else "profile"
        )
        updated = user.model_copy(
            update={
                "legal_acceptance": build_legal_acceptance(
                    accepted_at=stamped,
                    locale=payload.locale,
                    source=source,
                ),
                "updated_at": stamped,
            }
        )
        try:
            stored = store.update(updated)
        except CitizenNotFoundError as exc:
            raise CitizenServiceError(
                "UNAUTHORIZED", "Citizen authentication required.", 401
            ) from exc
        return to_profile_response(stored)

    def export_account(
        self,
        user_id: str,
        *,
        now: datetime | None = None,
    ) -> CitizenDataExportResponse:
        """Return a privacy export for the authenticated citizen only."""
        user = self._resolved_store().get(user_id)
        if user is None or not user.active or is_anonymized_citizen(user):
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)

        moment = now or _utcnow()
        owned = [
            ticket
            for ticket in self._resolved_tickets().list()
            if getattr(ticket, "owner_user_id", None) == user_id
        ]
        owned.sort(key=lambda ticket: ticket.created_at, reverse=True)
        ticket_summaries = [
            CitizenExportTicketSummary(
                ticketId=ticket.ticket_id,
                ticketNumber=ticket.ticket_number,
                trackingCode=ticket.tracking_code,
                status=ticket.status,
                category=ticket.category,
                description=ticket.description,
                locationAddress=ticket.location.address_text,
                createdAt=ticket.created_at,
                updatedAt=ticket.updated_at,
            )
            for ticket in owned
        ]
        from app.services.privacy_request_audit import record_privacy_request

        record_privacy_request(
            action="citizen_export",
            subject_user_id=user_id,
            summary="Citizen self-service data export.",
            created_at=_iso(moment),
        )
        from app.services.rewards.service import rewards_service

        return CitizenDataExportResponse(
            exportedAt=_iso(moment),
            profile=to_profile_response(user),
            tickets=ticket_summaries,
            rewards=rewards_service.export_rewards(user_id),
        )

    def list_ticket_history(
        self,
        user_id: str,
        *,
        limit: int = CITIZEN_TICKET_HISTORY_DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> CitizenTicketHistoryResponse:
        """Return citizen-safe summaries for tickets owned by the authenticated user."""
        user = self._resolved_store().get(user_id)
        if user is None or not user.active or is_anonymized_citizen(user):
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)

        try:
            page = self._resolved_tickets().list_by_owner(
                user_id,
                limit=limit,
                cursor=cursor,
            )
        except ValueError as exc:
            raise CitizenServiceError(
                "VALIDATION_ERROR",
                "cursor is invalid.",
            ) from exc

        return CitizenTicketHistoryResponse(
            items=[
                CitizenTicketHistoryItem(
                    trackingCode=ticket.tracking_code,
                    status=ticket.status,
                    category=self._citizen_history_category(ticket),
                    locationAddress=ticket.location.address_text,
                    submittedAt=ticket.created_at,
                    canSubmitResolutionFeedback=(
                        ticket.status == "RESOLVED"
                        and ticket.owner_user_id == user_id
                        and ticket.resolution_feedback_status is None
                    ),
                    resolutionFeedbackStatus=ticket.resolution_feedback_status,
                )
                for ticket in page.items
            ],
            nextCursor=page.next_cursor,
            limit=limit,
        )

    def delete_account(
        self,
        user_id: str,
        *,
        now: datetime | None = None,
    ) -> CitizenDeleteResponse:
        """Anonymize citizen PII, release the phone claim, and revoke sessions.

        Municipal ticket rows keep ``ownerUserId`` and immutable contact snapshots.
        """
        store = self._resolved_store()
        user = store.get(user_id)
        if user is None:
            raise CitizenServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)

        moment = now or _utcnow()
        stamped = _iso(moment)

        if is_anonymized_citizen(user):
            self._resolved_sessions().revoke_all_for_user(
                user_id,
                revoked_at=stamped,
                reason="account_deletion",
            )
            return CitizenDeleteResponse(status="deleted", userId=user_id, deletedAt=stamped)

        anonymized = user.model_copy(
            update={
                "phone": anonymized_phone_for(user_id),
                "full_name": None,
                "email": None,
                "notification_preferences": NotificationPreferences(),
                "push_devices": [],
                "public_name_visible": False,
                "leaderboard_opt_in": False,
                "legal_acceptance": None,
                "active": False,
                "session_epoch": user.session_epoch + 1,
                "updated_at": stamped,
            }
        )
        try:
            store.anonymize(
                user_id=user_id,
                current_phone=user.phone,
                anonymized_user=anonymized,
            )
        except CitizenNotFoundError as exc:
            raise CitizenServiceError(
                "UNAUTHORIZED", "Citizen authentication required.", 401
            ) from exc
        except CitizenPhoneMismatchError as exc:
            raise CitizenServiceError(
                "CONFLICT",
                "Unable to delete account.",
                status_code=409,
            ) from exc

        self._resolved_sessions().revoke_all_for_user(
            user_id,
            revoked_at=stamped,
            reason="account_deletion",
        )
        from app.services.privacy_request_audit import record_privacy_request

        record_privacy_request(
            action="citizen_delete",
            subject_user_id=user_id,
            summary="Citizen self-service account anonymization.",
            created_at=stamped,
        )
        from app.services.rewards.service import rewards_service

        rewards_service.withdraw_public(user_id, now=moment)
        logger.info("Citizen account anonymized user_id=%s", user_id)
        return CitizenDeleteResponse(status="deleted", userId=user_id, deletedAt=stamped)

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

        updated = self._project_profile_update(user, payload, stamped=_iso(moment))
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

        from app.services.rewards.service import rewards_service

        rewards_service.refresh_public_eligibility(stored.user_id)
        return to_profile_response(stored)

    def _project_profile_update(
        self,
        user: StoredCitizenUser,
        payload: CitizenProfileUpdateRequest,
        *,
        stamped: str,
    ) -> StoredCitizenUser:
        """Build the post-update citizen record without mutating storage."""
        fields_set = payload.model_fields_set
        updates: dict[str, Any] = {"updated_at": stamped}

        if "full_name" in fields_set:
            updates["full_name"] = payload.full_name

        if "email" in fields_set:
            updates["email"] = payload.email

        if "public_name_visible" in fields_set and payload.public_name_visible is not None:
            updates["public_name_visible"] = payload.public_name_visible

        if "leaderboard_opt_in" in fields_set and payload.leaderboard_opt_in is not None:
            updates["leaderboard_opt_in"] = payload.leaderboard_opt_in

        # Empty/missing names cannot be published (#270).
        next_full_name = updates["full_name"] if "full_name" in updates else user.full_name
        if not _valid_full_name(next_full_name):
            updates["public_name_visible"] = False

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
            for field in (
                "push_enabled",
                "email_enabled",
                "whatsapp_enabled",
                "report_created",
                "status_changes",
                "work_updates",
                "resolution_updates",
                "action_requests",
            ):
                value = getattr(pref_update, field)
                if field in pref_update.model_fields_set and value is not None:
                    setattr(prefs, field, value)

            # Keep the legacy aggregate readable by older clients during rollout.
            # SMS is deliberately not selected: ordinary phone updates now use WhatsApp.
            if prefs.email_enabled and prefs.whatsapp_enabled:
                prefs.ticket_updates = "BOTH"
            elif prefs.email_enabled:
                prefs.ticket_updates = "EMAIL"
            elif prefs.whatsapp_enabled:
                prefs.ticket_updates = "SMS"
            elif any(
                field in pref_update.model_fields_set
                for field in ("email_enabled", "whatsapp_enabled")
            ):
                prefs.ticket_updates = "NONE"
            if any(
                field in pref_update.model_fields_set
                for field in ("push_enabled", "email_enabled", "whatsapp_enabled")
            ):
                prefs.preference_version = 2
            updates["notification_preferences"] = prefs

        return user.model_copy(update=updates)

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
        # Validate every field in the request before consuming OTP or mutating claims.
        try:
            canonical = normalize_phone(phone, region)
        except PhoneNormalizationError as exc:
            raise CitizenServiceError("VALIDATION_ERROR", str(exc)) from exc

        if canonical == user.phone:
            raise CitizenServiceError(
                "VALIDATION_ERROR",
                "New phone must differ from the current phone.",
            )

        stamped = _iso(now)
        projected = self._project_profile_update(user, profile_payload, stamped=stamped)
        projected = projected.model_copy(
            update={
                "phone": canonical,
                "phone_verified_at": stamped,
                "updated_at": stamped,
                "session_epoch": user.session_epoch + 1,
                "push_devices": [],
            }
        )
        self._validate_notification_email_rules(projected)

        # Validate profile first, then consume OTP. If the claim transfer fails,
        # restore the pre-consume challenge so a valid code is not permanently burned.
        prior_challenge = self._consume_change_phone_challenge(
            user_id=user.user_id,
            phone=canonical,
            challenge_id=challenge_id,
            code=code,
            now=now,
        )

        try:
            updated = self._resolved_store().change_phone(
                user_id=user.user_id,
                old_phone=user.phone,
                updated_user=projected,
            )
        except PhoneClaimConflictError as exc:
            self._restore_change_phone_challenge(prior_challenge)
            raise CitizenServiceError(
                "PHONE_UNAVAILABLE",
                "Unable to update phone number.",
                status_code=409,
            ) from exc
        except (CitizenNotFoundError, CitizenPhoneMismatchError) as exc:
            self._restore_change_phone_challenge(prior_challenge)
            raise CitizenServiceError(
                "CONFLICT",
                "Unable to update phone number.",
                status_code=409,
            ) from exc

        # Best-effort per-session cleanup. Auth authority is sessionEpoch on the user.
        self._resolved_sessions().revoke_all_for_user(
            user.user_id,
            revoked_at=stamped,
            reason="phone_change",
        )
        logger.info(
            "Citizen phone claim transferred user_id=%s",
            user.user_id,
        )
        return to_profile_response(updated)

    def _consume_change_phone_challenge(
        self,
        *,
        user_id: str,
        phone: str,
        challenge_id: str,
        code: str,
        now: datetime,
    ) -> StoredCitizenOtpChallenge:
        """Consume the challenge and return the pre-consume snapshot for restore."""
        challenge = self._resolved_otp().get(challenge_id)
        if challenge is None:
            raise CitizenServiceError(
                "OTP_EXPIRED", "The verification challenge is no longer valid."
            )
        return self._consume_otp_challenge(
            challenge=challenge,
            expected_purpose=CHANGE_PHONE_PURPOSE,
            expected_user_id=user_id,
            expected_phone=phone,
            code=code,
            now=now,
        )

    def _restore_change_phone_challenge(self, prior: StoredCitizenOtpChallenge) -> None:
        """Undo a consume when the subsequent phone-claim transaction fails."""
        try:
            self._resolved_otp().save(prior)
        except Exception:
            logger.exception(
                "Failed to restore CHANGE_PHONE challenge after claim transfer failure "
                "challenge_id=%s",
                prior.challenge_id,
            )

    @staticmethod
    def _validate_notification_email_rules(user: StoredCitizenUser) -> None:
        ticket_updates = user.notification_preferences.ticket_updates
        if ticket_updates in {"EMAIL", "BOTH"} and user.email is None:
            raise CitizenServiceError(
                "VALIDATION_ERROR",
                "notificationPreferences.ticketUpdates EMAIL/BOTH requires a non-null email.",
            )

    @staticmethod
    def _citizen_history_category(ticket: Any) -> str | None:
        from app.schemas.stored_ticket import PENDING_CLASSIFICATION

        if ticket.final_category:
            return ticket.final_category
        if ticket.category and ticket.category != PENDING_CLASSIFICATION:
            return ticket.category
        return None


# Default singleton uses factory-resolved stores so memory/Dynamo stay equivalent.
citizen_service = CitizenService()

# Re-export helpers useful for tests without pulling OTP plaintext into API responses.
__all__ = [
    "ANONYMIZED_PHONE_PREFIX",
    "CITIZEN_SESSION_TTL_SECONDS",
    "CHANGE_PHONE_PURPOSE",
    "CITIZEN_TICKET_HISTORY_DEFAULT_LIMIT",
    "CITIZEN_TICKET_HISTORY_MAX_LIMIT",
    "GENERIC_OTP_MESSAGE",
    "LOGIN_OR_SIGNUP_PURPOSE",
    "OTP_MAX_ATTEMPTS",
    "OTP_TTL_SECONDS",
    "CitizenService",
    "CitizenServiceError",
    "anonymized_phone_for",
    "citizen_service",
    "hash_citizen_token",
    "is_anonymized_citizen",
    "is_contribution_ready",
    "legal_acceptance_required",
    "preferred_channel_from_ticket_updates",
    "snapshot_contact_for_ticket",
    "to_profile_response",
]
