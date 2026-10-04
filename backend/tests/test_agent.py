from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agent import AgentService
from app.main import create_app
from conftest import FakeModels, new_session


class OfflineToolModel(BaseChatModel):
    """只用于验证真实LangGraph调度和持久化，不作为实际LLM评估。"""
    @property
    def _llm_type(self):
        return "offline-tool-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        humans = [m.content for m in messages if m.type == "human"]
        if humans[-1] == "fail":
            raise RuntimeError("offline-failure")
        if messages[-1].type == "human" and "订单" in humans[-1]:
            message = AIMessage(content="", tool_calls=[{
                "name": "query_order", "args": {"order_id": "DD20240001"}, "id": uuid4().hex}])
        else:
            message = AIMessage(content="离线结果：" + "|".join(humans))
        return ChatResult(generations=[ChatGeneration(message=message)])


def test_only_current_tools_and_restart(settings):
    first = AgentService(settings, model=OfflineToolModel())
    result = first.chat("订单DD20240001", "sid", [], 0)
    assert result["tools_used"] == ["query_order"]
    first.close()
    restarted = AgentService(settings, model=OfflineToolModel())
    result = restarted.chat("我刚问了什么", "sid", [], 1)
    assert "DD20240001" in result["reply"]
    assert result["tools_used"] == []
    restarted.clear("sid")
    assert restarted.graph.get_state({"configurable": {"thread_id": "sid"}}).values == {}
    restarted.close()


def test_mode_switch_and_failure_rebuild(settings):
    agent = AgentService(settings, model=OfflineToolModel())
    with TestClient(create_app(settings, FakeModels(), agent)) as client:
        sid = new_session(client)
        client.post("/api/chat", json={"message": "我叫小明", "session_id": sid})
        result = client.post("/api/agent/chat", json={"message": "订单DD20240001", "session_id": sid})
        assert "小明" in result.json()["data"]["reply"]
        client.post("/api/chat", json={"message": "我喜欢蓝色", "session_id": sid})
        result = client.post("/api/agent/chat", json={"message": "我喜欢什么颜色", "session_id": sid})
        assert "蓝色" in result.json()["data"]["reply"]
        count = len(client.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"])
        assert client.post("/api/agent/chat", json={"message": "fail", "session_id": sid}).status_code == 502
        assert len(client.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"]) == count
        result = client.post("/api/agent/chat", json={"message": "重试", "session_id": sid})
        assert "fail" not in result.json()["data"]["reply"]
        assert client.delete(f"/api/sessions/{sid}").status_code == 200
        assert agent.graph.get_state({"configurable": {"thread_id": sid}}).values == {}


def test_smart_route(settings):
    agent = AgentService(settings, model=OfflineToolModel())
    with TestClient(create_app(settings, FakeModels(), agent)) as client:
        sid = new_session(client)
        assert client.post("/api/smart/chat", json={"message": "hello", "session_id": sid}).json()["data"]["route"] == "chat"
        result = client.post("/api/smart/chat", json={"message": "订单", "session_id": sid}).json()["data"]
        assert result["route"] == "agent" and result["tools_used"] == ["query_order"]
