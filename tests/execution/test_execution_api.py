from uuid import uuid4

from fastapi.testclient import TestClient

from its.db.session import get_session
from its.execution.service import ExecutionService
from its.services.execution_backend.app.main import create_app
from its.tech_system.auth.security import create_jwt_token


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


def test_order_stub_requires_auth_but_not_execution_permission(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1:Main")
    monkeypatch.setenv("EXECUTION_ORDER_SUBMISSION_MODE", "stub")
    client = TestClient(create_app())

    payload = {
        "instrument_id": "BBG004730N88",
        "side": "buy",
        "order_type": "market",
        "quantity": 1,
    }

    assert client.post("/api/v1/accounts/acc-1/orders", json=payload).status_code == 401

    response = client.post(
        "/api/v1/accounts/acc-1/orders",
        headers=auth_headers("app.docs.read"),
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted_by_stub"
    assert body["submission_mode"] == "stub"
    assert body["would_submit"] is False
    assert body["ticket"]["order_type"] == "market"


def test_limit_order_stub_validates_price(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    monkeypatch.setenv("EXECUTION_ORDER_SUBMISSION_MODE", "stub")
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/accounts/acc-1/orders",
        headers=auth_headers(),
        json={
            "instrument_id": "BBG004730N88",
            "side": "buy",
            "order_type": "limit",
            "quantity": 1,
        },
    )

    assert response.status_code == 422


def test_orderbook_websocket_rejects_missing_auth_message(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    client = TestClient(create_app())

    with client.websocket_connect("/api/v1/ws/orderbook") as websocket:
        websocket.send_json({"type": "subscribe"})
        assert websocket.receive_json() == {
            "type": "error",
            "message": "First message must be auth.",
        }


def test_strategy_assignments_require_auth(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")
    app = create_app()
    app.dependency_overrides[get_session] = dummy_session
    client = TestClient(app)

    assert client.get("/api/v1/accounts/acc-1/strategies").status_code == 401


def test_strategy_assignments_route_returns_payload(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")

    def fake_list(self, account_id, session):
        return {"account_id": account_id, "items": [], "available": [], "total": 0}

    monkeypatch.setattr(ExecutionService, "list_strategy_assignments", fake_list)
    app = create_app()
    app.dependency_overrides[get_session] = dummy_session
    client = TestClient(app)

    response = client.get(
        "/api/v1/accounts/acc-1/strategies",
        headers=auth_headers("app.docs.read"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "account_id": "acc-1",
        "items": [],
        "available": [],
        "total": 0,
    }


def test_strategy_run_route_is_dry_run_only(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_TINVEST_ACCOUNT_IDS", "acc-1")

    async def fake_run(
        self, account_id, strategy_name, request, session, authorization
    ):
        return {
            "account_id": account_id,
            "strategy_name": strategy_name,
            "settings": request.model_dump(mode="json"),
            "orders": [],
            "stop_orders": [],
            "authorization_seen": bool(authorization),
        }

    monkeypatch.setattr(ExecutionService, "run_assigned_strategy", fake_run)
    app = create_app()
    app.dependency_overrides[get_session] = dummy_session
    client = TestClient(app)

    response = client.post(
        "/api/v1/accounts/acc-1/strategies/Turnover/runs",
        headers=auth_headers("app.docs.read"),
        json={"class_code": "TQBR", "order_type": "market"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == "acc-1"
    assert body["strategy_name"] == "Turnover"
    assert body["settings"]["order_type"] == "market"
    assert body["orders"] == []
    assert body["authorization_seen"] is True


def dummy_session():
    yield object()
