import sqlite3
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langchain_openai import ChatOpenAI

from app.agent import AgentService
from app.llm import ModelService
from app.main import create_app


def test_shutdown_closes_actual_model_clients_and_checkpoint(settings, monkeypatch):
    # 真实SDK连接池，但不发送模型请求：只把分类执行替换为离线结果。
    configured = replace(settings, api_key="offline-lifecycle-check")
    models = ModelService(configured)
    ordinary = models.model
    monkeypatch.setattr(ChatOpenAI, "with_structured_output",
                        lambda *args, **kwargs: SimpleNamespace(invoke=lambda _: SimpleNamespace(intent="chat")))
    assert models.classify("你好", []) == "chat"
    router = models._router_model
    agent = AgentService(configured)
    agent.graph
    agent_model = agent._owned_model
    clients = [client for model in [ordinary, router, agent_model]
               for client in [model.root_client, model.root_async_client]]
    assert all(not client.is_closed() for client in clients)
    with TestClient(create_app(configured, models, agent)) as client:
        assert client.get("/api/health").status_code == 200
    assert all(client.is_closed() for client in clients)
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        agent.conn.execute("SELECT 1")


def test_startup_failure_still_closes_initialized_resources(settings, monkeypatch):
    configured = replace(settings, api_key="offline-lifecycle-check")
    models = ModelService(configured)
    model = models.model
    app = create_app(configured, models)
    database_closed = []
    original_close = app.state.database.close

    def close_database():
        database_closed.append(True)
        original_close()

    def failing_agent(_):
        raise RuntimeError("checkpoint initialization failed")

    monkeypatch.setattr(app.state.database, "close", close_database)
    monkeypatch.setattr("app.agent.AgentService", failing_agent)
    with pytest.raises(RuntimeError, match="initialization failed"):
        with TestClient(app):
            pass
    assert database_closed == [True]
    assert model.root_client.is_closed() and model.root_async_client.is_closed()


def test_invalid_checkpoint_file_closes_partial_connection(settings, monkeypatch):
    settings.agent_db_path.write_bytes(b"invalid sqlite checkpoint")
    connections = []
    original_connect = sqlite3.connect

    def record_connection(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr("app.agent.sqlite3.connect", record_connection)
    with pytest.raises(sqlite3.DatabaseError):
        AgentService(settings)
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")
