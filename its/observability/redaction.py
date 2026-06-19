from __future__ import annotations

from collections.abc import Mapping
from typing import Any

MASKED_SECRET = "***"
MASKED_BEARER = "Bearer ****"

SECRET_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "client_secret",
    "private_key",
)


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: redact_value(key, value) for key, value in payload.items()}


def redact_value(key: str, value: Any) -> Any:
    normalized = key.lower().replace("-", "_")
    if any(part in normalized for part in SECRET_KEY_PARTS):
        if normalized == "authorization" and isinstance(value, str):
            scheme, _, token = value.partition(" ")
            if scheme.lower() == "bearer" and token:
                return MASKED_BEARER
        return MASKED_SECRET
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return value
