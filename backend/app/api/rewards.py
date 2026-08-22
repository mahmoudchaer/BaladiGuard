"""Public and citizen contribution reward endpoints (issue #323)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.core.citizen_auth import CitizenDep
from app.core.errors import build_error_response, get_request_id
from app.schemas.citizen import CitizenProfileResponse
from app.schemas.rewards import (
    CitizenRewardsResponse,
    PublicLeaderboardResponse,
    RewardsRulesResponse,
    RewardsSettingsUpdateRequest,
)
from app.services.citizens.service import CitizenServiceError, citizen_service
from app.services.rewards.service import (
    LEADERBOARD_DEFAULT_LIMIT,
    LEADERBOARD_MAX_LIMIT,
    RewardsServiceError,
    rewards_service,
)

router = APIRouter(tags=["rewards"])


def _rewards_error(request: Request, exc: RewardsServiceError) -> JSONResponse:
    return build_error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        status_code=exc.status_code,
    )


def _citizen_error(request: Request, exc: CitizenServiceError) -> JSONResponse:
    response = build_error_response(
        code=exc.code,
        message=exc.message,
        request_id=get_request_id(request),
        status_code=exc.status_code,
    )
    if exc.status_code == 401:
        response.headers["WWW-Authenticate"] = "Bearer"
    return response


@router.get("/v1/rewards/rules", response_model=RewardsRulesResponse)
def get_reward_rules() -> RewardsRulesResponse:
    return rewards_service.rules()


@router.get("/v1/rewards/leaderboard", response_model=PublicLeaderboardResponse)
def get_public_leaderboard(
    request: Request,
    period: str = Query(default="all-time"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=LEADERBOARD_DEFAULT_LIMIT, ge=1, le=LEADERBOARD_MAX_LIMIT),
) -> PublicLeaderboardResponse | JSONResponse:
    try:
        return rewards_service.public_leaderboard(period=period, cursor=cursor, limit=limit)
    except RewardsServiceError as exc:
        return _rewards_error(request, exc)


@router.get("/v1/citizen/me/rewards", response_model=CitizenRewardsResponse)
def get_my_rewards(
    request: Request,
    principal: CitizenDep,
) -> CitizenRewardsResponse | JSONResponse:
    try:
        return rewards_service.get_citizen_rewards(principal.user_id)
    except RewardsServiceError as exc:
        return _rewards_error(request, exc)


@router.patch("/v1/citizen/me/rewards-settings", response_model=CitizenProfileResponse)
def patch_my_rewards_settings(
    payload: RewardsSettingsUpdateRequest,
    request: Request,
    principal: CitizenDep,
) -> CitizenProfileResponse | JSONResponse:
    try:
        from app.schemas.citizen import CitizenProfileUpdateRequest

        return citizen_service.update_profile(
            principal.user_id,
            CitizenProfileUpdateRequest(leaderboardOptIn=payload.leaderboard_opt_in),
        )
    except CitizenServiceError as exc:
        return _citizen_error(request, exc)
