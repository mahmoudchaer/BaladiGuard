"""Verification of Firebase Phone Auth ID tokens at the server boundary."""

from __future__ import annotations

from typing import Any

from google.auth import exceptions as google_auth_exceptions
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token


class FirebasePhoneTokenError(ValueError):
    """Safe token-validation error; token details must never enter logs/responses."""


def verified_firebase_phone(*, token: str, project_id: str) -> str:
    """Return only the verified E.164 phone claim from a Firebase Phone Auth token."""
    try:
        claims: dict[str, Any] = id_token.verify_firebase_token(
            token,
            GoogleRequest(),
            audience=project_id,
        )
    except (google_auth_exceptions.GoogleAuthError, ValueError, TypeError) as exc:
        raise FirebasePhoneTokenError("Invalid Firebase authentication token.") from exc

    firebase = claims.get("firebase")
    phone = claims.get("phone_number")
    if (
        not isinstance(firebase, dict)
        or firebase.get("sign_in_provider") != "phone"
        or not isinstance(phone, str)
    ):
        raise FirebasePhoneTokenError("A Firebase phone authentication token is required.")
    return phone
