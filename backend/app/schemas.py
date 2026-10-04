from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(min_length=1, max_length=64)

    @field_validator("message", "session_id", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)

    @field_validator("title", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: dict = Field(default_factory=dict)


class Intent(BaseModel):
    intent: Literal["chat", "agent"] = Field(
        description="chat=日常问答；agent=订单、天气、精确计算、当前时间或优惠券")


class CourseInfo(BaseModel):
    name: str = Field(description="课程名称")
    teacher: str = Field(description="教师姓名")
    day_of_week: Literal["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    period: int = Field(ge=1, description="第几节课")


class BookInfo(BaseModel):
    name: str = Field(description="书名")
    author: str = Field(description="作者")
    price: float = Field(ge=0, description="人民币价格")
    category: str = Field(description="书籍分类")
