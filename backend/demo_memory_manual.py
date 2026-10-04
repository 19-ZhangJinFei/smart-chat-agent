from app.config import Settings
from app.llm import ModelService

if __name__ == "__main__":
    model, history = ModelService(Settings.load()), []
    print("输入exit退出")
    while True:
        question = input("你：").strip()
        if question == "exit":
            break
        if not question:
            continue
        reply = model.chat(question, history)
        history.extend([{"role": "user", "content": question},
                        {"role": "assistant", "content": reply}])
        print("AI：", reply)
