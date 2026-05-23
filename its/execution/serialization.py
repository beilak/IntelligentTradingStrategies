from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from t_tech.invest import MoneyValue, Quotation, utils


def serialize_sdk_value(value: Any) -> Any:
    if _is_missing_sdk_value(value):
        return None
    if isinstance(value, Enum):
        return value.name
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, MoneyValue):
        return serialize_money(value)
    if isinstance(value, Quotation):
        return serialize_quotation(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return {
            field.name: serialize_sdk_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(serialize_sdk_value(key)): serialize_sdk_value(item)
            for key, item in value.items()
        }
    if isinstance(value, Iterable) and not isinstance(value, bytes | bytearray):
        return [serialize_sdk_value(item) for item in value]
    if hasattr(value, "DESCRIPTOR") and hasattr(value, "ListFields"):
        return {
            field.name: serialize_sdk_value(item)
            for field, item in value.ListFields()
        }
    return value


def serialize_money(value: MoneyValue | None) -> dict[str, Any] | None:
    if value is None or _is_missing_sdk_value(value):
        return None
    currency = None if _is_missing_sdk_value(value.currency) else value.currency
    units = 0 if _is_missing_sdk_value(value.units) else value.units
    nano = 0 if _is_missing_sdk_value(value.nano) else value.nano
    amount = Decimal(units) + (Decimal(nano) / Decimal("1000000000"))
    return {
        "currency": currency,
        "units": units,
        "nano": nano,
        "value": float(amount),
    }


def serialize_quotation(value: Quotation | None) -> dict[str, Any] | None:
    if value is None or _is_missing_sdk_value(value):
        return None
    return {
        "units": value.units,
        "nano": value.nano,
        "value": float(utils.quotation_to_decimal(value)),
    }


def quotation_to_decimal(value: Quotation | None) -> float | None:
    serialized = serialize_quotation(value)
    return None if serialized is None else serialized["value"]


def money_to_decimal(value: MoneyValue | None) -> float | None:
    serialized = serialize_money(value)
    return None if serialized is None else serialized["value"]


def _is_missing_sdk_value(value: Any) -> bool:
    return type(value) is object
