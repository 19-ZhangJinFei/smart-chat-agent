"""真实API集成验证，独立业务/检查点数据库，不污染用户对话。"""
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def run():
    results = []
    settings = Settings.load()
    if not settings.api_key:
        print("尚未配置模型")
        return 2
    with tempfile.TemporaryDirectory() as directory:
        settings = replace(settings, db_path=Path(directory) / "chat.db",
                           agent_db_path=Path(directory) / "agent.db", rate_limit=1000)
        with TestClient(create_app(settings)) as client:
            sid = client.post("/api/sessions").json()["data"]["session"]["id"]
            cases = [
                ("/api/chat", "我叫小明，请记住", None),
                ("/api/chat", "我叫什么名字？", "小明"),
                ("/api/agent/chat", "订单DD20240001现在到哪里了？", "DD20240001"),
                ("/api/chat", "我喜欢蓝色，请记住", None),
                ("/api/agent/chat", "我喜欢什么颜色？", "蓝色"),
                ("/api/smart/chat", "用一句话介绍Docker", None),
                ("/api/smart/chat", "WELCOME10优惠券有效吗？", None),
            ]
            for path, message, expected in cases:
                response = client.post(path, json={"message": message, "session_id": sid})
                value = response.json()
                passed = response.status_code == 200 and bool(value.get("data", {}).get("reply"))
                if expected:
                    passed = passed and expected in value["data"]["reply"]
                if "Docker" in message:
                    passed = passed and value["data"].get("route") == "chat"
                if "WELCOME10" in message:
                    passed = passed and value["data"].get("route") == "agent" and "get_coupon" in value["data"].get("tools_used", [])
                result = {"path": path, "message": message, "passed": passed, "response": value}
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            response = client.post("/api/chat/stream", json={"message": "用一句话解释SSE", "session_id": sid})
            results.append({"name": "真实SSE", "passed": response.status_code == 200 and "[DONE]" in response.text})
        with TestClient(create_app(settings)) as restarted:
            response = restarted.post("/api/agent/chat", json={"message": "我叫什么名字，喜欢什么颜色？", "session_id": sid})
            value = response.json()
            reply = value.get("data", {}).get("reply", "")
            results.append({"name": "双库重启记忆", "passed": "小明" in reply and "蓝色" in reply, "response": value})
    output = Path(__file__).resolve().parents[1] / "artifacts/evidence/live-integration.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"真实集成验证：{sum(r['passed'] for r in results)}/{len(results)}")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
