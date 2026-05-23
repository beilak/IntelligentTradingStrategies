from uuid import uuid4

from fastapi.testclient import TestClient

from its.services.ga_backend.app.main import create_app as create_ga_app
from its.tech_system.auth.security import create_jwt_token
from services.data_backend.app.main import create_app as create_data_app
from services.strategy_backend.app.main import create_app as create_strategy_app


def auth_headers(*permissions: str) -> dict[str, str]:
    token, _ = create_jwt_token(
        subject=uuid4(),
        email="user@example.com",
        role_version=1,
        token_type="access",
        roles=["test"],
        permissions=list(permissions),
    )
    return {"Authorization": f"Bearer {token}"}


def test_data_backend_requires_data_permission() -> None:
    client = TestClient(create_data_app())

    assert client.get("/api/v1/sources").status_code == 401
    assert (
        client.get(
            "/api/v1/sources",
            headers=auth_headers("app.docs.read"),
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/sources",
            headers=auth_headers("data.sources.read"),
        ).status_code
        == 200
    )


def test_strategy_backend_requires_strategy_permission() -> None:
    client = TestClient(create_strategy_app())

    assert client.get("/api/v1/strategy-type").status_code == 401
    assert (
        client.get(
            "/api/v1/strategy-type",
            headers=auth_headers("app.docs.read"),
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/strategy-type",
            headers=auth_headers("strategy.component.read"),
        ).status_code
        == 200
    )


def test_ga_backend_requires_ga_permission() -> None:
    client = TestClient(create_ga_app())

    assert client.get("/api/v1/alphabets").status_code == 401
    assert (
        client.get(
            "/api/v1/alphabets",
            headers=auth_headers("app.docs.read"),
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/alphabets",
            headers=auth_headers("ga.alphabet.read"),
        ).status_code
        == 200
    )
