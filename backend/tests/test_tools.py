import pytest
from app.tools import calculate, get_coupon, get_current_time, get_weather, query_order, safe_calculate


@pytest.mark.parametrize("expression,expected", [
    ("3874*239", "925886"), ("0.1+0.2", "0.3"),
    ("365*24*60", "525600"), ("-(2+3)/2", "-2.5"), ("3.5*12", "42"),
])
def test_calculation(expression, expected):
    assert safe_calculate(expression) == expected


@pytest.mark.parametrize("expression", ["1/0", "2**1000", "__import__('os')", "x+2", "1e200", "9" * 80, "(" * 25 + "1" + ")" * 25])
def test_invalid_calculation(expression):
    assert "失败" in calculate.invoke({"expression": expression})


def test_fake_data_and_time():
    assert "暂无模拟数据" in get_weather.invoke({"city": "太原"})
    assert "未找到" in query_order.invoke({"order_id": "wrong"})
    assert "已过期" in get_coupon.invoke({"code": "EXPIRED"})
    assert "教学模拟" in get_coupon.invoke({"code": "WELCOME10"})
    assert "北京时间" in get_current_time.invoke({})
