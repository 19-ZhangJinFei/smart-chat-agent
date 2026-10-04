import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeModels:
    def chat(self, message, history):
        if message == "fail":
            raise RuntimeError("secret-upstream-detail")
        return "离线测试：" + "/".join(m["content"] for m in history if m["role"] == "user") + message

    def classify(self, message, history):
        return "agent" if "订单" in message else "chat"

    async def stream(self, message, history):
        yield "中文"
        if message == "fail":
            raise RuntimeError("secret-upstream-detail")
        yield "回复"


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=tmp_path / "chat.db", agent_db_path=tmp_path / "agent.db", rate_limit=1000)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, model_service=FakeModels())) as client:
        yield client


def new_session(client):
    return client.post("/api/sessions").json()["data"]["session"]["id"]
