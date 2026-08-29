"""Staff workforce directory and workload HTTP API (issue #245)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.core.staff_auth import AdminStaffDep
from app.core.staff_auth import MunicipalStaffDep as StaffDep
from app.schemas.workforce import (
    TeamResponse,
    UpsertTeamRequest,
    UpsertWorkerRequest,
    WorkerResponse,
    WorkloadResponse,
)
from app.services.workforce.service import WorkforceError, workforce_service

router = APIRouter(prefix="/v1/workforce", tags=["workforce"])


def _error(request: Request, exc: WorkforceError) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        status_code=exc.status_code,
    )


@router.get("/workers", response_model=list[WorkerResponse])
def list_workers(
    principal: StaffDep,
    request: Request,
    municipality_id: str | None = Query(default=None, alias="municipalityId"),
) -> list[WorkerResponse] | JSONResponse:
    try:
        return workforce_service.list_workers(principal, municipality_id=municipality_id)
    except WorkforceError as exc:
        return _error(request, exc)


@router.post("/workers", response_model=WorkerResponse, status_code=201)
def create_worker(
    payload: UpsertWorkerRequest, request: Request, principal: AdminStaffDep
) -> WorkerResponse | JSONResponse:
    try:
        return workforce_service.create_worker(principal, payload)
    except WorkforceError as exc:
        return _error(request, exc)


@router.patch("/workers/{worker_id}", response_model=WorkerResponse)
def update_worker(
    worker_id: str, payload: UpsertWorkerRequest, request: Request, principal: AdminStaffDep
) -> WorkerResponse | JSONResponse:
    try:
        return workforce_service.update_worker(principal, worker_id, payload)
    except WorkforceError as exc:
        return _error(request, exc)


@router.post("/workers/{worker_id}/deactivate", response_model=WorkerResponse)
def deactivate_worker(
    worker_id: str, request: Request, principal: AdminStaffDep
) -> WorkerResponse | JSONResponse:
    try:
        return workforce_service.set_worker_active(principal, worker_id, active=False)
    except WorkforceError as exc:
        return _error(request, exc)


@router.post("/workers/{worker_id}/reactivate", response_model=WorkerResponse)
def reactivate_worker(
    worker_id: str, request: Request, principal: AdminStaffDep
) -> WorkerResponse | JSONResponse:
    try:
        return workforce_service.set_worker_active(principal, worker_id, active=True)
    except WorkforceError as exc:
        return _error(request, exc)


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(
    principal: StaffDep,
    request: Request,
    municipality_id: str | None = Query(default=None, alias="municipalityId"),
) -> list[TeamResponse] | JSONResponse:
    try:
        return workforce_service.list_teams(principal, municipality_id=municipality_id)
    except WorkforceError as exc:
        return _error(request, exc)


@router.post("/teams", response_model=TeamResponse, status_code=201)
def create_team(
    payload: UpsertTeamRequest, request: Request, principal: AdminStaffDep
) -> TeamResponse | JSONResponse:
    try:
        return workforce_service.create_team(principal, payload)
    except WorkforceError as exc:
        return _error(request, exc)


@router.patch("/teams/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: str, payload: UpsertTeamRequest, request: Request, principal: AdminStaffDep
) -> TeamResponse | JSONResponse:
    try:
        return workforce_service.update_team(principal, team_id, payload)
    except WorkforceError as exc:
        return _error(request, exc)


@router.post("/teams/{team_id}/deactivate", response_model=TeamResponse)
def deactivate_team(
    team_id: str, request: Request, principal: AdminStaffDep
) -> TeamResponse | JSONResponse:
    try:
        return workforce_service.set_team_active(principal, team_id, active=False)
    except WorkforceError as exc:
        return _error(request, exc)


@router.post("/teams/{team_id}/reactivate", response_model=TeamResponse)
def reactivate_team(
    team_id: str, request: Request, principal: AdminStaffDep
) -> TeamResponse | JSONResponse:
    try:
        return workforce_service.set_team_active(principal, team_id, active=True)
    except WorkforceError as exc:
        return _error(request, exc)


@router.get("/workload", response_model=WorkloadResponse)
def get_workload(
    principal: StaffDep,
    request: Request,
    municipality_id: str | None = Query(default=None, alias="municipalityId"),
) -> WorkloadResponse | JSONResponse:
    try:
        return workforce_service.workload(principal, municipality_id=municipality_id)
    except WorkforceError as exc:
        return _error(request, exc)
