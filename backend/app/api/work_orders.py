"""Staff maintenance work-order HTTP API (issue #247)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.core.staff_auth import StaffDep
from app.schemas.work_order import (
    CancelWorkOrderRequest,
    CompleteWorkOrderRequest,
    CreateWorkOrderRequest,
    WorkOrderListResponse,
    WorkOrderResponse,
)
from app.schemas.workforce import AssignWorkforceRequest
from app.services.work_orders.reasons import OutcomeReasonError
from app.services.work_orders.service import WorkOrderError, work_order_service
from app.services.work_orders.transitions import InvalidWorkOrderTransitionError
from app.services.workforce.service import WorkforceError

router = APIRouter(prefix="/v1", tags=["work-orders"])


def _error(request: Request, exc: WorkOrderError) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        status_code=exc.status_code,
    )


def _map_known_errors(request: Request, exc: Exception) -> JSONResponse | None:
    if isinstance(exc, WorkOrderError):
        return _error(request, exc)
    if isinstance(exc, InvalidWorkOrderTransitionError):
        return build_error_response(
            code="INVALID_WORK_ORDER_TRANSITION",
            message=str(exc),
            request_id=get_request_id(request),
            status_code=400,
        )
    if isinstance(exc, OutcomeReasonError):
        return build_error_response(
            code=exc.code,
            message=str(exc),
            request_id=get_request_id(request),
            status_code=400,
        )
    if isinstance(exc, WorkforceError):
        return build_error_response(
            code=exc.code,
            message=exc.message,
            request_id=get_request_id(request),
            status_code=exc.status_code,
        )
    return None


@router.post("/tickets/{ticket_id}/work-orders", response_model=WorkOrderResponse)
def create_work_order(
    ticket_id: str,
    payload: CreateWorkOrderRequest,
    request: Request,
    principal: StaffDep,
) -> WorkOrderResponse | JSONResponse:
    try:
        created = work_order_service.create(ticket_id, payload, principal=principal)
        if created.created:
            return JSONResponse(
                status_code=201,
                content=created.model_dump(by_alias=True, exclude_none=False),
            )
        return created
    except Exception as exc:
        mapped = _map_known_errors(request, exc)
        if mapped is not None:
            return mapped
        raise


@router.get("/tickets/{ticket_id}/work-orders", response_model=WorkOrderListResponse)
def list_work_orders(
    ticket_id: str, request: Request, principal: StaffDep
) -> WorkOrderListResponse | JSONResponse:
    try:
        return work_order_service.list_for_ticket(ticket_id, principal=principal)
    except Exception as exc:
        mapped = _map_known_errors(request, exc)
        if mapped is not None:
            return mapped
        raise


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order(
    work_order_id: str, request: Request, principal: StaffDep
) -> WorkOrderResponse | JSONResponse:
    try:
        return work_order_service.get(work_order_id, principal=principal)
    except Exception as exc:
        mapped = _map_known_errors(request, exc)
        if mapped is not None:
            return mapped
        raise


@router.post("/work-orders/{work_order_id}/assign", response_model=WorkOrderResponse)
def assign_work_order(
    work_order_id: str,
    payload: AssignWorkforceRequest,
    request: Request,
    principal: StaffDep,
) -> WorkOrderResponse | JSONResponse:
    try:
        return work_order_service.assign(work_order_id, payload, principal=principal)
    except Exception as exc:
        mapped = _map_known_errors(request, exc)
        if mapped is not None:
            return mapped
        raise


@router.post("/work-orders/{work_order_id}/start", response_model=WorkOrderResponse)
def start_work_order(
    work_order_id: str, request: Request, principal: StaffDep
) -> WorkOrderResponse | JSONResponse:
    try:
        return work_order_service.start(work_order_id, principal=principal)
    except Exception as exc:
        mapped = _map_known_errors(request, exc)
        if mapped is not None:
            return mapped
        raise


@router.post("/work-orders/{work_order_id}/complete", response_model=WorkOrderResponse)
def complete_work_order(
    work_order_id: str,
    payload: CompleteWorkOrderRequest,
    request: Request,
    principal: StaffDep,
) -> WorkOrderResponse | JSONResponse:
    try:
        return work_order_service.complete(work_order_id, payload, principal=principal)
    except Exception as exc:
        mapped = _map_known_errors(request, exc)
        if mapped is not None:
            return mapped
        raise


@router.post("/work-orders/{work_order_id}/cancel", response_model=WorkOrderResponse)
def cancel_work_order(
    work_order_id: str,
    payload: CancelWorkOrderRequest,
    request: Request,
    principal: StaffDep,
) -> WorkOrderResponse | JSONResponse:
    try:
        return work_order_service.cancel(work_order_id, payload, principal=principal)
    except Exception as exc:
        mapped = _map_known_errors(request, exc)
        if mapped is not None:
            return mapped
        raise
