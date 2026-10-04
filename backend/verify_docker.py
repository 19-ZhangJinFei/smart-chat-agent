"""本机Docker验收：需先启动Compose，使用独立测试会话与本地证据。"""
import argparse
import json
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True)


def run(port):
    rows = []
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=120)
    def record(name, passed, **details):
        rows.append({"name": name, "passed": bool(passed), **details})
        print(f"{name}: {'通过' if passed else '失败'}", flush=True)
        if not passed:
            raise AssertionError(name)
    try:
        record("静态页面与健康", "SmartChat" in client.get("/").text and client.get("/api/health").json()["data"]["status"] == "ok")
        sid = client.post("/api/sessions").json()["data"]["session"]["id"]
        for path, question, expected in [
            ("/api/chat", "我叫小明，请记住", "小明"),
            ("/api/agent/chat", "计算3874*239", "925886"),
            ("/api/smart/chat", "WELCOME10优惠券能用吗", "WELCOME10"),
        ]:
            response = client.post(path, json={"session_id": sid, "message": question})
            value = response.json()
            reply = value.get("data", {}).get("reply", "").replace(",", "")
            record(path, response.status_code == 200 and expected in reply, response=value)
        streamed = client.post("/api/chat/stream", json={"session_id": sid, "message": "我叫什么名字？只回复姓名"})
        deltas = [json.loads(line[6:])["delta"] for line in streamed.text.splitlines()
                  if line.startswith("data: {") and "delta" in json.loads(line[6:])]
        record("Nginx SSE", streamed.status_code == 200 and "[DONE]" in streamed.text and "小明" in "".join(deltas))
        url = f"/api/sessions/{sid}/messages"
        before = client.get(url).json()["data"]["messages"]
        compose("down")
        compose("up", "-d", "--wait")
        record("停启数据保留", client.get(url).json()["data"]["messages"] == before)
        compose("up", "-d", "--build", "--force-recreate", "--wait")
        record("重建与重建容器数据保留", client.get(url).json()["data"]["messages"] == before)
        compose("stop", "backend")
        backup = ROOT / "artifacts/private" / f"backup-{uuid4().hex}"
        subprocess.run([str(ROOT / ".venv/Scripts/python.exe"), str(ROOT / "backend/backup_data.py"), str(backup)], cwd=ROOT, check=True)
        settings = Settings.load()
        # 独立目录上的业务库和检查点库作为恢复后的新服务，验证实际继续对话。
        with tempfile.TemporaryDirectory(prefix="smartchat-restore-") as directory:
            import shutil
            copied = Path(directory)
            for file in backup.iterdir():
                shutil.copy2(file, copied / file.name)
            restored = replace(settings, db_path=copied / settings.db_path.name,
                               agent_db_path=copied / settings.agent_db_path.name)
            with TestClient(create_app(restored)) as recovered:
                record("备份恢复历史", recovered.get(url).json()["data"]["messages"] == before)
                value = recovered.post("/api/agent/chat", json={"session_id": sid, "message": "我叫什么名字？"}).json()
                record("备份恢复继续智能体对话", "小明" in value.get("data", {}).get("reply", ""), response=value)
        compose("up", "-d", "--wait")
        record("恢复后原部署正常", client.get("/api/health").status_code == 200)
        # 新容器限流窗口干净。改变伪造XFF也无法绕过Nginx覆盖。
        codes = [client.get("/api/sessions", headers={"X-Forwarded-For": f"192.0.2.{i}"}).status_code for i in range(21)]
        record("可信代理与第21次限流", codes[:20] == [200] * 20 and codes[20] == 429, codes=codes)
        limited = client.get("/api/sessions")
        record("429重试头", limited.status_code == 429 and int(limited.headers["Retry-After"]) > 0)
        record("健康接口豁免", client.get("/api/health").status_code == 200)
        # 重新启动清空限流窗口，保留验收会话供查看。
        compose("restart", "backend")
        compose("up", "-d", "--wait")
    finally:
        client.close()
        output = ROOT / "artifacts/evidence/docker-acceptance.json"
        output.write_text(json.dumps({"port": port, "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    raise SystemExit(run(parser.parse_args().port))
