"""API tests for authentication, nodes, and tasks."""

from fastapi.testclient import TestClient

from daemonos.api import create_app


def test_unauthenticated_nodes_rejected():
    app = create_app()
    client = TestClient(app)
    r = client.get("/v1/nodes")
    assert r.status_code == 401


def test_bootstrap_enroll_and_task():
    app = create_app()
    client = TestClient(app)

    # Enroll a simulated node
    r = client.post(
        "/v1/bootstrap/enroll",
        json={
            "device_serial": "sim-api-1",
            "model": "sim-phone",
            "requested_capabilities": ["task.submit", "task.execute", "task.cancel", "node.report"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    token_id = body["token_id"]
    node_id = body["node"]["node_id"]
    headers = {"Authorization": f"Bearer {token_id}"}

    # List nodes
    r = client.get("/v1/nodes", headers=headers)
    assert r.status_code == 200
    nodes = r.json()
    assert len(nodes) == 1
    assert nodes[0]["node_id"] == node_id

    # Capabilities
    r = client.get(f"/v1/nodes/{node_id}/capabilities", headers=headers)
    assert r.status_code == 200
    caps = r.json()
    assert caps["node_id"] == node_id

    # Health
    r = client.get(f"/v1/nodes/{node_id}/health", headers=headers)
    assert r.status_code == 200
    assert r.json()["health"] == "healthy"

    # Submit echo task
    r = client.post(
        "/v1/tasks",
        headers=headers,
        json={"capability": "echo", "parameters": {"message": "api-ok"}, "idempotency_key": "ik-1"},
    )
    assert r.status_code == 201
    task = r.json()
    assert task["state"] == "succeeded"
    assert task["result"]["stdout"] == "api-ok"
    assert task["result"]["verified"] is True

    # Idempotent resubmit
    r2 = client.post(
        "/v1/tasks",
        headers=headers,
        json={"capability": "echo", "parameters": {"message": "api-ok"}, "idempotency_key": "ik-1"},
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == task["id"]

    # Get task
    r = client.get(f"/v1/tasks/{task['id']}", headers=headers)
    assert r.status_code == 200
