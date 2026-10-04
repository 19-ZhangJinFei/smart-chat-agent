"""五个教学工具。业务样例明确标注模拟，计算器不执行eval。"""
import ast
import json
from datetime import datetime
from decimal import Decimal, DecimalException, localcontext
from zoneinfo import ZoneInfo

from langchain.tools import tool


def safe_calculate(expression):
    if not 1 <= len(expression) <= 200:
        raise ValueError("表达式长度应为1—200字符")
    if not set(expression) <= set("0123456789+-*/.() \t"):
        raise ValueError("表达式含非法字符")
    nesting = 0
    for char in expression:
        nesting += (char == "(") - (char == ")")
        if nesting > 16 or nesting < 0:
            raise ValueError("括号嵌套无效或过深")
    if nesting:
        raise ValueError("括号不匹配")
    tree = ast.parse(expression.strip(), mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ValueError("表达式过于复杂")

    def evaluate(node, depth=0):
        if depth > 16:
            raise ValueError("括号嵌套过深")
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            # 从源码取十进制文本，避免3.5等数字先转换成二进制浮点。
            result = Decimal(ast.get_source_segment(expression.strip(), node))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand, depth + 1)
            result = value if isinstance(node.op, ast.UAdd) else -value
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = evaluate(node.left, depth + 1), evaluate(node.right, depth + 1)
            if isinstance(node.op, ast.Add):
                result = a + b
            elif isinstance(node.op, ast.Sub):
                result = a - b
            elif isinstance(node.op, ast.Mult):
                result = a * b
            else:
                if b == 0:
                    raise ValueError("不能除以零")
                result = a / b
        else:
            raise ValueError("只允许数字、括号和四则运算")
        if not result.is_finite() or abs(result) > Decimal("1e30"):
            raise ValueError("数值超出允许范围")
        return result

    with localcontext() as ctx:
        ctx.prec = 40
        value = evaluate(tree.body)
        return format(value.normalize(), "f")


@tool
def query_order(order_id: str) -> str:
    """查询教学模拟订单状态。询问订单物流、发货、签收必须使用。
    order_id为用户提供的原始订单号，例如DD20240001。即使订单号未知或格式异常，
    也必须调用本工具判定是否存在，不可自行断言不存在；未找到时不要猜测。"""
    data = {
        "DD20240001": "已发货，顺丰速运，预计下一日18:00前送达",
        "DD20240002": "待付款，金额129.00元，待支付",
        "DD20240003": "已签收，签收时间2026-09-18 14:32",
        "DD20240004": "打包中，尚未发出",
    }
    return "【教学模拟订单】" + data.get(order_id.strip().upper(), "未找到该订单，请核对订单号")


@tool
def get_weather(city: str) -> str:
    """查询教学模拟天气；天气、是否适合出行或发货问题必须使用。
    city为中国城市名，例如长沙。不是实时预报，未知城市没有数据。"""
    data = {"长沙": "晴，25℃，微风", "北京": "多云，18℃，早晚温差大",
            "上海": "小雨，22℃", "广州": "晴间多云，28℃", "深圳": "阵雨，26℃"}
    city = city.strip().removesuffix("市")
    return f"【教学模拟天气，非实时预报】{city}：" + data.get(city, "暂无模拟数据")


@tool
def calculate(expression: str) -> str:
    """精确计算四则表达式。任何数学计算必须使用，禁止口算。
    expression例如3874*239、365*24*60，只允许数字、括号、+ - * /。
    小数使用Decimal，非终止小数保留40位有效数字。"""
    try:
        return f"{expression} = {safe_calculate(expression)}"
    except (ValueError, SyntaxError, DecimalException, RecursionError):
        return "计算失败：表达式无效、除零、过于复杂或数值过大，请检查输入"


@tool
def get_current_time() -> str:
    """获取北京时间。询问现在几点、今天日期必须使用，无参数。"""
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("北京时间 %Y年%m月%d日 %H:%M:%S")


@tool
def get_coupon(code: str) -> str:
    """查询教学模拟优惠券状态、折扣和条件。询问优惠券是否有效必须使用。
    code为优惠券代码，例如WELCOME10、SAVE20、EXPIRED。不要猜测其他优惠券。"""
    data = {
        "WELCOME10": {"status": "可用", "discount": "九折", "condition": "新用户，最低消费100元"},
        "SAVE20": {"status": "可用", "discount": "减20元", "condition": "满200元"},
        "EXPIRED": {"status": "已过期", "discount": "不可使用", "condition": "不可使用"},
    }
    result = data.get(code.strip().upper(), {"status": "未找到优惠券"})
    return "【教学模拟优惠券】" + json.dumps(result, ensure_ascii=False)


TOOLS = [query_order, get_weather, calculate, get_current_time, get_coupon]
