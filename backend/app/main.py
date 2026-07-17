from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

import app.config  # noqa: F401 - load .env before other app modules
from app.api.health import router as health_router
from app.api.locations import router as locations_router
from app.api.tickets import router as tickets_router
from app.api.uploads import router as uploads_router
from app.core.errors import create_request_id, validation_exception_handler

LOCAL_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8081",
    "http://localhost:19006",
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="BaladiGuard API",
        version="0.1.0",
        description="BaladiGuard civic reporting backend API.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_CORS_ORIGINS,
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
    app.include_router(locations_router)
    app.include_router(uploads_router)

    return app


app = create_app()
