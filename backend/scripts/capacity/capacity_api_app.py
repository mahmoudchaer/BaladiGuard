"""Uvicorn entry for staging-equivalent capacity runs (local only).

Provides a development-only bootstrap endpoint so the harness can obtain a
contribution-ready synthetic citizen without SMS. Refuses to register that
route when APP_ENV is production/staging.

Also installs a process-local fake S3 put_object (unless CAPACITY_USE_REAL_S3=1)
so photo upload latency is measured without writing real buckets, and stubs AI
classification so queue completion is deterministic without Bedrock spend.
"""

from __future__ import annotations

import os
import time
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

# Importing app.main triggers settings load / env.
from app.main import app
from app.schemas.classification import ClassificationInputs, ClassificationResult
from app.schemas.cleaning import CleaningResult
from app.services.citizens.service import citizen_service
from app.services.complaints.ticket_service import ticket_service
from app.services.uploads.photo_upload_service import photo_upload_service


class _BootstrapRequest(BaseModel):
    runKey: str = Field(min_length=1, max_length=64)


class FakeS3Client:
    def __init__(self) -> None:
        self.put_object_calls: list[dict] = []

    def put_object(self, **kwargs):
        self.put_object_calls.append(kwargs)
        return {"ETag": '"capacity-fake"'}


def _stub_classify(description: str, *, image_object_key: str | None = None, **_: object):
    del image_object_key
    return ClassificationResult(
        category="road_damage",
        explanation="Capacity harness stub classification.",
        usedInputs=ClassificationInputs(description=bool(description), image=False),
    )


def _stub_clean(description: str, **_: object) -> CleaningResult:
    return CleaningResult(cleanedDescription=description, usedFallback=False)


if os.environ.get("CAPACITY_USE_REAL_S3") != "1":
    photo_upload_service._s3_client = FakeS3Client()  # noqa: SLF001 - capacity harness injection

# Deterministic AI terminal status without Bedrock (cost-safe capacity).
ticket_service._classifier = _stub_classify  # noqa: SLF001
ticket_service._description_cleaner = _stub_clean  # noqa: SLF001

router = APIRouter(prefix="/v1/capacity", tags=["capacity-local"])


@router.post("/bootstrap-citizen")
def bootstrap_citizen(payload: _BootstrapRequest) -> dict:
    """Local capacity helper — disabled outside development/local/test."""
    from app.config import get_settings

    settings = get_settings()
    env = (settings.app_env or "").strip().lower()
    if env in {"production", "prod", "staging"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not found")

    # Lebanese mobiles: +9617X + 6 digits (e.g. +96170123456).
    serial = (abs(hash(payload.runKey)) + int(time.time())) % 1_000_000
    phone = f"+96170{serial:06d}"
    full_name = "Capacity Test Citizen"
    email = f"capacitytest+{uuid4().hex[:10]}@example.com"
    user = citizen_service.get_by_phone(phone)
    if user is None:
        user = citizen_service.create_citizen(phone=phone, full_name=full_name, email=email)
    token = citizen_service.issue_session(user.user_id)
    return {
        "accessToken": token,
        "phone": phone,
        "userId": user.user_id,
        "runKey": payload.runKey,
    }


app.include_router(router)
