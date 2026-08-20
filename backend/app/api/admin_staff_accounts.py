"""Administrator-only staff-account HTTP API (issue #236)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.core.staff_auth import AdminStaffDep
from app.database.store_factory import get_staff_store
from app.schemas.admin_staff_accounts import (
    CreateStaffAccountRequest,
    StaffAccountResponse,
    UpdateStaffAccountRequest,
)
from app.services.staff.admin_accounts import StaffAccountAdminError, staff_account_admin_service

router = APIRouter(prefix="/v1/admin/staff-accounts", tags=["administrator-staff-accounts"])


def _error(request: Request, exc: StaffAccountAdminError) -> JSONResponse:
    message = exc.message
    if message == "Staff account not found.":
        return build_error_response(
            code="STAFF_ACCOUNT_NOT_FOUND",
            message=message,
            request_id=get_request_id(request),
            status_code=404,
        )
    if message == "Username is already in use.":
        return build_error_response(
            code="STAFF_USERNAME_CONFLICT",
            message=message,
            request_id=get_request_id(request),
            status_code=409,
        )
    return build_error_response(
        code="VALIDATION_ERROR",
        message=message,
        request_id=get_request_id(request),
        status_code=400,
    )


@router.get("", response_model=list[StaffAccountResponse])
def list_staff_accounts(principal: AdminStaffDep) -> list[StaffAccountResponse]:
    users = [user for user in get_staff_store().list() if user.role != "developer_operator"]
    return [StaffAccountResponse.from_user(user) for user in users]


@router.get("/{staff_id}", response_model=StaffAccountResponse)
def get_staff_account(
    staff_id: str, request: Request, principal: AdminStaffDep
) -> StaffAccountResponse | JSONResponse:
    user = get_staff_store().get(staff_id)
    if user is None or user.role == "developer_operator":
        return build_error_response(
            code="STAFF_ACCOUNT_NOT_FOUND",
            message="Staff account not found.",
            request_id=get_request_id(request),
            status_code=404,
        )
    return StaffAccountResponse.from_user(user)


@router.post("", response_model=StaffAccountResponse, status_code=201)
def create_staff_account(
    payload: CreateStaffAccountRequest, request: Request, principal: AdminStaffDep
) -> StaffAccountResponse | JSONResponse:
    try:
        user = staff_account_admin_service.create_staff(principal, **payload.model_dump())
    except StaffAccountAdminError as exc:
        return _error(request, exc)
    return StaffAccountResponse.from_user(user)


@router.patch("/{staff_id}", response_model=StaffAccountResponse)
def update_staff_account(
    staff_id: str, payload: UpdateStaffAccountRequest, request: Request, principal: AdminStaffDep
) -> StaffAccountResponse | JSONResponse:
    fields = payload.model_fields_set
    if not fields:
        return build_error_response(
            code="VALIDATION_ERROR",
            message="At least one updatable field is required.",
            request_id=get_request_id(request),
            status_code=400,
        )
    try:
        if "role" in fields:
            user = staff_account_admin_service.change_role(
                principal,
                staff_id=staff_id,
                role=payload.role,
                municipality_id=payload.municipality_id,
                department_ids=payload.department_ids,
            )
        else:
            existing = get_staff_store().get(staff_id)
            if existing is None:
                return build_error_response(
                    code="STAFF_ACCOUNT_NOT_FOUND",
                    message="Staff account not found.",
                    request_id=get_request_id(request),
                    status_code=404,
                )
            user = staff_account_admin_service.change_scope(
                principal,
                staff_id=staff_id,
                municipality_id=(
                    payload.municipality_id
                    if "municipality_id" in fields
                    else existing.municipality_id
                ),
                department_ids=(
                    payload.department_ids
                    if "department_ids" in fields
                    else existing.department_ids
                ),
            )
    except StaffAccountAdminError as exc:
        return _error(request, exc)
    return StaffAccountResponse.from_user(user)


@router.post("/{staff_id}/deactivate", response_model=StaffAccountResponse)
def deactivate_staff_account(
    staff_id: str, request: Request, principal: AdminStaffDep
) -> StaffAccountResponse | JSONResponse:
    try:
        user = staff_account_admin_service.set_active(principal, staff_id=staff_id, active=False)
    except StaffAccountAdminError as exc:
        return _error(request, exc)
    return StaffAccountResponse.from_user(user)


@router.post("/{staff_id}/reactivate", response_model=StaffAccountResponse)
def reactivate_staff_account(
    staff_id: str, request: Request, principal: AdminStaffDep
) -> StaffAccountResponse | JSONResponse:
    try:
        user = staff_account_admin_service.set_active(principal, staff_id=staff_id, active=True)
    except StaffAccountAdminError as exc:
        return _error(request, exc)
    return StaffAccountResponse.from_user(user)
