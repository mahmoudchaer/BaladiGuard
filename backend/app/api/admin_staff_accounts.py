"""Administrator-only staff-account HTTP API (issue #236)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.core.staff_auth import AdminStaffDep, MunicipalStaffDep
from app.schemas.admin_staff_accounts import (
    CreateStaffAccountRequest,
    StaffAccountResponse,
    UpdateStaffAccountRequest,
)
from app.schemas.municipality import DepartmentListResponse, DepartmentResponse
from app.services.municipalities.departments import departments_for_municipality
from app.services.staff.admin_accounts import StaffAccountAdminError, staff_account_admin_service

router = APIRouter(prefix="/v1/admin/staff-accounts", tags=["administrator-staff-accounts"])
departments_router = APIRouter(prefix="/v1/staff", tags=["staff-departments"])


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


@departments_router.get("/departments", response_model=DepartmentListResponse)
def list_staff_departments(principal: MunicipalStaffDep) -> DepartmentListResponse:
    if not principal.municipality_id:
        return DepartmentListResponse(items=[])
    return DepartmentListResponse(
        items=[
            DepartmentResponse.from_stored(item)
            for item in departments_for_municipality(principal.municipality_id)
        ]
    )


@router.get("", response_model=list[StaffAccountResponse])
def list_staff_accounts(principal: AdminStaffDep) -> list[StaffAccountResponse]:
    return [
        StaffAccountResponse.from_user(user)
        for user in staff_account_admin_service.list_managed(principal)
    ]


@router.get("/{staff_id}", response_model=StaffAccountResponse)
def get_staff_account(
    staff_id: str, request: Request, principal: AdminStaffDep
) -> StaffAccountResponse | JSONResponse:
    try:
        user = staff_account_admin_service.get_managed(principal, staff_id)
    except StaffAccountAdminError as exc:
        return _error(request, exc)
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
        existing = staff_account_admin_service.get_managed(principal, staff_id)
        if "role" in fields:
            user = staff_account_admin_service.change_role(
                principal,
                staff_id=staff_id,
                role=payload.role,
                municipality_id=payload.municipality_id,
                department_ids=payload.department_ids,
            )
        else:
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
