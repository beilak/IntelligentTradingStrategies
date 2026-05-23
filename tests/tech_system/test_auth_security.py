from uuid import uuid4

from its.tech_system.auth.schemas import RegisterRequest
from its.tech_system.auth.security import (
    create_jwt_token,
    decode_jwt_token,
    hash_password,
    verify_password,
)
from its.tech_system.auth.settings import AuthSettings


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("correct horse password")

    assert password_hash.startswith("$argon2")
    assert verify_password("correct horse password", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_jwt_access_token_contains_user_context() -> None:
    user_id = uuid4()
    settings = AuthSettings(
        jwt_secret_key="unit-test-secret-with-at-least-32-bytes",
        jwt_issuer="unit-test",
    )

    token, expires_in = create_jwt_token(
        subject=user_id,
        email="user@example.com",
        role_version=1,
        token_type="access",
        roles=["quant_researcher"],
        permissions=["strategy.test.run", "ga.run.create"],
        env_scopes=["research", "paper"],
        settings=settings,
    )
    payload = decode_jwt_token(token, expected_type="access", settings=settings)

    assert expires_in == 1800
    assert payload["sub"] == str(user_id)
    assert payload["email"] == "user@example.com"
    assert payload["typ"] == "access"
    assert payload["role_version"] == 1
    assert payload["roles"] == ["quant_researcher"]
    assert payload["permissions"] == ["strategy.test.run", "ga.run.create"]
    assert payload["env_scopes"] == ["research", "paper"]


def test_register_request_normalizes_email() -> None:
    payload = RegisterRequest(email=" User@Example.COM ", password="long-password")

    assert payload.email == "user@example.com"
