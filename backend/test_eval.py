"""真实模型工具评估：固定用例、独立会话、结果可追溯。"""
import csv
import json
import tempfile
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.agent import AgentService
from app.config import Settings

CASES = [
    ("订单DD20240001到哪了？", {"query_order"}),
    ("我的订单DD20240003签收了吗", {"query_order"}),
    ("长沙今天天气怎么样？", {"get_weather"}),
    ("北京会下雨吗？要不要带伞", {"get_weather"}),
    ("计算1234*5678等于多少", {"calculate"}),
    ("3.5乘以12是多少", {"calculate"}),
    ("现在几点了？", {"get_current_time"}),
    ("今天几号？", {"get_current_time"}),
    ("用一句话介绍你自己", set()),
    ("Python和Java的区别是什么", set()),
]
EXTRA_CASES = [
    ("WELCOME10优惠券能用吗？", {"get_coupon"}),
    ("现在几点？顺便算365*24*60，一年有多少分钟？", {"get_current_time", "calculate"}),
    ("订单NOTFOUND是什么状态？", {"query_order"}),
    ("太原天气怎么样？", {"get_weather"}),
]


def run():
    settings = Settings.load()
    if not settings.api_key:
        print("尚未配置LLM_API_KEY，未进行真实模型评估")
        return 2
    run_id = uuid4().hex
    rows = []
    with tempfile.TemporaryDirectory(prefix="smartchat-eval-") as directory:
        agent = AgentService(replace(settings, agent_db_path=Path(directory) / "agent.db"))
        try:
            for i, (question, expected) in enumerate(CASES + EXTRA_CASES):
                start = time.monotonic()
                try:
                    result = agent.chat(question, f"{run_id}-{i}", [], 0)
                    used = set(result["tools_used"])
                    # 保留教程指标，同时提供更严格的集合完全相同指标。
                    passed = expected <= used if expected else not used
                    row = {"question": question, "expected": sorted(expected), "actual": sorted(used),
                           "passed": passed, "exact_match": used == expected, "reply": result["reply"]}
                except Exception as exc:
                    row = {"question": question, "expected": sorted(expected), "actual": [],
                           "passed": False, "exact_match": False, "error_type": type(exc).__name__}
                row.update(index=i, group="course" if i < len(CASES) else "extra",
                           seconds=round(time.monotonic() - start, 3))
                rows.append(row)
                print(json.dumps({k: v for k, v in row.items() if k != "reply"}, ensure_ascii=False), flush=True)
        finally:
            agent.close()
    correct = sum(row["passed"] for row in rows[:10])
    report = {"run_id": run_id, "timestamp": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "model": settings.model, "course_correct": correct, "course_total": 10,
              "course_accuracy": correct / 10, "rows": rows}
    output = Path(__file__).resolve().parents[1] / "artifacts/evidence"
    output.mkdir(parents=True, exist_ok=True)
    (output / f"eval-{run_id}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / f"eval-{run_id}.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["index", "group", "question", "expected", "actual", "passed", "exact_match", "seconds"])
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in writer.fieldnames} for row in rows)
    print(f"课堂工具选择正确率：{correct}/10 = {correct / 10:.0%}")
    return 0 if correct >= 9 and all(row["passed"] for row in rows[10:]) else 1


if __name__ == "__main__":
    raise SystemExit(run())
