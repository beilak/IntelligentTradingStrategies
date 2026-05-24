from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


OrderSide = Literal["buy", "sell"]
OrderKind = Literal["limit", "market"]
StopOrderKind = Literal["stop_loss", "take_profit"]
TimeInForce = Literal["day", "fill_or_kill", "fill_and_kill"]
PriceTypeKind = Literal["currency", "point"]


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
    def validate_price(self) -> "OrderTicket":
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
