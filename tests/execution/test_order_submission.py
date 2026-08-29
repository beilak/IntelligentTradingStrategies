from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from t_tech.invest import (
    ExchangeOrderType,
    OrderDirection,
    OrderExecutionReportStatus,
    OrderType,
    PriceType,
    PostOrderResponse,
    PostStopOrderResponse,
    StopOrderDirection,
    StopOrderExpirationType,
    StopOrderType,
    TimeInForceType,
    utils,
)

import its.execution.service as service_module
from its.execution.schemas import OrderTicket, StopOrderTicket
from its.execution.service import ExecutionService, normalize_client_order_id


def test_normalize_client_order_id_rejects_non_uuid() -> None:
    with pytest.raises(Exception, match="client_order_id"):
        normalize_client_order_id("order-123")


async def test_submit_limit_order_posts_to_tinvest(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeOrders:
        async def post_order(self, **kwargs):
            calls.append(kwargs)
            return PostOrderResponse(
                order_id=kwargs["order_id"],
                execution_report_status=(
                    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_NEW
                ),
                lots_requested=kwargs["quantity"],
                figi=kwargs["figi"],
                direction=kwargs["direction"],
                order_type=kwargs["order_type"],
            )

    class FakeAsyncClient:
        def __init__(self, token: str) -> None:
            self.token = token
            self.orders = FakeOrders()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setenv("EXECUTION_TINVEST_TOKEN", "token")
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1:Main")
    monkeypatch.setenv("EXECUTION_ORDER_SUBMISSION_MODE", "real")
    monkeypatch.setattr(service_module, "AsyncClient", FakeAsyncClient)

    service = ExecutionService()
    ticket = OrderTicket(
        instrument_id="uid-1",
        figi="figi-1",
        side="buy",
        order_type="limit",
        quantity=3,
        price=123.45,
        time_in_force="fill_or_kill",
    )

    response = await service.submit_order("acc-1", ticket)

    assert response["submission_mode"] == "real"
    assert response["submitted"] is True
    assert response["broker_order_id"] == response["id"]
    UUID(str(response["id"]))

    call = calls[0]
    assert call["account_id"] == "acc-1"
    assert call["instrument_id"] == "uid-1"
    assert call["figi"] == "figi-1"
    assert call["quantity"] == 3
    assert call["direction"] == OrderDirection.ORDER_DIRECTION_BUY
    assert call["order_type"] == OrderType.ORDER_TYPE_LIMIT
    assert call["time_in_force"] == TimeInForceType.TIME_IN_FORCE_FILL_OR_KILL
    assert call["price_type"] == PriceType.PRICE_TYPE_CURRENCY
    assert utils.quotation_to_decimal(call["price"]) == Decimal("123.45")


async def test_rejected_broker_response_is_not_marked_submitted(monkeypatch) -> None:
    class FakeOrders:
        async def post_order(self, **kwargs):
            return PostOrderResponse(
                order_id=kwargs["order_id"],
                execution_report_status=(
                    OrderExecutionReportStatus.EXECUTION_REPORT_STATUS_REJECTED
                ),
                message="Order rejected: insufficient funds",
            )

    class FakeAsyncClient:
        def __init__(self, _token: str) -> None:
            self.orders = FakeOrders()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setenv("EXECUTION_TINVEST_TOKEN", "token")
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    monkeypatch.setenv("EXECUTION_ORDER_SUBMISSION_MODE", "real")
    monkeypatch.setattr(service_module, "AsyncClient", FakeAsyncClient)

    response = await ExecutionService().submit_order(
        "acc-1",
        OrderTicket(
            instrument_id="uid-1",
            side="buy",
            order_type="market",
            quantity=1,
        ),
    )

    assert response["status"] == "EXECUTION_REPORT_STATUS_REJECTED"
    assert response["submitted"] is False
    assert response["message"] == "Order rejected: insufficient funds"


def test_broker_error_30083_is_human_readable() -> None:
    error = SimpleNamespace(
        details="30083",
        metadata=SimpleNamespace(
            message="`order_type` is invalid",
            tracking_id="tracking-1",
        ),
    )

    response = ExecutionService._broker_error(error)

    assert response.status_code == 502
    assert response.detail == {
        "message": (
            "T-Invest отклонил тип заявки (код 30083): выбранный тип "
            "недоступен для инструмента или текущего режима торгов."
        ),
        "broker_code": "30083",
        "broker_message": "`order_type` is invalid",
        "tracking_id": "tracking-1",
    }


async def test_submit_take_profit_stop_order_posts_to_tinvest(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    client_order_id = "c1b96f8f-0d4b-4b6e-b0ce-92038d90227a"

    class FakeStopOrders:
        async def post_stop_order(self, **kwargs):
            calls.append(kwargs)
            return PostStopOrderResponse(
                stop_order_id="stop-1",
                order_request_id=kwargs["order_id"],
            )

    class FakeAsyncClient:
        def __init__(self, token: str) -> None:
            self.token = token
            self.stop_orders = FakeStopOrders()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setenv("EXECUTION_TINVEST_TOKEN", "token")
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1:Main")
    monkeypatch.setenv("EXECUTION_ORDER_SUBMISSION_MODE", "real")
    monkeypatch.setattr(service_module, "AsyncClient", FakeAsyncClient)

    service = ExecutionService()
    ticket = StopOrderTicket(
        instrument_id="uid-1",
        figi="figi-1",
        side="sell",
        stop_order_type="take_profit",
        quantity=2,
        stop_price=130.0,
        limit_price=129.5,
        price_type="point",
        expire_at=datetime(2026, 5, 25, 12, 30),
        client_order_id=client_order_id,
    )

    response = await service.submit_stop_order("acc-1", ticket)

    assert response["submission_mode"] == "real"
    assert response["broker_order_id"] == "stop-1"

    call = calls[0]
    assert call["account_id"] == "acc-1"
    assert call["direction"] == StopOrderDirection.STOP_ORDER_DIRECTION_SELL
    assert call["stop_order_type"] == StopOrderType.STOP_ORDER_TYPE_TAKE_PROFIT
    assert call["expiration_type"] == (
        StopOrderExpirationType.STOP_ORDER_EXPIRATION_TYPE_GOOD_TILL_DATE
    )
    assert call["exchange_order_type"] == ExchangeOrderType.EXCHANGE_ORDER_TYPE_LIMIT
    assert call["price_type"] == PriceType.PRICE_TYPE_POINT
    assert call["expire_date"] == datetime(2026, 5, 25, 12, 30, tzinfo=UTC)
    assert call["order_id"] == client_order_id
    assert utils.quotation_to_decimal(call["stop_price"]) == Decimal("130")
    assert utils.quotation_to_decimal(call["price"]) == Decimal("129.5")
