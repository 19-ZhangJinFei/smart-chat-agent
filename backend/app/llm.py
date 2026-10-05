from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import SYSTEM_PROMPT
from app.schemas import Intent


class ModelNotConfigured(Exception):
    pass


def text_content(content):
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") for block in content if isinstance(block, dict))


def to_messages(history):
    return [(HumanMessage if m["role"] == "user" else AIMessage)(content=m["content"])
            for m in history]


def make_model(settings, temperature=0.7):
    if not settings.api_key:
        raise ModelNotConfigured()
    return ChatOpenAI(model=settings.model, api_key=settings.api_key,
                      base_url=settings.base_url, temperature=temperature,
                      timeout=settings.timeout, max_retries=1)


async def close_model_clients(model):
    """释放LangChain持有的同步和异步OpenAI连接池，不触发模型请求。"""
    if model is None:
        return
    try:
        model.root_client.close()
    finally:
        await model.root_async_client.close()


class ModelService:
    def __init__(self, settings):
        self.settings = settings
        self._model = None
        self._router = None
        self._router_model = None

    async def aclose(self):
        model, router_model = self._model, self._router_model
        self._model = self._router = self._router_model = None
        try:
            await close_model_clients(model)
        finally:
            await close_model_clients(router_model)

    @property
    def model(self):
        if self._model is None:
            self._model = make_model(self.settings)
        return self._model

    def prompt(self, message, history):
        return [SystemMessage(content=SYSTEM_PROMPT), *to_messages(history),
                HumanMessage(content=message)]

    def chat(self, message, history):
        result = text_content(self.model.invoke(self.prompt(message, history)).content)
        if not result.strip():
            raise ValueError("模型未返回正文")
        return result

    async def stream(self, message, history):
        async for chunk in self.model.astream(self.prompt(message, history)):
            text = text_content(chunk.content)
            if text:
                yield text

    def classify(self, message, history):
        if self._router is None:
            if self._router_model is None:
                self._router_model = make_model(self.settings, 0)
            self._router = self._router_model.with_structured_output(
                Intent, method="function_calling")
        result = self._router.invoke([
            SystemMessage(content="你是意图分类器。闲聊/知识/写作为chat；订单、天气、"
                          "当前时间、精确计算、优惠券为agent。结合历史理解追问，只输出分类。"),
            *to_messages(history[-6:]), HumanMessage(content=message)])
        return result.intent
