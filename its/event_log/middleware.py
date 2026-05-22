from __future__ import annotations

import asyncio
import json
from json import JSONDecodeError
from urllib.parse import unquote

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from its.event_log.config import get_event_log_settings
from its.event_log.repository import EventLogCreate, append_event_log
from its.tech_system.auth.security import AuthTokenError, decode_jwt_token

UNAUTH_USER = "unauth"
MASKED_SECRET = "***"
MASKED_BEARER = "Bearer ****"


class EventLogMiddleware:
    def __init__(self, app: ASGIApp, service_name: str) -> None:
        self.app = app
        self.service_name = service_name
        self.max_body_bytes = get_event_log_settings().max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        captured_bytes = 0
        truncated = False

        async def receive_wrapper() -> Message:
            nonlocal captured_bytes, truncated
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body and captured_bytes < self.max_body_bytes:
                    remaining = self.max_body_bytes - captured_bytes
                    chunks.append(body[:remaining])
                    captured_bytes += min(len(body), remaining)
                    if len(body) > remaining:
                        truncated = True
                elif body:
                    truncated = True
            return message

        try:
            await self.app(scope, receive_wrapper, send)
        finally:
            headers = _headers_to_dict(scope)
            logged_headers = _mask_sensitive_headers(headers)
            await asyncio.to_thread(
                append_event_log,
                EventLogCreate(
                    service=self.service_name,
                    user=_extract_user(headers),
                    http_action=str(scope.get("method", "")),
                    ip_address=_extract_ip_address(scope, headers),
                    path=_build_path(scope),
                    header=logged_headers,
                    body=_decode_body(
                        chunks,
                        truncated,
                        path=str(scope.get("path", "")),
                    ),
                ),
            )


def _headers_to_dict(scope: Scope) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1", errors="replace")
        for key, value in scope.get("headers", [])
    }


def _mask_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
    masked = dict(headers)
    authorization = masked.get("authorization")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            masked["authorization"] = MASKED_BEARER
    return masked


def _extract_user(headers: dict[str, str]) -> str:
    authorization = headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return UNAUTH_USER
    try:
        payload = decode_jwt_token(token, expected_type="access")
    except AuthTokenError:
        return UNAUTH_USER
    user = payload.get("email") or payload.get("sub")
    return str(user) if user else UNAUTH_USER


def _extract_ip_address(scope: Scope, headers: dict[str, str]) -> str:
    forwarded_for = headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip() or "unknown"

    real_ip = headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip() or "unknown"

    client = scope.get("client")
    if isinstance(client, tuple) and client:
        return str(client[0])
    return "unknown"


def _build_path(scope: Scope) -> str:
    path = str(scope.get("path", ""))
    query_string = scope.get("query_string", b"")
    if not query_string:
        return path
    return f"{path}?{unquote(query_string.decode('latin-1', errors='replace'))}"


def _decode_body(chunks: list[bytes], truncated: bool, *, path: str) -> str | None:
    if not chunks:
        return None
    body = b"".join(chunks).decode("utf-8", errors="replace")
    body = _mask_sensitive_body(path=path, body=body)
    if truncated:
        return f"{body}\n...[truncated]"
    return body


def _mask_sensitive_body(*, path: str, body: str) -> str:
    if not _is_auth_login_path(path):
        return body

    try:
        payload = json.loads(body)
    except JSONDecodeError:
        return '{"password":"***"}'

    if not isinstance(payload, dict):
        return '{"password":"***"}'

    if "password" in payload:
        payload["password"] = MASKED_SECRET
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _is_auth_login_path(path: str) -> bool:
    return path.rstrip("/").endswith("/auth/login")
