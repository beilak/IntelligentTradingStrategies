from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from its.authz.context import AuthContext
from its.authz.dependencies import get_auth_context
from its.authz.jwt import decode_access_context
from its.db.session import get_session
from its.event_log.integration import install_event_log
from its.execution.schemas import (
    OrderTicket,
    StopOrderTicket,
    StrategyAssignmentRequest,
    StrategyRunRequest,
)
from its.execution.service import ExecutionService
from its.tech_system.auth.security import AuthTokenError

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
        return await service.submit_order(account_id, ticket)

    @app.post(f"{API_PREFIX}/accounts/{{account_id}}/stop-orders")
    async def create_stop_order(
        account_id: str,
        ticket: StopOrderTicket,
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> dict[str, Any]:
        return await service.submit_stop_order(account_id, ticket)

    @app.get(f"{API_PREFIX}/market-data/last-price")
    async def last_price(
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
        instrument_id: str | None = None,
        figi: str | None = None,
    ) -> dict[str, Any]:
        return await service.get_last_price(instrument_id=instrument_id, figi=figi)

    @app.get(f"{API_PREFIX}/accounts/{{account_id}}/strategies")
    async def account_strategies(
        account_id: str,
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, Any]:
        return service.list_strategy_assignments(account_id, session)

    @app.put(f"{API_PREFIX}/accounts/{{account_id}}/strategies/{{strategy_name}}")
    async def assign_strategy(
        account_id: str,
        strategy_name: str,
        payload: StrategyAssignmentRequest,
        auth: Annotated[AuthContext, Depends(get_auth_context)],
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, Any]:
        return service.assign_strategy(
            account_id,
            strategy_name,
            payload,
            session,
            assigned_by_user_id=auth.user_id,
        )

    @app.delete(f"{API_PREFIX}/accounts/{{account_id}}/strategies/{{strategy_name}}")
    async def unassign_strategy(
        account_id: str,
        strategy_name: str,
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, Any]:
        return service.unassign_strategy(account_id, strategy_name, session)

    @app.post(f"{API_PREFIX}/accounts/{{account_id}}/strategies/{{strategy_name}}/runs")
    async def run_assigned_strategy(
        account_id: str,
        strategy_name: str,
        payload: StrategyRunRequest,
        http_request: Request,
        _auth: Annotated[AuthContext, Depends(get_auth_context)],
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, Any]:
        return await service.run_assigned_strategy(
            account_id,
            strategy_name,
            payload,
            session,
            authorization=http_request.headers.get("authorization"),
        )

    @app.websocket(f"{API_PREFIX}/ws/orderbook")
    async def orderbook_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            auth_payload = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=10,
            )
            if not isinstance(auth_payload, dict) or auth_payload.get("type") != "auth":
                await send_ws_error(websocket, "First message must be auth.")
                await websocket.close(code=1008)
                return

            token = str(auth_payload.get("access_token") or "")
            try:
                decode_access_context(token)
            except AuthTokenError:
                await send_ws_error(websocket, "Authentication token is invalid.")
                await websocket.close(code=1008)
                return

            instrument_id = optional_text(auth_payload.get("instrument_id"))
            figi = optional_text(auth_payload.get("figi"))
            if not instrument_id and not figi:
                await send_ws_error(websocket, "Pass instrument_id or figi.")
                await websocket.close(code=1008)
                return

            try:
                depth = int(auth_payload.get("depth") or 20)
            except (TypeError, ValueError):
                await send_ws_error(websocket, "Depth must be an integer.")
                await websocket.close(code=1008)
                return

            async for snapshot in service.stream_order_book(
                instrument_id=instrument_id,
                figi=figi,
                depth=depth,
            ):
                await websocket.send_json(snapshot)
        except WebSocketDisconnect:
            return
        except asyncio.TimeoutError:
            await send_ws_error(websocket, "Auth message timeout.")
            await websocket.close(code=1008)
        except Exception as error:
            await send_ws_error(websocket, str(error))
            await websocket.close(code=1011)

    return app


async def send_ws_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_json({"type": "error", "message": message})


def optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
