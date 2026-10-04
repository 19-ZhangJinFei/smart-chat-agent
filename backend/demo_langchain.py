from langchain_core.messages import HumanMessage, SystemMessage
from app.config import Settings
from app.llm import make_model

if __name__ == "__main__":
    result = make_model(Settings.load()).invoke([
        SystemMessage(content="你是IT讲解员，回答不超过两句。"),
        HumanMessage(content="一句话介绍LangChain")])
    print(type(result).__name__, result.content)
