"""离线上下文增长分析，不调用模型、不把字符数称为token数。"""
import json
from pathlib import Path

from app.config import Settings
from app.memory import bounded_history

if __name__ == "__main__":
    settings = Settings()
    rows = []
    for turns in [1, 10, 20, 30, 100]:
        messages = [{"role": role, "content": f"第{i}轮：" + "教学上下文示例"*12}
                    for i in range(turns) for role in ["user", "assistant"]]
        used = bounded_history(messages, settings)
        rows.append({"saved_turns": turns, "saved_characters": sum(len(m["content"]) for m in messages),
                     "context_turns": len(used)//2, "context_characters": sum(len(m["content"]) for m in used)})
    result = {"kind":"offline-synthetic-character-analysis", "history_turns":settings.history_turns,
              "history_char_limit":settings.history_char_limit, "rows":rows}
    path = Path(__file__).resolve().parents[1]/"artifacts/evidence/history-growth.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
