from app.config import Settings
from app.llm import make_model
from app.schemas import BookInfo, CourseInfo

if __name__ == "__main__":
    model = make_model(Settings.load(), 0)
    for schema, prompt in [
        (CourseInfo, "周三第2节，张伟老师上《软件工程》"),
        (BookInfo, "《三体》是刘慈欣写的科幻小说，定价45元"),
    ]:
        info = model.with_structured_output(schema, method="function_calling").invoke(prompt)
        print(info.model_dump())
        if isinstance(info, BookInfo):
            print("price类型：", type(info.price).__name__)
            assert isinstance(info.price, float)
