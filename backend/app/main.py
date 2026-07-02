from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.tickets import router as tickets_router
from app.core.config import get_settings
from app.core.errors import create_request_id, validation_exception_handler


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BaladiGuard API",
        version="0.1.0",
        description="BaladiGuard civic reporting backend API.",
    )

    origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = create_request_id()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.include_router(health_router)
    app.include_router(tickets_router)

    return app


app = create_app()
