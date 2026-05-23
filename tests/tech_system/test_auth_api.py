from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import its.db.models  # noqa: F401
from its.db.base import Base
from its.db.models import AuthUser
from its.db.session import get_session
from its.tech_system.auth.rbac_service import assign_roles_to_user, seed_rbac_catalog
from its.tech_system.auth.security import decode_jwt_token
from services.tech_system_backend.app.main import create_app


def build_test_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with testing_session() as session:
        seed_rbac_catalog(session)
        session.commit()

    def override_get_session() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), testing_session


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_me_refresh_flow() -> None:
    client, _ = build_test_client()

    with client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": "User@Example.COM", "password": "long-password"},
        )
        assert register_response.status_code == 201
        register_payload = register_response.json()
        assert register_payload["user"]["email"] == "user@example.com"
        assert register_payload["access_token"]
        assert register_payload["refresh_token"]
        assert [role["code"] for role in register_payload["user"]["roles"]] == [
            "documentation_reader"
        ]
        assert set(register_payload["user"]["permissions"]) == {
            "app.launchpad.read",
            "app.docs.read",
            "profile.self.read",
            "role.request.create",
        }

        access_payload = decode_jwt_token(
            register_payload["access_token"], expected_type="access"
        )
        assert access_payload["roles"] == ["documentation_reader"]
        assert "profile.self.read" in access_payload["permissions"]
        assert "app.launchpad.read" in access_payload["permissions"]
        assert "data.sources.read" not in access_payload["permissions"]

        me_response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers(register_payload["access_token"]),
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


def test_role_request_approval_updates_refresh_claims() -> None:
    client, testing_session = build_test_client()

    with client:
        user_response = client.post(
            "/api/v1/auth/register",
            json={"email": "researcher@example.com", "password": "long-password"},
        )
        assert user_response.status_code == 201
        user_payload = user_response.json()

        request_response = client.post(
            "/api/v1/profile/me/role-requests",
            headers=auth_headers(user_payload["access_token"]),
            json={
                "role_code": "quant_researcher",
                "justification": "Need to run research workflows and GA experiments.",
            },
        )
        assert request_response.status_code == 201
        request_id = request_response.json()["id"]

        admin_response = client.post(
            "/api/v1/auth/register",
            json={"email": "admin@example.com", "password": "long-password"},
        )
        assert admin_response.status_code == 201

        with testing_session() as session:
            admin = session.scalar(
                select(AuthUser).where(AuthUser.email == "admin@example.com")
            )
            assert admin is not None
            assign_roles_to_user(
                session=session,
                user=admin,
                role_codes=["role_admin"],
                assigned_by=None,
                reason="test admin",
            )
            session.commit()

        admin_login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "long-password"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]

        approve_response = client.post(
            f"/api/v1/role-requests/{request_id}/approve",
            headers=auth_headers(admin_token),
            json={"comment": "Approved for research work."},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "approved"

        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": user_payload["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        refreshed_payload = refresh_response.json()
        role_codes = [role["code"] for role in refreshed_payload["user"]["roles"]]
        assert "quant_researcher" in role_codes

        access_payload = decode_jwt_token(
            refreshed_payload["access_token"], expected_type="access"
        )
        assert "quant_researcher" in access_payload["roles"]
        assert "ga.run.create" in access_payload["permissions"]
