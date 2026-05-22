from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import its.db.models  # noqa: F401
from its.db.base import Base
from its.db.session import get_session
from services.tech_system_backend.app.main import create_app


def test_register_login_me_refresh_flow() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_session() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": "User@Example.COM", "password": "long-password"},
        )
        assert register_response.status_code == 201
        register_payload = register_response.json()
        assert register_payload["user"]["email"] == "user@example.com"
        assert register_payload["access_token"]
        assert register_payload["refresh_token"]

        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {register_payload['access_token']}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "user@example.com"

        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": register_payload["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        assert refresh_response.json()["access_token"]

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "long-password"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["user"]["last_login_at"] is not None
