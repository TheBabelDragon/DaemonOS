"""API contract tests for discovery and planning."""

from fastapi.testclient import TestClient

from daemonos.api import create_app


def _token(client: TestClient) -> str:
    r = client.post(
        "/v1/bootstrap/enroll",
        json={
            "device_serial": "api-disc-1",
            "requested_capabilities": [
                "discover",
                "plan",
                "task.submit",
                "task.execute",
                "task.cancel",
            ],
        },
    )
    assert r.status_code == 200
    return r.json()["token_id"]


def test_operations_no_auth():
    client = TestClient(create_app())
    r = client.get("/v1/operations")
    assert r.status_code == 200
    body = r.json()
    assert "operations" in body
    ids = {op["id"] for op in body["operations"]}
    assert "discover_device" in ids
    assert "plan_deployment" in ids


def test_discover_requires_auth():
    client = TestClient(create_app())
    r = client.get("/v1/discovery/devices")
    assert r.status_code == 401


def test_discover_and_plan_flow():
    client = TestClient(create_app())
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/v1/discovery/providers", headers=headers)
    assert r.status_code == 200
    assert "mock" in r.json()["providers"]

    r = client.get("/v1/discovery/devices", headers=headers)
    assert r.status_code == 200
    devices = r.json()["devices"]
    assert any(d["device_key"] == "mock-pixel-like" for d in devices)

    r = client.get(
        "/v1/discovery/devices/mock/mock-pixel-like/probes", headers=headers
    )
    assert r.status_code == 200
    assert len(r.json()["probes"]) > 0

    r = client.post(
        "/v1/discovery/profile",
        headers=headers,
        json={"provider": "mock", "device_key": "mock-pixel-like"},
    )
    assert r.status_code == 200
    profile = r.json()
    assert profile["hardware"]["arch"] == "arm64"
    assert profile["schema_version"] == "1.0"

    r = client.post(
        "/v1/plan",
        headers=headers,
        json={
            "provider": "mock",
            "device_key": "mock-pixel-like",
            "objective": "run_agent",
        },
    )
    assert r.status_code == 200
    plan = r.json()
    assert plan["execution_authorized"] is False
    assert plan["side_effects"] == []
    assert plan["overall_status"] == "viable"
    assert plan["preferred"]["target_id"] == "agent-android-existing"


def test_plan_without_capability_denied():
    client = TestClient(create_app())
    r = client.post(
        "/v1/bootstrap/enroll",
        json={
            "device_serial": "api-disc-2",
            "requested_capabilities": ["discover"],  # no plan
        },
    )
    token = r.json()["token_id"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/v1/plan",
        headers=headers,
        json={"provider": "mock", "device_key": "mock-pixel-like"},
    )
    assert r.status_code == 403


def test_existing_task_api_still_works():
    """Regression: prior task API must remain functional."""
    client = TestClient(create_app())
    r = client.post(
        "/v1/bootstrap/enroll",
        json={
            "device_serial": "reg-1",
            "requested_capabilities": [
                "task.submit",
                "task.execute",
                "task.cancel",
                "discover",
                "plan",
            ],
        },
    )
    token = r.json()["token_id"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/v1/tasks",
        headers=headers,
        json={"capability": "echo", "parameters": {"message": "still-works"}},
    )
    assert r.status_code == 201
    assert r.json()["state"] == "succeeded"
