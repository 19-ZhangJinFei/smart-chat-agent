"""第二课快速验证；不会在导入时调用模型。"""
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from app.agent import AgentService
from app.config import Settings


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        agent = AgentService(replace(Settings.load(), agent_db_path=Path(directory) / "agent.db"))
        history = []
        try:
            for version, question in enumerate([
                "订单DD20240001现在到哪了？", "长沙天气怎么样？", "3874*239等于多少？",
                "刚才第一个订单号是多少？", "WELCOME10优惠券能用吗？",
            ]):
                result = agent.chat(question, "course-demo", history, version)
                history.extend([{"role": "user", "content": question},
                                {"role": "assistant", "content": result["reply"]}])
                print(json.dumps(result, ensure_ascii=False), flush=True)
        finally:
            agent.close()
