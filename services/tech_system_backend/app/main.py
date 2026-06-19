from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from its.event_log.integration import install_event_log
from its.observability import install_observability
from its.tech_system.auth.router import router as auth_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title="ITS Tech System Backend",
        description="Technical services API for Intelligent Trading Strategies",
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
    install_observability(app, service_name="tech-system-backend")
    install_event_log(app, service_name="tech-system-backend")

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router, prefix=API_PREFIX, tags=["Auth"])
    return app
