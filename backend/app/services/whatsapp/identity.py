"""Trusted WhatsApp-channel citizen reconciliation (issue #296)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from app.schemas.citizen import StoredCitizenUser
from app.services.citizens.service import CitizenService, CitizenServiceError, citizen_service
from app.utils.phone import PhoneNormalizationError, normalize_phone

logger = logging.getLogger(__name__)

WHATSAPP_VERIFICATION_PROVENANCE = "whatsapp_cloud_api"


class InactiveCitizenError(RuntimeError):
    """Matching citizen exists but is inactive — do not create a replacement."""


@dataclass(frozen=True)
class ReconciledCitizen:
    user: StoredCitizenUser
    created: bool


def reconcile_whatsapp_sender(
    *,
    wa_id: str,
    citizen_svc: CitizenService | None = None,
) -> ReconciledCitizen:
    """Map a trusted WhatsApp sender id to a contribution-ready citizen.

    Identity comes only from the signed webhook sender id (normalized to E.164).
    Never trusts a phone typed into message text. Does not issue sessions/tokens.
    """
    service = citizen_svc or citizen_service
    try:
        # WhatsApp wa_id is typically digits without '+'; normalize_phone accepts that.
        canonical = normalize_phone(wa_id if wa_id.startswith("+") else f"+{wa_id}")
    except PhoneNormalizationError as exc:
        raise CitizenServiceError("VALIDATION_ERROR", "Invalid WhatsApp sender phone.") from exc

    existing = service.get_by_phone(canonical)
    if existing is not None:
        if not existing.active:
            logger.info(
                "WhatsApp reconcile blocked inactive citizen provenance=%s",
                WHATSAPP_VERIFICATION_PROVENANCE,
            )
            raise InactiveCitizenError("Citizen account is inactive.")
        return ReconciledCitizen(user=existing, created=False)

    try:
        created = service.create_citizen(phone=canonical, now=datetime.now(UTC))
    except CitizenServiceError as exc:
        if exc.code == "PHONE_UNAVAILABLE":
            # Concurrent first-message race: reload the winner.
            raced = service.get_by_phone(canonical)
            if raced is not None and raced.active:
                return ReconciledCitizen(user=raced, created=False)
            if raced is not None and not raced.active:
                raise InactiveCitizenError("Citizen account is inactive.") from exc
        raise

    logger.info(
        "WhatsApp reconcile created citizen provenance=%s",
        WHATSAPP_VERIFICATION_PROVENANCE,
    )
    return ReconciledCitizen(user=created, created=True)
