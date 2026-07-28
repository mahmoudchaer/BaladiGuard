"""Shared FastAPI dependencies.

Issue #72 replaces ``require_staff_actor`` with real Bearer-token staff auth.
Staff-only routes should depend on ``StaffActorDep`` so that swap is localized.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends


def require_staff_actor() -> None:
    """Staff authorization integration point for issue #72.

    Currently a no-op placeholder so #141 can ship the department endpoint on
    main before #72 merges. After #72, this dependency (or its callers) should
    validate ``Authorization: Bearer <token>`` and reject with ``401 UNAUTHORIZED``.
    """
    return None


StaffActorDep = Annotated[None, Depends(require_staff_actor)]
