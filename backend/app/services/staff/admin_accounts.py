"""Administrator staff-account mutations with safe audit logging (issue #181).

These helpers are the Sprint 6 account-management surface for audit purposes.
They enforce administrator role at the service boundary so future HTTP routes
can thin-wrap them with ``AdminStaffDep``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

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


def _guard_municipality_admin_scope(
    actor: StaffPrincipal, *, target_role: str | None = None
) -> None:
    if actor.role != "administrator":
        raise StaffAccountAdminError("Only administrators may manage staff accounts.")
    if target_role == "developer_operator":
        raise StaffAccountAdminError(
            "Municipality administrators cannot create or assign developer-operator access."
        )
    if target_role == "administrator":
        raise StaffAccountAdminError(
            "Municipality administrators cannot create or promote other administrators."
        )


def _require_admin(actor: StaffPrincipal) -> None:
    _guard_municipality_admin_scope(actor)


NOT_FOUND_MESSAGE = "Staff account not found."


def _reject_operator_target(user: StoredStaffUser) -> None:
    if user.role == "developer_operator":
        raise StaffAccountAdminError(NOT_FOUND_MESSAGE)


def _require_managed_target(actor: StaffPrincipal, user: StoredStaffUser | None) -> StoredStaffUser:
    """Hide accounts outside the actor's municipality with the same not-found error."""
    if user is None:
        raise StaffAccountAdminError(NOT_FOUND_MESSAGE)
    _reject_operator_target(user)
    if not actor.municipality_id or user.municipality_id != actor.municipality_id:
        raise StaffAccountAdminError(NOT_FOUND_MESSAGE)
    return user


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

    def list_managed(self, actor: StaffPrincipal) -> list[StoredStaffUser]:
        _require_admin(actor)
        if not actor.municipality_id:
            return []
        return [
            user
            for user in self._store().list()
            if user.role != "developer_operator" and user.municipality_id == actor.municipality_id
        ]

    def get_managed(self, actor: StaffPrincipal, staff_id: str) -> StoredStaffUser:
        _require_admin(actor)
        return _require_managed_target(actor, self._store().get(staff_id))

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
        _guard_municipality_admin_scope(actor, target_role=role)
        if role != "municipal_staff":
            raise StaffAccountAdminError(
                "Municipality administrators may only create municipal staff accounts."
            )
        scoped_municipality = actor.municipality_id
        if not scoped_municipality:
            raise StaffAccountAdminError("Administrator municipality scope is required.")
        if municipality_id and municipality_id != scoped_municipality:
            raise StaffAccountAdminError("You cannot create staff for another municipality.")
        stamped = _iso_now()
        try:
            user = StoredStaffUser(
                staffId=staff_id or f"staff_{uuid4().hex[:12]}",
                username=username,
                name=name,
                email=email,
                passwordHash=hash_password(password),
                role=role,
                municipalityId=scoped_municipality,
                departmentIds=department_ids,
                active=True,
                sessionEpoch=0,
                createdAt=stamped,
                updatedAt=stamped,
            )
        except ValidationError as exc:
            raise StaffAccountAdminError(
                "Invalid staff role, municipality, or department scope."
            ) from exc
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
        user = _require_managed_target(actor, store.get(staff_id))
        if role == "developer_operator":
            raise StaffAccountAdminError(
                "Municipality administrators cannot create or assign developer-operator access."
            )

        previous = _snapshot(user)
        stamped = _iso_now()
        if role == "administrator":
            raise StaffAccountAdminError(
                "Municipality administrators cannot create or promote other administrators."
            )
        update = {
            "role": role,
            "municipality_id": actor.municipality_id,
            "department_ids": (
                department_ids if department_ids is not None else user.department_ids
            ),
            "updated_at": stamped,
        }
        del municipality_id
        try:
            updated = store.update(StoredStaffUser.model_validate({**user.model_dump(), **update}))
        except ValidationError as exc:
            raise StaffAccountAdminError(
                "Invalid staff role, municipality, or department scope."
            ) from exc
        except StaffNotFoundError as exc:
            raise StaffAccountAdminError(NOT_FOUND_MESSAGE) from exc

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
        user = _require_managed_target(actor, store.get(staff_id))
        if user.role == "administrator":
            raise StaffAccountAdminError(
                "Municipality administrator scope is fixed; provision a new administrator instead."
            )
        if municipality_id and municipality_id != actor.municipality_id:
            raise StaffAccountAdminError("You cannot move staff to another municipality.")
        scoped_municipality = actor.municipality_id
        if not scoped_municipality:
            raise StaffAccountAdminError("Administrator municipality scope is required.")

        previous = _snapshot(user)
        stamped = _iso_now()
        try:
            updated = store.update(
                StoredStaffUser.model_validate(
                    {
                        **user.model_dump(),
                        "municipality_id": scoped_municipality,
                        "department_ids": department_ids,
                        "updated_at": stamped,
                    }
                )
            )
        except ValidationError as exc:
            raise StaffAccountAdminError(
                "Invalid staff role, municipality, or department scope."
            ) from exc
        except StaffNotFoundError as exc:
            raise StaffAccountAdminError(NOT_FOUND_MESSAGE) from exc

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
        user = _require_managed_target(actor, store.get(staff_id))

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
            raise StaffAccountAdminError(NOT_FOUND_MESSAGE) from exc

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
