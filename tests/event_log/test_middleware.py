from its.event_log.middleware import (
    _decode_body,
    _extract_ip_address,
    _mask_sensitive_headers,
)


def test_auth_login_body_masks_password() -> None:
    body = _decode_body(
        [b'{"email":"beylak@yandex.ru","password":"1234567890"}'],
        truncated=False,
        path="/api/v1/auth/login",
    )

    assert body == '{"email":"beylak@yandex.ru","password":"***"}'


def test_non_auth_login_body_is_kept() -> None:
    body = _decode_body(
        [b'{"password":"1234567890"}'],
        truncated=False,
        path="/api/v1/other",
    )

    assert body == '{"password":"1234567890"}'


def test_ip_address_prefers_first_forwarded_for() -> None:
    ip_address = _extract_ip_address(
        {"type": "http", "client": ("10.0.0.10", 12345)},
        {"x-forwarded-for": "203.0.113.10, 10.0.0.1", "x-real-ip": "198.51.100.1"},
    )

    assert ip_address == "203.0.113.10"


def test_ip_address_falls_back_to_scope_client() -> None:
    ip_address = _extract_ip_address(
        {"type": "http", "client": ("10.0.0.10", 12345)},
        {},
    )

    assert ip_address == "10.0.0.10"


def test_headers_mask_bearer_authorization() -> None:
    headers = _mask_sensitive_headers(
        {"authorization": "Bearer token-value", "content-type": "application/json"}
    )

    assert headers == {
        "authorization": "Bearer ****",
        "content-type": "application/json",
    }


def test_headers_keep_non_bearer_authorization() -> None:
    headers = _mask_sensitive_headers({"authorization": "Basic token-value"})

    assert headers == {"authorization": "Basic token-value"}
