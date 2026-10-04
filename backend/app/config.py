"""项目配置：环境变量优先，路径独立于启动目录。"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-plus"
    db_path: Path = BACKEND_DIR / "data/smartchat.db"
    agent_db_path: Path = BACKEND_DIR / "data/agent_memory.db"
    timeout: float = 60
    rate_limit: int = 20
    history_turns: int = 20
    history_char_limit: int = 16000
    recursion_limit: int = 25

    def __post_init__(self):
        if min(self.timeout, self.rate_limit, self.history_turns,
               self.history_char_limit, self.recursion_limit) <= 0:
            raise ValueError("超时、限流和历史窗口必须大于零")
        if self.db_path.resolve() == self.agent_db_path.resolve():
            raise ValueError("业务数据库与检查点数据库必须使用不同文件")

    @classmethod
    def load(cls):
        values = {**dotenv_values(BACKEND_DIR / ".env"), **os.environ}

        def path(name, default):
            value = Path(values.get(name) or default)
            return value if value.is_absolute() else BACKEND_DIR / value

        return cls(
            api_key=values.get("LLM_API_KEY", "").strip(),
            base_url=values.get("LLM_BASE_URL") or cls.base_url,
            model=values.get("LLM_MODEL") or cls.model,
            db_path=path("DB_PATH", "data/smartchat.db"),
            agent_db_path=path("AGENT_DB_PATH", "data/agent_memory.db"),
            timeout=float(values.get("LLM_TIMEOUT", 60)),
            rate_limit=int(values.get("RATE_LIMIT", 20)),
            history_turns=int(values.get("HISTORY_TURNS", 20)),
            history_char_limit=int(values.get("HISTORY_CHAR_LIMIT", 16000)),
            recursion_limit=int(values.get("AGENT_RECURSION_LIMIT", 25)),
        )


SYSTEM_PROMPT = (
    "你是「智聊」，电商智能客服。使用简体中文，礼貌简洁地回答。"
    "订单、天气和优惠券是教学模拟数据，不是真实业务或实时天气；相关回答必须注明教学模拟。"
    "涉及业务数据时以工具结果为准，未知信息明确说明，禁止编造。"
)
