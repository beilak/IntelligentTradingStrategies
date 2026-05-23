from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from its.authz.context import AuthContext
from its.authz.dependencies import get_auth_context
from its.event_log.integration import install_event_log
from its.execution.schemas import OrderTicket, StopOrderTicket
from its.execution.service import ExecutionService

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title="ITS Execution Backend",
        description="Broker account and execution control API",
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
    install_event_log(app, service_name="execution-backend")

    service = ExecutionService()

    @app.get(f"{API_PREFIX}/health")
    async def health() -> dict[str, Any]:
        return service.health()

    @app.get(f"{API_PREFIX}/accounts")
    async def accounts(
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> dict[str, Any]:
        return await service.list_accounts()

    @app.get(f"{API_PREFIX}/accounts/{{account_id}}/overview")
    async def account_overview(
        account_id: str,
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
        operations_days: Annotated[int, Query(ge=1, le=365)] = 30,
    ) -> dict[str, Any]:
        return await service.get_account_overview(
            account_id,
            operations_days=operations_days,
        )

    @app.post(f"{API_PREFIX}/accounts/{{account_id}}/orders")
    async def create_order(
        account_id: str,
        ticket: OrderTicket,
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> dict[str, Any]:
        return service.create_order_stub(account_id, ticket)

    @app.post(f"{API_PREFIX}/accounts/{{account_id}}/stop-orders")
    async def create_stop_order(
        account_id: str,
        ticket: StopOrderTicket,
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> dict[str, Any]:
        return service.create_stop_order_stub(account_id, ticket)

    return app
