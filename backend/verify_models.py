"""有界真实模型能力检查，不打印密钥和上游异常正文。"""
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage

from app.config import Settings
from app.llm import make_model, text_content
from app.schemas import BookInfo, CourseInfo


def run():
    settings = Settings.load()
    if not settings.api_key:
        print("尚未配置LLM_API_KEY")
        return 2
    model = make_model(settings, 0)
    checks = []
    tasks = [
        ("普通调用", lambda: text_content(model.invoke("用一句话介绍LangChain").content)),
        ("CourseInfo", lambda: model.with_structured_output(CourseInfo, method="function_calling").invoke(
            "周三第2节，张伟老师上《软件工程》").model_dump()),
        ("BookInfo", lambda: model.with_structured_output(BookInfo, method="function_calling").invoke(
            "《三体》是刘慈欣写的科幻小说，定价45元").model_dump()),
        ("流式调用", lambda: "".join(text_content(c.content) for c in model.stream([
            HumanMessage(content="请只回复：流式输出正常")]))),
    ]
    for name, task in tasks:
        try:
            value = task()
            passed = bool(value)
            if name == "BookInfo":
                passed = value["name"] == "三体" and value["author"] == "刘慈欣" and isinstance(value["price"], float) and value["price"] == 45
            if name == "CourseInfo":
                passed = value["teacher"] == "张伟" and value["period"] == 2 and value["day_of_week"] == "周三"
            result = {"name": name, "passed": passed, "result": value}
        except Exception as exc:
            result = {"name": name, "passed": False, "error_type": type(exc).__name__}
        checks.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    output = Path(__file__).resolve().parents[1] / "artifacts/evidence/model-capabilities.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"timestamp": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                                 "model": settings.model, "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(run())
