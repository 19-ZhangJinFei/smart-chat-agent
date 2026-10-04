"""独立会话提示词对照实验，记录结果而不预设结论。"""
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from app.agent import AgentService
from app.config import Settings


if __name__ == "__main__":
    settings, results = Settings.load(), []
    with tempfile.TemporaryDirectory() as directory:
        for strict in [True, False]:
            agent = AgentService(replace(settings, agent_db_path=Path(directory) / f"{strict}.db"), strict=strict)
            try:
                result = agent.chat("订单DD20240001到哪了？", "experiment", [], 0)
                results.append({"strict_prompt": strict, **result})
            except Exception as exc:
                results.append({"strict_prompt": strict, "error_type": type(exc).__name__})
            finally:
                agent.close()
    output = Path(__file__).resolve().parents[1] / "artifacts/evidence/prompt-experiment.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
