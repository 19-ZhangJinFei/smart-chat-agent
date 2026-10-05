from dataclasses import replace

from fastapi.testclient import TestClient

from app import memory
from app.agent import AgentService
from app.main import create_app
from conftest import FakeModels, new_session
from test_agent import OfflineToolModel


def test_history_window_keeps_complete_recent_pairs(settings):
    history = [{"role": role, "content": f"{i}{role}"}
               for i in range(4) for role in ["user", "assistant"]]
    limited = memory.bounded_history(history, replace(settings, history_turns=2))
    assert limited == history[-4:]
    cap = sum(len(m["content"]) for m in history[-2:])
    assert memory.bounded_history(history, replace(settings, history_char_limit=cap)) == history[-2:]
    assert memory.bounded_history(history, replace(settings, history_char_limit=cap-1)) == []


def test_agent_business_write_failure_clears_checkpoint(settings, monkeypatch):
    agent = AgentService(settings, model=OfflineToolModel())
    original = memory.append_turn
    with TestClient(create_app(settings, FakeModels(), agent)) as client:
        sid = new_session(client)
        def fail_write(*args, **kwargs):
            raise RuntimeError("database-write-failure")
        monkeypatch.setattr(memory, "append_turn", fail_write)
        assert client.post("/api/agent/chat", json={"message":"订单", "session_id":sid}).status_code == 502
        assert agent.graph.get_state({"configurable":{"thread_id":sid}}).values == {}
        assert client.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"] == []
        monkeypatch.setattr(memory, "append_turn", original)
        result = client.post("/api/agent/chat", json={"message":"重试", "session_id":sid}).json()["data"]
        assert "订单" not in result["reply"]


def test_classifier_failure_does_not_save_or_fallback(settings):
    class BrokenClassifier(FakeModels):
        def classify(self, message, history):
            raise RuntimeError("secret-classifier-error")
        def chat(self, message, history):
            raise AssertionError("不应该静默降级")
    with TestClient(create_app(settings, BrokenClassifier())) as client:
        sid = new_session(client)
        response = client.post("/api/smart/chat", json={"message":"hi", "session_id":sid})
        assert response.status_code == 502 and "secret" not in response.text
        assert client.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"] == []
