from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

OrderSide = Literal["buy", "sell"]
OrderKind = Literal["limit", "market"]
StopOrderKind = Literal["stop_loss", "take_profit"]
TimeInForce = Literal["day", "fill_or_kill", "fill_and_kill"]
PriceTypeKind = Literal["currency", "point"]
StrategyOrderKind = Literal["limit", "market"]


class OrderTicket(BaseModel):
    instrument_id: str = Field(min_length=1, max_length=80)
    figi: str | None = Field(default=None, max_length=80)
    side: OrderSide
    order_type: OrderKind
    quantity: int = Field(gt=0, le=1_000_000)
    price: float | None = Field(default=None, gt=0)
    price_type: PriceTypeKind | None = "currency"
    time_in_force: TimeInForce = "day"
    client_order_id: str | None = Field(default=None, max_length=80)
    comment: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_price(self) -> OrderTicket:
        if self.order_type == "limit" and self.price is None:
            raise ValueError("price is required for limit orders")
        return self


class StopOrderTicket(BaseModel):
    instrument_id: str = Field(min_length=1, max_length=80)
    figi: str | None = Field(default=None, max_length=80)
    side: OrderSide
    stop_order_type: StopOrderKind
    quantity: int = Field(gt=0, le=1_000_000)
    stop_price: float = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    price_type: PriceTypeKind | None = "currency"
    expire_at: datetime | None = None
    client_order_id: str | None = Field(default=None, max_length=80)
    comment: str | None = Field(default=None, max_length=500)


class StrategyAssignmentRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class StrategyRunRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    interval: str = "CANDLE_INTERVAL_DAY"
    class_code: str = Field(default="TQBR", min_length=1, max_length=32)
    order_type: StrategyOrderKind = "limit"
    limit_offset_pct: float = Field(default=0.001, ge=0, le=0.1)
    min_order_value: float = Field(default=0.0, ge=0)
    cash_buffer_pct: float = Field(default=0.01, ge=0, le=0.2)


class StrategyExecutionRequest(StrategyRunRequest):
    plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation: Literal["execute_market_orders"]

    @model_validator(mode="after")
    def validate_market_orders(self) -> StrategyExecutionRequest:
        if self.order_type != "market":
            raise ValueError("strategy execution supports market orders only")
        return self
