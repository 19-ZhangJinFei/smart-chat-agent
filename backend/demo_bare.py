"""python demo_bare.py：理解OpenAI兼容HTTP调用。"""
from openai import OpenAI
from app.config import Settings


if __name__ == "__main__":
    s = Settings.load()
    with OpenAI(api_key=s.api_key, base_url=s.base_url, timeout=s.timeout) as client:
        result = client.chat.completions.create(model=s.model, messages=[
            {"role": "user", "content": "一句话介绍LangChain"}])
        print(result.choices[0].message.content)
