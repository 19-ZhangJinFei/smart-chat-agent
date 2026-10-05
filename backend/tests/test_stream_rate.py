from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import create_app
from app.rate_limit import RateLimiter
from conftest import FakeModels, new_session


def test_stream_commits_complete_only_and_releases_lock(client):
    sid = new_session(client)
    response = client.post("/api/chat/stream", json={"message": "你好", "session_id": sid})
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "中文" in response.text and "[DONE]" in response.text
    history = client.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"]
    assert history[-1]["content"] == "中文回复"
    failure = client.post("/api/chat/stream", json={"message": "fail", "session_id": sid})
    assert "[DONE]" not in failure.text and '"error"' in failure.text and "secret" not in failure.text
    assert len(client.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"]) == 2
    assert client.patch(f"/api/sessions/{sid}", json={"title": "解锁成功"}).status_code == 200


def test_window_and_separate_ips():
    clock = [0.0]
    limiter = RateLimiter(20, clock=lambda: clock[0])
    for _ in range(20):
        assert limiter.check("a") == 0
    assert limiter.check("a") == 60
    assert limiter.check("b") == 0
    clock[0] = 60
    assert limiter.check("a") == 0


def test_21st_request_and_health_exemption(settings):
    with TestClient(create_app(replace(settings, rate_limit=20), FakeModels())) as client:
        for _ in range(25):
            assert client.get("/api/health").status_code == 200
        for _ in range(20):
            assert client.get("/api/sessions").status_code == 200
        response = client.get("/api/sessions")
        assert response.status_code == 429 and response.headers["retry-after"]


def test_tcp_disconnect_discards_partial_answer_and_unlocks(settings):
    """真实TCP断流，避免TestClient缓冲完整响应掩盖取消问题。"""
    import asyncio
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    class SlowModels(FakeModels):
        async def stream(self, message, history):
            yield "第一段中文"
            await asyncio.sleep(5)
            yield "最后一段"

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(settings, SlowModels()), log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3) as client:
            sid = client.post("/api/sessions").json()["data"]["session"]["id"]
            with client.stream("POST", "/api/chat/stream", json={"message": "hi", "session_id": sid}) as response:
                lines = response.iter_lines()
                assert "第一段中文" in next(lines)
                assert client.delete(f"/api/sessions/{sid}").status_code == 409
            for _ in range(100):
                renamed = client.patch(f"/api/sessions/{sid}", json={"title": "断开后可改名"})
                if renamed.status_code == 200:
                    break
                time.sleep(0.02)
            assert renamed.status_code == 200
            assert client.get(f"/api/sessions/{sid}/messages").json()["data"]["messages"] == []
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
