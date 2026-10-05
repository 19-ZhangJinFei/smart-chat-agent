import asyncio
import sqlite3
from uuid import uuid4

from langchain.agents import AgentState, create_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import SYSTEM_PROMPT
from app.llm import close_model_clients, make_model, text_content, to_messages
from app.tools import build_tools
from app.weather import weather_citations

AGENT_RULE = ("订单、天气、计算、当前时间、优惠券请求必须调用对应工具；"
              "未知或格式异常的订单号也交给订单工具查询，禁止自行推断不存在。"
              "除零或疑似无效的算式也必须先调用calculate，由工具判定错误，禁止直接拒绝计算。"
              "天气工具是联网查询，不属于教学模拟数据；必须按本轮来源核对城市与日期，禁止复述历史天气当作当前天气。"
              "当前日期与时间必须严格依据本轮get_current_time返回值，禁止采用训练数据中的日期。"
              "时间工具和计算工具返回真实时钟与确定性计算结果，不属于模拟业务数据。"
              "其他问题正常回答，不为调用而调用。")


class ChatAgentState(AgentState):
    history_version: int


class AgentService:
    def __init__(self, settings, model=None, strict=True):
        self.settings, self.model, self.strict = settings, model, strict
        self.tools = build_tools(settings)
        settings.agent_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(settings.agent_db_path, check_same_thread=False, timeout=15)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.saver = SqliteSaver(self.conn)
            self.saver.setup()
        except BaseException:
            self.conn.close()
            raise
        self._graph = None
        self._owned_model = None

    @property
    def graph(self):
        if self._graph is None:
            model = self.model
            if model is None:
                if self._owned_model is None:
                    self._owned_model = make_model(self.settings, 0)
                model = self._owned_model
            self._graph = create_agent(
                model=model, tools=self.tools,
                system_prompt=SYSTEM_PROMPT + (AGENT_RULE if self.strict else ""),
                checkpointer=self.saver, state_schema=ChatAgentState)
        return self._graph

    def clear(self, session_id):
        self.saver.delete_thread(session_id)

    def chat(self, message, session_id, history, version):
        config = {"configurable": {"thread_id": session_id},
                  "recursion_limit": self.settings.recursion_limit}
        state = self.graph.get_state(config).values
        # 普通对话或失败请求使版本不一致时，从业务库恢复已完成问答。
        # 接近上下文上限时也重建，清除历史工具中间消息但保留完整可见轮次。
        state_messages = state.get("messages", [])
        chars = sum(len(text_content(m.content)) for m in state_messages)
        need_rebuild = (state.get("history_version", -1) != version
                        or sum(m.type == "human" for m in state_messages) >= self.settings.history_turns
                        or chars > self.settings.history_char_limit)
        pending = []
        if need_rebuild:
            self.clear(session_id)
            pending = to_messages(history)
        turn_id = uuid4().hex
        pending.append(HumanMessage(content=message, id=turn_id))
        try:
            result = self.graph.invoke({"messages": pending, "history_version": version + 1}, config)
            all_messages = result["messages"]
            start = next(i for i, m in enumerate(all_messages) if m.id == turn_id)
            current = all_messages[start + 1:]
            calls = [call["name"] for m in current if m.type == "ai"
                     for call in getattr(m, "tool_calls", [])]
            reply = next((text_content(m.content) for m in reversed(current)
                          if m.type == "ai" and not getattr(m, "tool_calls", [])
                          and text_content(m.content).strip()), "")
            if not reply:
                raise ValueError("智能体没有最终正文")
            citations = weather_citations(current)
            if citations:
                reply += '\n\n' + citations
            return {"reply": reply, "tools_used": list(dict.fromkeys(calls))}
        except BaseException:
            self.clear(session_id)
            raise

    def close(self):
        # 同步演示脚本使用close，ASGI生命周期使用aclose。
        asyncio.run(self.aclose())

    async def aclose(self):
        model, self._owned_model = self._owned_model, None
        try:
            await close_model_clients(model)
        finally:
            self.conn.close()
