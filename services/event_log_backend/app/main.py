from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from its.event_log.integration import install_event_log
from its.event_log.router import router as event_log_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title="ITS Event Log Backend",
        description="Append-only user action audit log API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_event_log(app, service_name="event-log-backend")

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(event_log_router, prefix=API_PREFIX)
    return app

