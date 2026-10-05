from fastapi.testclient import TestClient

from app.main import create_app
from app.models import ChatMessage
from conftest import FakeModels, new_session
from sqlalchemy import select


def test_crud_and_memory_isolation(client):
    first, second = new_session(client), new_session(client)
    assert client.patch(f"/api/sessions/{first}", json={"title": "  自定义标题  "}).status_code == 200
    response = client.post("/api/chat", json={"session_id": first, "message": "我叫小明"})
    assert response.status_code == 200
    saved = response.json()["data"]
    assert saved["session"]["id"] == first and saved["session"]["history_version"] == 1
    assert saved["messages"] == client.get(f"/api/sessions/{first}/messages").json()["data"]["messages"]
    response = client.post("/api/chat", json={"session_id": first, "message": "姓名？"})
    assert "我叫小明" in response.json()["data"]["reply"]
    response = client.post("/api/chat", json={"session_id": second, "message": "姓名？"})
    assert "小明" not in response.json()["data"]["reply"]
    sessions = client.get("/api/sessions").json()["data"]["sessions"]
    assert next(s for s in sessions if s["id"] == first)["title"] == "自定义标题"
    assert len(client.get(f"/api/sessions/{first}/messages").json()["data"]["messages"]) == 4
    assert client.delete(f"/api/sessions/{first}").status_code == 200
    assert client.get(f"/api/sessions/{first}/messages").status_code == 404
    with client.app.state.database.sessions() as db:
        assert list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == first))) == []


def test_invalid_and_unknown_session(client):
    for message in ["", "  ", "x" * 2001]:
        assert client.post("/api/chat", json={"message": message, "session_id": "missing"}).status_code == 422
    assert client.post("/api/chat", json={"message": "你好", "session_id": "missing"}).status_code == 404
    assert client.patch("/api/sessions/missing", json={"title": " "}).status_code == 422


def test_failure_does_not_commit_or_leak(client):
    sid = new_session(client)
    response = client.post("/api/chat", json={"message": "fail", "session_id": sid})
    assert response.status_code == 502
    assert "secret" not in response.text
    assert client.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"] == []


def test_missing_model_health(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json()["data"]["model_configured"] is False
        sid = new_session(client)
        assert client.post("/api/chat", json={"message": "你好", "session_id": sid}).status_code == 503


def test_restart(settings):
    with TestClient(create_app(settings, FakeModels())) as first:
        sid = new_session(first)
        first.post("/api/chat", json={"message": "我叫小明", "session_id": sid})
    with TestClient(create_app(settings, FakeModels())) as restarted:
        assert len(restarted.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"]) == 2
        assert "小明" in restarted.post("/api/chat", json={"message": "名字？", "session_id": sid}).json()["data"]["reply"]


def test_lock_prevents_conflict(client):
    sid = new_session(client)
    with client.app.state.locks.hold(sid):
        assert client.patch(f"/api/sessions/{sid}", json={"title": "test"}).status_code == 409
        assert client.delete(f"/api/sessions/{sid}").status_code == 409
        assert client.post("/api/chat", json={"message": "hi", "session_id": sid}).status_code == 409
