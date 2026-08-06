"""Administrator staff-account mutations with safe audit logging (issue #181).

These helpers are the Sprint 6 account-management surface for audit purposes.
They enforce administrator role at the service boundary so future HTTP routes
can thin-wrap them with ``AdminStaffDep``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.password_hashing import hash_password
from app.core.staff_auth import StaffPrincipal
from app.database.staff_store import StaffNotFoundError, StaffUsernameConflictError
from app.schemas.staff_user import StaffRole, StoredStaffUser
from app.services.audit.safe_values import staff_snapshot_for_audit
from app.services.staff.account_audit import account_audit_service


class StaffAccountAdminError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _require_admin(actor: StaffPrincipal) -> None:
    if actor.role != "administrator":
        raise StaffAccountAdminError("Only administrators may manage staff accounts.")


def _snapshot(user: StoredStaffUser) -> dict:
    return staff_snapshot_for_audit(
        staff_id=user.staff_id,
        username=user.username,
        name=user.name,
        role=user.role,
        municipality_id=user.municipality_id,
        department_ids=user.department_ids,
        active=user.active,
    )


class StaffAccountAdminService:
    def __init__(self, staff_store=None, audit=None) -> None:
        self._staff_store = staff_store
        self._audit = audit or account_audit_service

    def _store(self):
        if self._staff_store is not None:
            return self._staff_store
        from app.database.store_factory import get_staff_store

        return get_staff_store()

    def create_staff(
        self,
        actor: StaffPrincipal,
        *,
        username: str,
        name: str,
        email: str,
        password: str,
        role: StaffRole,
        municipality_id: str | None = None,
        department_ids: list[str] | None = None,
        staff_id: str | None = None,
    ) -> StoredStaffUser:
        _require_admin(actor)
        stamped = _iso_now()
        user = StoredStaffUser(
            staffId=staff_id or f"staff_{uuid4().hex[:12]}",
            username=username,
            name=name,
            email=email,
            passwordHash=hash_password(password),
            role=role,
            municipalityId=municipality_id,
            departmentIds=department_ids,
            active=True,
            sessionEpoch=0,
            createdAt=stamped,
            updatedAt=stamped,
        )
        try:
            created = self._store().create(user)
        except StaffUsernameConflictError as exc:
            raise StaffAccountAdminError("Username is already in use.") from exc

        self._audit.record_safe(
            action_type="STAFF_CREATED",
            actor=actor,
            target_staff_id=created.staff_id,
            summary=f"Staff account created for username {created.username}.",
            previous_value=None,
            new_value=_snapshot(created),
            created_at=stamped,
        )
        return created

    def change_role(
        self,
        actor: StaffPrincipal,
        *,
        staff_id: str,
        role: StaffRole,
        municipality_id: str | None = None,
        department_ids: list[str] | None = None,
    ) -> StoredStaffUser:
        _require_admin(actor)
        store = self._store()
        user = store.get(staff_id)
        if user is None:
            raise StaffAccountAdminError("Staff account not found.")

        previous = _snapshot(user)
        stamped = _iso_now()
        if role == "administrator":
            update = {
                "role": role,
                "municipality_id": None,
                "department_ids": None,
                "updated_at": stamped,
            }
        else:
            update = {
                "role": role,
                "municipality_id": (
                    municipality_id if municipality_id is not None else user.municipality_id
                ),
                "department_ids": (
                    department_ids if department_ids is not None else user.department_ids
                ),
                "updated_at": stamped,
            }
        try:
            updated = store.update(user.model_copy(update=update))
        except StaffNotFoundError as exc:
            raise StaffAccountAdminError("Staff account not found.") from exc

        self._audit.record_safe(
            action_type="STAFF_ROLE_CHANGED",
            actor=actor,
            target_staff_id=updated.staff_id,
            summary=f"Staff role changed to {updated.role}.",
            previous_value=previous,
            new_value=_snapshot(updated),
            created_at=stamped,
        )
        return updated

    def change_scope(
        self,
        actor: StaffPrincipal,
        *,
        staff_id: str,
        municipality_id: str | None,
        department_ids: list[str] | None,
    ) -> StoredStaffUser:
        _require_admin(actor)
        store = self._store()
        user = store.get(staff_id)
        if user is None:
            raise StaffAccountAdminError("Staff account not found.")
        if user.role == "administrator":
            raise StaffAccountAdminError(
                "Administrator accounts use global scope; change role before assigning scope."
            )

        previous = _snapshot(user)
        stamped = _iso_now()
        try:
            updated = store.update(
                user.model_copy(
                    update={
                        "municipality_id": municipality_id,
                        "department_ids": department_ids,
                        "updated_at": stamped,
                    }
                )
            )
        except StaffNotFoundError as exc:
            raise StaffAccountAdminError("Staff account not found.") from exc

        self._audit.record_safe(
            action_type="STAFF_SCOPE_CHANGED",
            actor=actor,
            target_staff_id=updated.staff_id,
            summary="Staff municipality/department scope updated.",
            previous_value=previous,
            new_value=_snapshot(updated),
            created_at=stamped,
        )
        return updated

    def set_active(
        self,
        actor: StaffPrincipal,
        *,
        staff_id: str,
        active: bool,
    ) -> StoredStaffUser:
        _require_admin(actor)
        store = self._store()
        user = store.get(staff_id)
        if user is None:
            raise StaffAccountAdminError("Staff account not found.")

        previous = _snapshot(user)
        stamped = _iso_now()
        update = {
            "active": active,
            "updated_at": stamped,
        }
        if not active:
            update["session_epoch"] = user.session_epoch + 1
        try:
            updated = store.update(user.model_copy(update=update))
        except StaffNotFoundError as exc:
            raise StaffAccountAdminError("Staff account not found.") from exc

        action = "STAFF_REACTIVATED" if active else "STAFF_DEACTIVATED"
        self._audit.record_safe(
            action_type=action,
            actor=actor,
            target_staff_id=updated.staff_id,
            summary=("Staff account reactivated." if active else "Staff account deactivated."),
            previous_value=previous,
            new_value=_snapshot(updated),
            created_at=stamped,
        )
        return updated


staff_account_admin_service = StaffAccountAdminService()
