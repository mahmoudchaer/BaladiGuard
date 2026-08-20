"""Private developer-operator observability API (issue #320)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.core.errors import build_error_response, get_request_id
from app.core.staff_auth import DeveloperOperatorDep
from app.schemas.ops import AcknowledgeAlertRequest, OpsOverviewResponse
from app.services.observability.safe import (
    ALLOWED_ERROR_CATEGORIES,
    ALLOWED_JOB_TYPES,
    ALLOWED_SERVICES,
    ALLOWED_SEVERITIES,
    is_safe_municipality_id,
    parse_optional_allowlist,
    parse_time_range,
)
from app.services.observability.snapshot import (
    acknowledge_alert,
    all_runbooks,
    build_metrics,
    build_overview,
    list_alerts,
    list_errors,
    list_workers,
    replay_job,
)

router = APIRouter(prefix="/v1/ops", tags=["developer-ops"])


def _bad_request(request: Request, message: str) -> JSONResponse:
    return build_error_response(
        code="VALIDATION_ERROR",
        message=message,
        request_id=get_request_id(request),
        status_code=400,
    )


def _parse_filters(
    request: Request,
    *,
    range_value: str | None,
    service: str | None = None,
    severity: str | None = None,
    error_category: str | None = None,
    job_type: str | None = None,
    municipality_id: str | None = None,
):
    try:
        time_range = parse_time_range(range_value)
        service_value = parse_optional_allowlist(service, ALLOWED_SERVICES, field="service")
        severity_value = parse_optional_allowlist(severity, ALLOWED_SEVERITIES, field="severity")
        category_value = parse_optional_allowlist(
            error_category, ALLOWED_ERROR_CATEGORIES, field="errorCategory"
        )
        job_type_value = parse_optional_allowlist(job_type, ALLOWED_JOB_TYPES, field="jobType")
    except ValueError as exc:
        return None, _bad_request(request, str(exc))
    if not is_safe_municipality_id(municipality_id):
        return None, _bad_request(request, "municipalityId is not a valid identifier.")
    return (
        {
            "time_range": time_range,
            "service": service_value,
            "severity": severity_value,
            "error_category": category_value,
            "job_type": job_type_value,
            "municipality_id": municipality_id,
        },
        None,
    )


@router.get("/overview", response_model=OpsOverviewResponse)
def ops_overview(
    request: Request,
    principal: DeveloperOperatorDep,
    range: str = Query(default="1h"),
    service: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    municipalityId: str | None = Query(default=None),
):
    parsed, error = _parse_filters(
        request,
        range_value=range,
        service=service,
        severity=severity,
        municipality_id=municipalityId,
    )
    if error is not None:
        return error
    assert parsed is not None
    return build_overview(
        time_range=parsed["time_range"],
        service=parsed["service"],
        severity=parsed["severity"],
        municipality_id=parsed["municipality_id"],
    )


@router.get("/metrics")
def ops_metrics(
    request: Request,
    principal: DeveloperOperatorDep,
    range: str = Query(default="1h"),
):
    parsed, error = _parse_filters(request, range_value=range)
    if error is not None:
        return error
    assert parsed is not None
    return build_metrics(time_range=parsed["time_range"]).model_dump(by_alias=True)


@router.get("/alerts")
def ops_alerts(
    request: Request,
    principal: DeveloperOperatorDep,
    range: str = Query(default="1h"),
    severity: str | None = Query(default=None),
):
    parsed, error = _parse_filters(request, range_value=range, severity=severity)
    if error is not None:
        return error
    assert parsed is not None
    return {
        "items": [
            item.model_dump(by_alias=True)
            for item in list_alerts(
                time_range=parsed["time_range"],
                severity=parsed["severity"],
            )
        ]
    }


@router.post("/alerts/{alarm_name}/ack")
def ops_ack_alert(
    alarm_name: str,
    payload: AcknowledgeAlertRequest,
    request: Request,
    principal: DeveloperOperatorDep,
):
    try:
        record = acknowledge_alert(alarm_name, principal, note=payload.note)
    except ValueError as exc:
        return _bad_request(request, str(exc))
    return record.model_dump(by_alias=True)


@router.get("/workers")
def ops_workers(
    request: Request,
    principal: DeveloperOperatorDep,
    jobType: str | None = Query(default=None),
):
    parsed, error = _parse_filters(request, range_value="1h", job_type=jobType)
    if error is not None:
        return error
    assert parsed is not None
    return list_workers(job_type=parsed["job_type"])


@router.post("/workers/jobs/{job_id}/replay")
def ops_replay_job(job_id: str, request: Request, principal: DeveloperOperatorDep):
    try:
        result = replay_job(job_id, principal)
    except ValueError as exc:
        return _bad_request(request, str(exc))
    if not result.replayed:
        return build_error_response(
            code="JOB_NOT_REPLAYABLE",
            message="The job could not be replayed.",
            request_id=get_request_id(request),
            status_code=409,
        )
    return result.model_dump(by_alias=True)


@router.get("/errors")
def ops_errors(
    request: Request,
    principal: DeveloperOperatorDep,
    errorCategory: str | None = Query(default=None),
    service: str | None = Query(default=None),
):
    parsed, error = _parse_filters(
        request,
        range_value="1h",
        service=service,
        error_category=errorCategory,
    )
    if error is not None:
        return error
    assert parsed is not None
    return {
        "items": [
            item.model_dump(by_alias=True)
            for item in list_errors(
                category=parsed["error_category"],
                service=parsed["service"],
            )
        ]
    }


@router.get("/product")
def ops_product(
    request: Request,
    principal: DeveloperOperatorDep,
    range: str = Query(default="1h"),
    municipalityId: str | None = Query(default=None),
):
    parsed, error = _parse_filters(
        request,
        range_value=range,
        municipality_id=municipalityId,
    )
    if error is not None:
        return error
    assert parsed is not None
    overview = build_overview(
        time_range=parsed["time_range"],
        municipality_id=parsed["municipality_id"],
    )
    return overview.product.model_dump(by_alias=True)


@router.get("/runbooks")
def ops_runbooks(principal: DeveloperOperatorDep):
    return {"items": [item.model_dump(by_alias=True) for item in all_runbooks()]}
