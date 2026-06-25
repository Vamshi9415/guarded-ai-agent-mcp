from fastapi.testclient import TestClient

from backend import main


class FakeAgent:
    def __init__(self):
        self.messages = []

    async def run(self, message):
        self.messages.append(message)
        return f"echo: {message}"

    async def list_tools(self):
        return [{"name": "local__read_file"}]


def client():
    return TestClient(main.app)


def test_dashboard_serves_html():
    response = client().get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_chat_returns_503_when_agent_not_ready(monkeypatch):
    monkeypatch.setattr(main, "_agent", None)

    response = client().post("/chat", json={"message": "hello"})

    assert response.status_code == 503


def test_chat_calls_running_agent(monkeypatch):
    fake = FakeAgent()
    monkeypatch.setattr(main, "_agent", fake)

    response = client().post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"response": "echo: hello"}
    assert fake.messages == ["hello"]


def test_list_tools_uses_running_agent(monkeypatch):
    monkeypatch.setattr(main, "_agent", FakeAgent())

    response = client().get("/api/tools")

    assert response.status_code == 200
    assert response.json() == {"tools": [{"name": "local__read_file"}]}


def test_rules_crud_routes(monkeypatch):
    created = []
    toggled = []
    deleted = []

    monkeypatch.setattr(main, "get_all_rules", lambda: [{"_id": "r1", "tool_name": "read_file"}])
    monkeypatch.setattr(main, "create_rule", lambda rule: created.append(rule) or "new-rule")
    monkeypatch.setattr(main, "toggle_rule", lambda rule_id: toggled.append(rule_id) or True)
    monkeypatch.setattr(main, "delete_rule", lambda rule_id: deleted.append(rule_id) or True)

    c = client()

    assert c.get("/api/rules").json() == {"rules": [{"_id": "r1", "tool_name": "read_file"}]}
    create_response = c.post(
        "/api/rules",
        json={"tool_name": "delete_file", "action": "BLOCK", "reason": "danger", "config": {}},
    )
    assert create_response.status_code == 201
    assert create_response.json() == {"id": "new-rule"}
    assert created == [{"tool_name": "delete_file", "action": "BLOCK", "reason": "danger", "config": {}}]

    assert c.patch("/api/rules/r1/toggle").json() == {"status": "toggled"}
    assert toggled == ["r1"]

    assert c.delete("/api/rules/r1").json() == {"status": "deleted"}
    assert deleted == ["r1"]


def test_rule_toggle_and_delete_return_404(monkeypatch):
    monkeypatch.setattr(main, "toggle_rule", lambda rule_id: False)
    monkeypatch.setattr(main, "delete_rule", lambda rule_id: False)
    c = client()

    assert c.patch("/api/rules/missing/toggle").status_code == 404
    assert c.delete("/api/rules/missing").status_code == 404


def test_approval_routes(monkeypatch):
    monkeypatch.setattr(main, "get_pending_approvals", lambda: [{"_id": "a1", "status": "pending"}])
    monkeypatch.setattr(main, "resolve_approval", lambda approval_id, status: True)
    c = client()

    assert c.get("/api/approvals").json() == {"approvals": [{"_id": "a1", "status": "pending"}]}
    assert c.post("/api/approvals/a1/approve").json() == {"status": "approved"}
    assert c.post("/api/approvals/a1/deny").json() == {"status": "denied"}


def test_approval_resolution_404(monkeypatch):
    monkeypatch.setattr(main, "resolve_approval", lambda approval_id, status: False)
    c = client()

    assert c.post("/api/approvals/missing/approve").status_code == 404
    assert c.post("/api/approvals/missing/deny").status_code == 404


def test_logs_route(monkeypatch):
    monkeypatch.setattr(main, "get_recent_logs", lambda limit: [{"limit": limit}])

    response = client().get("/api/logs?limit=7")

    assert response.status_code == 200
    assert response.json() == {"logs": [{"limit": 7}]}


def test_mongo_read_routes_degrade_when_storage_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise main.MongoUnavailable("dns timeout")

    monkeypatch.setattr(main, "get_all_rules", unavailable)
    monkeypatch.setattr(main, "get_pending_approvals", unavailable)
    monkeypatch.setattr(main, "get_recent_logs", unavailable)
    c = client()

    rules = c.get("/api/rules")
    approvals = c.get("/api/approvals")
    logs = c.get("/api/logs")

    assert rules.status_code == 200
    assert rules.json()["rules"] == []
    assert rules.json()["storage"]["status"] == "unavailable"
    assert approvals.status_code == 200
    assert approvals.json()["approvals"] == []
    assert logs.status_code == 200
    assert logs.json()["logs"] == []


def test_mongo_write_routes_return_503_when_storage_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise main.MongoUnavailable("dns timeout")

    monkeypatch.setattr(main, "create_rule", unavailable)
    monkeypatch.setattr(main, "toggle_rule", unavailable)
    monkeypatch.setattr(main, "delete_rule", unavailable)
    monkeypatch.setattr(main, "resolve_approval", unavailable)
    c = client()

    assert c.post(
        "/api/rules",
        json={"tool_name": "read_file", "action": "BLOCK", "reason": "", "config": {}},
    ).status_code == 503
    assert c.patch("/api/rules/r1/toggle").status_code == 503
    assert c.delete("/api/rules/r1").status_code == 503
    assert c.post("/api/approvals/a1/approve").status_code == 503
    assert c.post("/api/approvals/a1/deny").status_code == 503
