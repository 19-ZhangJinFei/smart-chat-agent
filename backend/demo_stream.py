from langchain_core.messages import HumanMessage
from app.config import Settings
from app.llm import make_model

if __name__ == "__main__":
    for chunk in make_model(Settings.load()).stream([
        HumanMessage(content="写一首关于程序员的四行短诗")]):
        print(chunk.content, end="", flush=True)
    print()
