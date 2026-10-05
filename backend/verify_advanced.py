"""有条件的多工具任务与动态未来日期验收，各题独立会话。"""
import json
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.agent import AgentService
from app.config import Settings

if __name__ == "__main__":
    current = datetime.now(ZoneInfo("Asia/Shanghai"))
    future = (current + timedelta(days=30)).date().isoformat()
    cases = [
        ("查订单DD20240001，如果已发货则查询当前北京时间，否则只说明订单状态。", {"query_order", "get_current_time"}, str(current.year)),
        (f"查询当前日期，再算从今天到{future}有多少天，按日期整天计算。", {"get_current_time", "calculate"}, "30"),
    ]
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        agent = AgentService(replace(Settings.load(), agent_db_path=Path(directory) / "agent.db"))
        try:
            for i, (question, expected, answer) in enumerate(cases):
                result = agent.chat(question, f"advanced-{i}", [], 0)
                rows.append({"question": question, "expected": sorted(expected), "expected_answer": answer,
                             "passed": expected <= set(result["tools_used"]) and answer in result["reply"], **result})
        finally:
            agent.close()
    output = Path(__file__).resolve().parents[1] / "artifacts/evidence/advanced-model.json"
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(row["passed"] for row in rows) else 1)
